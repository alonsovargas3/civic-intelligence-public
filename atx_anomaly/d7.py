"""D7 — 311 responsiveness disparity detector.

Compares each council district's mix-weighted median days-to-resolution against
what its OWN request mix would predict at the metro pace (indirect standardization),
then flags districts whose disparity ratio crosses a threshold. Reads
raw_austin_311 read-only; writes anomaly_flag + metric_311_equity.

Why a ratio threshold, not a modified-z: there are only 10 districts, so a
median/MAD z is degenerate (fair districts cluster at ratio ~1.0 -> MAD ~0 ->
nothing flags). The observed/expected ratio is also more interpretable ("resolves
50%+ slower than its request mix predicts") and is honestly a SCREEN, not a
significance test.
"""
from __future__ import annotations

import logging

from psycopg.types.json import Json

from .stats import mix_adjusted_ratio, percentile_rank

log = logging.getLogger("atx.anomaly.d7")

DETECTOR = "d7_311_equity"
CLUSTER_KIND = "district"
METHODOLOGY = (
    "311 responsiveness disparity: for each request type, the metro-wide median "
    "days-to-resolution is the baseline. Each district's observed mix-weighted "
    "median is compared to the median it would post if it ran its OWN request mix "
    "at the metro pace (indirect standardization); a disparity ratio >= {high} "
    "(slower) or <= {low} (faster) is flagged. This CONTROLS FOR REQUEST MIX — a "
    "district dominated by inherently slow request types is not flagged on that "
    "basis alone. It does NOT yet control for crew capacity/geography, reporting-"
    "rate differences, or seasonality, so a flag is a screening signal for review, "
    "not a finding of inequity. District is the finest geography 311 carries "
    "directly, and there are only 10 districts, so this is a coarse screen."
)

# valid council district = numeric text in 1..10 (mirrors aggregate._VALID_CD)
_VALID_CD = "(p->>'sr_location_council_district') ~ '^[0-9]+$' " \
            "AND (p->>'sr_location_council_district')::int BETWEEN 1 AND 10"

# resolution time in days for a closed case; guards against negative/zero-length
# durations from data errors (closed before created).
_DAYS = ("EXTRACT(epoch FROM ((p->>'sr_closed_date')::timestamp "
         "- (p->>'sr_created_date')::timestamp)) / 86400.0")

_CLOSED = ("nullif(p->>'sr_closed_date','') IS NOT NULL "
           "AND nullif(p->>'sr_created_date','') IS NOT NULL "
           f"AND {_DAYS} >= 0")

_SR_TYPE = "coalesce(nullif(p->>'sr_type_desc',''), 'UNKNOWN')"


def _since_clause(since: str | None) -> str:
    return "" if since is None else \
        " AND (p->>'sr_created_date')::timestamp >= %(since)s"


def pull_metro_type_medians(conn, since: str | None = None) -> dict:
    """Metro-wide median resolution days per request type (the baseline)."""
    params = {} if since is None else {"since": since}
    rows = conn.execute(
        f"""
        SELECT {_SR_TYPE} AS sr_type,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY {_DAYS}) AS metro_median_days
        FROM (SELECT payload AS p FROM raw_austin_311) s
        WHERE {_VALID_CD} AND {_CLOSED}{_since_clause(since)}
        GROUP BY 1
        """,
        params,
    ).fetchall()
    return {r["sr_type"]: float(r["metro_median_days"]) for r in rows}


def pull_district_type_stats(conn, since: str | None = None,
                             min_type_cases: int = 20) -> list[dict]:
    """Per-(district, request type) closed-case count + median resolution days.

    Only (district, type) cells with at least `min_type_cases` closed cases are
    returned — thin cells make per-type medians noisy and are dropped from that
    district's mix.
    """
    params = {"minc": min_type_cases}
    if since is not None:
        params["since"] = since
    return conn.execute(
        f"""
        SELECT (p->>'sr_location_council_district')::int AS district,
               {_SR_TYPE} AS sr_type,
               count(*) AS n_closed,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY {_DAYS}) AS median_days
        FROM (SELECT payload AS p FROM raw_austin_311) s
        WHERE {_VALID_CD} AND {_CLOSED}{_since_clause(since)}
        GROUP BY 1, 2
        HAVING count(*) >= %(minc)s
        ORDER BY 1, 2
        """,
        params,
    ).fetchall()


