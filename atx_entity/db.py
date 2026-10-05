"""Entity-resolution storage: schema + read tcad_owner / write the entity tables.

Rebuild-in-place: each build truncates dim_entity/parcel_entity/entity_link and rewrites
for one roll year. Reads tcad_owner; never mutates it.
"""
import logging

import psycopg
from psycopg.types.json import Json

from .resolve import resolve, ResolveResult

log = logging.getLogger("atx.entity.db")

DDL = """
CREATE TABLE IF NOT EXISTS dim_entity (
    entity_id       text PRIMARY KEY,
    canonical_name  text NOT NULL,
    kind            text NOT NULL,
    confidence      text NOT NULL,
    n_parcels       int  NOT NULL,
    n_owner_records int  NOT NULL,
    roll_year       int  NOT NULL,
    meta            jsonb
);

CREATE TABLE IF NOT EXISTS parcel_entity (
    account_id text PRIMARY KEY,
    entity_id  text NOT NULL REFERENCES dim_entity(entity_id),
    roll_year  int  NOT NULL,
    link_type  text NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_link (
    entity_id  text NOT NULL,
    kind       text NOT NULL,
    value      text NOT NULL,
    suppressed boolean NOT NULL DEFAULT false,
    n_records  int  NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entity_link_entity ON entity_link (entity_id);
"""


def connect(dsn: str):
    return psycopg.connect(dsn, autocommit=True)


def bootstrap(conn) -> None:
    conn.execute(DDL)


def load_owner_records(conn, roll_year: int | None = None) -> tuple[list, int]:
    """Read tcad_owner rows for a roll year (latest if None). Returns (records, roll_year)."""
    if roll_year is None:
        row = conn.execute("SELECT max(roll_year) FROM tcad_owner").fetchone()
        roll_year = row[0]
    cur = conn.execute(
        """
        SELECT account_id, owner_name_raw, owner_name_norm, mail_addr
        FROM tcad_owner WHERE roll_year = %s
        """,
        (roll_year,),
    )
    records = [
        {"account_id": a, "owner_name_raw": raw, "owner_name_norm": norm,
         "mail_addr": mail or {}}
        for (a, raw, norm, mail) in cur.fetchall()
    ]
    return records, roll_year


def rows_for_write(result: ResolveResult, roll_year: int):
    """Flatten a ResolveResult into (dim_entity rows, parcel_entity rows, entity_link rows)."""
    ent_rows = [
        {"entity_id": e.entity_id, "canonical_name": e.canonical_name, "kind": e.kind,
         "confidence": e.confidence, "n_parcels": e.n_parcels,
         "n_owner_records": e.n_owner_records, "roll_year": roll_year,
         "meta": {"name_variants": e.name_variants, "addr_keys": e.addr_keys}}
        for e in result.entities.values()
    ]
    parcel_rows = [
        {"account_id": pl.account_id, "entity_id": pl.entity_id,
         "roll_year": roll_year, "link_type": pl.link_type}
        for pl in result.parcel_links.values()
    ]
    link_rows = [
        {"entity_id": l.entity_id, "kind": l.kind, "value": l.value,
         "suppressed": l.suppressed, "n_records": l.n_records}
        for l in result.links
    ]
    return ent_rows, parcel_rows, link_rows


def build(conn, roll_year: int | None = None, hub_threshold: int = 25) -> dict:
    """Full build: read owners -> resolve -> rebuild-in-place. Returns a summary."""
    records, roll_year = load_owner_records(conn, roll_year)
    result = resolve(records, hub_threshold=hub_threshold)
    ent_rows, parcel_rows, link_rows = rows_for_write(result, roll_year)

    conn.execute("TRUNCATE parcel_entity, entity_link;")
    conn.execute("DELETE FROM dim_entity;")
    for e in ent_rows:
        conn.execute(
            """INSERT INTO dim_entity (entity_id, canonical_name, kind, confidence,
                   n_parcels, n_owner_records, roll_year, meta)
               VALUES (%(entity_id)s,%(canonical_name)s,%(kind)s,%(confidence)s,
                   %(n_parcels)s,%(n_owner_records)s,%(roll_year)s,%(meta)s)""",
            {**e, "meta": Json(e["meta"])},
        )
    for p in parcel_rows:
        conn.execute(
            """INSERT INTO parcel_entity (account_id, entity_id, roll_year, link_type)
               VALUES (%(account_id)s,%(entity_id)s,%(roll_year)s,%(link_type)s)""",
            p,
        )
    for l in link_rows:
        conn.execute(
            """INSERT INTO entity_link (entity_id, kind, value, suppressed, n_records)
               VALUES (%(entity_id)s,%(kind)s,%(value)s,%(suppressed)s,%(n_records)s)""",
            l,
        )
    summary = {"roll_year": roll_year, "entities": len(ent_rows),
               "parcels": len(parcel_rows), "links": len(link_rows)}
    log.info("entity build: %s", summary)
    return summary
