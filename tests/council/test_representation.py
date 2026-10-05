import os
import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from atx_council import db, representation  # noqa: E402

TEST_DSN = os.environ.get("DASHBOARD_TEST_DSN")
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="DASHBOARD_TEST_DSN not set")

_SCHEMA = "council_rep_test"


def _connect(dsn):
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def _scoped(dsn, schema):
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}"


def _seed(admin):
    admin.execute("CREATE TABLE raw_council_matter_sponsors (payload jsonb)")

    def s(matter, name, seq, name_id=1):
        admin.execute("INSERT INTO raw_council_matter_sponsors (payload) VALUES (%s)",
                      (Json({"MatterSponsorMatterId": matter, "MatterSponsorName": name,
                             "MatterSponsorSequence": seq, "MatterSponsorNameId": name_id}),))

    # matter 1: Alter leads, Ellis + Pool co-sponsor
    s(1, "Council Member Ryan Alter", 0)
    s(1, "Council Member Paige Ellis", 1)
    s(1, "Council Member Leslie Pool", 2)
    # matter 2: Alter leads, Ellis co-sponsors
    s(2, "Council Member Ryan Alter", 0)
    s(2, "Council Member Paige Ellis", 1)
    # a body sponsor must be ignored (no NameId)
    admin.execute("INSERT INTO raw_council_matter_sponsors (payload) VALUES (%s)",
                  (Json({"MatterSponsorMatterId": 2, "MatterSponsorName": "Some Committee",
                         "MatterSponsorSequence": 3, "MatterSponsorNameId": None}),))


def _run():
    admin = _connect(TEST_DSN)
    admin.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    admin.execute(f"CREATE SCHEMA {_SCHEMA}")
    admin.execute(f"SET search_path TO {_SCHEMA}")
    _seed(admin)
    admin.execute(db.DDL)
    admin.close()
    conn = _connect(_scoped(TEST_DSN, _SCHEMA))
    summary = representation.build_representation(conn)
    spon = {r["member_key"]: r for r in conn.execute(
        "SELECT * FROM metric_member_sponsorship").fetchall()}
    pairs = {(r["member_a"], r["member_b"]): r["shared_matters"] for r in conn.execute(
        "SELECT * FROM metric_cosponsorship").fetchall()}
    conn.close()
    _connect(TEST_DSN).execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
    return summary, spon, pairs


def test_lead_vs_cosponsor_counts():
    _summary, spon, _pairs = _run()
    assert spon["alter|ryan"]["n_lead"] == 2
    assert spon["alter|ryan"]["n_cosponsor"] == 0
    assert spon["alter|ryan"]["n_total"] == 2
    assert spon["ellis|paige"]["n_lead"] == 0
    assert spon["ellis|paige"]["n_cosponsor"] == 2
    assert spon["pool|leslie"]["n_cosponsor"] == 1


def test_cosponsorship_pairs_unordered_and_counted():
    _summary, _spon, pairs = _run()
    # Alter+Ellis share both matters; Alter+Pool and Ellis+Pool share matter 1 only
    assert pairs[("alter|ryan", "ellis|paige")] == 2
    assert pairs[("alter|ryan", "pool|leslie")] == 1
    assert pairs[("ellis|paige", "pool|leslie")] == 1
    # stored unordered (a<b) — no reversed duplicate
    assert ("ellis|paige", "alter|ryan") not in pairs
