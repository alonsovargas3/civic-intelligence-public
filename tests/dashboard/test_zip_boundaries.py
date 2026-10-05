from atx_dashboard.zip_boundaries import features_to_rows, valid_zips, ZCTA_QUERY_URL


def test_query_url_is_census_tigerweb():
    assert "tigerweb.geo.census.gov" in ZCTA_QUERY_URL


def test_valid_zips_keeps_5digit_drops_junk():
    raw = ["78704", "78704", "00000", "", None, "787", "78641", "abcde"]
    assert valid_zips(raw) == ["78641", "78704"]   # deduped, sorted, no junk/00000


def test_features_to_rows_extracts_zip_and_geom():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"BASENAME": "78704", "GEOID": "78704"},
             "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]}},
            {"type": "Feature", "properties": {"BASENAME": "78641"},
             "geometry": {"type": "MultiPolygon", "coordinates": []}},
        ],
    }
    rows = dict(features_to_rows(fc))
    assert set(rows) == {"78704", "78641"}
    assert rows["78704"]["type"] == "Polygon"


def test_features_to_rows_skips_missing_zip_or_geom():
    fc = {"features": [
        {"properties": {"BASENAME": ""}, "geometry": {"type": "Polygon"}},
        {"properties": {"BASENAME": "78702"}, "geometry": None},
    ]}
    assert features_to_rows(fc) == []
