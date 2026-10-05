import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_anomaly import d3a, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "anom_test"


def _connect(dsn):
    """psycopg connection with dict rows (the detector + asserts use r[...] keys)."""
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


def _seed(admin):
    """Create minimal parcel/parcel_value in the test schema and seed A1 rows.

    Three ZIPs: 'normal1' and 'normal2' near 100/acre; 'high' extreme at ~1000/acre;
    'thin' has only 2 parcels (below the 50 floor in Task 4, but Task 3 returns all)."""
    admin.execute("CREATE TABLE parcel (account_id text PRIMARY KEY, category text, "
                  "acreage numeric, situs jsonb)")
    admin.execute("CREATE TABLE parcel_value (account_id text, roll_year int, "
                  "roll_stage text, appraised_value numeric, "
                  "PRIMARY KEY (account_id, roll_year, roll_stage))")
    rows = []
    # 60 normal1 parcels at 100/acre (value 100, acre 1)
    for i in range(60):
        rows.append((f"n1-{i}", "78701", 1.0, 100))
    # 60 normal2 parcels at 110/acre
    for i in range(60):
        rows.append((f"n2-{i}", "78702", 1.0, 110))
    # 60 high parcels at 1000/acre (extreme)
    for i in range(60):
        rows.append((f"hi-{i}", "78703", 1.0, 1000))
    # 2 thin parcels (sub-floor)
    for i in range(2):
        rows.append((f"th-{i}", "78704", 1.0, 105))
    for acct, zip_, acre, val in rows:
        admin.execute("INSERT INTO parcel VALUES (%s, 'A1', %s, %s)",
                      (acct, acre, Json({"zip": zip_})))
        admin.execute("INSERT INTO parcel_value VALUES (%s, 2025, 'certified', %s)",
                      (acct, val))


def test_pull_per_zip_aggregates(monkeypatch):
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.close()

    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    rows = d3a.pull_zip_stats(conn, roll_year=2025, klass="A1", min_parcels=50)
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")

    by_zip = {r["zip"]: r for r in rows}
    # thin ZIP (2 parcels) is below the floor -> excluded
    assert "78704" not in by_zip
    assert set(by_zip) == {"78701", "78702", "78703"}
    assert by_zip["78701"]["n_parcels"] == 60
    assert float(by_zip["78701"]["median_per_acre"]) == 100.0
    assert float(by_zip["78703"]["median_per_acre"]) == 1000.0
    assert float(by_zip["78702"]["median_per_acre"]) == 110.0


def _run_in_schema():
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)        # anomaly_flag + metric_assessment_equity in-schema
    admin.close()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = d3a.run_d3a(conn, roll_year=2025, klass="A1", min_parcels=50, z_threshold=3.5)
    detail = {r["zip"]: r for r in conn.execute(
        "SELECT zip, modified_z, flagged, n_parcels FROM metric_assessment_equity "
        "ORDER BY zip").fetchall()}
    flags = conn.execute(
        "SELECT cluster_id, score, direction, detector, review_state FROM anomaly_flag "
        "ORDER BY cluster_id").fetchall()
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    return summary, detail, flags


def test_run_flags_the_extreme_zip():
    summary, detail, flags = _run_in_schema()
    # three ZIPs scored, the extreme one flagged
    assert summary["scored_zips"] == 3
    assert summary["flagged_zips"] == 1
    assert set(detail) == {"78701", "78702", "78703"}
    assert detail["78703"]["flagged"] is True
    assert detail["78701"]["flagged"] is False
    assert detail["78702"]["flagged"] is False
    # one flag row, for the extreme ZIP, over-assessed, unreviewed
    assert len(flags) == 1
    f = flags[0]
    assert f["cluster_id"] == "78703"
    assert f["detector"] == "d3a_assessment_equity"
    assert f["direction"] == "over"
    assert f["review_state"] == "unreviewed"
    assert float(f["score"]) >= 3.5


def test_run_does_not_mutate_public_tables():
    admin = _connect(TEST_DSN)
    try:
        # public anomaly tables may not exist yet; create them so the count is defined
        admin.execute(db.DDL)
        before_flag = admin.execute(
            "SELECT count(*) AS n FROM public.anomaly_flag").fetchone()["n"]
        before_metric = admin.execute(
            "SELECT count(*) AS n FROM public.metric_assessment_equity").fetchone()["n"]
        before_parcel = admin.execute(
            "SELECT count(*) AS n FROM public.parcel").fetchone()["n"]
    finally:
        admin.close()

    _run_in_schema()   # full detector run inside the throwaway schema

    after = _connect(TEST_DSN)
    try:
        assert after.execute(
            "SELECT count(*) AS n FROM public.anomaly_flag").fetchone()["n"] == before_flag
        assert after.execute(
            "SELECT count(*) AS n FROM public.metric_assessment_equity").fetchone()["n"] == before_metric
        assert after.execute(
            "SELECT count(*) AS n FROM public.parcel").fetchone()["n"] == before_parcel
    finally:
        after.close()
