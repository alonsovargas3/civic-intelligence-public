import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.types.json import Json  # noqa: E402

from atx_dashboard import aggregate, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")


@pytest.fixture()
def conn():
    c = psycopg.connect(TEST_DSN, autocommit=True)
    c.execute("CREATE TABLE IF NOT EXISTS t_raw_crime (payload jsonb)")
    c.execute("CREATE TABLE IF NOT EXISTS t_raw_311 (payload jsonb)")
    c.execute("TRUNCATE t_raw_crime, t_raw_311")
    c.execute(db.DDL.replace("metric_", "t_metric_")
                    .replace("district_boundary", "t_district_boundary")
                    .replace("recent_incidents", "t_recent_incidents"))
    c.execute("TRUNCATE t_metric_incidents_by_district, t_metric_district_breakdown, "
              "t_metric_311_response, t_recent_incidents")
    yield c
    for t in ("t_raw_crime", "t_raw_311", "t_metric_incidents_by_district",
              "t_metric_district_breakdown", "t_metric_311_response",
              "t_recent_incidents", "t_district_boundary"):
        c.execute(f"DROP TABLE IF EXISTS {t}")
    c.close()


def _crime(cd, occ, cat):
    return {"council_district": cd, "occ_date": occ, "category_description": cat,
            "ucr_category": cat, "clearance_status": "N"}


def _sr(cd, created, closed, typ, status):
    return {"sr_location_council_district": cd, "sr_created_date": created,
            "sr_closed_date": closed, "sr_type_desc": typ, "sr_status_desc": status}


def test_incidents_by_district_counts_and_excludes_unknown(conn):
    rows = [_crime("9", "2025-04-03T00:00:00.000", "THEFT"),
            _crime("9", "2025-04-20T00:00:00.000", "THEFT"),
            _crime("9", "2025-05-01T00:00:00.000", "ASSAULT"),
            _crime("3", "2025-04-09T00:00:00.000", "THEFT"),
            _crime("0", "2025-04-09T00:00:00.000", "THEFT")]   # district 0 -> unknown, excluded
    for r in rows:
        conn.execute("INSERT INTO t_raw_crime (payload) VALUES (%s)", (Json(r),))

    res = aggregate.run(conn, tables={"crime": "t_raw_crime", "311": "t_raw_311"}, prefix="t_")

    got = conn.execute(
        "SELECT council_district, period_month, incident_count FROM t_metric_incidents_by_district "
        "WHERE dataset='crime' ORDER BY council_district, period_month"
    ).fetchall()
    assert (3, 1) == (got[0][0], got[0][2])
    assert (9, 2) in [(g[0], g[2]) for g in got]
    assert (9, 1) in [(g[0], g[2]) for g in got]
    assert res["crime_district_unknown"] == 1


def test_311_response_time_median(conn):
    conn.execute("INSERT INTO t_raw_311 (payload) VALUES (%s)",
                 (Json(_sr("5", "2025-04-01T00:00:00.000", "2025-04-03T00:00:00.000", "Pothole", "Closed")),))
    conn.execute("INSERT INTO t_raw_311 (payload) VALUES (%s)",
                 (Json(_sr("5", "2025-04-01T00:00:00.000", "2025-04-05T00:00:00.000", "Pothole", "Closed")),))
    conn.execute("INSERT INTO t_raw_311 (payload) VALUES (%s)",
                 (Json(_sr("5", "2025-04-10T00:00:00.000", None, "Pothole", "Open")),))

    aggregate.run(conn, tables={"crime": "t_raw_crime", "311": "t_raw_311"}, prefix="t_")

    row = conn.execute(
        "SELECT median_days, closed_count, open_count FROM t_metric_311_response "
        "WHERE council_district=5 AND period='2025'"
    ).fetchone()
    assert float(row[0]) == 3.0
    assert row[1] == 2 and row[2] == 1


def _drop_any(c, name: str) -> None:
    """Drop a relation regardless of whether it's a plain table or materialized view."""
    row = c.execute(
        "SELECT relkind FROM pg_class WHERE oid = to_regclass(%s)", (name,)
    ).fetchone()
    if row is None:
        return
    kind = row["relkind"] if isinstance(row, dict) else row[0]
    if kind == "m":
        c.execute(f"DROP MATERIALIZED VIEW IF EXISTS {name}")
    else:
        c.execute(f"DROP TABLE IF EXISTS {name}")


