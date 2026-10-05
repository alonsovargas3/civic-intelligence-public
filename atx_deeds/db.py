"""Deed storage: schema + load (upsert raw_deeds, derive deed_parcel). Only DB module.

Reads `parcel` (account_id, legal) read-only to build the match index; never mutates it.
Upsert on instrument_num makes re-runs idempotent.
"""
import logging

import psycopg
from psycopg.types.json import Json

from .match import build_parcel_index, match_to_parcel

log = logging.getLogger("atx.deeds.db")

DDL = """
CREATE TABLE IF NOT EXISTS raw_deeds (
    instrument_num text PRIMARY KEY,
    recorded_date  date,
    doc_type       text,
    grantors       jsonb,
    grantees       jsonb,
    legal_desc     text,
    payload        jsonb NOT NULL,
    source         text NOT NULL,
    ingested_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deed_parcel (
    instrument_num   text NOT NULL REFERENCES raw_deeds(instrument_num),
    account_id       text NOT NULL,
    match_confidence text NOT NULL,
    method           text NOT NULL,
    PRIMARY KEY (instrument_num, account_id)
);
CREATE INDEX IF NOT EXISTS idx_deed_parcel_account ON deed_parcel (account_id);

CREATE OR REPLACE VIEW parcel_transfer_history AS
SELECT dp.account_id, d.instrument_num, d.recorded_date, d.doc_type,
       d.grantors, d.grantees, dp.match_confidence
FROM deed_parcel dp
JOIN raw_deeds d USING (instrument_num)
ORDER BY dp.account_id, d.recorded_date;
"""


def connect(dsn: str):
    return psycopg.connect(dsn, autocommit=True)


def bootstrap(conn) -> None:
    conn.execute(DDL)


def load_parcel_index(conn) -> dict:
    """Read parcel (account_id, legal) ordered by account_id, build the match index."""
    rows = conn.execute(
        "SELECT account_id, legal FROM parcel WHERE legal IS NOT NULL "
        "AND legal <> '' ORDER BY account_id"
    ).fetchall()
    return build_parcel_index(rows)


def load_deeds(conn, source) -> dict:
    """Stream deeds from `source`: upsert raw_deeds, derive deed_parcel. Idempotent.

    Returns {"deeds": n, "matched": m, "unmatched": u}.
    """
    index = load_parcel_index(conn)
    deeds = matched = unmatched = 0
    for d in source.iter_deeds():
        inst = d["instrument_num"]
        if not inst:
            continue
        conn.execute(
            """
            INSERT INTO raw_deeds (instrument_num, recorded_date, doc_type,
                grantors, grantees, legal_desc, payload, source)
            VALUES (%(instrument_num)s, %(recorded_date)s, %(doc_type)s,
                %(grantors)s, %(grantees)s, %(legal_desc)s, %(payload)s, %(source)s)
            ON CONFLICT (instrument_num) DO UPDATE
                SET recorded_date = EXCLUDED.recorded_date,
                    doc_type      = EXCLUDED.doc_type,
                    grantors      = EXCLUDED.grantors,
                    grantees      = EXCLUDED.grantees,
                    legal_desc    = EXCLUDED.legal_desc,
                    payload       = EXCLUDED.payload,
                    source        = EXCLUDED.source,
                    ingested_at   = now()
            """,
            {"instrument_num": inst, "recorded_date": d.get("recorded_date"),
             "doc_type": d.get("doc_type"), "grantors": Json(d.get("grantors") or []),
             "grantees": Json(d.get("grantees") or []), "legal_desc": d.get("legal_desc"),
             "payload": Json(d.get("raw") or {}), "source": getattr(source, "name", "unknown")},
        )
        deeds += 1
        acct, conf, method = match_to_parcel(d, index)
        if acct is not None:
            conn.execute(
                """
                INSERT INTO deed_parcel (instrument_num, account_id, match_confidence, method)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (instrument_num, account_id) DO UPDATE
                    SET match_confidence = EXCLUDED.match_confidence,
                        method = EXCLUDED.method
                """,
                (inst, acct, conf, method),
            )
            matched += 1
        else:
            unmatched += 1
    summary = {"deeds": deeds, "matched": matched, "unmatched": unmatched}
    log.info("deeds load: %s", summary)
    return summary
