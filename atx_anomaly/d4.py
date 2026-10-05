"""D4 — institutional-cluster divergence from assessment fundamentals.

Cross-sectional (single roll) form of the spec's D4: for each institutional
ENTITY (a resolved dim_entity cluster), compare its parcels' appraised value per
acre to the fundamentals baseline — the all-owner median within the same property
category and situs ZIP. The entity's divergence_ratio is the median, across its
parcels, of (parcel appraised/acre ÷ that parcel's stratum median). ~1.0 = tracks
fundamentals; <1 = assessed below comparable property; >1 = above.

Composes the assessment layer (parcel_value) + ownership segmentation (dim_entity /
parcel_entity). Flags entities whose divergence crosses a ratio threshold (a robust
modified-z is also stored for context but isn't the screen — with clustered ratios
it degenerates). The spec's rent/price-TRAJECTORY divergence needs ≥2 roll years
(blocked on the prior-year backfill, bead qqi); this is the buildable proxy now.

HONESTY: a single-roll screening signal, NOT a finding. It does not control for
genuine location/amenity premia, renovation intensity, or new-build mix; an entity
above or below fundamentals may simply hold atypical (but fairly-assessed) property.
Note the homestead-cap twist: institutional owners get no homestead cap and are
carried at full appraised value, so 'below' (favorable) divergence is the signal
of interest, not 'above'. No sale prices (Texas non-disclosure).

Reads dim_entity / parcel_entity / parcel / parcel_value read-only; writes
metric_d4_divergence + anomaly_flag.
"""
from __future__ import annotations

import logging

from psycopg.types.json import Json

from .stats import mad, median, modified_z, percentile_rank

log = logging.getLogger("atx.anomaly.d4")

DETECTOR = "d4_institutional_divergence"
CLUSTER_KIND = "entity"
METHODOLOGY = (
    "Institutional-cluster divergence (cross-sectional): each institutional owner "
    "entity's median appraised value per acre is compared to the all-owner median "
    "within the same property category and ZIP (the fundamentals baseline). A "
    "divergence ratio <= {low} (assessed below comparable property) or >= {high} "
    "(above) is flagged. SCREENING SIGNAL, not a finding — it does not control for "
    "genuine location premia, renovation, or new-build mix, and uses a single roll "
    "(the trajectory form needs prior-year rolls). No sale prices are used."
)


def pull_entity_divergence(conn, roll_year, roll_stage, kind, min_parcels,
                           min_value=10000, prefix=""):
    """Per institutional entity: median (appraised/acre ÷ stratum all-owner median).

    Parcels appraised below `min_value` are dropped (from both the stratum baseline
    and each entity) — these are HOA/builder common-area lots (greenbelt, drainage)
    miscategorized residential, which otherwise crush an entity's divergence toward
    zero with property that isn't a comparable home.
    """
    return conn.execute(
        f"""
        WITH valued AS (
            SELECT p.account_id, p.category AS cat, (p.situs->>'zip') AS zip,
                   pv.appraised_value / p.acreage AS vpa
            FROM {prefix}parcel p
            JOIN {prefix}parcel_value pv ON pv.account_id = p.account_id
                  AND pv.roll_year = %(yr)s AND pv.roll_stage = %(st)s
            WHERE pv.appraised_value >= %(minval)s AND p.acreage > 0
              AND nullif(p.situs->>'zip', '') IS NOT NULL
        ),
        strat AS (
            SELECT cat, zip, percentile_cont(0.5) WITHIN GROUP (ORDER BY vpa) AS med
            FROM valued GROUP BY cat, zip
        ),
        ent AS (
            SELECT pe.entity_id, de.canonical_name, de.kind,
                   v.vpa / nullif(s.med, 0) AS ratio
            FROM {prefix}parcel_entity pe
            JOIN {prefix}dim_entity de ON de.entity_id = pe.entity_id
            JOIN valued v ON v.account_id = pe.account_id
            JOIN strat s USING (cat, zip)
            WHERE de.kind = %(kind)s
        )
        SELECT entity_id, canonical_name, kind, count(*) AS n_parcels,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY ratio) AS divergence
        FROM ent
        GROUP BY entity_id, canonical_name, kind
        HAVING count(*) >= %(minp)s
        """,
        {"yr": roll_year, "st": roll_stage, "kind": kind, "minp": min_parcels,
         "minval": min_value},
    ).fetchall()


