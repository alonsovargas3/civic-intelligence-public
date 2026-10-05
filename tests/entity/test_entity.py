from atx_entity.normalize import addr_key, name_kind, is_junk_addr
from atx_entity.resolve import resolve
from atx_entity.db import DDL, rows_for_write


def test_addr_key_normalizes_line1_and_zip():
    a = {"line1": "  100 Main St  ", "zip": "78701"}
    b = {"line1": "100 MAIN ST", "zip": "78701 "}
    assert addr_key(a) == addr_key(b)
    assert addr_key(a) == "100 main st|78701"


def test_addr_key_blank_when_no_line1():
    assert addr_key({"line1": "", "zip": "78701"}) == ""
    assert addr_key({}) == ""


def test_is_junk_addr():
    assert is_junk_addr("") is True
    assert is_junk_addr("REVOCABLE TRUST") is True
    assert is_junk_addr("living trust") is True
    assert is_junk_addr("100 MAIN ST") is False


def test_name_kind():
    assert name_kind("CITY OF AUSTIN") == "government"
    assert name_kind("TRAVIS COUNTY") == "government"
    assert name_kind("AUSTIN ISD") == "government"
    assert name_kind("KB HOME LONE STAR INC") == "institutional"
    assert name_kind("MILLROSE PROPERTIES TEXAS LLC") == "institutional"
    assert name_kind("SMITH FAMILY TRUST") == "institutional"
    assert name_kind("JOHN Q SMITH") == "individual"


def test_name_kind_does_not_overmatch_short_tokens():
    # bare 'CO'/'LP' as a name word must NOT make an individual look institutional
    assert name_kind("NGUYEN THI CO") == "individual"
    assert name_kind("TRAN VAN LP") == "individual"
    # but real business suffixes still classify
    assert name_kind("ACME CO LLC") == "institutional"


def test_name_kind_government_extended():
    # patterns the 2026-06-01 ownership build found mis-tagged as individual
    assert name_kind("UNITED STATES OF AMERICA") == "government"
    assert name_kind("TEXAS PUBLIC FINANCE AUTHORITY") == "government"
    assert name_kind("AUSTIN PUBLIC SCHOOLS") == "government"


def test_name_kind_institutional_extended():
    assert name_kind("SETON HEALTHCARE") == "institutional"
    assert name_kind("ST DAVIDS MEDICAL CENTER") == "institutional"
    assert name_kind("CENTRAL TEXAS HOSPITAL") == "institutional"
    assert name_kind("BROWN INVESTMENTS") == "institutional"
    assert name_kind("ACME MANAGEMENT") == "institutional"
    assert name_kind("EASTON PARK DEVELOPMENT") == "institutional"


def test_name_kind_extended_does_not_break_individuals():
    # the new multi-char terms must not catch person names
    assert name_kind("JOHN Q SMITH") == "individual"
    assert name_kind("MARIA GARCIA LOPEZ") == "individual"
    assert name_kind("TRAN VAN LP") == "individual"


def _rec(account_id, name, line1="", zip_=""):
    # helper: build an owner record dict as resolve() expects
    norm = " ".join(name.upper().replace(",", " ").replace(".", " ").split())
    return {
        "account_id": account_id,
        "owner_name_raw": name,
        "owner_name_norm": norm,
        "mail_addr": {"line1": line1, "zip": zip_},
    }


def test_resolve_links_by_exact_name():
    recs = [_rec("1", "ACME LLC", "10 A ST", "1"),
            _rec("2", "ACME LLC", "99 Z ST", "2")]   # same name, diff address
    res = resolve(recs)
    assert len(res.entities) == 1
    eid = res.parcel_links["1"].entity_id
    assert res.parcel_links["2"].entity_id == eid
    assert res.entities[eid].confidence == "strong"   # name edge
    assert res.entities[eid].n_parcels == 2


def test_resolve_links_by_shared_address():
    recs = [_rec("1", "FOO LLC", "5 SHARED ST", "78701"),
            _rec("2", "BAR LLC", "5 SHARED ST", "78701")]  # diff name, same addr
    res = resolve(recs)
    assert len(res.entities) == 1
    eid = res.parcel_links["1"].entity_id
    assert res.parcel_links["2"].entity_id == eid
    assert res.entities[eid].confidence == "review"   # address-only link


def test_resolve_transitive_bridge():
    # A-B by name, B-C by address -> all one entity
    recs = [_rec("1", "ACME LLC", "1 ST", "1"),
            _rec("2", "ACME LLC", "5 SHARED", "9"),
            _rec("3", "OTHER LLC", "5 SHARED", "9")]
    res = resolve(recs)
    assert len({pl.entity_id for pl in res.parcel_links.values()}) == 1


def test_resolve_singletons_stay_separate():
    recs = [_rec("1", "ALICE JONES", "1 ST", "1"),
            _rec("2", "BOB SMITH", "2 ST", "2")]
    res = resolve(recs)
    assert len(res.entities) == 2
    assert res.parcel_links["1"].link_type == "singleton"


def test_resolve_suppresses_hub_address():
    # 3 distinct names share one address; threshold 2 -> address is a hub, NOT merged
    recs = [_rec(str(i), f"NAME{i} LLC", "999 AGENT ST", "00000") for i in range(3)]
    res = resolve(recs, hub_threshold=2)
    assert len(res.entities) == 3            # not merged (hub suppressed)
    # the hub is recorded in links with suppressed=True
    hubs = [l for l in res.links if l.kind == "address" and l.suppressed]
    assert hubs and hubs[0].value == "999 agent st|00000"


def test_resolve_skips_junk_address():
    recs = [_rec("1", "X LLC", "REVOCABLE TRUST", "1"),
            _rec("2", "Y LLC", "REVOCABLE TRUST", "1")]   # junk addr -> no link
    res = resolve(recs)
    assert len(res.entities) == 2


def test_resolve_entity_id_deterministic():
    recs = [_rec("2", "ACME LLC"), _rec("1", "ACME LLC")]
    a = resolve(recs)
    b = resolve(list(reversed(recs)))
    # same member set -> same entity_id regardless of input order
    assert set(a.entities) == set(b.entities)


def test_ddl_has_tables():
    for t in ("dim_entity", "parcel_entity", "entity_link"):
        assert t in DDL


def test_rows_for_write_shapes(monkeypatch):
    recs = [_rec("1", "ACME LLC", "10 A ST", "1"),
            _rec("2", "ACME LLC", "99 Z ST", "2")]
    res = resolve(recs)
    ent_rows, parcel_rows, link_rows = rows_for_write(res, roll_year=2025)
    assert len(ent_rows) == 1
    e = ent_rows[0]
    assert e["roll_year"] == 2025
    assert e["canonical_name"] == "ACME LLC"
    assert e["kind"] == "institutional"
    assert e["n_parcels"] == 2
    assert set(parcel_rows[0]) == {"account_id", "entity_id", "roll_year", "link_type"}
    assert all(pr["roll_year"] == 2025 for pr in parcel_rows)


def test_cli_parses_build_args():
    from atx_entity.cli import build_parser
    args = build_parser().parse_args(["build", "--roll-year", "2025", "--hub-threshold", "30"])
    assert args.cmd == "build"
    assert args.roll_year == 2025
    assert args.hub_threshold == 30
    d = build_parser().parse_args(["build"])
    assert d.roll_year is None and d.hub_threshold == 25


def test_cli_parses_explain_args():
    from atx_entity.cli import build_parser
    args = build_parser().parse_args(["explain", "deadbeef"])
    assert args.cmd == "explain"
    assert args.entity_id == "deadbeef"
