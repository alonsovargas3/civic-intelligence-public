"""Aggregate raw_* incident rows into the metric_* summary tables.

Full rebuild per run (delete-per-dataset + re-insert); volumes make a single pass
acceptable. Each dataset's clear is gated on its own source raw_* table existing, so
a source that's offloaded to NAS (see CLAUDE.md "Data tiering") never gets its prior
rows wiped by a routine refresh it has no way to rebuild from.
Only crime + 311 carry council_district, so only they feed the district metrics.
The `tables`/`prefix` params let tests point the same SQL at throwaway t_* tables.
"""
from __future__ import annotations

import logging

from psycopg.types.json import Json

log = logging.getLogger("atx.dashboard.aggregate")

DEFAULT_TABLES = {"crime": "raw_crime_reports", "311": "raw_austin_311",
                  "crashes": "raw_traffic_crashes", "code": "raw_code_cases"}

RECENT_WINDOW_DAYS = 90

# dataset -> (date_key in payload, council_district key or None). crashes/code carry
# no district. code's date column is `opened_date` (confirmed from a sample row:
# the row also has closed_date/last_update/date_updated; opened_date is case open).
RECENT_META = {
    "crime":   ("occ_date",        "council_district"),
    "311":     ("sr_created_date",  "sr_location_council_district"),
    "crashes": ("crash_timestamp",  None),
    "code":    ("opened_date",      None),
}

# dataset -> (lat_key, lon_key) in the source payload; crime publishes no coordinates.
RECENT_GEO = {"311": ("sr_location_lat", "sr_location_long"),
              "code": ("latitude", "longitude"),
              "crashes": ("latitude", "longitude"),
              "crime": (None, None)}


def _num_or_null(key, col="p"):
    """SQL fragment: payload key as float8, NULL when absent/malformed."""
    if key is None:
        return "NULL::float8"
    return (f"CASE WHEN ({col}->>'{key}') ~ '^-?[0-9]+(\\.[0-9]+)?$' "
            f"THEN ({col}->>'{key}')::float8 END")


# valid district = numeric text in 1..10 (mirrors metrics.district_or_none in SQL)
_VALID_CD = "(p->>'{k}') ~ '^[0-9]+$' AND (p->>'{k}')::int BETWEEN 1 AND 10"


def _by_district_sql(dataset: str, src: str, cd_key: str, date_key: str, prefix: str) -> str:
    cond = _VALID_CD.format(k=cd_key)
    return f"""
    INSERT INTO {prefix}metric_incidents_by_district
        (dataset, council_district, period_month, incident_count)
    SELECT '{dataset}', (p->>'{cd_key}')::smallint,
           date_trunc('month', (p->>'{date_key}')::timestamp)::date, count(*)
    FROM (SELECT payload AS p FROM {src}) s
    WHERE {cond} AND nullif(p->>'{date_key}','') IS NOT NULL
    GROUP BY 1, 2, 3
    """


def _unknown_count(conn, src: str, cd_key: str) -> int:
    cond = _VALID_CD.format(k=cd_key)
    row = conn.execute(
        f"SELECT count(*) AS n FROM (SELECT payload AS p FROM {src}) s WHERE NOT ({cond})"
    ).fetchone()
    return row["n"] if isinstance(row, dict) else row[0]


