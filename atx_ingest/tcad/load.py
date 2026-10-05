"""TCAD load orchestration: stream PROP.TXT -> provenance, raw (PII-stripped), owner, derived.

Append-only per spec §4/§5: each load is a new generation keyed by file_sha256; an already-
loaded file (same sha256) is a no-op. Derivation maps the raw payload to the analytic parcel
and parcel_value rows that D3/D4 read.
"""
import logging

from psycopg.types.json import Json

from . import db
from .acquire import sha256_file
from .layouts import load_layout
from .parse import iter_records

log = logging.getLogger("atx.tcad.load")


def _num(payload, key):
    v = payload.get(key)
    return v if v is not None else 0


def derive_parcel_value(payload: dict, roll_year: int, roll_stage: str,
                        owner_token: str, informational: bool = False) -> dict:
    return {
        "account_id": str(payload.get("prop_id")),
        "roll_year": roll_year,
        "roll_stage": roll_stage,
        "land_value": _num(payload, "land_hstd_val") + _num(payload, "land_non_hstd_val"),
        "improvement_value": _num(payload, "imprv_hstd_val") + _num(payload, "imprv_non_hstd_val"),
        "market_value": payload.get("market_value"),
        "appraised_value": payload.get("appraised_val"),
        "assessed_value": payload.get("assessed_val"),
        "capped_value": payload.get("ten_percent_cap"),
        "owner_token": owner_token,
        "informational": informational,
    }


def derive_parcel(payload: dict, roll_year: int) -> dict:
    return {
        "account_id": str(payload.get("prop_id")),
        "geo_id": payload.get("geo_id"),
        "situs": {
            "street": payload.get("situs_street", ""),
            "city": payload.get("situs_city", ""),
            "zip": payload.get("situs_zip", ""),
        },
        "legal": payload.get("legal_desc"),
        "category": payload.get("land_state_cd"),
        "acreage": payload.get("legal_acreage"),
        "first_seen": roll_year,
        "last_seen": roll_year,
    }


def derive_parcel_entity_value(rec: dict, roll_year: int, roll_stage: str,
                               informational: bool = False) -> dict:
    """Map a parsed PROP_ENT record to a parcel_entity_value row (per taxing unit)."""
    def _txt(v):
        return None if v is None or v == "" else str(v)
    return {
        "account_id": str(rec.get("prop_id")),
        "roll_year": roll_year,
        "roll_stage": roll_stage,
        "owner_id": _txt(rec.get("owner_id")),
        "entity_id": _txt(rec.get("entity_id")),
        "entity_cd": rec.get("entity_cd") or None,
        "entity_name": rec.get("entity_name") or None,
        "taxable_val": rec.get("taxable_val"),
        "hs_amt": rec.get("hs_amt"),
        "hs_state_amt": rec.get("hs_state_amt"),
        "hs_local_amt": rec.get("hs_local_amt"),
        "hs_cap": rec.get("hs_cap"),
        "informational": informational,
    }


