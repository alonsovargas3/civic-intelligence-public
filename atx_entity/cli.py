"""Entity-resolution CLI: python -m atx_entity.cli <command>."""
import argparse
import logging
import os

from . import db


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atx-entity", description="TCAD owner entity resolution")
    sub = p.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build", help="resolve tcad_owner -> entity tables (rebuild-in-place)")
    pb.add_argument("--roll-year", type=int, default=None, help="roll year (default: latest)")
    pb.add_argument("--hub-threshold", type=int, default=25,
                    help="suppress address edges shared by > N distinct names")
    sub.add_parser("stats", help="print entity counts + kind/confidence breakdown")
    pe = sub.add_parser("explain", help="dump one entity's members + link evidence")
    pe.add_argument("entity_id")
    return p


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://atx:atx@localhost:5432/atx_civic")


def main(argv=None):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    with db.connect(_dsn()) as conn:
        db.bootstrap(conn)
        if args.cmd == "build":
            print("entity build summary:",
                  db.build(conn, roll_year=args.roll_year, hub_threshold=args.hub_threshold))
        elif args.cmd == "stats":
            n_ent = conn.execute("SELECT count(*) FROM dim_entity").fetchone()[0]
            n_par = conn.execute("SELECT count(*) FROM parcel_entity").fetchone()[0]
            print(f"  dim_entity: {n_ent}")
            print(f"  parcel_entity: {n_par}")
            print("  by kind/confidence:")
            for kind, conf, c in conn.execute(
                "SELECT kind, confidence, count(*) FROM dim_entity "
                "GROUP BY kind, confidence ORDER BY count(*) DESC"
            ).fetchall():
                print(f"    {kind:14} {conf:8} {c}")
            print("  largest entities:")
            for name, k, n in conn.execute(
                "SELECT canonical_name, kind, n_parcels FROM dim_entity "
                "ORDER BY n_parcels DESC LIMIT 10"
            ).fetchall():
                print(f"    {n:6}  {k:14} {name}")
        elif args.cmd == "explain":
            ent = conn.execute(
                "SELECT canonical_name, kind, confidence, n_parcels, n_owner_records, meta "
                "FROM dim_entity WHERE entity_id=%s", (args.entity_id,)
            ).fetchone()
            if not ent:
                print("no such entity:", args.entity_id); return
            print("entity:", args.entity_id, "->", ent[0],
                  f"({ent[1]}, {ent[2]}, {ent[3]} parcels, {ent[4]} owner records)")
            print("meta:", ent[5])
            print("links:")
            for kind, value, supp, n in conn.execute(
                "SELECT kind, value, suppressed, n_records FROM entity_link "
                "WHERE entity_id=%s ORDER BY n_records DESC", (args.entity_id,)
            ).fetchall():
                flag = " [SUPPRESSED HUB]" if supp else ""
                print(f"  {kind:8} n={n:4} {value}{flag}")


if __name__ == "__main__":
    main()
