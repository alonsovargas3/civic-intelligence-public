"""Offline tests for the money-wins crosswalk parser and fight tally (no net, no DB)."""
import pytest

from atx_dashboard.money_wins import fight_summary
from scripts.analyze_money_wins import parse_crosswalk

HEADER = ("election_date,measure,committee_recipient_name,side,"
          "votes_for,votes_against,outcome,source_url,notes\n")

GOOD = HEADER + (
    '2016-05-07,"Prop 1 — rideshare",Ridesharing Works for Austin,for,'
    "38539,48673,failed,https://example.gov/canvass,\n"
    '2021-11-02,"Prop A — police staffing",Save Austin Now PAC,for,'
    "63006,135973,failed,https://example.gov/canvass2,\n"
    '2021-11-02,"Prop A — police staffing",Equity Action,against,'
    "63006,135973,failed,https://example.gov/canvass2,\n"
)


def test_parse_crosswalk_good():
    rows = parse_crosswalk(GOOD)
    assert len(rows) == 3
    assert rows[0]["votes_for"] == 38539          # coerced to int
    assert rows[0]["side"] == "for"


def test_parse_crosswalk_rejects_bad_side():
    bad = HEADER + "2020-11-03,Prop A,Mobility for All,pro,1,2,passed,https://x,\n"
    with pytest.raises(ValueError, match="side"):
        parse_crosswalk(bad)


def test_parse_crosswalk_rejects_bad_outcome():
    bad = HEADER + "2020-11-03,Prop A,Mobility for All,for,1,2,won,https://x,\n"
    with pytest.raises(ValueError, match="outcome"):
        parse_crosswalk(bad)


def test_parse_crosswalk_rejects_missing_source():
    bad = HEADER + "2020-11-03,Prop A,Mobility for All,for,1,2,passed,,\n"
    with pytest.raises(ValueError, match="source_url"):
        parse_crosswalk(bad)


def test_parse_crosswalk_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        parse_crosswalk(HEADER)


def test_fight_summary_tallies_and_scores():
    rows = parse_crosswalk(GOOD)
    money = {
        ("Ridesharing Works for Austin", "2016-05-07"): 3_200_000.0,
        ("Save Austin Now PAC", "2021-11-02"): 2_000_000.0,
        ("Equity Action", "2021-11-02"): 900_000.0,
    }
    fights = fight_summary(rows, money)
    assert len(fights) == 2
    rideshare = next(f for f in fights if f["election_date"] == "2016-05-07")
    assert rideshare["money_for"] == 3_200_000.0
    assert rideshare["money_against"] == 0.0
    assert rideshare["winner"] == "against"        # failed => 'against' won
    assert rideshare["better_funded"] == "for"
    assert rideshare["money_won"] is False
    staffing = next(f for f in fights if f["election_date"] == "2021-11-02")
    assert staffing["money_for"] == 2_000_000.0
    assert staffing["money_against"] == 900_000.0
    assert staffing["money_won"] is False          # better-funded 'for' lost
