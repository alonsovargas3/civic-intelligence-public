import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_anomaly import assessment_cod, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "cod_test"


def _connect(dsn):
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


def _seed(admin):
    admin.execute("CREATE TABLE parcel (account_id text PRIMARY KEY, category text, "
                  "acreage numeric, situs jsonb)")
    admin.execute("CREATE TABLE parcel_value (account_id text, roll_year int, roll_stage text, "
                  "appraised_value numeric, PRIMARY KEY (account_id, roll_year, roll_stage))")

    def add(acct, zip_, klass, appraised):
        admin.execute("INSERT INTO parcel VALUES (%s,%s,1.0,%s)",
                      (acct, klass, Json({"zip": zip_})))
        admin.execute("INSERT INTO parcel_value VALUES (%s,2025,'certified',%s)", (acct, appraised))

    # UNIF: 30 A1 parcels all at 100/acre -> COD 0, not flagged
    for i in range(30):
        add(f"u{i}", "UNIF", "A1", 100)
    # SPREAD: 30 A1 parcels, half 50 half 150 -> median 100, mean abs dev 50, COD 50% -> flagged
    for i in range(15):
        add(f"slo{i}", "SPREAD", "A1", 50)
    for i in range(15):
        add(f"shi{i}", "SPREAD", "A1", 150)
    # THIN: only 10 parcels -> below the min-N=30 guard (the 78701 instability case)
    for i in range(10):
        add(f"t{i}", "THIN", "A1", 100 + i * 50)


def _run():
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)
    admin.close()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = assessment_cod.run_assessment_cod(conn, roll_year=2025, min_parcels=30)
    detail = {r["situs_zip"]: r for r in conn.execute(
        "SELECT * FROM metric_assessment_cod ORDER BY situs_zip").fetchall()}
    flags = conn.execute(
        "SELECT cluster_id, score, review_state, methodology FROM anomaly_flag "
        "WHERE detector=%s ORDER BY cluster_id", (assessment_cod.DETECTOR,)).fetchall()
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    return summary, detail, flags


def test_cod_within_stratum_and_min_n_guard():
    summary, detail, flags = _run()
    # thin stratum (10 parcels) dropped by the min-N guard
    assert set(detail) == {"UNIF", "SPREAD"}
    assert float(detail["UNIF"]["cod"]) == pytest.approx(0.0, abs=0.01)
    assert detail["UNIF"]["high_dispersion"] is False
    assert float(detail["SPREAD"]["cod"]) == pytest.approx(50.0, abs=0.5)
    assert detail["SPREAD"]["high_dispersion"] is True
    # percentile within class: UNIF (cod 0) lowest, SPREAD (cod 50) highest
    assert float(detail["UNIF"]["cod_pctile_in_class"]) == pytest.approx(0.0)
    assert float(detail["SPREAD"]["cod_pctile_in_class"]) == pytest.approx(1.0)


def test_only_high_dispersion_stratum_flagged():
    summary, _detail, flags = _run()
    assert summary["flagged"] == 1
    assert len(flags) == 1
    # flag carries zip + class so multiple classes per zip don't collide on the key
    assert "SPREAD" in flags[0]["cluster_id"]
    assert "A1" in flags[0]["cluster_id"]
    assert flags[0]["review_state"] == "unreviewed"
    # framed as dispersion (the methodology explicitly disclaims "over-assessed")
    assert "dispersion" in flags[0]["methodology"].lower()
    assert "high dispersion" in flags[0]["methodology"].lower()
