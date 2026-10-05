from atx_dashboard.boundaries import features_to_rows, BOUNDARY_URL


def test_boundary_url_is_austin_socrata_geojson():
    assert "data.austintexas.gov" in BOUNDARY_URL


def test_features_to_rows_extracts_district_and_geom():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "properties": {"council_district": "9"},
             "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]}},
            {"type": "Feature",
             "properties": {"district_number": 3},
             "geometry": {"type": "Polygon", "coordinates": [[[2, 2], [2, 3], [3, 3], [2, 2]]]}},
        ],
    }
    rows = features_to_rows(fc)
    by_d = {d: g for d, g in rows}
    assert set(by_d) == {9, 3}
    assert by_d[9]["type"] == "Polygon"


def test_features_to_rows_skips_unparseable_district():
    fc = {"features": [
        {"properties": {"name": "no district here"}, "geometry": {"type": "Polygon"}},
    ]}
    assert features_to_rows(fc) == []
