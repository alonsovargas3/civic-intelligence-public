"""Build the descriptive ownership-concentration tables.

Reads the resolved entity layer (dim_entity, parcel_entity) joined to parcel,
parcel_value (a single roll_year/roll_stage) and the parcel_district crosswalk;
writes metric_ownership_concentration (by kind, property category, and council
district) + metric_owner_ranking (top owners). Full rebuild each run.

Shares use a single denominator — all entity-owned parcels / appraised value —
so the district dimension's segments (including an 'unknown' segment for parcels
with no matched geometry) sum to ~1. This is a DESCRIPTIVE layer: it reports who
owns what, not whether that ownership is anomalous.
"""
from __future__ import annotations

import logging

from .concentration import hhi, top_n_share

log = logging.getLogger("atx.ownership.build")

# dimension -> SQL expression for the segment label
_DIMENSIONS = {
    "overall": "'all'",
    "kind": "de.kind",
    "category": "coalesce(nullif(p.category,''), 'UNKNOWN')",
    "district": "coalesce(pd.council_district::text, 'unknown')",
}


def _entity_aggregates(conn, seg_expr, roll_year, roll_stage, prefix):
    """Per (segment, entity) parcel count + total appraised value."""
    return conn.execute(
        f"""
        SELECT {seg_expr} AS segment, pe.entity_id AS entity_id,
               de.kind AS kind, de.canonical_name AS canonical_name,
               count(*) AS n_parcels,
               coalesce(sum(pv.appraised_value), 0) AS total_appraised
        FROM {prefix}parcel_entity pe
        JOIN {prefix}dim_entity de ON de.entity_id = pe.entity_id
        JOIN {prefix}parcel p ON p.account_id = pe.account_id
        LEFT JOIN {prefix}parcel_value pv ON pv.account_id = pe.account_id
              AND pv.roll_year = %(yr)s AND pv.roll_stage = %(st)s
        LEFT JOIN {prefix}parcel_district pd ON pd.account_id = pe.account_id
        GROUP BY 1, 2, 3, 4
        """,
        {"yr": roll_year, "st": roll_stage},
    ).fetchall()


def build_ownership(conn, roll_year: int = 2025, roll_stage: str = "certified",
                    top_n: int = 100, prefix: str = "") -> dict:
    """Rebuild metric_ownership_concentration + metric_owner_ranking. Returns a summary."""
    conn.execute(f"TRUNCATE {prefix}metric_ownership_concentration")
    conn.execute(f"TRUNCATE {prefix}metric_owner_ranking")

    # grand totals come from the 'overall' dimension (one segment, all entities)
    overall_rows = _entity_aggregates(conn, _DIMENSIONS["overall"], roll_year, roll_stage, prefix)
    grand_parcels = sum(int(r["n_parcels"]) for r in overall_rows) or 1
    grand_value = float(sum(float(r["total_appraised"]) for r in overall_rows)) or 1.0

    n_segments = 0
    for dimension, seg_expr in _DIMENSIONS.items():
        rows = overall_rows if dimension == "overall" else \
            _entity_aggregates(conn, seg_expr, roll_year, roll_stage, prefix)
        by_segment: dict[str, list] = {}
        for r in rows:
            by_segment.setdefault(r["segment"], []).append(r)

        for segment, ents in by_segment.items():
            counts = [int(e["n_parcels"]) for e in ents]
            seg_parcels = sum(counts)
            seg_value = float(sum(float(e["total_appraised"]) for e in ents))
            conn.execute(
                f"""
                INSERT INTO {prefix}metric_ownership_concentration
                    (dimension, segment, n_entities, n_parcels, total_appraised,
                     parcel_share, value_share, top10_parcel_share, hhi_parcels)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (dimension, segment, len(ents), seg_parcels, seg_value,
                 round(seg_parcels / grand_parcels, 6), round(seg_value / grand_value, 6),
                 round(top_n_share(counts, 10), 6), round(hhi(counts), 6)),
            )
            n_segments += 1

    # rankings off the overall per-entity aggregates
    by_parcels = sorted(overall_rows,
                        key=lambda r: (int(r["n_parcels"]), float(r["total_appraised"])),
                        reverse=True)[:top_n]
    by_value = sorted(overall_rows,
                      key=lambda r: (float(r["total_appraised"]), int(r["n_parcels"])),
                      reverse=True)[:top_n]
    for scope, ranked in (("by_parcels", by_parcels), ("by_value", by_value)):
        for rank, r in enumerate(ranked, start=1):
            conn.execute(
                f"""
                INSERT INTO {prefix}metric_owner_ranking
                    (scope, rank, entity_id, canonical_name, kind, n_parcels, total_appraised)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (scope, rank, r["entity_id"], r["canonical_name"], r["kind"],
                 int(r["n_parcels"]), float(r["total_appraised"])),
            )

    summary = {"entities": len(overall_rows), "grand_parcels": grand_parcels,
               "grand_appraised": round(grand_value, 2), "segments": n_segments,
               "roll_year": roll_year, "roll_stage": roll_stage}
    log.info("ownership build: %s", summary)
    return summary
