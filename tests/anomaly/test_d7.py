import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_anomaly import d7, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "d7_test"


def _connect(dsn):
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


def _seed(admin):
    """Seed raw_austin_311 with closed cases across districts.

    Two request types: 'Pothole' (metro median 2 days) and 'Code' (metro median 30).
    Districts 1-3 + 4 run every type at the metro pace (fair, ratio ~1.0). District 4
    is dominated by the slow 'Code' type (high raw median days) but is still fair.
    District 5 runs 3x slow on both types (ratio ~3.0). District 9 is below the
    min-cases floor.
    """
    admin.execute("CREATE TABLE raw_austin_311 (payload jsonb)")

    # Build closed_date = created + days so resolution-day diffs are exact.
    def add_exact(district, sr_type, days, count):
        for i in range(count):
            admin.execute(
                "INSERT INTO raw_austin_311 (payload) VALUES "
                "(jsonb_build_object("
                "  'sr_location_council_district', %s::text,"
                "  'sr_type_desc', %s::text,"
                "  'sr_created_date', '2024-01-01T00:00:00',"
                "  'sr_closed_date', (TIMESTAMP '2024-01-01 00:00:00' + make_interval(days => %s::int))::text"
                "))",
                (str(district), sr_type, days))

    # Fair districts at metro pace (Pothole=2, Code=30)
    add_exact(1, "Pothole", 2, 40); add_exact(1, "Code", 30, 40)   # obs 16.0, ratio 1.0
    add_exact(2, "Pothole", 2, 60); add_exact(2, "Code", 30, 20)
    add_exact(3, "Pothole", 2, 40); add_exact(3, "Code", 30, 40)
    # Mix-heavy but fair: dominated by slow Code, Pothole below the per-type floor
    add_exact(4, "Pothole", 2, 5); add_exact(4, "Code", 30, 80)    # high raw median, ratio 1.0
    # Genuinely slow on every type -> ratio ~3.0
    add_exact(5, "Pothole", 6, 40); add_exact(5, "Code", 90, 40)   # obs 48.0, ratio 3.0
    # Below the min-cases floor
    add_exact(9, "Pothole", 2, 5)


def _prep_schema():
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)
    admin.close()


def _drop_schema():
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")


def test_metro_and_district_type_pull():
    _prep_schema()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    metro = d7.pull_metro_type_medians(conn)
    dt = d7.pull_district_type_stats(conn, min_type_cases=10)
    conn.close()
    _drop_schema()

    assert metro["Pothole"] == 2.0
    assert metro["Code"] == 30.0
    by = {(r["district"], r["sr_type"]): r for r in dt}
    # district 4's Pothole (5 cases) is below the per-type floor -> excluded
    assert (4, "Pothole") not in by
    assert (4, "Code") in by
    assert by[(1, "Pothole")]["median_days"] == 2.0
    assert by[(5, "Code")]["median_days"] == 90.0
    assert by[(1, "Pothole")]["n_closed"] == 40


def _run():
    _prep_schema()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = d7.run_d7(conn, min_cases=50, min_type_cases=10, high_ratio=1.5)
    detail = {r["council_district"]: r for r in conn.execute(
        "SELECT council_district, observed_days, expected_days, disparity_ratio, flagged "
        "FROM metric_311_equity ORDER BY council_district").fetchall()}
    flags = conn.execute(
        "SELECT cluster_id, score, direction, detector, review_state FROM anomaly_flag "
        "WHERE detector=%s ORDER BY cluster_id", (d7.DETECTOR,)).fetchall()
    conn.close()
    _drop_schema()
    return summary, detail, flags


def test_run_flags_slow_district_only():
    summary, detail, flags = _run()
    # districts 1-5 scored; district 9 dropped below the min-cases floor
    assert set(detail) == {1, 2, 3, 4, 5}
    assert summary["flagged_districts"] == 1
    # the genuinely-slow district flags 'slower'
    assert detail[5]["flagged"] is True
    assert float(detail[5]["disparity_ratio"]) == pytest.approx(3.0, abs=0.01)
    assert len(flags) == 1
    assert flags[0]["cluster_id"] == "5"
    assert flags[0]["direction"] == "slower"
    assert flags[0]["detector"] == "d7_311_equity"
    assert flags[0]["review_state"] == "unreviewed"


def test_mix_heavy_district_not_flagged_despite_high_raw_days():
    _summary, detail, _flags = _run()
    # district 4 is dominated by the slow Code type -> high raw resolution days,
    # higher than a balanced fair district (1)...
    assert float(detail[4]["observed_days"]) > float(detail[1]["observed_days"])
    # ...but mix-adjustment leaves its ratio ~1.0, so it is NOT flagged.
    assert float(detail[4]["disparity_ratio"]) == pytest.approx(1.0, abs=0.01)
    assert detail[4]["flagged"] is False
    assert detail[1]["flagged"] is False


def test_run_does_not_mutate_public_tables():
    admin = _connect(TEST_DSN)
    try:
        admin.execute(db.DDL)
        before_flag = admin.execute(
            "SELECT count(*) AS n FROM public.anomaly_flag").fetchone()["n"]
        before_metric = admin.execute(
            "SELECT count(*) AS n FROM public.metric_311_equity").fetchone()["n"]
    finally:
        admin.close()

    _run()

    after = _connect(TEST_DSN)
    try:
        assert after.execute(
            "SELECT count(*) AS n FROM public.anomaly_flag").fetchone()["n"] == before_flag
        assert after.execute(
            "SELECT count(*) AS n FROM public.metric_311_equity").fetchone()["n"] == before_metric
    finally:
        after.close()
