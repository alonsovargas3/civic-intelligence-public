"""TCAD Tier 2 storage: schema DDL + pure helpers (PII split, hashing, tokens).

Deliberately separate from the Tier 1 atx_ingest/db.py — different storage model
(append-only versioned snapshots, spec §4), so it does not share that module's upsert.
Connection handling reuses psycopg directly.
"""
import hashlib
import json
import logging

import psycopg

log = logging.getLogger("atx.tcad.db")

# Owner-PII field names in a parsed PROP.TXT record. These NEVER land in raw_tcad_roll.payload.
_PII_FIELDS = (
    "py_owner_name",
    "py_addr_line1", "py_addr_line2", "py_addr_line3",
    "py_addr_city", "py_addr_state", "py_addr_zip",
)

DDL = """
CREATE TABLE IF NOT EXISTS tcad_roll_load (
    roll_load_id   bigserial PRIMARY KEY,
    roll_year      int  NOT NULL,
    roll_stage     text NOT NULL,
    source_route   text NOT NULL,
    source_uri     text,
    source_file    text,
    file_sha256    text NOT NULL,
    layout_version text,
    license        text DEFAULT 'public_domain',
    record_count   int,
    loaded_at      timestamptz NOT NULL DEFAULT now(),
    completed_at   timestamptz,          -- set only when the load finished; NULL = partial/in-flight
    informational boolean NOT NULL DEFAULT false,  -- true = backfilled prior-year roll (may differ from what was certified that year)
    UNIQUE (file_sha256)
);
-- Backfill the column on pre-existing installs (CREATE TABLE IF NOT EXISTS won't add it).
ALTER TABLE tcad_roll_load ADD COLUMN IF NOT EXISTS completed_at timestamptz;
ALTER TABLE tcad_roll_load ADD COLUMN IF NOT EXISTS informational boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS raw_tcad_roll (
    raw_id       bigserial PRIMARY KEY,
    roll_load_id bigint REFERENCES tcad_roll_load(roll_load_id),
    account_id   text NOT NULL,
    geo_id       text,
    roll_year    int  NOT NULL,
    roll_stage   text NOT NULL,
    payload      jsonb NOT NULL,
    row_hash     text,
    captured_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_tcad_acct_year
    ON raw_tcad_roll (account_id, roll_year, roll_stage);

CREATE TABLE IF NOT EXISTS tcad_owner (
    roll_load_id   bigint REFERENCES tcad_roll_load(roll_load_id),
    account_id     text NOT NULL,
    roll_year      int  NOT NULL,
    owner_id       text,
    owner_name_raw text,
    owner_name_norm text,
    mail_addr      jsonb,
    owner_token    text,
    PRIMARY KEY (roll_load_id, account_id)
);

CREATE TABLE IF NOT EXISTS parcel (
    account_id text PRIMARY KEY,
    geo_id     text,
    situs      jsonb,
    legal      text,
    category   text,
    acreage    numeric,
    first_seen int,
    last_seen  int
);

CREATE TABLE IF NOT EXISTS parcel_value (
    account_id        text NOT NULL,
    roll_year         int  NOT NULL,
    roll_stage        text NOT NULL,
    land_value        numeric,
    improvement_value numeric,
    market_value      numeric,
    appraised_value   numeric,
    assessed_value    numeric,
    capped_value      numeric,
    owner_token       text,
    informational boolean NOT NULL DEFAULT false,  -- mirrors the roll's informational flag, for D3b
    PRIMARY KEY (account_id, roll_year, roll_stage)
);
ALTER TABLE parcel_value ADD COLUMN IF NOT EXISTS informational boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS raw_tcad_entity (
    raw_id       bigserial PRIMARY KEY,
    roll_load_id bigint REFERENCES tcad_roll_load(roll_load_id),
    prop_id      text NOT NULL,
    owner_id     text,
    entity_id    text,
    roll_year    int  NOT NULL,
    roll_stage   text NOT NULL,
    payload      jsonb NOT NULL,
    captured_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_tcad_entity_acct
    ON raw_tcad_entity (prop_id, roll_year, roll_stage);

CREATE TABLE IF NOT EXISTS parcel_entity_value (
    account_id    text NOT NULL,
    roll_year     int  NOT NULL,
    roll_stage    text NOT NULL,
    owner_id      text NOT NULL,
    entity_id     text NOT NULL,
    entity_cd     text,
    entity_name   text,
    taxable_val   numeric,
    hs_amt        numeric,
    hs_state_amt  numeric,
    hs_local_amt  numeric,
    hs_cap        numeric,
    informational boolean NOT NULL DEFAULT false,
    PRIMARY KEY (account_id, roll_year, roll_stage, owner_id, entity_id)
);

CREATE TABLE IF NOT EXISTS parcel_geo (
    account_id text PRIMARY KEY,   -- PROP_ID as text; matches parcel.account_id
    geo_id     text,
    geom       jsonb NOT NULL,     -- GeoJSON geometry (Polygon/MultiPolygon)
    srid       int  NOT NULL,      -- 2277 (NAD83 / Texas Central, ftUS)
    acres      numeric,
    situs      text,
    loaded_at  timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW parcel_value_current AS
SELECT DISTINCT ON (account_id, roll_year) *
FROM parcel_value
ORDER BY account_id, roll_year,
         informational,                                       -- false (authoritative) sorts before true
         CASE roll_stage WHEN 'certified' THEN 0 WHEN 'supplement' THEN 1 ELSE 2 END;
"""


def connect(dsn: str):
    return psycopg.connect(dsn, autocommit=True)


def bootstrap(conn) -> None:
    conn.execute(DDL)


def _norm_name(name: str) -> str:
    """Normalize an owner name for matching: upper, collapse whitespace, drop commas/periods."""
    return " ".join(name.upper().replace(",", " ").replace(".", " ").split())


def owner_token(name: str, mail_addr: dict) -> str:
    """Stable, PII-free id for an owner = sha256(normalized name + normalized mailing address)."""
    addr = "|".join(
        str(mail_addr.get(k, "")).upper().strip()
        for k in ("line1", "line2", "line3", "city", "state", "zip")
    )
    return hashlib.sha256(f"{_norm_name(name)}|{addr}".encode()).hexdigest()


def row_hash(payload: dict) -> str:
    """Content hash of a (PII-stripped) record; key-order independent."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def split_record(rec: dict) -> tuple[dict, dict]:
    """Split a parsed PROP.TXT record into (owner, payload).

    owner: PII (name + mailing address) for tcad_owner. payload: everything else for
    raw_tcad_roll (no PII). The account/year keys are copied into owner for linkage.
    """
    payload = {k: v for k, v in rec.items() if k not in _PII_FIELDS}
    mail_addr = {
        "line1": rec.get("py_addr_line1", ""),
        "line2": rec.get("py_addr_line2", ""),
        "line3": rec.get("py_addr_line3", ""),
        "city": rec.get("py_addr_city", ""),
        "state": rec.get("py_addr_state", ""),
        "zip": rec.get("py_addr_zip", ""),
    }
    name = rec.get("py_owner_name", "") or ""
    owner = {
        "account_id": str(rec.get("prop_id")),
        "roll_year": rec.get("prop_val_yr"),
        "owner_id": str(rec.get("py_owner_id")) if rec.get("py_owner_id") is not None else None,
        "owner_name_raw": name,
        "owner_name_norm": _norm_name(name),
        "mail_addr": mail_addr,
        "owner_token": owner_token(name, mail_addr),
    }
    return owner, payload
