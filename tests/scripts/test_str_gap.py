"""Offline tests for the STR-gap pure helpers (no net, no DB)."""
from atx_dashboard.str_gap import (
    classify_license,
    district_for_point,
    is_active,
    md_table,
    normalize_license,
    prepare_boundaries,
)

# unit square around origin = district 1; unit square shifted x+2 = district 2
SQ1 = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
SQ2 = {"type": "Polygon", "coordinates": [[[2, 0], [3, 0], [3, 1], [2, 1], [2, 0]]]}


def test_normalize_license_keeps_digit_sequence():
    assert normalize_license("2000-000001 OL") == "2000000001"
    assert normalize_license(" 2000 0000 02 ") == "2000000002"
    assert normalize_license(None) == ""
    assert normalize_license("Exempt") == ""


def test_classify_license():
    assert classify_license("") == "missing"
    assert classify_license(None) == "missing"
    assert classify_license("  ") == "missing"
    assert classify_license("Exempt: hotel") == "exempt"
    assert classify_license("2000-000001 OL") == "claims_number"
    assert classify_license("pending") == "other"


def test_is_active_reads_reviews_ltm():
    assert is_active({"number_of_reviews_ltm": "3"}) is True
    assert is_active({"number_of_reviews_ltm": "0"}) is False
    assert is_active({"number_of_reviews_ltm": ""}) is False
    assert is_active({}) is False


def test_district_for_point_with_bbox_prefilter():
    bounds = prepare_boundaries([(1, SQ1), (2, SQ2)])
    assert district_for_point(0.5, 0.5, bounds) == 1
    assert district_for_point(2.5, 0.5, bounds) == 2
    assert district_for_point(1.5, 0.5, bounds) is None   # between the squares


def test_md_table():
    out = md_table(["a", "b"], [[1, "x"], [2, "y"]])
    assert out.splitlines() == ["| a | b |", "|---|---|", "| 1 | x |", "| 2 | y |"]
