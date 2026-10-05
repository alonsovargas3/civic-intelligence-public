import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402

from atx_ownership import build, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "own_build_test"


def _connect(dsn):
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


# entity, kind ; parcels = (account_id, category, appraised, district-or-None)
_ENTITIES = [("E1", "BigCo LLC", "llc"), ("E2", "Trust A", "trust"),
             ("E3", "Jane Homeowner", "person"), ("E4", "John Homeowner", "person")]
_PARCELS = (
    [(f"p{i}", "E1", "A1", 100, 1) for i in range(1, 6)] +     # 5 parcels, llc, dist 1
    [(f"p{i}", "E2", "A1", 200, 1) for i in range(6, 9)] +     # 3 parcels, trust, dist 1
    [("p9", "E3", "A1", 300, 2)] +                              # 1 parcel, person, dist 2
    [("p10", "E4", "C1", 50, None)]                             # 1 parcel, person, unmatched
)


def _seed(admin):
    admin.execute("CREATE TABLE dim_entity (entity_id text PRIMARY KEY, canonical_name text, "
                  "kind text, confidence text, n_parcels int, n_owner_records int, "
                  "roll_year int, meta jsonb)")
    admin.execute("CREATE TABLE parcel_entity (account_id text PRIMARY KEY, entity_id text, "
                  "roll_year int, link_type text)")
    admin.execute("CREATE TABLE parcel (account_id text PRIMARY KEY, category text, acreage numeric)")
    admin.execute("CREATE TABLE parcel_value (account_id text, roll_year int, roll_stage text, "
                  "appraised_value numeric, PRIMARY KEY (account_id, roll_year, roll_stage))")
    admin.execute("CREATE TABLE parcel_district (account_id text PRIMARY KEY, council_district int)")
    for eid, name, kind in _ENTITIES:
        admin.execute("INSERT INTO dim_entity VALUES (%s,%s,%s,'strong',0,0,2025,NULL)",
                      (eid, name, kind))
    for acct, eid, cat, val, dist in _PARCELS:
        admin.execute("INSERT INTO parcel_entity VALUES (%s,%s,2025,'name')", (acct, eid))
        admin.execute("INSERT INTO parcel VALUES (%s,%s,1.0)", (acct, cat))
        admin.execute("INSERT INTO parcel_value VALUES (%s,2025,'certified',%s)", (acct, val))
        if dist is not None:
            admin.execute("INSERT INTO parcel_district VALUES (%s,%s)", (acct, dist))


def _run():
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)
    admin.close()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = build.build_ownership(conn, roll_year=2025, roll_stage="certified")
    conc = {(r["dimension"], r["segment"]): r for r in conn.execute(
        "SELECT * FROM metric_ownership_concentration").fetchall()}
    rank = {(r["scope"], r["rank"]): r for r in conn.execute(
        "SELECT * FROM metric_owner_ranking ORDER BY scope, rank").fetchall()}
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    return summary, conc, rank


def test_overall_totals():
    _summary, conc, _rank = _run()
    o = conc[("overall", "all")]
    assert o["n_entities"] == 4
    assert o["n_parcels"] == 10
    assert float(o["total_appraised"]) == 1450.0
    assert float(o["parcel_share"]) == 1.0
    # HHI over entity parcel counts [5,3,1,1] = .25+.09+.01+.01
    assert float(o["hhi_parcels"]) == pytest.approx(0.36, abs=1e-6)


def test_kind_dimension():
    _summary, conc, _rank = _run()
    person = conc[("kind", "person")]
    assert person["n_entities"] == 2
    assert person["n_parcels"] == 2
    assert float(person["parcel_share"]) == pytest.approx(0.2)
    assert float(person["hhi_parcels"]) == pytest.approx(0.5)   # two equal owners
    assert float(conc[("kind", "llc")]["parcel_share"]) == pytest.approx(0.5)


def test_district_dimension_includes_unknown():
    _summary, conc, _rank = _run()
    assert float(conc[("district", "1")]["parcel_share"]) == pytest.approx(0.8)
    assert conc[("district", "1")]["n_entities"] == 2
    # the unmatched parcel surfaces as an 'unknown' district segment (disclosed gap)
    assert conc[("district", "unknown")]["n_parcels"] == 1


def test_owner_rankings():
    _summary, _conc, rank = _run()
    # most parcels -> E1 (5); most value -> E2 (3 x 200 = 600)
    assert rank[("by_parcels", 1)]["entity_id"] == "E1"
    assert rank[("by_value", 1)]["entity_id"] == "E2"
    assert float(rank[("by_value", 1)]["total_appraised"]) == 600.0
