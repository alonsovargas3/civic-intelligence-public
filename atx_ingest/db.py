"""Postgres persistence.

Design: every source lands in a `raw_<table>` with the same shape:
    socrata_id  text  PRIMARY KEY   -- Socrata :id
    updated_at  timestamptz         -- Socrata :updated_at
    payload     jsonb               -- the full row, untouched
    ingested_at timestamptz
This keeps ingestion schema-agnostic. Promote columns later with views or
generated columns once you know which fields you care about per dataset.
"""
import logging

import psycopg
from psycopg.types.json import Json

log = logging.getLogger("atx.db")


def connect(dsn: str):
    # autocommit keeps the v1 simple; each statement is durable on return.
    return psycopg.connect(dsn, autocommit=True)


def bootstrap(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingestion_state (
            dataset_id    text PRIMARY KEY,
            last_cursor   text,
            last_run_at   timestamptz,
            rows_ingested bigint DEFAULT 0
        );
        """
    )


def ensure_source_table(conn, table: str) -> None:
    t = _safe(table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS raw_{t} (
            socrata_id  text PRIMARY KEY,
            updated_at  timestamptz,
            payload     jsonb NOT NULL,
            ingested_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_raw_{t}_updated ON raw_{t} (updated_at);")


def upsert_rows(conn, table: str, rows: list[tuple]) -> tuple[int, int]:
    """Upsert rows, returning (inserted, updated) counts.

    rows = [(socrata_id, updated_at, payload_dict), ...]. Rows without a
    socrata_id are skipped (legacy datasets lacking :id). The `xmax = 0` flag on
    the RETURNING clause distinguishes a fresh INSERT (xmax 0) from an ON CONFLICT
    UPDATE (xmax non-zero), so callers can count genuinely new rows separately
    from boundary re-pulls.
    """
    t = _safe(table)
    params = [(sid, uts, Json(payload)) for sid, uts, payload in rows if sid]
    if not params:
        return (0, 0)
    sql = f"""
        INSERT INTO raw_{t} (socrata_id, updated_at, payload)
        VALUES (%s, %s, %s)
        ON CONFLICT (socrata_id) DO UPDATE
            SET payload     = EXCLUDED.payload,
                updated_at  = EXCLUDED.updated_at,
                ingested_at = now()
        RETURNING (xmax = 0) AS inserted;
    """
    inserted = updated = 0
    with conn.cursor() as cur:
        cur.executemany(sql, params, returning=True)
        while True:
            row = cur.fetchone()
            if row is not None:
                if row[0]:
                    inserted += 1
                else:
                    updated += 1
            if not cur.nextset():
                break
    return (inserted, updated)


def get_cursor(conn, dataset_id: str) -> str | None:
    row = conn.execute(
        "SELECT last_cursor FROM ingestion_state WHERE dataset_id=%s", (dataset_id,)
    ).fetchone()
    return row[0] if row else None


def seconds_since_last_run(conn, dataset_id: str) -> float | None:
    """Seconds since this source last completed a pass, or None if never run.

    Computed DB-side (now() - last_run_at) so the comparison uses the same clock
    that wrote last_run_at — avoids host/container wall-clock skew.
    """
    row = conn.execute(
        "SELECT EXTRACT(EPOCH FROM (now() - last_run_at)) "
        "FROM ingestion_state WHERE dataset_id=%s",
        (dataset_id,),
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def set_cursor(conn, dataset_id: str, cursor: str | None, rows: int) -> None:
    conn.execute(
        """
        INSERT INTO ingestion_state (dataset_id, last_cursor, last_run_at, rows_ingested)
        VALUES (%s, %s, now(), %s)
        ON CONFLICT (dataset_id) DO UPDATE
            SET last_cursor   = EXCLUDED.last_cursor,
                last_run_at   = now(),
                rows_ingested = ingestion_state.rows_ingested + EXCLUDED.rows_ingested;
        """,
        (dataset_id, cursor, rows),
    )


def _safe(name: str) -> str:
    # table names are interpolated into DDL, so validate hard.
    if not name.replace("_", "").isalnum():
        raise ValueError(f"unsafe table name: {name!r}")
    return name.lower()
