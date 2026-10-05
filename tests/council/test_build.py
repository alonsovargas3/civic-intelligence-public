import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_council import build, db  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "council_test"


def _connect(dsn):
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


def _seed(admin):
    admin.execute("CREATE TABLE raw_council_matter_sponsors (payload jsonb)")
    admin.execute("CREATE TABLE raw_campaign_contributions (payload jsonb)")

    def sponsor(name, matter_id, name_id=1):
        admin.execute("INSERT INTO raw_council_matter_sponsors (payload) VALUES (%s)",
                      (Json({"MatterSponsorName": name, "MatterSponsorMatterId": matter_id,
                             "MatterSponsorNameId": name_id}),))

    def body_sponsor(name, matter_id):  # committee/body sponsor (no person name id)
        admin.execute("INSERT INTO raw_council_matter_sponsors (payload) VALUES (%s)",
                      (Json({"MatterSponsorName": name, "MatterSponsorMatterId": matter_id,
                             "MatterSponsorNameId": None, "MatterSponsorBodyId": 250}),))

    def contrib(recipient, amount):
        admin.execute("INSERT INTO raw_campaign_contributions (payload) VALUES (%s)",
                      (Json({"recipient": recipient, "contribution_amount": amount}),))

    # roster from sponsors: Ryan Alter (2 matters), Steve Adler (1 matter)
    sponsor("Council Member Ryan Alter", 1)
    sponsor("Council Member Ryan Alter", 2)
    sponsor("Mayor Steve Adler", 3)
    # a committee/body sponsor must NOT become a roster "member"
    body_sponsor("Climate, Water, Environment, and Parks Committee", 4)
    # contributions
    contrib("Alter, Ryan", "100")
    contrib("Alter, Ryan", "50")
    contrib("Adler, Stephen", "500")          # Stephen ~ Steve -> matches Adler
    contrib("Alter, Alison B.", "999")        # different Alter -> NOT matched (excluded)
    contrib("Austin Fire Fighters PAC", "9999")  # org -> excluded


def _run():
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)
    admin.close()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = build.build_member_activity(conn)
    rows = {r["member_key"]: r for r in conn.execute(
        "SELECT * FROM metric_member_funding_activity").fetchall()}
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    return summary, rows


def test_roster_from_sponsors_with_matched_contributions():
    _summary, rows = _run()
    # roster = the two PERSON sponsors only (the committee/body sponsor is excluded)
    assert set(rows) == {"alter|ryan", "adler|steve"}
    assert not any(k.startswith("climate") for k in rows)
    ryan = rows["alter|ryan"]
    assert ryan["n_matters_sponsored"] == 2
    assert float(ryan["contributions_total"]) == 150.0   # 100 + 50
    assert ryan["n_contributions"] == 2


def test_nickname_match_and_distinct_people_excluded():
    _summary, rows = _run()
    # "Adler, Stephen" matched Mayor Steve Adler (last + first-initial)
    adler = rows["adler|steve"]
    assert adler["n_matters_sponsored"] == 1
    assert float(adler["contributions_total"]) == 500.0
    # the Alison Alter contribution (999) went to NO roster member, and the PAC was
    # rejected -> neither inflates Ryan Alter
    assert float(rows["alter|ryan"]["contributions_total"]) == 150.0
