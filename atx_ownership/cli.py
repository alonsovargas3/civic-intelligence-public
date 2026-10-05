"""Ownership CLI: python -m atx_ownership.cli <build-crosswalk|build|stats>."""
from __future__ import annotations

import argparse
import logging

from . import build as build_mod
from . import crosswalk, db, differential


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atx-ownership",
                                description="Austin ownership-concentration layer")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build-crosswalk",
                   help="reproject parcel_geo centroids and assign each to a council district")

    pb = sub.add_parser("build", help="rebuild metric_ownership_* from the entity + parcel layers")
    pb.add_argument("--roll-year", dest="roll_year", type=int, default=2025)
    pb.add_argument("--stage", dest="roll_stage", default="certified",
                    help="parcel_value roll_stage to value parcels at (default certified)")
    pb.add_argument("--top-n", dest="top_n", type=int, default=100,
                    help="how many owners to store in each ranking")

    pd = sub.add_parser("build-differential",
                        help="rebuild metric_owner_treatment (category-stratified owner treatment)")
    pd.add_argument("--roll-year", dest="roll_year", type=int, default=2025)
    pd.add_argument("--stage", dest="roll_stage", default="certified")
    pd.add_argument("--window-start", dest="window_start", default="2024-01-01",
                    help="count only code cases opened on/after this date (limits mis-attribution)")
    pd.add_argument("--min-parcels", dest="min_parcels", type=int, default=30,
                    help="minimum parcels per (property_class, owner_type) cell")

    sub.add_parser("stats", help="print ownership concentration + top owners")
    return p


def main(argv=None):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    with db.connect() as conn:
        db.bootstrap(conn)
        if args.cmd == "build-crosswalk":
            print("crosswalk summary:", crosswalk.build_crosswalk(conn))
        elif args.cmd == "build":
            print("ownership build:", build_mod.build_ownership(
                conn, roll_year=args.roll_year, roll_stage=args.roll_stage, top_n=args.top_n))
        elif args.cmd == "build-differential":
            print("differential build:", differential.build_differential(
                conn, roll_year=args.roll_year, roll_stage=args.roll_stage,
                window_start=args.window_start, min_parcels=args.min_parcels))
        elif args.cmd == "stats":
            print("  ownership concentration by kind:")
            for r in conn.execute(
                "SELECT segment, n_entities, n_parcels, round(parcel_share,4) ps, "
                "round(value_share,4) vs, round(hhi_parcels,4) hhi "
                "FROM metric_ownership_concentration WHERE dimension='kind' "
                "ORDER BY n_parcels DESC").fetchall():
                print(f"    {r['segment']:10} ent={r['n_entities']:>7} parcels={r['n_parcels']:>7} "
                      f"pshare={r['ps']} vshare={r['vs']} hhi={r['hhi']}")
            print("  top owners by parcel count:")
            for r in conn.execute(
                "SELECT rank, canonical_name, kind, n_parcels, total_appraised "
                "FROM metric_owner_ranking WHERE scope='by_parcels' ORDER BY rank LIMIT 15").fetchall():
                print(f"    {r['rank']:>3}. {r['canonical_name'][:40]:40} {r['kind']:8} "
                      f"{r['n_parcels']:>6} parcels  ${int(r['total_appraised']):,}")


if __name__ == "__main__":
    main()
