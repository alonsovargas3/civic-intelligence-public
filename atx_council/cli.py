"""Council CLI: python -m atx_council.cli <build|stats>."""
from __future__ import annotations

import argparse
import logging

from . import build as build_mod
from . import db, representation


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atx-council",
                                description="Council contribution->sponsorship analytics")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="rebuild metric_member_funding_activity")
    sub.add_parser("build-representation",
                   help="rebuild metric_member_sponsorship + metric_cosponsorship")
    sub.add_parser("stats", help="print members ranked by contributions / sponsorship")
    return p


def main(argv=None):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    with db.connect() as conn:
        db.bootstrap(conn)
        if args.cmd == "build":
            print("member activity build:", build_mod.build_member_activity(conn))
        elif args.cmd == "build-representation":
            print("representation build:", representation.build_representation(conn))
        elif args.cmd == "stats":
            print("  council members — contributions vs matters sponsored:")
            for r in conn.execute(
                "SELECT canonical_name, n_matters_sponsored, contributions_total, n_contributions "
                "FROM metric_member_funding_activity ORDER BY contributions_total DESC").fetchall():
                print(f"    {r['canonical_name'][:28]:28} ${int(r['contributions_total']):>12,} "
                      f"({r['n_contributions']:>5} contribs) · {r['n_matters_sponsored']:>4} matters")


if __name__ == "__main__":
    main()