def test_ensure_matview_heals_plain_table():
    """_ensure_matview must replace a plain table with a matview (the converted-mv case)."""
    c = psycopg.connect(TEST_DSN, autocommit=True)
    try:
        # Setup: create the relation as a plain table (mimics the converted-mv state)
        _drop_any(c, "t_story_heal")
        c.execute("CREATE TABLE t_story_heal (x int)")
        c.execute("INSERT INTO t_story_heal VALUES (42)")

        # RED before fix: the old CREATE MATVIEW IF NOT EXISTS silently no-ops, then
        # REFRESH errors "is not a materialized view".  After fix: heals to relkind='m'.
        aggregate._ensure_matview(c, "t_story_heal", "SELECT 1 AS x")

        row = c.execute(
            "SELECT relkind FROM pg_class WHERE oid = to_regclass('t_story_heal')"
        ).fetchone()
        assert row is not None
        relkind = row["relkind"] if isinstance(row, dict) else row[0]
        assert relkind == "m", f"expected relkind='m' (matview), got {relkind!r}"

        cnt = c.execute("SELECT count(*) FROM t_story_heal").fetchone()
        n = cnt["count"] if isinstance(cnt, dict) else cnt[0]
        assert isinstance(n, int)
    finally:
        _drop_any(c, "t_story_heal")
        c.close()


def test_absent_source_keeps_prior_rows_while_present_source_rebuilds(conn):
    """CLAUDE.md's tiering contract: derived tables for a NAS-offloaded source must
    survive a refresh untouched, while a dataset whose source *is* present still
    rebuilds normally. Regression test for the truncate-then-skip bug: run() used to
    TRUNCATE metric_incidents_by_district/metric_district_breakdown/metric_311_response
    and _build_recent used to TRUNCATE recent_incidents up front, then skip the rebuild
    per-source -- wiping rows for datasets it had no way to reconstruct."""
    # Seed marker rows for 'crime' -- the source we'll point at a table that doesn't exist.
    conn.execute(
        "INSERT INTO t_metric_incidents_by_district "
        "(dataset, council_district, period_month, incident_count) "
        "VALUES ('crime', 7, '2020-01-01', 999)")
    conn.execute(
        "INSERT INTO t_metric_district_breakdown "
        "(dataset, council_district, period, dimension, label, value) "
        "VALUES ('crime', 7, '2020', 'category', 'MARKER', 999)")
    conn.execute(
        "INSERT INTO t_recent_incidents (dataset, council_district, ts, payload) "
        "VALUES ('crime', 7, now(), %s)", (Json({"marker": True}),))

    # Seed real 311 data so we can also assert the present source still rebuilds.
    conn.execute("INSERT INTO t_raw_311 (payload) VALUES (%s)",
                 (Json(_sr("5", "2025-04-01T00:00:00.000", "2025-04-03T00:00:00.000",
                            "Pothole", "Closed")),))

    res = aggregate.run(
        conn, tables={"crime": "t_raw_crime_absent", "311": "t_raw_311"}, prefix="t_")

    assert res["crime_district_unknown"] is None  # crime block was skipped

    # Marker rows for the absent source survive untouched.
    crime_by_district = conn.execute(
        "SELECT council_district, incident_count FROM t_metric_incidents_by_district "
        "WHERE dataset='crime'").fetchall()
    assert [(r[0], r[1]) for r in crime_by_district] == [(7, 999)]

    crime_breakdown = conn.execute(
        "SELECT label, value FROM t_metric_district_breakdown WHERE dataset='crime'"
    ).fetchall()
    assert [(r[0], r[1]) for r in crime_breakdown] == [("MARKER", 999)]

    crime_recent = conn.execute(
        "SELECT council_district FROM t_recent_incidents WHERE dataset='crime'"
    ).fetchall()
    assert [r[0] for r in crime_recent] == [7]

    # The present source (311) still rebuilds from scratch.
    sr_by_district = conn.execute(
        "SELECT council_district, incident_count FROM t_metric_incidents_by_district "
        "WHERE dataset='311'").fetchall()
    assert [(r[0], r[1]) for r in sr_by_district] == [(5, 1)]

    sr_response = conn.execute(
        "SELECT median_days, closed_count FROM t_metric_311_response "
        "WHERE council_district=5 AND period='2025'").fetchone()
    assert float(sr_response[0]) == 2.0 and sr_response[1] == 1


def test_recent_incidents_keeps_only_window_and_maps_district(conn):
    recent = "2099-01-01T00:00:00.000"   # far future -> always inside the 90d window
    old = "2000-01-01T00:00:00.000"      # far past -> outside the window
    for r in [_crime("9", recent, "THEFT"),     # in window, D9
              _crime("3", recent, "THEFT"),      # in window, D3
              _crime("0", recent, "THEFT"),      # in window, invalid district -> NULL cd
              _crime("9", old, "THEFT")]:         # out of window -> excluded
        conn.execute("INSERT INTO t_raw_crime (payload) VALUES (%s)", (Json(r),))

    aggregate.run(conn, tables={"crime": "t_raw_crime", "311": "t_raw_311"}, prefix="t_")

    rows = conn.execute(
        "SELECT council_district FROM t_recent_incidents WHERE dataset='crime' "
        "ORDER BY council_district NULLS LAST").fetchall()
    assert len(rows) == 3                                  # the old row is excluded
    assert [r[0] for r in rows] == [3, 9, None]            # invalid district -> NULL
