"""CLI: python -m atx_ingest.cli <command>"""
import argparse
import logging
import time

from . import db, run
from .config import load_settings
from .socrata import SocrataClient


def main(argv=None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(prog="atx-ingest", description="Austin civic data ingester")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create database tables")
    sub.add_parser("run-once", help="one ingest pass over all enabled sources")
    pr = sub.add_parser("run", help="loop forever")
    pr.add_argument("--interval", type=int, default=1800, help="seconds between passes")
    pd = sub.add_parser("discover", help="print column names for a dataset id")
    pd.add_argument("dataset_id")
    pb = sub.add_parser("backfill", help="reset cursor then re-pull (dataset id or 'all')")
    pb.add_argument("dataset_id")

    args = p.parse_args(argv)
    settings = load_settings()
    cli_log = logging.getLogger("atx.cli")

    if args.cmd == "init":
        with db.connect(settings.database_url) as conn:
            db.bootstrap(conn)
            for s in settings.sources:
                db.ensure_source_table(conn, s.table)
        print("initialized:", ", ".join(s.table for s in settings.sources))

    elif args.cmd == "discover":
        client = SocrataClient(settings.socrata_domain, settings.app_token)
        rows = client.sample(args.dataset_id, 1)
        if not rows:
            print("no rows returned")
        else:
            for k in sorted(rows[0].keys()):
                print(k)

    elif args.cmd == "backfill":
        with db.connect(settings.database_url) as conn:
            db.bootstrap(conn)
            if args.dataset_id == "all":
                conn.execute("UPDATE ingestion_state SET last_cursor=NULL")
            else:
                conn.execute(
                    "UPDATE ingestion_state SET last_cursor=NULL WHERE dataset_id=%s",
                    (args.dataset_id,),
                )
        print("cursor reset — run 'run-once' to backfill")

    elif args.cmd == "run-once":
        ins, upd = run.run_once(settings)
        print(f"ingested {run._fmt_counts(ins, upd)}")

    elif args.cmd == "run":
        cli_log.info("starting loop, interval=%ds", args.interval)
        while True:
            try:
                ins, upd = run.run_once(settings)
                cli_log.info(
                    "pass complete: %s; sleeping %ds",
                    run._fmt_counts(ins, upd), args.interval,
                )
            except Exception as exc:
                cli_log.error("pass failed: %s", exc)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
