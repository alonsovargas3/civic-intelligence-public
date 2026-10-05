"""TCAD Tier 2 CLI: python -m atx_ingest.tcad.cli <command>.

Mirrors the Tier 1 cli.py conventions but targets the TCAD schema/loader.
"""
import argparse
import logging
import os

from . import db
from .load import load_prop_file, load_prop_ent_file
from .geo import load_parcel_geo


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atx-tcad", description="TCAD Tier 2 loader")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create TCAD tables + the current-snapshot view")
    pl = sub.add_parser("load-prop", help="load one PROP.TXT export file")
    pl.add_argument("path")
    pl.add_argument("--year", type=int, required=True, help="roll year, e.g. 2025")
    pl.add_argument("--stage", required=True,
                    choices=["certified", "preliminary", "supplement"])
    pl.add_argument("--uri", default="", help="source URL for provenance")
    pl.add_argument("--informational", action="store_true",
                    help="mark this as a prior-year backfill (may differ from what was certified that year)")
    pe = sub.add_parser("load-prop-ent", help="load one PROP_ENT.TXT (per property-taxing-unit)")
    pe.add_argument("path")
    pe.add_argument("--year", type=int, required=True, help="roll year, e.g. 2025")
    pe.add_argument("--stage", required=True,
                    choices=["certified", "preliminary", "supplement"])
    pe.add_argument("--uri", default="", help="source URL for provenance")
    pe.add_argument("--informational", action="store_true",
                    help="mark this as a prior-year backfill (may differ from what was certified that year)")
    sub.add_parser("stats", help="print row counts per TCAD table")
    pg = sub.add_parser("load-geo", help="load parcel polygons from the ArcGIS REST API")
    pg.add_argument("--url", default=None, help="override the ArcGIS layer URL")
    pa = sub.add_parser(
        "acquire",
        help="download + unzip a TCAD export, locate its PROP file, then load it")
    pa.add_argument("--url", required=True, help="export zip URL (traviscad.org largefiles)")
    pa.add_argument("--year", type=int, required=True, help="roll year, e.g. 2025")
    pa.add_argument("--stage", required=True,
                    choices=["certified", "preliminary", "supplement"])
    pa.add_argument("--workdir", default="data/tcad",
                    help="working dir for the download + extraction "
                         "(staged per <year>_<stage> so rolls don't overwrite)")
    pa.add_argument("--no-load", action="store_true",
                    help="only fetch + locate the PROP file; do not load it")
    pa.add_argument("--allow-any-url", action="store_true",
                    help="bypass the traviscad.org host allowlist (use with care)")
    pa.add_argument("--informational", action="store_true",
                    help="mark this as a prior-year backfill (may differ from what was certified that year)")
    return p


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://atx:atx@localhost:5432/atx_civic")


def main(argv=None):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    if args.cmd == "acquire":
        from .acquire import acquire_prop_file
        prop_path = acquire_prop_file(args.url, args.workdir, year=args.year,
                                      stage=args.stage,
                                      allow_any_host=args.allow_any_url)
        print("PROP file:", prop_path)
        if args.no_load:
            return
        with db.connect(_dsn()) as conn:
            db.bootstrap(conn)
            summary = load_prop_file(conn, prop_path, args.year, args.stage,
                                     source_uri=args.url, informational=args.informational)
            print("load summary:", summary)
        return
    with db.connect(_dsn()) as conn:
        db.bootstrap(conn)
        if args.cmd == "init":
            print("tcad initialized")
        elif args.cmd == "load-prop":
            summary = load_prop_file(conn, args.path, args.year, args.stage,
                                     source_uri=args.uri, informational=args.informational)
            print("load summary:", summary)
        elif args.cmd == "load-prop-ent":
            summary = load_prop_ent_file(conn, args.path, args.year, args.stage,
                                         source_uri=args.uri, informational=args.informational)
            print("load summary:", summary)
        elif args.cmd == "load-geo":
            kwargs = {"base_url": args.url} if args.url else {}
            summary = load_parcel_geo(conn, **kwargs)
            print("geo load summary:", summary)
        elif args.cmd == "stats":
            for t in ("tcad_roll_load", "raw_tcad_roll", "tcad_owner",
                      "parcel", "parcel_value", "parcel_geo",
                      "raw_tcad_entity", "parcel_entity_value"):
                n = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                print(f"  {t}: {n}")


if __name__ == "__main__":
    main()
