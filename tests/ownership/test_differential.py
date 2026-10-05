import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_ownership import db, differential  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "own_diff_test"


def _connect(dsn):
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


def _seed(admin):
    admin.execute("CREATE TABLE dim_entity (entity_id text PRIMARY KEY, kind text)")
    admin.execute("CREATE TABLE parcel_entity (account_id text PRIMARY KEY, entity_id text)")
    admin.execute("CREATE TABLE parcel (account_id text PRIMARY KEY, geo_id text, "
                  "category text, acreage numeric, situs jsonb)")
    admin.execute("CREATE TABLE parcel_value (account_id text, roll_year int, roll_stage text, "
                  "appraised_value numeric, PRIMARY KEY (account_id, roll_year, roll_stage))")
    admin.execute("CREATE TABLE raw_code_cases (payload jsonb)")
    admin.execute("INSERT INTO dim_entity VALUES ('IND','individual'),('INST','institutional')")

    def parc(acct, geo, ent, klass, appraised):
        admin.execute("INSERT INTO parcel_entity VALUES (%s,%s)", (acct, ent))
        admin.execute("INSERT INTO parcel VALUES (%s,%s,%s,1.0,%s)",
                      (acct, geo, klass, Json({"zip": "78701"})))
        admin.execute("INSERT INTO parcel_value VALUES (%s,2025,'certified',%s)", (acct, appraised))

    def case(geo, opened):
        admin.execute("INSERT INTO raw_code_cases (payload) VALUES (%s)",
                      (Json({"parcelid": geo, "opened_date": opened}),))

    # A1: individuals and institutional both at 100/acre, SAME within-class rate
    for i in range(10):
        parc(f"I{i}", f"gI{i}", "IND", "A1", 100)
    for i in range(10):
        parc(f"N{i}", f"gN{i}", "INST", "A1", 100)
    case("gI0", "2024-06-01")          # in window -> counts
    case("gI1", "2020-01-01")          # BEFORE window -> excluded
    case("gN0", "2024-06-01")          # in window -> counts
    # F1 institutional thin cell (3 parcels) -> dropped by min-N
    for i in range(3):
        parc(f"F{i}", f"gF{i}", "INST", "F1", 500)


def _run(window_start="2024-01-01", min_parcels=5):
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)
    admin.close()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = differential.build_owner_treatment(
        conn, roll_year=2025, window_start=window_start, min_parcels=min_parcels)
    rows = {(r["property_class"], r["owner_type"]): r for r in conn.execute(
        "SELECT * FROM metric_owner_treatment").fetchall()}
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    return summary, rows


def test_within_class_code_case_index_is_deconfounded():
    _summary, rows = _run()
    inst = rows[("A1", "institutional")]
    ind = rows[("A1", "individual")]
    # within A1, institutional and individual run the SAME code-case rate ->
    # code_case_index collapses to ~1.0 (the blended cross-class gap was mix)
    assert float(inst["code_case_index"]) == pytest.approx(1.0, abs=0.01)
    assert float(ind["code_case_index"]) == pytest.approx(1.0, abs=0.01)
    assert inst["code_cases"] == 1
    assert float(inst["code_cases_per_1k"]) == pytest.approx(100.0)


def test_assessment_index_within_class():
    _summary, rows = _run()
    # same appraised/acre within (A1, 78701) -> index ~1.0 for both owner types
    assert float(rows[("A1", "institutional")]["assessment_index"]) == pytest.approx(1.0, abs=0.01)


def test_code_case_window_excludes_old_cases():
    _summary, rows = _run()
    # the 2020 case on an A1 individual parcel is before the 2024 window -> not counted
    assert rows[("A1", "individual")]["code_cases"] == 1


def test_min_parcels_drops_thin_cells():
    _summary, rows = _run(min_parcels=5)
    # F1 institutional has only 3 parcels -> below the floor, not emitted
    assert ("F1", "institutional") not in rows
