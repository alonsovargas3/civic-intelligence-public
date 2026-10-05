import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_anomaly import d4, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "d4_test"


def _connect(dsn):
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


def _seed(admin):
    admin.execute("CREATE TABLE dim_entity (entity_id text PRIMARY KEY, canonical_name text, kind text)")
    admin.execute("CREATE TABLE parcel_entity (account_id text PRIMARY KEY, entity_id text)")
    admin.execute("CREATE TABLE parcel (account_id text PRIMARY KEY, category text, acreage numeric, situs jsonb)")
    admin.execute("CREATE TABLE parcel_value (account_id text, roll_year int, roll_stage text, "
                  "appraised_value numeric, PRIMARY KEY (account_id, roll_year, roll_stage))")
    admin.execute("INSERT INTO dim_entity VALUES "
                  "('IND','Joe Public','individual'),('FAIR','Fair Holdings LLC','institutional'),"
                  "('LOW','Underassessed Trust','institutional')")

    def parc(acct, ent, vpa):
        admin.execute("INSERT INTO parcel_entity VALUES (%s,%s)", (acct, ent))
        admin.execute("INSERT INTO parcel VALUES (%s,'A1',1.0,%s)", (acct, Json({"zip": "78701"})))
        admin.execute("INSERT INTO parcel_value VALUES (%s,2025,'certified',%s)", (acct, vpa))

    # individuals anchor the stratum fundamentals median at 100/acre
    for i in range(20):
        parc(f"i{i}", "IND", 100)
    # institutional entity at parity (divergence 1.0) and one assessed far below (0.4)
    for i in range(5):
        parc(f"f{i}", "FAIR", 100)
    for i in range(5):
        parc(f"u{i}", "LOW", 40)


def _run():
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)
    admin.close()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = d4.run_d4(conn, roll_year=2025, min_parcels=5, low_ratio=0.7, min_value=0)
    detail = {r["entity_id"]: r for r in conn.execute(
        "SELECT * FROM metric_d4_divergence ORDER BY entity_id").fetchall()}
    flags = conn.execute(
        "SELECT cluster_id, direction, score, detector FROM anomaly_flag "
        "WHERE detector=%s ORDER BY cluster_id", (d4.DETECTOR,)).fetchall()
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    return summary, detail, flags


def test_only_institutional_entities_scored():
    _summary, detail, _flags = _run()
    # individuals are excluded; only the two institutional entities are scored
    assert set(detail) == {"FAIR", "LOW"}


def test_divergent_institutional_entity_flagged_below():
    summary, detail, flags = _run()
    assert float(detail["FAIR"]["divergence_ratio"]) == pytest.approx(1.0, abs=0.01)
    assert detail["FAIR"]["flagged"] is False
    assert float(detail["LOW"]["divergence_ratio"]) == pytest.approx(0.4, abs=0.01)
    assert detail["LOW"]["flagged"] is True
    assert summary["flagged"] == 1
    assert len(flags) == 1
    assert flags[0]["cluster_id"] == "LOW"
    assert flags[0]["direction"] == "below"
    assert flags[0]["detector"] == "d4_institutional_divergence"


def test_common_area_parcels_excluded_by_value_floor():
    # an HOA holding 5 real homes (vpa 100) + 5 near-zero common-area lots (appraised 1).
    # Without a floor its divergence collapses toward ~0.5 (false "below" flag); the
    # value floor drops the common-area lots so it tracks fundamentals (~1.0).
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)   # individuals anchor the stratum median at 100
    admin.execute("INSERT INTO dim_entity VALUES ('HOA','Greenbelt HOA Inc','institutional')")
    for i in range(5):
        admin.execute("INSERT INTO parcel_entity VALUES (%s,'HOA')", (f"h{i}",))
        admin.execute("INSERT INTO parcel VALUES (%s,'A1',1.0,%s)", (f"h{i}", Json({"zip": "78701"})))
        admin.execute("INSERT INTO parcel_value VALUES (%s,2025,'certified',100)", (f"h{i}",))
    for i in range(5):  # common-area lots, appraised $1
        admin.execute("INSERT INTO parcel_entity VALUES (%s,'HOA')", (f"hc{i}",))
        admin.execute("INSERT INTO parcel VALUES (%s,'A1',1.0,%s)", (f"hc{i}", Json({"zip": "78701"})))
        admin.execute("INSERT INTO parcel_value VALUES (%s,2025,'certified',1)", (f"hc{i}",))
    admin.execute(db.DDL)
    admin.close()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    d4.run_d4(conn, roll_year=2025, min_parcels=5, low_ratio=0.7, min_value=50)
    hoa = conn.execute("SELECT divergence_ratio, n_parcels, flagged FROM metric_d4_divergence "
                       "WHERE entity_id='HOA'").fetchone()
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    assert hoa["n_parcels"] == 5                       # 5 common-area lots dropped
    assert float(hoa["divergence_ratio"]) == pytest.approx(1.0, abs=0.01)
    assert hoa["flagged"] is False
