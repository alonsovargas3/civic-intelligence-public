"""DB-gated tests for parcel_bbox + parcel_for_point (skip unless DASHBOARD_TEST_DSN set)."""
import json
import os

import pytest

DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="Skipped: DASHBOARD_TEST_DSN not set")

# a 200x200 ft square parcel in EPSG:2277 around a point we can hit from WGS84.
# Build it AROUND the transform of a known WGS84 point so the test is CRS-exact.


@pytest.fixture()
def conn():
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as c:
        yield c
        c.execute("DELETE FROM parcel_geo WHERE account_id LIKE 'youtest-%'")
        c.execute("DELETE FROM parcel_bbox WHERE account_id LIKE 'youtest-%'")
        c.execute("DELETE FROM parcel WHERE account_id LIKE 'youtest-%'")


def test_parcel_bbox_build_and_point_lookup(conn):
    from atx_dashboard.aggregate import _build_parcel_bbox
    from atx_dashboard.you import parcel_for_point, to_2277

    # A point in NE Travis County with NO real TCAD parcel coverage (verified), so the
    # synthetic 'youtest-1' square is the UNIQUE polygon containing it — otherwise a real
    # overlapping parcel could win the point-in-polygon race and make this test flaky.
    lat, lon = 30.62, -97.68
    x, y = to_2277(lat, lon)
    square = {"type": "Polygon", "coordinates": [[
        [x - 100, y - 100], [x + 100, y - 100], [x + 100, y + 100], [x - 100, y + 100],
        [x - 100, y - 100]]]}
    conn.execute(
        "INSERT INTO parcel_geo (account_id, geo_id, geom, srid) VALUES (%s,%s,%s,2277) "
        "ON CONFLICT (account_id) DO UPDATE SET geom=EXCLUDED.geom",
        ("youtest-1", "youtest-1", json.dumps(square)))

    _build_parcel_bbox(conn)

    row = conn.execute(
        "SELECT * FROM parcel_bbox WHERE account_id='youtest-1'").fetchone()
    assert row is not None and row["minx"] < x < row["maxx"] and row["miny"] < y < row["maxy"]

    assert parcel_for_point(conn, lat, lon) == "youtest-1"
    # ~60m east (~200ft) is outside the 200ft-wide square (and still parcel-free)
    assert parcel_for_point(conn, lat, lon + 0.0006) != "youtest-1"


def test_nearest_parcel_prefers_matching_street(conn):
    """When no polygon contains the point, snap to the nearest parcel ON THE GEOCODED
    STREET — not a closer sliver on a different street (the ROW-sliver failure mode)."""
    from atx_dashboard.aggregate import _build_parcel_bbox
    from atx_dashboard.you import nearest_parcel, to_2277

    lat, lon = 30.62, -97.68           # parcel-free point (same as above)
    x, y = to_2277(lat, lon)

    def sq(cx):                        # 200ft square centered cx ft east of the point
        return {"type": "Polygon", "coordinates": [[
            [x + cx - 100, y - 100], [x + cx + 100, y - 100],
            [x + cx + 100, y + 100], [x + cx - 100, y + 100], [x + cx - 100, y - 100]]]}

    # 'near' is CLOSER but on the wrong street; 'far' is farther but on the target street.
    for acct, cx, street in [("youtest-near", 150, "SLIVER RD"), ("youtest-far", 250, "MAINOAK DR")]:
        conn.execute(
            "INSERT INTO parcel_geo (account_id, geo_id, geom, srid) VALUES (%s,%s,%s,2277) "
            "ON CONFLICT (account_id) DO UPDATE SET geom=EXCLUDED.geom",
            (acct, acct, json.dumps(sq(cx))))
        conn.execute(
            "INSERT INTO parcel (account_id, situs) VALUES (%s, %s) "
            "ON CONFLICT (account_id) DO UPDATE SET situs=EXCLUDED.situs",
            (acct, json.dumps({"street": street, "zip": "78660"})))
    _build_parcel_bbox(conn)

    # street given -> pick the matching-street parcel even though it's farther
    hit = nearest_parcel(conn, lat, lon, "MAINOAK DR")
    assert hit is not None and hit[0] == "youtest-far"
    # a street that matches nothing nearby -> None (never a confident-wrong snap)
    assert nearest_parcel(conn, lat, lon, "NOWHERE LN") is None
    # no street -> nearest overall (the closer sliver)
    assert nearest_parcel(conn, lat, lon)[0] == "youtest-near"


