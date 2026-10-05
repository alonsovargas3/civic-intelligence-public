"""Anomaly CLI: python -m atx_anomaly.cli <run-d3a|run-d7|stats>."""
from __future__ import annotations

import argparse
import logging

from . import assessment_cod, d3a, d4, d7, db


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atx-anomaly", description="Civic anomaly detectors")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run-d3a", help="run the D3a assessment-equity detector")
    pr.add_argument("--roll-year", dest="roll_year", type=int, default=2025)
    pr.add_argument("--class", dest="klass", default="A1")
    pr.add_argument("--min-parcels", dest="min_parcels", type=int, default=50)
    pr.add_argument("--z", type=float, default=3.5)
    pr.add_argument("--stage", dest="roll_stage", default="certified",
                    help="parcel_value roll_stage to score (default certified)")

    p7 = sub.add_parser("run-d7", help="run the D7 311-responsiveness-disparity detector")
    p7.add_argument("--since", default=None,
                    help="only count 311 cases created on/after this date (ISO; default all)")
    p7.add_argument("--window-year", dest="window_year", type=int, default=0,
                    help="analysis-window anchor stored on the flag (0 = all history)")
    p7.add_argument("--min-cases", dest="min_cases", type=int, default=200,
                    help="minimum closed cases for a district to be scored")
    p7.add_argument("--min-type-cases", dest="min_type_cases", type=int, default=20,
                    help="minimum closed cases for a (district, request type) cell")
    p7.add_argument("--high-ratio", dest="high_ratio", type=float, default=1.5,
                    help="flag when observed/expected >= this (and <= 1/this for 'faster')")

    pc = sub.add_parser("run-assessment-cod",
                        help="run the assessment-dispersion (COD) detector — supersedes d3a")
    pc.add_argument("--roll-year", dest="roll_year", type=int, default=2025)
    pc.add_argument("--stage", dest="roll_stage", default="certified")
    pc.add_argument("--min-parcels", dest="min_parcels", type=int, default=30,
                    help="minimum parcels per (ZIP, class) stratum")

    p4 = sub.add_parser("run-d4",
                        help="run the D4 institutional-divergence detector (cross-sectional)")
    p4.add_argument("--roll-year", dest="roll_year", type=int, default=2025)
    p4.add_argument("--stage", dest="roll_stage", default="certified")
    p4.add_argument("--kind", default="institutional", help="owner kind to score (default institutional)")
    p4.add_argument("--min-parcels", dest="min_parcels", type=int, default=20,
                    help="minimum valued parcels for an entity to be scored")
    p4.add_argument("--low-ratio", dest="low_ratio", type=float, default=0.7,
                    help="flag divergence <= this (below) or >= 1/this (above)")
    p4.add_argument("--min-value", dest="min_value", type=float, default=10000,
                    help="drop parcels appraised below this (HOA/common-area lots)")

    sub.add_parser("stats", help="print detector flag + detail counts")
    return p


def main(argv=None):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    with db.connect() as conn:
        db.bootstrap(conn)
        if args.cmd == "run-d3a":
            print("d3a summary:", d3a.run_d3a(
                conn, roll_year=args.roll_year, klass=args.klass,
                min_parcels=args.min_parcels, z_threshold=args.z,
                roll_stage=args.roll_stage))
        elif args.cmd == "run-d7":
            print("d7 summary:", d7.run_d7(
                conn, since=args.since, window_year=args.window_year,
                min_cases=args.min_cases, min_type_cases=args.min_type_cases,
                high_ratio=args.high_ratio))
        elif args.cmd == "run-d4":
            print("d4 summary:", d4.run_d4(
                conn, roll_year=args.roll_year, roll_stage=args.roll_stage,
                kind=args.kind, min_parcels=args.min_parcels, low_ratio=args.low_ratio,
                min_value=args.min_value))
        elif args.cmd == "run-assessment-cod":
            print("assessment_cod summary:", assessment_cod.run_assessment_cod(
                conn, roll_year=args.roll_year, roll_stage=args.roll_stage,
                min_parcels=args.min_parcels))
        elif args.cmd == "stats":
            scored = conn.execute(
                "SELECT count(*) AS n FROM metric_assessment_equity").fetchone()["n"]
            flagged = conn.execute(
                "SELECT count(*) AS n FROM anomaly_flag WHERE detector=%s",
                (d3a.DETECTOR,)).fetchone()["n"]
            print(f"  metric_assessment_equity rows: {scored}")
            print(f"  d3a flags: {flagged}")
            for r in conn.execute(
                "SELECT cluster_id, direction, score FROM anomaly_flag "
                "WHERE detector=%s ORDER BY score DESC LIMIT 20", (d3a.DETECTOR,)).fetchall():
                print(f"    {r['cluster_id']:8} {r['direction']:5} z={r['score']}")

            d7_scored = conn.execute(
                "SELECT count(*) AS n FROM metric_311_equity").fetchone()["n"]
            d7_flagged = conn.execute(
                "SELECT count(*) AS n FROM anomaly_flag WHERE detector=%s",
                (d7.DETECTOR,)).fetchone()["n"]
            print(f"  metric_311_equity rows: {d7_scored}")
            print(f"  d7 flags: {d7_flagged}")
            for r in conn.execute(
                "SELECT cluster_id, direction, score FROM anomaly_flag "
                "WHERE detector=%s ORDER BY score DESC LIMIT 20", (d7.DETECTOR,)).fetchall():
                print(f"    district {r['cluster_id']:3} {r['direction']:6} ratio={r['score']}")


if __name__ == "__main__":
    main()
