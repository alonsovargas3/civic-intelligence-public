#!/usr/bin/env python3
"""Pull specific Socrata sources by table name, without touching the others.

Calls the same atx_ingest.run.ingest_source the poller uses, so cursors and
upserts behave identically — just scoped to the tables you name.

Usage:  python scripts/pull_sources.py council_votes city_contracts
"""
import sys

from atx_ingest import db, run
from atx_ingest.config import load_settings
from atx_ingest.run import _make_client, ingest_source

wanted = set(sys.argv[1:])
if not wanted:
    sys.exit("usage: pull_sources.py <table> [<table> ...]")

settings = load_settings()
srcs = [s for s in settings.sources if s.table in wanted]
found = {s.table for s in srcs}
missing = wanted - found
if missing:
    sys.exit(f"unknown table(s) in config/sources.yaml: {', '.join(sorted(missing))}")

for src in srcs:
    with db.connect(settings.database_url) as conn:
        db.bootstrap(conn)
        db.ensure_source_table(conn, src.table)
        client = _make_client(src, settings)
        ins, upd = ingest_source(client, conn, src)
        print(f"{src.table}: {run._fmt_counts(ins, upd)}")
