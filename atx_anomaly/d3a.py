"""D3a — assessment-equity dispersion detector.

Within a comparable class (A1 single-family), compare each situs ZIP's median
appraised-value-per-acre against the metro distribution and flag robust outliers.
Reads parcel/parcel_value read-only; writes anomaly_flag + metric_assessment_equity.
"""
from __future__ import annotations

import logging

from psycopg.types.json import Json

from .stats import mad, median, modified_z, percentile_rank

log = logging.getLogger("atx.anomaly.d3a")

DETECTOR = "d3a_assessment_equity"
CLUSTER_KIND = "zip"
METHODOLOGY = (
    "Assessment-equity dispersion: within class {klass}, each situs ZIP's median "
    "appraised value per acre is compared to the metro distribution via a robust "
    "modified z-score (median/MAD); |z| >= {z} is flagged. This measures assessment "
    "DISPERSION from the appraisal roll alone, NOT an assessment-to-sale ratio "
    "(Texas is a non-disclosure state; no sale prices are used). It does not yet "
    "control for genuine location premia, property mix, or protest rates, so a flag "
    "is a screening signal for review, not a finding of unfair assessment."
)


def pull_zip_stats(conn, roll_year: int, klass: str, min_parcels: int,
                   roll_stage: str = "certified") -> list[dict]:
    """Per-ZIP A1 aggregates from parcel + parcel_value (read-only).

    Returns dict rows: zip, n_parcels (with acreage), n_total, median_per_acre,
    median_appraised. Only ZIPs with n_parcels >= min_parcels are returned.

    Filters parcel_value to a SINGLE roll_stage (default 'certified'): the table's
    PK is (account_id, roll_year, roll_stage), so a parcel can carry several stages
    in one year once supplements/prior-year rolls land — without this filter those
    rows would double-count into the per-ZIP medians.
    """
    return conn.execute(
        """
        WITH src AS (
            SELECT (p.situs->>'zip') AS zip,
                   pv.appraised_value AS appraised,
                   p.acreage AS acreage
            FROM parcel p
            JOIN parcel_value pv USING (account_id)
            WHERE p.category = %(klass)s
              AND pv.roll_year = %(yr)s
              AND pv.roll_stage = %(stage)s
              AND pv.appraised_value > 0
              AND nullif(p.situs->>'zip', '') IS NOT NULL
        )
        SELECT zip,
               count(*) FILTER (WHERE acreage > 0)                          AS n_parcels,
               count(*)                                                     AS n_total,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY appraised / acreage)
                   FILTER (WHERE acreage > 0)                               AS median_per_acre,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY appraised)       AS median_appraised
        FROM src
        GROUP BY zip
        HAVING count(*) FILTER (WHERE acreage > 0) >= %(minp)s
        ORDER BY zip
        """,
        {"klass": klass, "yr": roll_year, "minp": min_parcels, "stage": roll_stage},
    ).fetchall()


def run_d3a(conn, roll_year: int = 2025, klass: str = "A1", min_parcels: int = 50,
           z_threshold: float = 3.5, roll_stage: str = "certified",
           prefix: str = "") -> dict:
    """Score per-ZIP assessment equity and write the detail + flag tables.

    Full-rebuild for this (detector, class, roll_year): clears its own prior rows,
    then re-inserts. Scores a single roll_stage (default 'certified'). Returns a
    summary dict.

    NOTE: anomaly_flag has no `class` column and the flag-clearing DELETE is keyed
    on (detector, roll_year) only. v1 is single-class (A1), so this is safe; if a
    second class is ever run for the same roll_year, add a `class` column to
    anomaly_flag (or filter the DELETE) first, or the second run will wipe the
    first class's flags.
    """
    rows = pull_zip_stats(conn, roll_year, klass, min_parcels, roll_stage)
    per_acre = [float(r["median_per_acre"]) for r in rows]
    metro_med = median(per_acre) or 0.0
    metro_mad = mad(per_acre)

    # clear this detector/class/year's prior output (idempotent re-run)
    conn.execute(
        f"DELETE FROM {prefix}metric_assessment_equity WHERE roll_year=%s AND class=%s",
        (roll_year, klass),
    )
    conn.execute(
        f"DELETE FROM {prefix}anomaly_flag WHERE detector=%s AND roll_year=%s",
        (DETECTOR, roll_year),
    )

    flagged = 0
    for r in rows:
        val = float(r["median_per_acre"])
        z = modified_z(val, metro_med, metro_mad)
        pct = percentile_rank(val, per_acre)
        is_flag = abs(z) >= z_threshold
        detail = {
            "roll_year": roll_year, "class": klass, "zip": r["zip"],
            "n_parcels": r["n_parcels"], "n_total": r["n_total"],
            "median_per_acre": val,
            "median_appraised": float(r["median_appraised"]) if r["median_appraised"] is not None else None,
            "modified_z": round(z, 4), "percentile": round(pct, 1), "flagged": is_flag,
        }
        conn.execute(
            f"""
            INSERT INTO {prefix}metric_assessment_equity
                (roll_year, class, zip, n_parcels, n_total, median_per_acre,
                 median_appraised, modified_z, percentile, flagged)
            VALUES (%(roll_year)s, %(class)s, %(zip)s, %(n_parcels)s, %(n_total)s,
                    %(median_per_acre)s, %(median_appraised)s, %(modified_z)s,
                    %(percentile)s, %(flagged)s)
            ON CONFLICT (roll_year, class, zip) DO UPDATE SET
                n_parcels=EXCLUDED.n_parcels, n_total=EXCLUDED.n_total,
                median_per_acre=EXCLUDED.median_per_acre,
                median_appraised=EXCLUDED.median_appraised,
                modified_z=EXCLUDED.modified_z, percentile=EXCLUDED.percentile,
                flagged=EXCLUDED.flagged
            """,
            detail,
        )
        if is_flag:
            flagged += 1
            conn.execute(
                f"""
                INSERT INTO {prefix}anomaly_flag
                    (detector, cluster_kind, cluster_id, roll_year, score, direction,
                     evidence, methodology)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (detector, cluster_kind, cluster_id, roll_year) DO UPDATE SET
                    score=EXCLUDED.score, direction=EXCLUDED.direction,
                    evidence=EXCLUDED.evidence, methodology=EXCLUDED.methodology,
                    review_state='unreviewed'
                """,
                (DETECTOR, CLUSTER_KIND, r["zip"], roll_year, round(abs(z), 4),
                 "over" if z > 0 else "under", Json(detail),
                 METHODOLOGY.format(klass=klass, z=z_threshold)),
            )
    summary = {"scored_zips": len(rows), "flagged_zips": flagged,
               "metro_median_per_acre": round(metro_med, 2), "mad": round(metro_mad, 2)}
    log.info("d3a run: %s", summary)
    return summary
