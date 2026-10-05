"""assessment_cod — within-stratum assessment dispersion detector.

Supersedes D3a (which compared each ZIP's median appraised $/acre to the METRO
distribution — a land-value detector that flags the most EXPENSIVE ZIPs, not an
equity detector). Here we measure a coefficient-of-dispersion-style uniformity
statistic WITHIN each (ZIP, property class) stratum: do comparable neighbours get
assessed alike?

HONESTY: without sale prices this is NOT the IAAO ratio-based COD; it is a
uniformity measure on appraised value density (appraised per acre). High
dispersion = a screening signal that like properties are valued inconsistently,
NOT a finding of unfair assessment. The label is "HIGH DISPERSION", never
"over-assessed".

Reads parcel + parcel_value read-only; writes metric_assessment_cod + anomaly_flag.
"""
from __future__ import annotations

import logging

from psycopg.types.json import Json

log = logging.getLogger("atx.anomaly.assessment_cod")

DETECTOR = "assessment_cod"
CLUSTER_KIND = "zip_class"
METHODOLOGY = (
    "Assessment dispersion within a stratum: among comparable parcels (same "
    "property class, same ZIP) we compute a coefficient of dispersion (mean "
    "absolute deviation of appraised value per acre about the stratum median, as a "
    "percent of that median). High dispersion means like properties are assessed "
    "INCONSISTENTLY — a screening signal for review, labelled HIGH DISPERSION, "
    "never 'over-assessed'. This is a value-density uniformity measure, NOT an IAAO "
    "ratio-based COD: Texas is a non-disclosure state, so no sale prices are used. "
    "Strata with fewer than {minp} parcels are dropped (too few to be stable). The "
    "primary screen is dispersion percentile within the same class."
)

# The PRIMARY screen is dispersion percentile within the same class: flag the top
# decile. (Absolute COD thresholds ~20/25% are only heuristic anchors and, on this
# value-density COD, flag ~84% of strata — useless — because per-acre spread within
# a ZIP is naturally large; the relative rank is what isolates the unusual strata.)
_FLAG_PCTILE = 0.90


def pull_cod(conn, roll_year: int, roll_stage: str, min_parcels: int,
             prefix: str = "") -> list[dict]:
    """Per (ZIP, class) dispersion: n, median value/acre, COD%, percentile in class."""
    return conn.execute(
        f"""
        WITH base AS (
            SELECT (p.situs->>'zip') AS zip, p.category AS klass,
                   pv.appraised_value / p.acreage AS vpu
            FROM {prefix}parcel p
            JOIN {prefix}parcel_value pv ON pv.account_id = p.account_id
                  AND pv.roll_year = %(yr)s AND pv.roll_stage = %(st)s
            WHERE pv.appraised_value > 0 AND p.acreage > 0
              AND nullif(p.situs->>'zip', '') IS NOT NULL
        ),
        strata AS (
            SELECT zip, klass, count(*) AS n,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY vpu) AS med
            FROM base GROUP BY zip, klass
            HAVING count(*) >= %(minp)s
        ),
        cod AS (
            SELECT b.zip, b.klass, s.n, s.med,
                   100.0 * avg(abs(b.vpu - s.med)) / nullif(s.med, 0) AS cod
            FROM base b JOIN strata s USING (zip, klass)
            GROUP BY b.zip, b.klass, s.n, s.med
        )
        SELECT zip, klass, n, med, cod,
               percent_rank() OVER (PARTITION BY klass ORDER BY cod) AS pctile
        FROM cod
        ORDER BY klass, cod DESC
        """,
        {"yr": roll_year, "st": roll_stage, "minp": min_parcels},
    ).fetchall()


def run_assessment_cod(conn, roll_year: int = 2025, roll_stage: str = "certified",
                       min_parcels: int = 30, flag_pctile: float = _FLAG_PCTILE,
                       prefix: str = "") -> dict:
    """Score within-stratum dispersion; write detail + flags. Full rebuild per year.

    high_dispersion (and a flag) = the stratum's COD is in the top decile of its
    property class (flag_pctile, default 0.90) — the spec's primary screen.
    """
    rows = pull_cod(conn, roll_year, roll_stage, min_parcels, prefix)

    conn.execute(
        f"DELETE FROM {prefix}metric_assessment_cod WHERE roll_year=%s", (roll_year,))
    conn.execute(
        f"DELETE FROM {prefix}anomaly_flag WHERE detector=%s AND roll_year=%s",
        (DETECTOR, roll_year))

    flagged = 0
    for r in rows:
        klass = r["klass"]
        cod = float(r["cod"])
        pct = float(r["pctile"])
        high = pct >= flag_pctile
        detail = {
            "roll_year": roll_year, "situs_zip": r["zip"], "property_class": klass,
            "n_parcels": int(r["n"]), "median_value_per_unit": round(float(r["med"]), 2),
            "cod": round(cod, 1), "cod_pctile_in_class": round(pct, 3),
            "high_dispersion": high,
        }
        conn.execute(
            f"""
            INSERT INTO {prefix}metric_assessment_cod
                (roll_year, situs_zip, property_class, n_parcels, median_value_per_unit,
                 cod, cod_pctile_in_class, high_dispersion)
            VALUES (%(roll_year)s, %(situs_zip)s, %(property_class)s, %(n_parcels)s,
                    %(median_value_per_unit)s, %(cod)s, %(cod_pctile_in_class)s,
                    %(high_dispersion)s)
            ON CONFLICT (roll_year, situs_zip, property_class) DO UPDATE SET
                n_parcels=EXCLUDED.n_parcels,
                median_value_per_unit=EXCLUDED.median_value_per_unit,
                cod=EXCLUDED.cod, cod_pctile_in_class=EXCLUDED.cod_pctile_in_class,
                high_dispersion=EXCLUDED.high_dispersion
            """,
            detail,
        )
        if high:
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
                (DETECTOR, CLUSTER_KIND, f"{r['zip']}|{klass}", roll_year,
                 round(cod, 1), "dispersion", Json(detail),
                 METHODOLOGY.format(minp=min_parcels)),
            )
    summary = {"scored_strata": len(rows), "flagged": flagged, "roll_year": roll_year}
    log.info("assessment_cod run: %s", summary)
    return summary