def load_prop_file(conn, prop_path: str, roll_year: int, roll_stage: str,
                   source_uri: str = "", source_route: str = "free_export",
                   informational: bool = False) -> dict:
    """Load one PROP.TXT: provenance row, then stream records into raw/owner/derived.

    Idempotent on file_sha256: if this exact file was already loaded, returns {'skipped': True}.
    Returns a summary dict with counts.
    """
    layout = load_layout("property")
    sha = sha256_file(prop_path)

    existing = conn.execute(
        "SELECT roll_load_id, completed_at FROM tcad_roll_load WHERE file_sha256=%s",
        (sha,),
    ).fetchone()
    if existing:
        prev_id, completed_at = existing
        if completed_at is not None:
            log.info("file %s already loaded (sha=%s); skipping", prop_path, sha[:12])
            return {"skipped": True, "roll_load_id": prev_id}
        # A prior load with this sha never completed (crash/interrupt). Clear its
        # partial rows and re-load, rather than treating it as done.
        log.warning(
            "file %s has an incomplete prior load (roll_load_id=%s); clearing it and reloading",
            prop_path, prev_id,
        )
        conn.execute("DELETE FROM raw_tcad_roll WHERE roll_load_id=%s", (prev_id,))
        conn.execute("DELETE FROM tcad_owner WHERE roll_load_id=%s", (prev_id,))
        conn.execute("DELETE FROM tcad_roll_load WHERE roll_load_id=%s", (prev_id,))

    roll_load_id = conn.execute(
        """
        INSERT INTO tcad_roll_load
            (roll_year, roll_stage, source_route, source_uri, source_file,
             file_sha256, layout_version, license, informational)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'public_domain', %s)
        RETURNING roll_load_id
        """,
        (roll_year, roll_stage, source_route, source_uri, prop_path, sha,
         layout["layout_version"], informational),
    ).fetchone()[0]

    raw_n = owner_n = 0
    for rec in iter_records(prop_path, layout):
        owner, payload = db.split_record(rec)
        account_id = str(payload.get("prop_id"))
        conn.execute(
            """
            INSERT INTO raw_tcad_roll
                (roll_load_id, account_id, geo_id, roll_year, roll_stage, payload, row_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (roll_load_id, account_id, payload.get("geo_id"), roll_year, roll_stage,
             Json(payload), db.row_hash(payload)),
        )
        raw_n += 1
        conn.execute(
            """
            INSERT INTO tcad_owner
                (roll_load_id, account_id, roll_year, owner_id,
                 owner_name_raw, owner_name_norm, mail_addr, owner_token)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (roll_load_id, account_id) DO NOTHING
            """,
            (roll_load_id, account_id, roll_year, owner["owner_id"],
             owner["owner_name_raw"], owner["owner_name_norm"],
             Json(owner["mail_addr"]), owner["owner_token"]),
        )
        owner_n += 1

        pv = derive_parcel_value(payload, roll_year, roll_stage, owner["owner_token"], informational)
        conn.execute(
            """
            INSERT INTO parcel_value
                (account_id, roll_year, roll_stage, land_value, improvement_value,
                 market_value, appraised_value, assessed_value, capped_value, owner_token,
                 informational)
            VALUES (%(account_id)s, %(roll_year)s, %(roll_stage)s, %(land_value)s,
                    %(improvement_value)s, %(market_value)s, %(appraised_value)s,
                    %(assessed_value)s, %(capped_value)s, %(owner_token)s,
                    %(informational)s)
            ON CONFLICT (account_id, roll_year, roll_stage) DO NOTHING
            """,
            pv,
        )
        par = derive_parcel(payload, roll_year)
        conn.execute(
            """
            INSERT INTO parcel
                (account_id, geo_id, situs, legal, category, acreage, first_seen, last_seen)
            VALUES (%(account_id)s, %(geo_id)s, %(situs)s, %(legal)s, %(category)s,
                    %(acreage)s, %(first_seen)s, %(last_seen)s)
            ON CONFLICT (account_id) DO UPDATE
                SET last_seen  = GREATEST(parcel.last_seen, EXCLUDED.last_seen),
                    first_seen = LEAST(parcel.first_seen, EXCLUDED.first_seen)
            """,
            {**par, "situs": Json(par["situs"])},
        )

    # Mark complete only now that all rows landed — completed_at gates the skip
    # check above, so a crash before this point leaves the load re-runnable.
    conn.execute(
        "UPDATE tcad_roll_load SET record_count=%s, completed_at=now() WHERE roll_load_id=%s",
        (raw_n, roll_load_id),
    )
    log.info("loaded %s: %d raw, %d owner rows (roll_load_id=%s)",
             prop_path, raw_n, owner_n, roll_load_id)
    return {"skipped": False, "roll_load_id": roll_load_id,
            "raw_rows": raw_n, "owner_rows": owner_n}


def load_prop_ent_file(conn, prop_ent_path: str, roll_year: int, roll_stage: str,
                       source_uri: str = "", source_route: str = "free_export",
                       informational: bool = False) -> dict:
    """Load one PROP_ENT.TXT: provenance row, then stream records into raw_tcad_entity +
    derived parcel_entity_value. Idempotent on file_sha256. Returns a summary dict."""
    layout = load_layout("propertyentity")
    sha = sha256_file(prop_ent_path)

    existing = conn.execute(
        "SELECT roll_load_id, completed_at FROM tcad_roll_load WHERE file_sha256=%s",
        (sha,),
    ).fetchone()
    if existing:
        prev_id, completed_at = existing
        if completed_at is not None:
            log.info("file %s already loaded (sha=%s); skipping", prop_ent_path, sha[:12])
            return {"skipped": True, "roll_load_id": prev_id}
        log.warning(
            "file %s has an incomplete prior load (roll_load_id=%s); clearing it and reloading",
            prop_ent_path, prev_id,
        )
        conn.execute("DELETE FROM raw_tcad_entity WHERE roll_load_id=%s", (prev_id,))
        conn.execute("DELETE FROM tcad_roll_load WHERE roll_load_id=%s", (prev_id,))
        # parcel_entity_value rows from the partial load are NOT deleted here (they're
        # keyed independently of roll_load_id). That's safe: the re-load's ON CONFLICT
        # DO NOTHING re-writes the same derived values for the same source file (sha
        # is identical), so a complete re-load yields a complete, correct table.
        # Mirrors the parcel_value precedent in load_prop_file.

    roll_load_id = conn.execute(
        """
        INSERT INTO tcad_roll_load
            (roll_year, roll_stage, source_route, source_uri, source_file,
             file_sha256, layout_version, license, informational)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'public_domain', %s)
        RETURNING roll_load_id
        """,
        (roll_year, roll_stage, source_route, source_uri, prop_ent_path, sha,
         layout["layout_version"], informational),
    ).fetchone()[0]

    raw_n = entity_n = 0
    for rec in iter_records(prop_ent_path, layout):
        account_id = str(rec.get("prop_id"))
        conn.execute(
            """
            INSERT INTO raw_tcad_entity
                (roll_load_id, prop_id, owner_id, entity_id, roll_year, roll_stage, payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (roll_load_id, account_id,
             str(rec.get("owner_id")) if rec.get("owner_id") is not None else None,
             str(rec.get("entity_id")) if rec.get("entity_id") is not None else None,
             roll_year, roll_stage, Json(rec)),
        )
        raw_n += 1
        ev = derive_parcel_entity_value(rec, roll_year, roll_stage, informational)
        conn.execute(
            """
            INSERT INTO parcel_entity_value
                (account_id, roll_year, roll_stage, owner_id, entity_id, entity_cd,
                 entity_name, taxable_val, hs_amt, hs_state_amt, hs_local_amt, hs_cap,
                 informational)
            VALUES (%(account_id)s, %(roll_year)s, %(roll_stage)s, %(owner_id)s,
                    %(entity_id)s, %(entity_cd)s, %(entity_name)s, %(taxable_val)s,
                    %(hs_amt)s, %(hs_state_amt)s, %(hs_local_amt)s, %(hs_cap)s,
                    %(informational)s)
            ON CONFLICT (account_id, roll_year, roll_stage, owner_id, entity_id) DO NOTHING
            """,
            ev,
        )
        entity_n += 1

    conn.execute(
        "UPDATE tcad_roll_load SET record_count=%s, completed_at=now() WHERE roll_load_id=%s",
        (raw_n, roll_load_id),
    )
    log.info("loaded %s: %d raw, %d entity rows (roll_load_id=%s)",
             prop_ent_path, raw_n, entity_n, roll_load_id)
    return {"skipped": False, "roll_load_id": roll_load_id,
            "raw_rows": raw_n, "entity_rows": entity_n}
