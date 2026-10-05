#!/usr/bin/env python3
"""Load an Inside Airbnb summary listings.csv into raw_airbnb_listings.

Usage:  python scripts/load_airbnb.py data/airbnb/2025-09-16/listings.csv

The snapshot date is read from the parent directory name. Idempotent: rows
upsert on listing_id, so re-running (or a newer snapshot) replaces cleanly.
Source: https://insideairbnb.com/get-the-data/ — data (c) Inside Airbnb,
CC BY 4.0. The CSV itself stays out of git (data/ is ignored; re-acquire by URL).
"""
from __future__ import annotations

import csv
import io
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # runnable as scripts/foo.py

from psycopg.types.json import Json

from atx_dashboard import db

log = logging.getLogger("atx.scripts.load_airbnb")

DDL = """
CREATE TABLE IF NOT EXISTS raw_airbnb_listings (
    listing_id    text PRIMARY KEY,
    snapshot_date date NOT NULL,
    payload       jsonb NOT NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now()
)
"""

UPSERT = """
INSERT INTO raw_airbnb_listings (listing_id, snapshot_date, payload)
VALUES (%s, %s, %s)
ON CONFLICT (listing_id) DO UPDATE
   SET snapshot_date = EXCLUDED.snapshot_date,
       payload       = EXCLUDED.payload,
       ingested_at   = now()
"""


def snapshot_date_from_path(path) -> str:
    """data/airbnb/2025-09-16/listings.csv -> '2025-09-16' (fail loudly otherwise)."""
    name = Path(path).parent.name
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", name):
        raise ValueError(
            f"parent dir of {str(path)!r} must be a YYYY-MM-DD snapshot date, got {name!r}"
        )
    return name


def rows_from_csv(text: str) -> list[tuple[str, dict]]:
    """CSV text -> [(listing_id, payload dict)]. Requires an 'id' column; skips blank ids."""
    reader = csv.DictReader(io.StringIO(text))
    if "id" not in (reader.fieldnames or []):
        raise ValueError("CSV has no 'id' column — not an Inside Airbnb listings file")
    out = []
    for row in reader:
        lid = (row.get("id") or "").strip()
        if lid:
            out.append((lid, dict(row)))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/load_airbnb.py <path/to/YYYY-MM-DD/listings.csv>")
    path = Path(sys.argv[1])
    snap = snapshot_date_from_path(path)
    rows = rows_from_csv(path.read_text(encoding="utf-8"))
    with db.connect() as conn:
        conn.execute(DDL)
        with conn.cursor() as cur:
            cur.executemany(UPSERT, [(lid, snap, Json(p)) for lid, p in rows])
    log.info("loaded %d listings (snapshot %s) into raw_airbnb_listings", len(rows), snap)


if __name__ == "__main__":
    main()