def _make_t_recent(conn):
    """Create the t_-prefixed target tables from db.DDL (mirrors test_aggregate's approach)."""
    from atx_dashboard import db
    conn.execute(db.DDL.replace("metric_", "t_metric_")
                        .replace("district_boundary", "t_district_boundary")
                        .replace("zip_boundary", "t_zip_boundary")
                        .replace("recent_incidents", "t_recent_incidents"))
    conn.execute("TRUNCATE t_recent_incidents")


def _drop_t_recent(conn):
    conn.execute("DROP TABLE IF EXISTS t_metric_incidents_by_district, "
                 "t_metric_district_breakdown, t_metric_311_response, t_recent_incidents, "
                 "t_district_boundary, t_zip_boundary")


def test_build_recent_extracts_coordinates(conn):
    """When the source is present, 311 rows get lat/lon from the payload; malformed -> NULL."""
    from atx_dashboard import aggregate
    conn.execute("DROP TABLE IF EXISTS t_raw_311_you")
    conn.execute("CREATE TABLE t_raw_311_you (payload jsonb)")
    conn.execute(
        "INSERT INTO t_raw_311_you VALUES "
        "('{\"sr_created_date\": \"2099-01-01T00:00:00\", \"sr_location_council_district\": \"1\", "
        "  \"sr_location_lat\": \"30.30\", \"sr_location_long\": \"-97.70\"}'),"
        "('{\"sr_created_date\": \"2099-01-02T00:00:00\", \"sr_location_council_district\": \"1\", "
        "  \"sr_location_lat\": \"not-a-number\", \"sr_location_long\": \"\"}')")
    _make_t_recent(conn)
    aggregate._build_recent(conn, {"311": "t_raw_311_you"}, "t_")
    rows = conn.execute(
        "SELECT lat, lon FROM t_recent_incidents WHERE dataset='311' ORDER BY ts").fetchall()
    assert len(rows) == 2
    assert rows[0]["lat"] == pytest.approx(30.30) and rows[0]["lon"] == pytest.approx(-97.70)
    assert rows[1]["lat"] is None and rows[1]["lon"] is None
    conn.execute("DROP TABLE t_raw_311_you")
    _drop_t_recent(conn)


def test_build_recent_backfills_offloaded_coordinates(conn):
    """When the source is ABSENT, existing frozen rows get lat/lon backfilled from their
    own payloads (the /v1/you nearby panel must work on offloaded-but-resident data)."""
    from atx_dashboard import aggregate
    _make_t_recent(conn)
    # a resident 311 row with NULL lat/lon but a coordinate-bearing payload
    conn.execute(
        "INSERT INTO t_recent_incidents (dataset, council_district, ts, payload) VALUES "
        "('311', 1, '2099-01-01', "
        " '{\"sr_location_lat\": \"30.31\", \"sr_location_long\": \"-97.71\"}')")
    # source table does NOT exist -> absent branch -> backfill
    aggregate._build_recent(conn, {"311": "t_raw_311_absent"}, "t_")
    row = conn.execute(
        "SELECT lat, lon FROM t_recent_incidents WHERE dataset='311'").fetchone()
    assert row["lat"] == pytest.approx(30.31) and row["lon"] == pytest.approx(-97.71)
    _drop_t_recent(conn)
