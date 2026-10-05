"""Owner-type differential treatment (the D4-variant), CATEGORY-STRATIFIED.

Builds metric_owner_treatment: one row per (property_class, owner_type), so
institutional-vs-individual is read WITHIN a property class instead of across a
confounded mix (institutions hold commercial/multifamily, which generate more
complaints — stratifying removes that dominant confound). The de-confounded
readouts are the indices vs the category's all-owner rate:

  assessment_index = owner-type median appraised $/acre / all-owner median, within
                     (class, zip), parcel-weighted  (<1 = assessed lower)
  code_case_index  = owner-type code-case rate / the category's all-owner rate
                     (~1 => the blended cross-class gap was pure property mix)

Code cases are WINDOWED (opened_date >= window_start, recent by default since we
hold a single 2025 roll) and attributed to the current owner via parcel.geo_id
(~94%, deduped one owner-type per geo_id to avoid fan-out). Reads dim_entity /
parcel_entity / parcel / parcel_value / raw_code_cases read-only; writes only
metric_owner_treatment. Screening signal, not a finding.
"""
from __future__ import annotations

import logging

log = logging.getLogger("atx.ownership.differential")

DEFAULT_WINDOW_START = "2024-01-01"


def build_owner_treatment(conn, roll_year: int = 2025, roll_stage: str = "certified",
                          window_start: str = DEFAULT_WINDOW_START,
                          min_parcels: int = 30, prefix: str = "") -> dict:
    """Rebuild metric_owner_treatment for one window_start. Returns a summary."""
    # parcel count + acreage per (class, owner_type)
    cells = {
        (r["class"], r["owner_type"]): r
        for r in conn.execute(
            f"""
            SELECT p.category AS class, de.kind AS owner_type,
                   count(*) AS parcels, sum(p.acreage) AS acres
            FROM {prefix}parcel_entity pe
            JOIN {prefix}dim_entity de ON de.entity_id = pe.entity_id
            JOIN {prefix}parcel p ON p.account_id = pe.account_id
            JOIN {prefix}parcel_value pv ON pv.account_id = pe.account_id
                  AND pv.roll_year = %(yr)s AND pv.roll_stage = %(st)s
            WHERE pv.appraised_value > 0 AND p.acreage > 0
              AND nullif(p.situs->>'zip', '') IS NOT NULL
            GROUP BY 1, 2
            """, {"yr": roll_year, "st": roll_stage}).fetchall()
    }

    # parcel-weighted assessment index per (class, owner_type)
    assess = {
        (r["class"], r["owner_type"]): float(r["assessment_index"]) if r["assessment_index"] is not None else None
        for r in conn.execute(
            f"""
            WITH parcels AS (
                SELECT p.category AS class, (p.situs->>'zip') AS zip,
                       de.kind AS owner_type, pv.appraised_value / p.acreage AS vpa
                FROM {prefix}parcel_entity pe
                JOIN {prefix}dim_entity de ON de.entity_id = pe.entity_id
                JOIN {prefix}parcel p ON p.account_id = pe.account_id
                JOIN {prefix}parcel_value pv ON pv.account_id = pe.account_id
                      AND pv.roll_year = %(yr)s AND pv.roll_stage = %(st)s
                WHERE pv.appraised_value > 0 AND p.acreage > 0
                  AND nullif(p.situs->>'zip', '') IS NOT NULL
            ),
            ref AS (
                SELECT class, zip, percentile_cont(0.5) WITHIN GROUP (ORDER BY vpa) AS all_med
                FROM parcels GROUP BY class, zip
            ),
            ot AS (
                SELECT class, zip, owner_type, count(*) AS n,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY vpa) AS ot_med
                FROM parcels GROUP BY class, zip, owner_type
            )
            SELECT ot.class, ot.owner_type,
                   sum(ot.n * (ot.ot_med / nullif(ref.all_med, 0))) / nullif(sum(ot.n), 0)
                       AS assessment_index
            FROM ot JOIN ref USING (class, zip)
            GROUP BY ot.class, ot.owner_type
            """, {"yr": roll_year, "st": roll_stage}).fetchall()
    }

    # windowed code cases per (class, owner_type), one owner-type per geo_id (dedup)
    cc = {
        (r["class"], r["owner_type"]): int(r["code_cases"])
        for r in conn.execute(
            f"""
            WITH geo_map AS (
                SELECT DISTINCT ON (p.geo_id) p.geo_id, p.category AS class, de.kind AS owner_type
                FROM {prefix}parcel p
                JOIN {prefix}parcel_entity pe ON pe.account_id = p.account_id
                JOIN {prefix}dim_entity de ON de.entity_id = pe.entity_id
                WHERE p.geo_id IS NOT NULL
                ORDER BY p.geo_id, p.account_id
            )
            SELECT gm.class, gm.owner_type, count(*) AS code_cases
            FROM {prefix}raw_code_cases r
            JOIN geo_map gm ON gm.geo_id = r.payload->>'parcelid'
            WHERE nullif(r.payload->>'opened_date', '') IS NOT NULL
              AND (r.payload->>'opened_date')::timestamp >= %(ws)s::timestamp
            GROUP BY 1, 2
            """, {"ws": window_start}).fetchall()
    }

    # category all-owner baseline rate (per 1k parcels), derived from the cells
    cat_parcels: dict[str, int] = {}
    cat_cases: dict[str, int] = {}
    for (klass, ot), c in cells.items():
        cat_parcels[klass] = cat_parcels.get(klass, 0) + int(c["parcels"])
        cat_cases[klass] = cat_cases.get(klass, 0) + cc.get((klass, ot), 0)

    conn.execute(
        f"DELETE FROM {prefix}metric_owner_treatment WHERE window_start = %s", (window_start,))

    written = 0
    for (klass, ot), c in cells.items():
        parcels = int(c["parcels"])
        if parcels < min_parcels:
            continue
        acres = float(c["acres"]) if c["acres"] else 0.0
        n_cases = cc.get((klass, ot), 0)
        per_1k = 1000.0 * n_cases / parcels
        cat_rate = (1000.0 * cat_cases[klass] / cat_parcels[klass]) if cat_parcels.get(klass) else 0.0
        code_case_index = round(per_1k / cat_rate, 3) if cat_rate else None
        per_1k_acres = round(1000.0 * n_cases / acres, 2) if acres else None
        idx = assess.get((klass, ot))
        conn.execute(
            f"""
            INSERT INTO {prefix}metric_owner_treatment
                (property_class, owner_type, parcels, assessment_index, code_cases,
                 code_cases_per_1k, code_case_index, code_cases_per_1k_acres, window_start)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (property_class, owner_type, window_start) DO UPDATE SET
                parcels=EXCLUDED.parcels, assessment_index=EXCLUDED.assessment_index,
                code_cases=EXCLUDED.code_cases, code_cases_per_1k=EXCLUDED.code_cases_per_1k,
                code_case_index=EXCLUDED.code_case_index,
                code_cases_per_1k_acres=EXCLUDED.code_cases_per_1k_acres
            """,
            (klass, ot, parcels, round(idx, 3) if idx is not None else None, n_cases,
             round(per_1k, 1), code_case_index, per_1k_acres, window_start),
        )
        written += 1

    summary = {"cells": written, "window_start": window_start, "roll_year": roll_year}
    log.info("owner_treatment build: %s", summary)
    return summary


def build_differential(conn, roll_year: int = 2025, roll_stage: str = "certified",
                       window_start: str = DEFAULT_WINDOW_START,
                       min_parcels: int = 30, prefix: str = "") -> dict:
    """CLI entry point — builds the category-stratified owner-treatment table."""
    return build_owner_treatment(conn, roll_year, roll_stage, window_start, min_parcels, prefix)
