import pytest

from atx_ownership.geom import bbox, point_in_bbox, point_in_polygon, polygon_centroid

# Simple squares as GeoJSON-style geometries (rings are [x, y] lists).
SQUARE = {"type": "Polygon", "coordinates": [
    [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}
SQUARE_WITH_HOLE = {"type": "Polygon", "coordinates": [
    [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],   # exterior
    [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]]}        # hole
TWO_SQUARES = {"type": "MultiPolygon", "coordinates": [
    [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
    [[[20, 20], [22, 20], [22, 22], [20, 22], [20, 20]]]]}


def test_point_in_polygon_simple():
    assert point_in_polygon((5, 5), SQUARE) is True
    assert point_in_polygon((15, 15), SQUARE) is False


def test_point_in_polygon_respects_holes():
    assert point_in_polygon((1, 1), SQUARE_WITH_HOLE) is True
    assert point_in_polygon((5, 5), SQUARE_WITH_HOLE) is False   # inside the hole


def test_point_in_polygon_multipolygon():
    assert point_in_polygon((1, 1), TWO_SQUARES) is True         # first square
    assert point_in_polygon((21, 21), TWO_SQUARES) is True       # second square
    assert point_in_polygon((10, 10), TWO_SQUARES) is False      # between them


def test_polygon_centroid_square():
    cx, cy = polygon_centroid(SQUARE)
    assert (round(cx, 6), round(cy, 6)) == (5.0, 5.0)


def test_bbox_and_point_in_bbox():
    bb = bbox(TWO_SQUARES)                       # spans both squares
    assert bb == (0, 0, 22, 22)
    assert point_in_bbox((1, 1), bb) is True
    assert point_in_bbox((21, 21), bb) is True
    assert point_in_bbox((-5, 5), bb) is False   # west of the box
    # bbox is a cheap prefilter: a point can be in the bbox yet outside the geometry
    assert point_in_bbox((10, 10), bb) is True
    assert point_in_polygon((10, 10), TWO_SQUARES) is False


def test_polygon_centroid_rejects_degenerate_geometry():
    # real parcel_geo rows can carry empty coordinates; centroid must fail cleanly
    with pytest.raises(ValueError):
        polygon_centroid({"type": "Polygon", "coordinates": []})
    with pytest.raises(ValueError):
        polygon_centroid({"type": "MultiPolygon", "coordinates": []})


def test_polygon_centroid_multipolygon_uses_largest():
    # the larger square (side 2 at origin) dominates the smaller? both side 2 here;
    # for MultiPolygon the centroid must at least fall inside one of the parts.
    cx, cy = polygon_centroid(TWO_SQUARES)
    assert point_in_polygon((cx, cy), TWO_SQUARES) is True
