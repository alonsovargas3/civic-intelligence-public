from atx_dashboard.metrics import rank_and_percentile, district_or_none


def test_rank_and_percentile_orders_desc():
    rows = [
        {"council_district": 1, "incident_count": 10},
        {"council_district": 2, "incident_count": 30},
        {"council_district": 3, "incident_count": 20},
    ]
    out = {r["council_district"]: r for r in rank_and_percentile(rows)}
    assert out[2]["rank"] == 1            # highest count ranks first
    assert out[3]["rank"] == 2
    assert out[1]["rank"] == 3
    # percentile in [0,100]; the top is 100, the bottom is lowest
    assert out[2]["percentile"] == 100.0
    assert out[1]["percentile"] < out[3]["percentile"] < out[2]["percentile"]


def test_rank_and_percentile_empty():
    assert rank_and_percentile([]) == []


def test_district_or_none_keeps_1_to_10():
    assert district_or_none("9") == 9
    assert district_or_none("10") == 10
    assert district_or_none("1") == 1


def test_district_or_none_rejects_out_of_range_and_junk():
    for bad in ("0", "11", "", None, "APD", "UNK", "99"):
        assert district_or_none(bad) is None
