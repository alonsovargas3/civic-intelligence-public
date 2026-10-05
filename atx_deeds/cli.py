"""Deeds loader CLI: python -m atx_deeds.cli <command>."""
import argparse
import logging
import os

from . import db
from .source import SampleSource


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atx-deeds", description="Travis County deed loader")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("load", help="load deeds from a source into raw_deeds + deed_parcel")
    pl.add_argument("--source", default="sample", choices=["sample"],
                    help="acquisition source (only 'sample' for now; bulk adapters later)")
    pl.add_argument("path", help="path to the source file (for --source sample)")
    sub.add_parser("match", help="re-derive deed_parcel from current raw_deeds + parcels")
    sub.add_parser("stats", help="print deed counts + match rate")
    return p


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://atx:atx@localhost:5432/atx_civic")


def _make_source(args):
    if args.source == "sample":
        return SampleSource(args.path)
    raise ValueError(f"unknown source: {args.source}")


def main(argv=None):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    with db.connect(_dsn()) as conn:
        db.bootstrap(conn)
        if args.cmd == "load":
            print("deeds load summary:", db.load_deeds(conn, _make_source(args)))
        elif args.cmd == "match":
            # re-match existing raw_deeds against current parcels (no re-ingest)
            index = db.load_parcel_index(conn)
            from .match import match_to_parcel
            rows = conn.execute(
                "SELECT instrument_num, legal_desc FROM raw_deeds"
            ).fetchall()
            conn.execute("TRUNCATE deed_parcel;")
            n = 0
            for inst, legal in rows:
                acct, conf, method = match_to_parcel({"legal_desc": legal}, index)
                if acct is not None:
                    conn.execute(
                        "INSERT INTO deed_parcel (instrument_num, account_id, "
                        "match_confidence, method) VALUES (%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING",
                        (inst, acct, conf, method),
                    )
                    n += 1
            print(f"re-matched {n} of {len(rows)} deeds")
        elif args.cmd == "stats":
            d = conn.execute("SELECT count(*) FROM raw_deeds").fetchone()[0]
            m = conn.execute("SELECT count(DISTINCT instrument_num) FROM deed_parcel").fetchone()[0]
            print(f"  raw_deeds: {d}")
            print(f"  matched to a parcel: {m}")
            for conf, c in conn.execute(
                "SELECT match_confidence, count(*) FROM deed_parcel "
                "GROUP BY match_confidence ORDER BY count(*) DESC"
            ).fetchall():
                print(f"    {conf}: {c}")


if __name__ == "__main__":
    main()