def _build_recent(conn, tables: dict, prefix: str) -> None:
    """Rebuild {prefix}recent_incidents with the last RECENT_WINDOW_DAYS of each
    source present in `tables`. Sources whose table is absent are skipped so a
    partial DB (or the t_* test path, which only seeds crime/311) self-heals —
    and, critically, their *existing* rows for that dataset are left alone (the
    NAS-offloaded bulk sources can't be rebuilt here, so a routine refresh must not
    wipe the last-good rows; see CLAUDE.md "Data tiering"). Deletion happens per
    dataset, immediately before that dataset's own insert, never up front."""
    # lat/lon power the /v1/you "nearby" panel. Ensure the columns exist (self-heal
    # for DBs created before they were added) before either the insert or backfill path.
    conn.execute(f"ALTER TABLE {prefix}recent_incidents "
                 f"ADD COLUMN IF NOT EXISTS lat float8, ADD COLUMN IF NOT EXISTS lon float8")
    for dataset, (date_key, cd_key) in RECENT_META.items():
        src = tables.get(dataset)
        lat_key, lon_key = RECENT_GEO.get(dataset, (None, None))
        if src is None:
            continue
        reg = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS ok", (src,)).fetchone()
        if not (reg["ok"] if isinstance(reg, dict) else reg[0]):
            log.info("%s absent, keeping existing %srecent_incidents rows (dataset=%s)",
                      src, prefix, dataset)
            # The offloaded bulk incident rows stay resident (frozen) but carry their
            # coordinates in `payload`; backfill lat/lon from there so `nearby` works
            # without a raw restore. Idempotent (WHERE lat IS NULL); no-op once filled.
            if lat_key is not None:
                conn.execute(
                    f"UPDATE {prefix}recent_incidents "
                    f"SET lat = {_num_or_null(lat_key, 'payload')}, "
                    f"    lon = {_num_or_null(lon_key, 'payload')} "
                    f"WHERE dataset = %s AND lat IS NULL", (dataset,))
            continue
        conn.execute(f"DELETE FROM {prefix}recent_incidents WHERE dataset = %s", (dataset,))
        cd_expr = (
            f"CASE WHEN (p->>'{cd_key}') ~ '^[0-9]+$' "
            f"AND (p->>'{cd_key}')::int BETWEEN 1 AND 10 "
            f"THEN (p->>'{cd_key}')::smallint END"
            if cd_key else "NULL::smallint"
        )
        conn.execute(f"""
        INSERT INTO {prefix}recent_incidents (dataset, council_district, ts, lat, lon, payload)
        SELECT '{dataset}', {cd_expr}, (p->>'{date_key}')::timestamp,
               {_num_or_null(lat_key)}, {_num_or_null(lon_key)}, p
        FROM (SELECT payload AS p FROM {src}) s
        WHERE nullif(p->>'{date_key}','') IS NOT NULL
          AND (p->>'{date_key}')::timestamp >= now() - interval '{RECENT_WINDOW_DAYS} days'
        """)


def _build_str_gap(conn) -> None:
    """Precompute the STR-gap story payload (point-in-polygon runs in Python, so this
    can't be a SQL matview). Skips cleanly when the Airbnb snapshot isn't loaded."""
    from .str_gap import compute_gap
    reg = conn.execute("SELECT to_regclass('raw_airbnb_listings') IS NOT NULL AS ok").fetchone()
    if not (reg["ok"] if isinstance(reg, dict) else reg[0]):
        log.info("str-gap: raw_airbnb_listings absent, skipping mv_str_gap")
        return
    payload = compute_gap(conn)
    conn.execute("DROP TABLE IF EXISTS mv_str_gap")
    conn.execute("CREATE TABLE mv_str_gap "
                 "(payload jsonb NOT NULL, built_at timestamptz NOT NULL DEFAULT now())")
    conn.execute("INSERT INTO mv_str_gap (payload) VALUES (%s)", (Json(payload),))
    log.info("built mv_str_gap (snapshot %s)", payload["snapshot_date"])


def _build_parcel_bbox(conn) -> None:
    """Bounding-box prefilter table for point->parcel lookup (/v1/you). Rebuilt
    unconditionally — a ~374k-row pass over parcel_geo is cheap, and bbox data only
    changes on a TCAD reload anyway. Skips when parcel_geo is absent."""
    from atx_ownership.geom import bbox
    reg = conn.execute("SELECT to_regclass('parcel_geo') IS NOT NULL AS ok").fetchone()
    if not (reg["ok"] if isinstance(reg, dict) else reg[0]):
        log.info("parcel_bbox: parcel_geo absent, skipping")
        return
    conn.execute(
        "CREATE TABLE IF NOT EXISTS parcel_bbox ("
        " account_id text PRIMARY KEY,"
        " minx float8 NOT NULL, miny float8 NOT NULL,"
        " maxx float8 NOT NULL, maxy float8 NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS parcel_bbox_x ON parcel_bbox (minx, maxx)")
    conn.execute("TRUNCATE parcel_bbox")
    n = 0
    with conn.cursor() as read_cur, conn.cursor() as write_cur:
        read_cur.execute("SELECT account_id, geom FROM parcel_geo WHERE geom IS NOT NULL")
        batch = []
        for row in read_cur:
            geom = row["geom"] if isinstance(row, dict) else row[1]
            acct = row["account_id"] if isinstance(row, dict) else row[0]
            try:
                minx, miny, maxx, maxy = bbox(geom)
            except (ValueError, IndexError, TypeError):
                continue                      # degenerate geometry
            batch.append((acct, minx, miny, maxx, maxy))
            if len(batch) >= 5000:
                write_cur.executemany(
                    "INSERT INTO parcel_bbox VALUES (%s,%s,%s,%s,%s) "
                    "ON CONFLICT (account_id) DO NOTHING", batch)
                n += len(batch)
                batch = []
        if batch:
            write_cur.executemany(
                "INSERT INTO parcel_bbox VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (account_id) DO NOTHING", batch)
            n += len(batch)
    log.info("built parcel_bbox (%d parcels)", n)


