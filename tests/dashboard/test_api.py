import os
import pytest

pytest.importorskip("fastapi")
psycopg = pytest.importorskip("psycopg")
from fastapi.testclient import TestClient  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_dashboard import api, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

# Run these tests inside a throwaway Postgres schema so they NEVER touch the real
# public metric_*/district_boundary tables. The fixture creates the schema, seeds
# it, and points the app's connections at it via search_path; teardown drops it.
# This needs no change to api.py — production still uses the public schema.
_SCHEMA = "dash_apitest"


def _scoped_dsn(dsn: str, schema: str) -> str:
    """Return dsn with libpq options forcing search_path to `schema`."""
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


@pytest.fixture()
def client():
    admin = psycopg.connect(TEST_DSN, autocommit=True)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    # With search_path pinned to the test schema, public tables are invisible, so
    # db.DDL's CREATE TABLE IF NOT EXISTS builds fresh copies inside _SCHEMA.
    admin.execute(f"SET search_path TO {_SCHEMA}")
    admin.execute(db.DDL)
    # /v1/meta reads ingestion_state; create a minimal in-schema copy so that
    # endpoint is covered without touching the real table.
    admin.execute("CREATE TABLE IF NOT EXISTS ingestion_state ("
                  "dataset_id text PRIMARY KEY, last_cursor text, "
                  "last_run_at timestamptz, rows_ingested bigint DEFAULT 0)")
    admin.execute("INSERT INTO metric_incidents_by_district VALUES ('crime', 9, '2025-04-01', 40)")
    admin.execute("INSERT INTO metric_incidents_by_district VALUES ('crime', 9, '2025-05-01', 25)")
    admin.execute("INSERT INTO metric_incidents_by_district VALUES ('crime', 3, '2025-04-01', 10)")
    admin.execute("INSERT INTO metric_incidents_by_district VALUES ('311', 9, '2025-04-01', 70)")
    admin.execute("INSERT INTO metric_district_breakdown "
                  "VALUES ('crime', 9, '2025', 'category', 'THEFT', 30)")
    admin.execute("INSERT INTO metric_district_breakdown "
                  "VALUES ('crime', 9, '2025', 'category', 'ASSAULT', 12)")
    admin.execute("INSERT INTO metric_311_response VALUES (9, '2025', 3.5, 40, 5)")
    admin.execute("INSERT INTO district_boundary VALUES (9, %s)",
                  (Json({"type": "Polygon", "coordinates": []}),))
    # /v1/incidents/recent reads recent_incidents (built by aggregate.run); /v1/meta
    # reads ingestion_state. recent_incidents is part of db.DDL so it already exists
    # in-schema; seed two D9 311 rows + one D3 so the district filter is exercised.
    for cd in (9, 9, 3):
        admin.execute(
            "INSERT INTO recent_incidents (dataset, council_district, ts, payload) "
            "VALUES ('311', %s, now(), %s)",
            (cd, Json({"sr_number": f"SR-{cd}", "sr_location_council_district": str(cd),
                       "sr_type_desc": "Pothole"})))
    admin.execute("INSERT INTO ingestion_state (dataset_id, rows_ingested, last_run_at) "
                  "VALUES ('xwdj-i9he', 2458777, now())")
    # Anomaly tables (not part of the dashboard DDL) — created + seeded in-schema so
    # /v1/flags is covered without touching the real public anomaly tables.
    admin.execute("CREATE TABLE IF NOT EXISTS anomaly_flag ("
                  "flag_id bigserial PRIMARY KEY, detector text NOT NULL, "
                  "cluster_kind text NOT NULL, cluster_id text NOT NULL, roll_year int, "
                  "score numeric NOT NULL, direction text, evidence jsonb NOT NULL, "
                  "methodology text NOT NULL, review_state text NOT NULL DEFAULT 'unreviewed', "
                  "created_at timestamptz NOT NULL DEFAULT now())")
    admin.execute("CREATE TABLE IF NOT EXISTS metric_assessment_equity ("
                  "roll_year int NOT NULL, class text NOT NULL, zip text NOT NULL, "
                  "n_parcels int NOT NULL, n_total int NOT NULL, median_per_acre numeric NOT NULL, "
                  "median_appraised numeric, modified_z numeric NOT NULL, percentile numeric NOT NULL, "
                  "flagged boolean NOT NULL, PRIMARY KEY (roll_year, class, zip))")
    admin.execute("INSERT INTO metric_assessment_equity "
                  "VALUES (2025, 'A1', '78703', 4773, 5100, 736.0, 612345.0, 5.5714, 100.0, true)")
    admin.execute("INSERT INTO anomaly_flag "
                  "(detector, cluster_kind, cluster_id, roll_year, score, direction, "
                  " evidence, methodology) "
                  "VALUES ('d3a_assessment_equity', 'zip', '78703', 2025, 5.5714, 'over', %s, %s)",
                  (Json({"zip": "78703"}),
                   "Assessment-equity dispersion: screening signal, NOT a sale ratio."))
    # assessment_cod flag carries its detail in evidence (no dedicated join table)
    admin.execute("INSERT INTO anomaly_flag "
                  "(detector, cluster_kind, cluster_id, roll_year, score, direction, "
                  " evidence, methodology) "
                  "VALUES ('assessment_cod', 'zip_class', '78744|A1', 2025, 31.4, 'dispersion', %s, %s)",
                  (Json({"situs_zip": "78744", "property_class": "A1", "n_parcels": 420,
                         "cod": 31.4, "cod_pctile_in_class": 0.97, "high_dispersion": True}),
                   "Assessment dispersion within a stratum — HIGH DISPERSION, never over-assessed."))
    # Ownership owner-type tables (atx_ownership DDL) — seeded in-schema so
    # /v1/ownership/owner-type is covered without touching public tables.
    admin.execute("CREATE TABLE IF NOT EXISTS metric_ownership_concentration ("
                  "dimension text NOT NULL, segment text NOT NULL, n_entities int NOT NULL, "
                  "n_parcels int NOT NULL, total_appraised numeric NOT NULL, "
                  "parcel_share numeric NOT NULL, value_share numeric NOT NULL, "
                  "top10_parcel_share numeric NOT NULL, hhi_parcels numeric NOT NULL, "
                  "PRIMARY KEY (dimension, segment))")
    admin.execute("CREATE TABLE IF NOT EXISTS zip_boundary (zip text PRIMARY KEY, geom jsonb NOT NULL)")
    admin.execute("CREATE TABLE IF NOT EXISTS metric_assessment_cod ("
                  "roll_year int NOT NULL, situs_zip text NOT NULL, property_class text NOT NULL, "
                  "n_parcels int NOT NULL, median_value_per_unit numeric NOT NULL, cod numeric NOT NULL, "
                  "cod_pctile_in_class numeric NOT NULL, high_dispersion boolean NOT NULL, "
                  "PRIMARY KEY (roll_year, situs_zip, property_class))")
    admin.execute("INSERT INTO zip_boundary VALUES "
                  "('78744', %s), ('78702', %s)",
                  (Json({"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]}),
                   Json({"type": "Polygon", "coordinates": [[[2, 2], [2, 3], [3, 3], [2, 2]]]})))
    admin.execute("INSERT INTO metric_assessment_cod VALUES "
                  "(2025,'78744','A1',420,90,31.4,0.97,true)")  # 78702 has no A1 row -> null pctile
    admin.execute("CREATE TABLE IF NOT EXISTS metric_member_funding_activity ("
                  "member_key text PRIMARY KEY, canonical_name text NOT NULL, "
                  "n_matters_sponsored int NOT NULL, contributions_total numeric NOT NULL, "
                  "n_contributions int NOT NULL)")
    admin.execute("INSERT INTO metric_member_funding_activity VALUES "
                  "('alter|ryan','Ryan Alter',42,18650.0,57),"
                  "('kelly|mackenzie','Mackenzie Kelly',12,90250.0,310)")
    admin.execute("CREATE TABLE IF NOT EXISTS metric_member_sponsorship ("
                  "member_key text PRIMARY KEY, canonical_name text NOT NULL, "
                  "n_lead int NOT NULL, n_cosponsor int NOT NULL, n_total int NOT NULL)")
    admin.execute("CREATE TABLE IF NOT EXISTS metric_cosponsorship ("
                  "member_a text NOT NULL, member_b text NOT NULL, name_a text NOT NULL, "
                  "name_b text NOT NULL, shared_matters int NOT NULL, PRIMARY KEY (member_a, member_b))")
    admin.execute("INSERT INTO metric_member_sponsorship VALUES "
                  "('pool|leslie','Leslie Pool',309,794,1103),"
                  "('alter|alison','Alison Alter',408,395,803)")
    admin.execute("INSERT INTO metric_cosponsorship VALUES "
                  "('alter|alison','pool|leslie','Alison Alter','Leslie Pool',516)")
    admin.execute("CREATE TABLE IF NOT EXISTS metric_owner_treatment ("
                  "property_class text NOT NULL, owner_type text NOT NULL, parcels int NOT NULL, "
                  "assessment_index numeric, code_cases int NOT NULL, code_cases_per_1k numeric NOT NULL, "
                  "code_case_index numeric, code_cases_per_1k_acres numeric, window_start date NOT NULL, "
                  "PRIMARY KEY (property_class, owner_type, window_start))")
    admin.execute("INSERT INTO metric_ownership_concentration VALUES "
                  "('kind','individual',300,380,1000,0.78,0.56,0.001,0.0),"
                  "('kind','institutional',44,100,500,0.21,0.33,0.01,0.001)")
    # A1 (and a second class) so the class list + selector are exercised
    admin.execute("INSERT INTO metric_owner_treatment VALUES "
                  "('A1','individual',60,1.05,30,120.0,1.0,5.0,'2024-01-01'),"
                  "('A1','institutional',40,0.95,20,150.0,1.25,6.0,'2024-01-01'),"
                  "('C1','institutional',50,1.0,40,800.0,1.0,9.0,'2024-01-01')")
    admin.close()
    app = api.create_app(dsn=_scoped_dsn(TEST_DSN, _SCHEMA))
    yield TestClient(app)
    cleanup = psycopg.connect(TEST_DSN, autocommit=True)
    cleanup.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    cleanup.close()


def test_metric_incidents_ranks(client):
    r = client.get("/v1/metric/incidents?dataset=crime&period=2025")
    assert r.status_code == 200
    body = {row["council_district"]: row for row in r.json()}
    # crime 2025: D9 = 40+25 = 65 (rank 1), D3 = 10 (rank 2)
    assert body[9]["rank"] == 1 and body[9]["incident_count"] == 65
    assert body[3]["rank"] == 2
    assert "cache-control" in {k.lower() for k in r.headers}


def test_zips_geojson(client):
    r = client.get("/v1/zips.geojson?property_class=A1")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    by_zip = {f["properties"]["zip"]: f for f in fc["features"]}
    assert set(by_zip) == {"78744", "78702"}
    # 78744 has an A1 metric row -> cod + percentile (pctile * 100) present
    assert by_zip["78744"]["properties"]["cod"] == 31.4
    assert by_zip["78744"]["properties"]["percentile"] == 97.0
    assert by_zip["78744"]["properties"]["high_dispersion"] is True
    assert by_zip["78744"]["geometry"]["type"] == "Polygon"
    # 78702 has no A1 stratum -> percentile null (rendered neutral on the map)
    assert by_zip["78702"]["properties"]["percentile"] is None


def test_districts_geojson(client):
    r = client.get("/v1/districts.geojson")
    assert r.status_code == 200
    assert r.json()["type"] == "FeatureCollection"
    assert len(r.json()["features"]) == 1


def test_empty_period_returns_empty_array_not_error(client):
    r = client.get("/v1/metric/incidents?dataset=crime&period=1900")
    assert r.status_code == 200
    assert r.json() == []


def test_flags_assessment_cod_uses_evidence_detail(client):
    r = client.get("/v1/flags?detector=assessment_cod")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    f = rows[0]
    assert f["cluster_id"] == "78744|A1"
    assert f["direction"] == "dispersion"
    # detail comes from the flag's evidence (no dedicated detail join for this detector)
    assert f["detail"]["cod"] == 31.4
    assert f["detail"]["property_class"] == "A1"
    assert f["detail"]["n_parcels"] == 420


def test_flags_d3a_still_uses_join_detail(client):
    # the existing d3a path (detail from metric_assessment_equity join) is unchanged
    r = client.get("/v1/flags?detector=d3a_assessment_equity")
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["detail"]["median_per_acre"] == 736.0
    assert rows[0]["detail"]["n_parcels"] == 4773


def test_council_funding_endpoint(client):
    r = client.get("/v1/council/funding-activity")
    assert r.status_code == 200
    body = r.json()
    assert "cache-control" in {k.lower() for k in r.headers}
    members = {m["canonical_name"]: m for m in body["members"]}
    assert set(members) == {"Ryan Alter", "Mackenzie Kelly"}
    # ordered by contributions desc -> Kelly first
    assert body["members"][0]["canonical_name"] == "Mackenzie Kelly"
    assert members["Ryan Alter"]["n_matters_sponsored"] == 42
    assert members["Mackenzie Kelly"]["contributions_total"] == 90250.0
    assert body["methodology"]


def test_council_representation_endpoint(client):
    r = client.get("/v1/council/representation")
    assert r.status_code == 200
    body = r.json()
    members = {m["canonical_name"]: m for m in body["members"]}
    # ordered by lead desc -> Alison Alter (408) first
    assert body["members"][0]["canonical_name"] == "Alison Alter"
    assert members["Leslie Pool"]["n_cosponsor"] == 794
    pairs = body["coalitions"]
    assert pairs[0]["name_a"] == "Alison Alter" and pairs[0]["name_b"] == "Leslie Pool"
    assert pairs[0]["shared_matters"] == 516
    assert body["methodology"]


def test_owner_type_endpoint(client):
    r = client.get("/v1/ownership/owner-type?property_class=A1")
    assert r.status_code == 200
    body = r.json()
    assert "cache-control" in {k.lower() for k in r.headers}
    assert body["property_class"] == "A1"
    assert set(body["classes"]) == {"A1", "C1"}
    conc = {c["owner_kind"]: c for c in body["concentration"]}
    assert conc["individual"]["parcel_share"] == 0.78
    # category-stratified treatment for the selected class, leading with the indices
    t = {x["owner_type"]: x for x in body["treatment"]}
    assert t["institutional"]["assessment_index"] == 0.95
    assert t["institutional"]["code_case_index"] == 1.25
    assert t["individual"]["code_cases_per_1k"] == 120.0
    assert body["methodology"]


def test_owner_type_defaults_to_a1_and_unknown_class_empty(client):
    assert client.get("/v1/ownership/owner-type").json()["property_class"] == "A1"
    r = client.get("/v1/ownership/owner-type?property_class=ZZ")
    assert r.status_code == 200
    assert r.json()["treatment"] == []


def test_place_district_panel(client):
    r = client.get("/v1/place/district/9?period=2025")
    assert r.status_code == 200
    body = r.json()
    assert body["district"] == 9
    totals = {t["dataset"]: t["n"] for t in body["totals_by_dataset"]}
    assert totals == {"crime": 65, "311": 70}
    # monthly_trend has the crime April+May + the 311 April rows for D9
    assert len(body["monthly_trend"]) == 3
    # top breakdown is THEFT (30) before ASSAULT (12)
    assert body["breakdown"][0]["label"] == "THEFT"
    assert body["response_time"]["closed_count"] == 40
    assert body["response_time"]["open_count"] == 5
    assert "cache-control" in {k.lower() for k in r.headers}


def test_place_district_empty_period(client):
    r = client.get("/v1/place/district/9?period=1900")
    assert r.status_code == 200
    body = r.json()
    assert body["totals_by_dataset"] == []
    assert body["monthly_trend"] == []
    assert body["response_time"] is None


def test_incidents_recent_filters_by_district(client):
    r = client.get("/v1/incidents/recent?dataset=311&district=9&limit=10")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2                       # two seeded D9 311 rows
    assert all(row["sr_location_council_district"] == "9" for row in rows)
    assert "cache-control" in {k.lower() for k in r.headers}


def test_incidents_recent_unknown_dataset_is_empty(client):
    r = client.get("/v1/incidents/recent?dataset=bogus")
    assert r.status_code == 200
    assert r.json() == []


def test_incidents_recent_rejects_nonpositive_limit(client):
    # limit must be >= 1; 0 and negatives are a 422 validation error, not a 500
    assert client.get("/v1/incidents/recent?dataset=311&limit=0").status_code == 422
    assert client.get("/v1/incidents/recent?dataset=311&limit=-5").status_code == 422
    # and the upper bound still holds
    assert client.get("/v1/incidents/recent?dataset=311&limit=999").status_code == 422


def test_meta_reports_freshness(client):
    r = client.get("/v1/meta")
    assert r.status_code == 200
    fresh = r.json()["freshness"]
    assert any(row["dataset_id"] == "xwdj-i9he" and row["rows_ingested"] == 2458777
               for row in fresh)
    assert "cache-control" in {k.lower() for k in r.headers}


def test_methods_returns_caveats(client):
    r = client.get("/v1/methods/crime")
    assert r.status_code == 200
    body = r.json()
    assert body["metric"] == "crime"
    # the honest caveats must be present
    assert any("no point coordinates" in n for n in body["notes"])
    assert any("non-disclosure" in n for n in body["notes"])
    assert "cache-control" in {k.lower() for k in r.headers}


def test_flags_returns_joined_detail(client):
    r = client.get("/v1/flags?detector=d3a_assessment_equity")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    f = rows[0]
    assert f["cluster_id"] == "78703"
    assert f["cluster_kind"] == "zip"
    assert f["direction"] == "over"
    assert float(f["score"]) == 5.5714
    assert f["review_state"] == "unreviewed"
    # the caveat rides through verbatim (honesty guard)
    assert "screening signal" in f["methodology"]
    # the D3a detail is joined in
    assert f["detail"]["n_parcels"] == 4773
    assert float(f["detail"]["median_per_acre"]) == 736.0
    assert float(f["detail"]["percentile"]) == 100.0
    assert "cache-control" in {k.lower() for k in r.headers}


def test_flags_unknown_detector_is_empty(client):
    r = client.get("/v1/flags?detector=nope")
    assert r.status_code == 200
    assert r.json() == []


def test_flags_default_detector(client):
    # default detector param is d3a_assessment_equity -> returns the seeded flag
    r = client.get("/v1/flags")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_flags_non_d3a_detail_falls_back_to_evidence(client):
    # a non-d3a detector has no metric_assessment_equity join, so its detail comes
    # from the flag's evidence jsonb (detector-agnostic); core fields still come through
    admin = psycopg.connect(_scoped_dsn(TEST_DSN, _SCHEMA), autocommit=True)
    admin.execute(
        "INSERT INTO anomaly_flag (detector, cluster_kind, cluster_id, roll_year, "
        "score, direction, evidence, methodology) "
        "VALUES ('detector_evidence_only', 'zip', '99999', 2025, 4.0, 'under', %s, 'caveat')",
        (Json({"zip": "99999", "metric": 4.0}),),
    )
    admin.close()
    r = client.get("/v1/flags?detector=detector_evidence_only")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["cluster_id"] == "99999"
    assert rows[0]["direction"] == "under"
    assert rows[0]["detail"] == {"zip": "99999", "metric": 4.0}


def test_api_tests_do_not_mutate_public_tables():
    """Guard the isolation invariant directly: the dashboard api suite must never
    change the real public metric_*/district_boundary row counts."""
    admin = psycopg.connect(TEST_DSN, autocommit=True)
    try:
        before_m = admin.execute(
            "SELECT count(*) FROM public.metric_incidents_by_district").fetchone()[0]
        before_b = admin.execute(
            "SELECT count(*) FROM public.district_boundary").fetchone()[0]
    finally:
        admin.close()
    # exercise the full fixture + every endpoint via a fresh client
    app = None
    setup = psycopg.connect(TEST_DSN, autocommit=True)
    setup.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    setup.execute(f"CREATE SCHEMA {_SCHEMA}")
    setup.execute(f"SET search_path TO {_SCHEMA}")
    setup.execute(db.DDL)
    setup.execute("INSERT INTO metric_incidents_by_district VALUES ('crime', 9, '2025-04-01', 40)")
    setup.execute("INSERT INTO district_boundary VALUES (9, %s)",
                  (Json({"type": "Polygon", "coordinates": []}),))
    setup.close()
    c = TestClient(api.create_app(dsn=_scoped_dsn(TEST_DSN, _SCHEMA)))
    c.get("/v1/metric/incidents?dataset=crime&period=2025")
    c.get("/v1/districts.geojson")
    cleanup = psycopg.connect(TEST_DSN, autocommit=True)
    cleanup.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")

    after_m = cleanup.execute(
        "SELECT count(*) FROM public.metric_incidents_by_district").fetchone()[0]
    after_b = cleanup.execute(
        "SELECT count(*) FROM public.district_boundary").fetchone()[0]
    cleanup.close()
    assert after_m == before_m
    assert after_b == before_b