def run_d4(conn, roll_year: int = 2025, roll_stage: str = "certified",
           kind: str = "institutional", min_parcels: int = 20,
           low_ratio: float = 0.7, high_ratio: float | None = None,
           min_value: float = 10000, prefix: str = "") -> dict:
    """Score per-entity divergence from fundamentals; write detail + flags."""
    if high_ratio is None:
        high_ratio = round(1.0 / low_ratio, 4)
    rows = pull_entity_divergence(conn, roll_year, roll_stage, kind, min_parcels,
                                  min_value, prefix)
    ratios = [float(r["divergence"]) for r in rows]
    med = median(ratios) or 0.0
    mad_val = mad(ratios)

    conn.execute(f"DELETE FROM {prefix}metric_d4_divergence WHERE roll_year=%s", (roll_year,))
    conn.execute(f"DELETE FROM {prefix}anomaly_flag WHERE detector=%s AND roll_year=%s",
                 (DETECTOR, roll_year))

    flagged = 0
    for r in rows:
        ratio = float(r["divergence"])
        z = modified_z(ratio, med, mad_val)
        pct = percentile_rank(ratio, ratios)
        is_flag = ratio <= low_ratio or ratio >= high_ratio
        detail = {
            "roll_year": roll_year, "entity_id": r["entity_id"],
            "canonical_name": r["canonical_name"], "kind": r["kind"],
            "n_parcels": int(r["n_parcels"]), "divergence_ratio": round(ratio, 4),
            "modified_z": round(z, 4), "percentile": round(pct, 1), "flagged": is_flag,
        }
        conn.execute(
            f"""INSERT INTO {prefix}metric_d4_divergence
                (roll_year, entity_id, canonical_name, kind, n_parcels,
                 divergence_ratio, modified_z, percentile, flagged)
                VALUES (%(roll_year)s,%(entity_id)s,%(canonical_name)s,%(kind)s,
                        %(n_parcels)s,%(divergence_ratio)s,%(modified_z)s,
                        %(percentile)s,%(flagged)s)
                ON CONFLICT (roll_year, entity_id) DO UPDATE SET
                    canonical_name=EXCLUDED.canonical_name, kind=EXCLUDED.kind,
                    n_parcels=EXCLUDED.n_parcels, divergence_ratio=EXCLUDED.divergence_ratio,
                    modified_z=EXCLUDED.modified_z, percentile=EXCLUDED.percentile,
                    flagged=EXCLUDED.flagged""",
            detail,
        )
        if is_flag:
            flagged += 1
            conn.execute(
                f"""INSERT INTO {prefix}anomaly_flag
                    (detector, cluster_kind, cluster_id, roll_year, score, direction,
                     evidence, methodology)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (detector, cluster_kind, cluster_id, roll_year) DO UPDATE SET
                        score=EXCLUDED.score, direction=EXCLUDED.direction,
                        evidence=EXCLUDED.evidence, methodology=EXCLUDED.methodology,
                        review_state='unreviewed'""",
                (DETECTOR, CLUSTER_KIND, r["entity_id"], roll_year, round(ratio, 4),
                 "below" if ratio <= low_ratio else "above", Json(detail),
                 METHODOLOGY.format(low=low_ratio, high=high_ratio)),
            )
    summary = {"scored_entities": len(rows), "flagged": flagged,
               "kind": kind, "roll_year": roll_year}
    log.info("d4 run: %s", summary)
    return summary
