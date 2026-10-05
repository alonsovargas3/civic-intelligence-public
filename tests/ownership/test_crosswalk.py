import os
import pytest

psycopg = pytest.importorskip("psycopg")
pytest.importorskip("pyproj")
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_ownership import crosswalk, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "own_test"

# A 2277 (ftUS) box ~around the Texas Capitol in downtown Austin.
_CAPITOL_2277 = [[3113900, 10070500], [3114300, 10070500],
                 [3114300, 10071000], [3113900, 10071000], [3113900, 10070500]]
# Same box shifted ~500k ft north -> well outside any Austin district box.
_NORTH_2277 = [[p[0], p[1] + 500000] for p in _CAPITOL_2277]
# A 4326 box covering greater Austin (lon -98.5..-97.0, lat 30.0..31.0).
_AUSTIN_4326 = [[-98.5, 30.0], [-97.0, 30.0], [-97.0, 31.0], [-98.5, 31.0], [-98.5, 30.0]]


def _connect(dsn):
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


def _seed(admin):
    admin.execute("CREATE TABLE parcel_geo (account_id text PRIMARY KEY, geom jsonb, srid int)")
    admin.execute("CREATE TABLE district_boundary (council_district int PRIMARY KEY, geom jsonb)")
    admin.execute("INSERT INTO parcel_geo VALUES (%s, %s, 2277)",
                  ("capitol", Json({"type": "Polygon", "coordinates": [_CAPITOL_2277]})))
    admin.execute("INSERT INTO parcel_geo VALUES (%s, %s, 2277)",
                  ("far_north", Json({"type": "Polygon", "coordinates": [_NORTH_2277]})))
    admin.execute("INSERT INTO parcel_geo (account_id, geom, srid) VALUES (%s, NULL, 2277)",
                  ("no_geom",))
    # real rolls carry degenerate geometries (empty coordinates); must be skipped, not crash
    admin.execute("INSERT INTO parcel_geo VALUES (%s, %s, 2277)",
                  ("empty_geom", Json({"type": "Polygon", "coordinates": []})))
    admin.execute("INSERT INTO district_boundary VALUES (%s, %s)",
                  (7, Json({"type": "Polygon", "coordinates": [_AUSTIN_4326]})))


def _prep():
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)
    admin.close()


def _drop():
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")


def test_crosswalk_assigns_only_in_district_parcels():
    _prep()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = crosswalk.build_crosswalk(conn)
    rows = {r["account_id"]: r["council_district"] for r in conn.execute(
        "SELECT account_id, council_district FROM parcel_district").fetchall()}
    conn.close()
    _drop()

    # the Capitol parcel reprojects into the Austin district box; the others don't
    assert rows == {"capitol": 7}
    assert summary["matched"] == 1
    # far_north (outside) + no_geom (NULL) + empty_geom (degenerate) all unmatched
    assert summary["unmatched"] == 3
