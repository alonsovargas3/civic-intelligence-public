"""Dashboard CLI: python -m atx_dashboard.cli <refresh|load-boundaries|load-zip-boundaries|serve>."""
from __future__ import annotations

import argparse
import logging

from . import aggregate, boundaries, db, zip_boundaries


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atx-dashboard", description="Civic dashboard read layer")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh", help="rebuild metric_* summary tables from raw_*")
    sub.add_parser("load-boundaries", help="fetch + load council-district polygons")
    sub.add_parser("load-zip-boundaries", help="fetch + load ZCTA polygons for the analytics' ZIPs")
    ps = sub.add_parser("serve", help="run the read API")
    ps.add_argument("--port", type=int, default=8000)
    ps.add_argument("--host", default="127.0.0.1")
    return p


def main(argv=None):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    if args.cmd == "serve":
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(), host=args.host, port=args.port)
        return
    with db.connect() as conn:
        db.bootstrap(conn)
        if args.cmd == "refresh":
            print("aggregate:", aggregate.run(conn))
        elif args.cmd == "load-boundaries":
            n = boundaries.load(conn, boundaries.fetch())
            print(f"loaded {n} district boundaries")
        elif args.cmd == "load-zip-boundaries":
            zips = zip_boundaries.zips_to_load(conn)
            n = zip_boundaries.load(conn, zip_boundaries.fetch(zips))
            print(f"loaded {n} zip boundaries (of {len(zips)} requested)")


if __name__ == "__main__":
    main()