def run_d7(conn, since: str | None = None, window_year: int = 0,
           min_cases: int = 200, min_type_cases: int = 20,
           high_ratio: float = 1.5, low_ratio: float | None = None,
           prefix: str = "") -> dict:
    """Score per-district 311 responsiveness disparity; write detail + flags.

    Full-rebuild for this window_year: clears its own prior rows then re-inserts.
    `window_year` is the analysis-window anchor (0 = all history) and is stored in
    anomaly_flag.roll_year (which is generic; D7 has no appraisal roll) so the flag
    key (detector, cluster_kind, cluster_id, roll_year) stays non-null and upserts.
    Returns a summary dict.
    """
    if low_ratio is None:
        low_ratio = round(1.0 / high_ratio, 4)

    metro = pull_metro_type_medians(conn, since)
    stats = pull_district_type_stats(conn, since, min_type_cases)

    # group per-district strata: (n, district_median, metro_median)
    per_district: dict[int, list] = {}
    for r in stats:
        m = metro.get(r["sr_type"])
        if m is None:
            continue
        per_district.setdefault(r["district"], []).append(
            (int(r["n_closed"]), float(r["median_days"]), m))

    scored = []
    for district, strata in per_district.items():
        n_closed = sum(n for n, _, _ in strata)
        if n_closed < min_cases:
            continue
        ratio = mix_adjusted_ratio(strata)
        if ratio is None:
            continue
        observed = sum(n * obs for n, obs, _ in strata) / n_closed
        expected = sum(n * met for n, _, met in strata) / n_closed
        scored.append({
            "district": district, "n_closed": n_closed, "n_types": len(strata),
            "observed": observed, "expected": expected, "ratio": ratio,
        })

    ratios = [s["ratio"] for s in scored]

    conn.execute(
        f"DELETE FROM {prefix}metric_311_equity WHERE window_year=%s", (window_year,))
    conn.execute(
        f"DELETE FROM {prefix}anomaly_flag WHERE detector=%s AND roll_year=%s",
        (DETECTOR, window_year))

    flagged = 0
    for s in scored:
        ratio = s["ratio"]
        is_flag = ratio >= high_ratio or ratio <= low_ratio
        pct = percentile_rank(ratio, ratios)
        detail = {
            "window_year": window_year, "council_district": s["district"],
            "n_closed": s["n_closed"], "n_types": s["n_types"],
            "observed_days": round(s["observed"], 4),
            "expected_days": round(s["expected"], 4),
            "disparity_ratio": round(ratio, 4),
            "percentile": round(pct, 1), "flagged": is_flag,
        }
        conn.execute(
            f"""
            INSERT INTO {prefix}metric_311_equity
                (window_year, council_district, n_closed, n_types, observed_days,
                 expected_days, disparity_ratio, percentile, flagged)
            VALUES (%(window_year)s, %(council_district)s, %(n_closed)s, %(n_types)s,
                    %(observed_days)s, %(expected_days)s, %(disparity_ratio)s,
                    %(percentile)s, %(flagged)s)
            ON CONFLICT (window_year, council_district) DO UPDATE SET
                n_closed=EXCLUDED.n_closed, n_types=EXCLUDED.n_types,
                observed_days=EXCLUDED.observed_days, expected_days=EXCLUDED.expected_days,
                disparity_ratio=EXCLUDED.disparity_ratio, percentile=EXCLUDED.percentile,
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
                (DETECTOR, CLUSTER_KIND, str(s["district"]), window_year,
                 round(ratio, 4), "slower" if ratio >= high_ratio else "faster",
                 Json(detail), METHODOLOGY.format(high=high_ratio, low=low_ratio)),
            )
    summary = {"scored_districts": len(scored), "flagged_districts": flagged,
               "request_types": len(metro), "window_year": window_year}
    log.info("d7 run: %s", summary)
    return summary