def _table_exists(conn, name: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS ok", (name,)).fetchone()
    return row["ok"] if isinstance(row, dict) else row[0]


def run(conn, tables: dict | None = None, prefix: str = "") -> dict:
    """Rebuild metric_* from raw_*. Returns a summary incl. district-unknown tallies.

    crime/311 blocks are skipped (self-heal, logged) when their raw table is absent —
    the four bulk incident sources are offloaded to NAS in the tiered environment (see
    CLAUDE.md "Data tiering"); this keeps `cli refresh` runnable so the still-resident
    aggregates (story views, mv_str_gap, recent_incidents from whatever raw_* remain)
    still get rebuilt instead of the whole run() aborting on the first missing table.

    Never destroy what we can't rebuild: each metric block's clear (DELETE for the
    multi-dataset tables, TRUNCATE for the single-dataset one) happens immediately
    before that dataset's own insert, gated on its own source-table existence — never
    up front. When a source is absent, the prior rows for that dataset are left as-is
    so a routine refresh doesn't wipe last-good values it has no way to rebuild.
    """
    t = tables or DEFAULT_TABLES
    crime, sr = t["crime"], t["311"]
    crime_ok, sr_ok = _table_exists(conn, crime), _table_exists(conn, sr)
    if not crime_ok:
        log.info("aggregate: %s absent, skipping crime district metrics", crime)
    if not sr_ok:
        log.info("aggregate: %s absent, skipping 311 district metrics", sr)

    if crime_ok:
        conn.execute(f"DELETE FROM {prefix}metric_incidents_by_district WHERE dataset='crime'")
        conn.execute(_by_district_sql("crime", crime, "council_district", "occ_date", prefix))
    else:
        log.info("%s absent, keeping existing %smetric_incidents_by_district rows (dataset=crime)",
                  crime, prefix)

    if sr_ok:
        conn.execute(f"DELETE FROM {prefix}metric_incidents_by_district WHERE dataset='311'")
        conn.execute(_by_district_sql("311", sr, "sr_location_council_district", "sr_created_date", prefix))
    else:
        log.info("%s absent, keeping existing %smetric_incidents_by_district rows (dataset=311)",
                  sr, prefix)

    if crime_ok:
        conn.execute(f"DELETE FROM {prefix}metric_district_breakdown WHERE dataset='crime'")
        conn.execute(f"""
        INSERT INTO {prefix}metric_district_breakdown
            (dataset, council_district, period, dimension, label, value)
        SELECT 'crime', (p->>'council_district')::smallint,
               to_char((p->>'occ_date')::timestamp, 'YYYY'), 'category',
               coalesce(nullif(p->>'category_description',''), 'UNKNOWN'), count(*)
        FROM (SELECT payload AS p FROM {crime}) s
        WHERE {_VALID_CD.format(k='council_district')} AND nullif(p->>'occ_date','') IS NOT NULL
        GROUP BY 1, 2, 3, 4, 5
        """)
    else:
        log.info("%s absent, keeping existing %smetric_district_breakdown rows (dataset=crime)",
                  crime, prefix)

    if sr_ok:
        conn.execute(f"DELETE FROM {prefix}metric_district_breakdown WHERE dataset='311'")
        conn.execute(f"""
        INSERT INTO {prefix}metric_district_breakdown
            (dataset, council_district, period, dimension, label, value)
        SELECT '311', (p->>'sr_location_council_district')::smallint,
               to_char((p->>'sr_created_date')::timestamp, 'YYYY'), 'sr_type',
               coalesce(nullif(p->>'sr_type_desc',''), 'UNKNOWN'), count(*)
        FROM (SELECT payload AS p FROM {sr}) s
        WHERE {_VALID_CD.format(k='sr_location_council_district')} AND nullif(p->>'sr_created_date','') IS NOT NULL
        GROUP BY 1, 2, 3, 4, 5
        """)
    else:
        log.info("%s absent, keeping existing %smetric_district_breakdown rows (dataset=311)",
                  sr, prefix)

    if sr_ok:
        # metric_311_response has no `dataset` column and is fed solely by 311, so its
        # clear is a plain TRUNCATE — just moved inside the sr_ok guard.
        conn.execute(f"TRUNCATE {prefix}metric_311_response")
        conn.execute(f"""
        INSERT INTO {prefix}metric_311_response
            (council_district, period, median_days, closed_count, open_count)
        SELECT (p->>'sr_location_council_district')::smallint,
               to_char((p->>'sr_created_date')::timestamp, 'YYYY'),
               percentile_cont(0.5) WITHIN GROUP (
                   ORDER BY EXTRACT(epoch FROM ((p->>'sr_closed_date')::timestamp
                                                - (p->>'sr_created_date')::timestamp)) / 86400.0)
                   FILTER (WHERE nullif(p->>'sr_closed_date','') IS NOT NULL),
               count(*) FILTER (WHERE nullif(p->>'sr_closed_date','') IS NOT NULL),
               count(*) FILTER (WHERE nullif(p->>'sr_closed_date','') IS NULL)
        FROM (SELECT payload AS p FROM {sr}) s
        WHERE {_VALID_CD.format(k='sr_location_council_district')} AND nullif(p->>'sr_created_date','') IS NOT NULL
        GROUP BY 1, 2
        """)
    else:
        log.info("%s absent, keeping existing %smetric_311_response rows", sr, prefix)

    _build_recent(conn, t, prefix)

    # Story materialized views (pre-aggregated reads for the narrative pages, whose
    # source tables are far too large to scan per request). Only for the real tables
    # (tests use a t_* prefix and have none of these source tables).
    if not prefix:
        _refresh_story_views(conn)
        _build_str_gap(conn)
        _build_parcel_bbox(conn)

    summary = {
        "crime_district_unknown": _unknown_count(conn, crime, "council_district") if crime_ok else None,
        "sr_district_unknown": _unknown_count(conn, sr, "sr_location_council_district") if sr_ok else None,
    }
    log.info("aggregate rebuild: %s", summary)
    return summary


# Story materialized views: (source table, name) -> defining SELECT. Created empty
# if missing (so a fresh DB self-heals on the first `cli refresh`) then refreshed.
# Keyed by source table so a partial dev DB only builds what it can.
_STORY_MVS = {
    "raw_afo_checkbook": {
        "mv_afo_dept":
            "SELECT payload->>'dept_nm' AS dept, sum((payload->>'amount')::numeric) AS amount "
            "FROM raw_afo_checkbook GROUP BY 1",
        "mv_afo_year":
            "SELECT payload->>'cal_year' AS cal_year, sum((payload->>'amount')::numeric) AS amount "
            "FROM raw_afo_checkbook GROUP BY 1",
        "mv_afo_vendor_ops":
            "SELECT payload->>'lgl_nm' AS vendor, sum((payload->>'amount')::numeric) AS amount "
            "FROM raw_afo_checkbook WHERE payload->>'dept_nm' NOT ILIKE '%debt service%' GROUP BY 1",
    },
    # Flat projection of the ~400k-row campaign-contributions JSONB table — the
    # money-in-politics story endpoints (ballot-money, local-money, who-pays,
    # money-influence) classify candidate/committee, parse donor location and rank
    # by gift size; doing that over JSONB live was ~2-5s, over this flat view it's
    # sub-second.
    "raw_campaign_contributions": {
        "mv_campaign_contributions":
            "SELECT payload->>'recipient' AS recipient, payload->>'donor' AS donor, "
            "  lower(payload->>'donor_type') AS donor_type, "
            "  (payload->>'contribution_amount')::numeric AS amount, "
            "  payload->>'contribution_date' AS contribution_date, "
            "  payload->>'city_state_zip' AS city_state_zip, "
            # precompute the costly classifications so the story endpoints filter on
            # booleans/columns instead of running regexes over ~400k rows per request.
            "  ((payload->>'recipient') ~ '^[A-Z][a-zA-Z.''-]+,\\s') AS is_candidate, "
            "  (payload->>'recipient' NOT ILIKE '%abbott%') AS is_municipal, "
            "  CASE WHEN payload->>'city_state_zip' ~* '\\mTX\\M' THEN 'texas' "
            "       WHEN payload->>'city_state_zip' ~ '\\m[A-Z]{2}\\M' THEN 'out_of_state' "
            "       ELSE 'unknown' END AS loc "
            "FROM raw_campaign_contributions",
    },
    # New-home building permits. The permit feed has one row per TRADE permit
    # (electrical/plumbing/mechanical) as well as the building permit, so this
    # restricts to building permits (BP) for NEW residential work — the general
    # contractor's permit — to avoid conflating builders with their subcontractors.
    "raw_construction_permits": {
        "mv_home_permit_builder":
            "SELECT payload->>'contractor_company_name' AS builder, count(*)::int AS permits "
            "FROM raw_construction_permits "
            "WHERE payload->>'permittype'='BP' AND payload->>'work_class'='New' "
            "  AND payload->>'permit_class_mapped'='Residential' "
            "  AND payload->>'contractor_company_name' <> '' GROUP BY 1",
        "mv_home_permit_year":
            "SELECT payload->>'calendar_year_issued' AS yr, count(*)::int AS permits "
            "FROM raw_construction_permits "
            "WHERE payload->>'permittype'='BP' AND payload->>'work_class'='New' "
            "  AND payload->>'permit_class_mapped'='Residential' "
            "  AND payload->>'calendar_year_issued' ~ '^20(0[5-9]|1[0-9]|2[0-6])$' GROUP BY 1",
    },
    # Vision Zero / CRIS serves ~2 rows per real crash (duplicate :id, same
    # cris_crash_id), so this DEDUPES by cris_crash_id before aggregating by year.
    "raw_traffic_crashes": {
        "mv_crash_yearly":
            "WITH one AS ("
            "  SELECT DISTINCT ON (payload->>'cris_crash_id') "
            "    left(payload->>'crash_timestamp',4) AS yr, "
            "    (payload->>'death_cnt')::numeric AS deaths, "
            "    (payload->>'sus_serious_injry_cnt')::numeric AS serious, "
            "    (payload->>'pedestrian_death_count')::numeric AS ped_deaths, "
            "    (payload->>'motorcycle_death_count')::numeric AS moto_deaths, "
            "    (payload->>'bicycle_death_count')::numeric AS bike_deaths "
            "  FROM raw_traffic_crashes "
            "  WHERE payload->>'cris_crash_id' IS NOT NULL "
            "    AND payload->>'crash_timestamp' ~ '^20(1[0-9]|2[0-6])' "
            "  ORDER BY payload->>'cris_crash_id') "
            "SELECT yr, count(*)::int AS crashes, count(*) FILTER (WHERE deaths>0)::int AS fatal_crashes, "
            "       sum(deaths)::int AS deaths, sum(serious)::int AS serious_inj, "
            "       sum(ped_deaths)::int AS ped_deaths, sum(moto_deaths)::int AS moto_deaths, "
            "       sum(bike_deaths)::int AS bike_deaths "
            "FROM one GROUP BY yr",
    },
}


def _ensure_matview(conn, name: str, select: str) -> None:
    row = conn.execute(
        "SELECT relkind FROM pg_class WHERE oid = to_regclass(%s)", (name,)
    ).fetchone()
    if row is not None:
        relkind = row["relkind"] if isinstance(row, dict) else row[0]
        if relkind == "r":
            log.info("%s is a plain table, dropping to rebuild as matview", name)
            conn.execute(f"DROP TABLE {name}")
    conn.execute(f"CREATE MATERIALIZED VIEW IF NOT EXISTS {name} AS {select} WITH NO DATA")
    conn.execute(f"REFRESH MATERIALIZED VIEW {name}")


def _refresh_story_views(conn) -> None:
    for src, views in _STORY_MVS.items():
        exists = conn.execute(
            "SELECT to_regclass(%s) IS NOT NULL AS ok", (f"public.{src}",)).fetchone()
        if not (exists["ok"] if isinstance(exists, dict) else exists[0]):
            log.info("story views: %s absent, skipping %s", src, ", ".join(views))
            continue
        for name, select in views.items():
            _ensure_matview(conn, name, select)
        log.info("story views refreshed: %s", ", ".join(views))
