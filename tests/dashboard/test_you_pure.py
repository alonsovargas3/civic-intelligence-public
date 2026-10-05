"""Offline tests for the you-layer pure helpers (no net beyond pyproj's bundled data, no DB)."""
import math

from atx_dashboard.you import (
    LAT_PAD, LON_PAD, RADIUS_M, _street_core, haversine_m, to_2277, valid_point,
    zip_for_point,
)

# Austin City Hall, 301 W 2nd St
CH_LAT, CH_LON = 30.2653, -97.7497


def test_to_2277_lands_in_travis_range():
    x, y = to_2277(CH_LAT, CH_LON)
    # EPSG:2277 (Texas Central, ftUS): Travis County x ~2.9-3.3M ft, y ~9.9-10.3M ft
    assert 2.5e6 < x < 3.5e6
    assert 9.5e6 < y < 10.5e6


def test_to_2277_axes_orient_correctly():
    x0, y0 = to_2277(CH_LAT, CH_LON)
    x_east, _ = to_2277(CH_LAT, CH_LON + 0.01)   # east -> larger x
    _, y_north = to_2277(CH_LAT + 0.01, CH_LON)  # north -> larger y
    assert x_east > x0
    assert y_north > y0


def test_to_2277_scale_is_feet():
    # 0.01 deg longitude at ~30.27N is ~960m ~ 3150ft; allow generous tolerance
    x0, _ = to_2277(CH_LAT, CH_LON)
    x1, _ = to_2277(CH_LAT, CH_LON + 0.01)
    assert 2800 < (x1 - x0) < 3500


def test_valid_point_bounds():
    assert valid_point(CH_LAT, CH_LON) is True
    assert valid_point(0.0, 0.0) is False          # off-Texas
    assert valid_point(30.3, -97.7) is True
    assert valid_point(32.0, -97.7) is False        # Dallas-ish latitude
    assert valid_point(30.3, -96.0) is False        # too far east


def test_haversine_known_distance():
    # 0.01 deg latitude is ~1111.9m everywhere
    d = haversine_m(30.0, -97.7, 30.01, -97.7)
    assert math.isclose(d, 1111.9, rel_tol=0.01)
    assert haversine_m(30.3, -97.7, 30.3, -97.7) == 0.0


def test_zip_for_point_unit_squares():
    sq = lambda x0: {"type": "Polygon",
                     "coordinates": [[[x0, 0], [x0 + 1, 0], [x0 + 1, 1], [x0, 1], [x0, 0]]]}
    rows = [("78701", sq(0)), ("78702", sq(2))]
    assert zip_for_point(0.5, 0.5, rows) == "78701"     # (lat=0.5, lon=0.5) -> point (x=0.5, y=0.5)
    assert zip_for_point(0.5, 2.5, rows) == "78702"
    assert zip_for_point(0.5, 4.5, rows) is None


def test_street_core_normalizes_for_matching():
    # drops house number + street-type suffix; a geocoded street and its situs form collapse equal
    assert _street_core("LYNNBROOK DR") == "LYNNBROOK"
    assert _street_core("3300 Pall Mall") == "PALL MALL"
    # numbered + directional streets survive and both forms reduce to the same key
    assert _street_core("W 2ND ST") == "2ND"
    assert _street_core("2ND") == "2ND"
    assert _street_core("SAN ANTONIO") == "SAN ANTONIO"
    assert _street_core("") == "" and _street_core(None) == ""


def test_pads_cover_radius():
    # the bbox prefilter pads must cover RADIUS_M at Austin's latitude
    assert LAT_PAD * 111320 >= RADIUS_M
    assert LON_PAD * 111320 * math.cos(math.radians(30.3)) >= RADIUS_M


def test_build_payload_shape_keys():
    """Contract: top-level keys exist even with a stub conn returning nothing."""
    from atx_dashboard.you import build_payload

    class StubCur(list):
        def fetchone(self): return None
        def fetchall(self): return []

    class StubConn:
        def execute(self, *a, **k): return StubCur()

    out = build_payload(StubConn(), 30.2653, -97.7497)
    assert set(out) == {"parcel", "district", "nearby", "methodology", "caveat"}
    assert out["parcel"] is None and out["district"] is None
    assert out["nearby"]["incidents"] == {"311": 0, "code": 0, "crashes": 0}
    assert out["nearby"]["strs"] is None
