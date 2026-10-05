import hashlib
from pathlib import Path

from atx_ingest.tcad.acquire import sha256_file
from atx_ingest.tcad.layouts import load_layout
from atx_ingest.tcad.parse import parse_fixed_width, iter_records
from atx_ingest.tcad.db import owner_token, row_hash, split_record, DDL
from atx_ingest.tcad.load import derive_parcel, derive_parcel_value
from atx_ingest.tcad.geo import feature_to_row, DEFAULT_URL, GEO_FIELDS, ArcgisClient, load_parcel_geo

TCAD_DDL = DDL  # alias used by the view test


def test_sha256_file(tmp_path):
    p = tmp_path / "x.txt"
    p.write_bytes(b"hello tcad")
    assert sha256_file(str(p)) == hashlib.sha256(b"hello tcad").hexdigest()


def _mini_layout():
    # 1-indexed inclusive ranges; total width 20
    return {
        "record_length": 20,
        "encoding": "latin-1",
        "fields": [
            {"name": "acct", "start": 1, "end": 5, "type": "int"},
            {"name": "yr", "start": 6, "end": 9, "type": "int"},
            {"name": "name", "start": 10, "end": 20, "type": "str"},
        ],
    }


def test_parse_fixed_width_slices_and_types():
    line = "00042" + "2025" + "SMITH JOHN "  # 5 + 4 + 11 = 20
    rec = parse_fixed_width(line, _mini_layout())
    assert rec["acct"] == 42            # int, leading zeros stripped
    assert rec["yr"] == 2025
    assert rec["name"] == "SMITH JOHN"  # str, right-trimmed


def test_parse_fixed_width_blank_int_is_none():
    line = "     " + "    " + "           "  # all spaces, width 20
    rec = parse_fixed_width(line, _mini_layout())
    assert rec["acct"] is None
    assert rec["yr"] is None
    assert rec["name"] == ""


def test_iter_records_reads_lines(tmp_path):
    p = tmp_path / "mini.txt"
    p.write_text("000012025ALICE      \n000022024BOB        \n", encoding="latin-1")
    recs = list(iter_records(str(p), _mini_layout()))
    assert len(recs) == 2
    assert recs[0]["acct"] == 1 and recs[0]["name"] == "ALICE"
    assert recs[1]["acct"] == 2 and recs[1]["yr"] == 2024


def test_real_property_layout_loads():
    lay = load_layout("property")
    assert lay["layout_version"] == "legacy_8.0.32"
    names = {f["name"] for f in lay["fields"]}
    assert {"prop_id", "sup_num", "py_owner_name", "appraised_val"} <= names


def test_owner_token_stable_and_pii_free():
    t1 = owner_token("Smith, John", {"line1": "100 Main St", "city": "Austin", "zip": "78701"})
    t2 = owner_token("Smith, John", {"line1": "100 Main St", "city": "Austin", "zip": "78701"})
    assert t1 == t2                      # deterministic
    assert "Smith" not in t1             # it's a hash, not the name
    assert len(t1) == 64                 # sha256 hex


def test_split_record_separates_pii_from_payload():
    rec = {
        "prop_id": 42, "prop_val_yr": 2025, "sup_num": 0,
        "py_owner_id": 7, "py_owner_name": "SMITH JOHN",
        "py_addr_line1": "100 MAIN ST", "py_addr_city": "AUSTIN",
        "py_addr_state": "TX", "py_addr_zip": "78701",
        "appraised_val": 500000, "assessed_val": 450000,
    }
    owner, payload = split_record(rec)
    assert owner["owner_name_raw"] == "SMITH JOHN"
    assert owner["mail_addr"]["city"] == "AUSTIN"
    assert "py_owner_name" not in payload
    assert "py_addr_line1" not in payload
    assert payload["appraised_val"] == 500000
    assert payload["prop_id"] == 42


def test_row_hash_changes_with_content():
    a = row_hash({"prop_id": 1, "assessed_val": 100})
    b = row_hash({"prop_id": 1, "assessed_val": 200})
    assert a != b
    assert a == row_hash({"assessed_val": 100, "prop_id": 1})  # key order independent


def test_ddl_has_all_spec_tables():
    for t in ("tcad_roll_load", "raw_tcad_roll", "tcad_owner", "parcel", "parcel_value"):
        assert t in DDL


def test_derive_parcel_value_maps_fields():
    payload = {
        "prop_id": 42, "prop_val_yr": 2025,
        "land_hstd_val": 100, "land_non_hstd_val": 50,
        "imprv_hstd_val": 300, "imprv_non_hstd_val": 0,
        "market_value": 500, "appraised_val": 450,
        "assessed_val": 440, "ten_percent_cap": 10,
    }
    pv = derive_parcel_value(payload, roll_year=2025, roll_stage="certified",
                             owner_token="abc")
    assert pv["account_id"] == "42"
    assert pv["land_value"] == 150          # hstd + non_hstd
    assert pv["improvement_value"] == 300
    assert pv["market_value"] == 500
    assert pv["appraised_value"] == 450
    assert pv["assessed_value"] == 440
    assert pv["capped_value"] == 10
    assert pv["roll_stage"] == "certified"
    assert pv["owner_token"] == "abc"


def test_derive_parcel_maps_identity():
    payload = {
        "prop_id": 42, "geo_id": "0000000042",
        "situs_street": "100 MAIN ST", "situs_city": "AUSTIN", "situs_zip": "78701",
        "legal_desc": "LOT 1 BLK A", "land_state_cd": "A1", "legal_acreage": 5,
    }
    par = derive_parcel(payload, roll_year=2025)
    assert par["account_id"] == "42"
    assert par["geo_id"] == "0000000042"
    assert par["situs"]["street"] == "100 MAIN ST"
    assert par["legal"] == "LOT 1 BLK A"
    assert par["category"] == "A1"
    assert par["acreage"] == 5
    assert par["first_seen"] == 2025 and par["last_seen"] == 2025


def test_view_in_ddl():
    assert "parcel_value_current" in TCAD_DDL


def test_cli_parses_load_prop_args():
    from atx_ingest.tcad.cli import build_parser
    args = build_parser().parse_args(
        ["load-prop", "/tmp/PROP.TXT", "--year", "2025", "--stage", "certified"]
    )
    assert args.cmd == "load-prop"
    assert args.path == "/tmp/PROP.TXT"
    assert args.year == 2025
    assert args.stage == "certified"


def test_iter_records_warns_on_wrong_length(tmp_path, caplog):
    import logging
    layout = {
        "record_length": 20,
        "encoding": "latin-1",
        "fields": [{"name": "acct", "start": 1, "end": 5, "type": "int"}],
    }
    p = tmp_path / "bad.txt"
    # first line correct width (20), second line short (10) -> should warn once
    p.write_text("00001" + " " * 15 + "\n" + "00002    \n", encoding="latin-1")
    with caplog.at_level(logging.WARNING, logger="atx.tcad.parse"):
        recs = list(iter_records(str(p), layout))
    assert len(recs) == 2                      # still yields all rows
    assert recs[0]["acct"] == 1 and recs[1]["acct"] == 2
    assert any("length" in r.message.lower() for r in caplog.records)


def test_iter_records_no_warn_when_lengths_match(tmp_path, caplog):
    import logging
    layout = {
        "record_length": 20,
        "encoding": "latin-1",
        "fields": [{"name": "acct", "start": 1, "end": 5, "type": "int"}],
    }
    p = tmp_path / "good.txt"
    p.write_text("00001" + " " * 15 + "\n", encoding="latin-1")
    with caplog.at_level(logging.WARNING, logger="atx.tcad.parse"):
        list(iter_records(str(p), layout))
    assert not [r for r in caplog.records if "length" in r.message.lower()]


class _FakeCursor:
    """Records every execute() and returns scripted fetchone() values in order."""
    def __init__(self, fetch_queue):
        self.fetch_queue = list(fetch_queue)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return self.fetch_queue.pop(0)


def test_load_skips_when_prior_load_completed(tmp_path):
    from atx_ingest.tcad import load as load_mod
    f = tmp_path / "PROP.TXT"
    f.write_text("x", encoding="latin-1")
    # existing row with completed_at NOT NULL -> skip
    conn = _FakeCursor([(7, "2026-01-01T00:00:00")])
    out = load_mod.load_prop_file(conn, str(f), 2025, "certified")
    assert out == {"skipped": True, "roll_load_id": 7}
    # only the lookup SELECT ran; no INSERT/DELETE
    assert len(conn.calls) == 1
    assert conn.calls[0][0].startswith("SELECT roll_load_id, completed_at")


def test_load_clears_incomplete_prior_then_reloads(tmp_path):
    from atx_ingest.tcad import load as load_mod
    f = tmp_path / "PROP.TXT"
    # one valid PROP record line padded to the layout width (9247)
    line = ("000000900008" + "R    " + "02025" + "000000000000").ljust(9247)
    f.write_text(line + "\n", encoding="latin-1")
    # fetch queue: (1) lookup -> incomplete prior load id=3; (2) INSERT ... RETURNING -> new id=9
    conn = _FakeCursor([(3, None), (9,)])
    out = load_mod.load_prop_file(conn, str(f), 2025, "certified")
    sqls = [c[0] for c in conn.calls]
    # incomplete prior load is deleted from all three tables before reinsert
    assert any(s.startswith("DELETE FROM raw_tcad_roll") for s in sqls)
    assert any(s.startswith("DELETE FROM tcad_owner") for s in sqls)
    assert any(s.startswith("DELETE FROM tcad_roll_load") for s in sqls)
    # a fresh provenance row was inserted, and completed_at is set at the end
    assert any("INSERT INTO tcad_roll_load" in s for s in sqls)
    assert any("completed_at=now()" in s for s in sqls)
    assert out["skipped"] is False and out["roll_load_id"] == 9 and out["raw_rows"] == 1


def test_parcel_geo_in_ddl():
    assert "parcel_geo" in DDL
    # keyed on account_id, geometry stored as jsonb with an explicit srid
    assert "account_id text PRIMARY KEY" in DDL
    assert "geom       jsonb" in DDL or "geom jsonb" in DDL


def _geo_feature():
    return {
        "type": "Feature",
        "properties": {
            "PROP_ID": 900001,  # synthetic placeholder parcel
            "geo_id": "0000000001",
            "tcad_acres": 0.25,
            "situs_address": "100 EXAMPLE CV 78701",
        },
        "geometry": {"type": "Polygon",
                     "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
    }


def test_feature_to_row_maps_fields():
    row = feature_to_row(_geo_feature(), srid=2277)
    assert row["account_id"] == "900001"      # PROP_ID coerced to str
    assert row["geo_id"] == "0000000001"
    assert row["acres"] == 0.25
    assert row["situs"] == "100 EXAMPLE CV 78701"
    assert row["srid"] == 2277
    assert row["geom"]["type"] == "Polygon"   # geometry passed through as GeoJSON


def test_feature_to_row_skips_when_no_prop_id():
    f = _geo_feature()
    f["properties"]["PROP_ID"] = None
    assert feature_to_row(f, srid=2277) is None
    del f["properties"]["PROP_ID"]
    assert feature_to_row(f, srid=2277) is None


def test_geo_constants():
    assert DEFAULT_URL.endswith("/MapServer/0")
    assert "PROP_ID" in GEO_FIELDS and "geo_id" in GEO_FIELDS


def test_arcgis_first_page_params():
    c = ArcgisClient("https://x/MapServer/0")
    calls = []
    # fake _get records params and returns one short page (no exceededTransferLimit) -> stops
    c._get = lambda url, params: (calls.append((url, params))
                                  or {"features": [{"properties": {"PROP_ID": 1}}]})
    feats = list(c.fetch_features(out_fields="PROP_ID,geo_id", page_size=2000))
    assert len(feats) == 1
    url, params = calls[0]
    assert url.endswith("/MapServer/0/query")
    assert params["where"] == "1=1"
    assert params["f"] == "geojson"
    assert params["outFields"] == "PROP_ID,geo_id"
    assert params["resultOffset"] == 0
    assert params["resultRecordCount"] == 2000


def test_arcgis_paginates_until_short_page():
    c = ArcgisClient("https://x/MapServer/0")
    # page 1: full (2 feats) + exceededTransferLimit -> continue; page 2: 1 feat, no flag -> stop
    pages = [
        {"features": [{"properties": {"PROP_ID": 1}}, {"properties": {"PROP_ID": 2}}],
         "exceededTransferLimit": True},
        {"features": [{"properties": {"PROP_ID": 3}}]},
    ]
    offsets = []
    def fake_get(url, params):
        offsets.append(params["resultOffset"])
        return pages.pop(0)
    c._get = fake_get
    feats = list(c.fetch_features(out_fields="PROP_ID", page_size=2))
    assert [f["properties"]["PROP_ID"] for f in feats] == [1, 2, 3]
    assert offsets == [0, 2]          # advanced by page_size after a full+flagged page


def test_load_parcel_geo_upserts_each_feature(monkeypatch):
    import atx_ingest.tcad.geo as geo_mod

    features = [
        {"properties": {"PROP_ID": 1, "geo_id": "a", "tcad_acres": 0.5,
                        "situs_address": "1 MAIN"},
         "geometry": {"type": "Polygon", "coordinates": [[[0, 0]]]}},
        {"properties": {"PROP_ID": None}},          # skipped (no PROP_ID)
        {"properties": {"PROP_ID": 2, "geo_id": "b"},
         "geometry": {"type": "Polygon", "coordinates": [[[1, 1]]]}},
    ]
    # stub the client so no network is touched
    monkeypatch.setattr(geo_mod.ArcgisClient, "fetch_features",
                        lambda self, **kw: iter(features))

    conn = _FakeCursor([])               # load_parcel_geo issues only execute() (no fetchone)
    summary = geo_mod.load_parcel_geo(conn, base_url="https://x/MapServer/0", srid=2277)

    assert summary == {"rows": 2, "skipped": 1}
    upserts = [c for c in conn.calls if c[0].startswith("INSERT INTO parcel_geo")]
    assert len(upserts) == 2
    assert "ON CONFLICT (account_id) DO UPDATE" in upserts[0][0]
    # account_id is the stringified PROP_ID
    assert upserts[0][1]["account_id"] == "1"
    assert upserts[1][1]["account_id"] == "2"


def test_cli_parses_load_geo_args():
    from atx_ingest.tcad.cli import build_parser
    args = build_parser().parse_args(["load-geo", "--url", "https://x/MapServer/0"])
    assert args.cmd == "load-geo"
    assert args.url == "https://x/MapServer/0"
    # url is optional (defaults to None -> loader uses DEFAULT_URL)
    args2 = build_parser().parse_args(["load-geo"])
    assert args2.url is None


def test_cli_parses_acquire_args():
    from atx_ingest.tcad.cli import build_parser
    args = build_parser().parse_args(
        ["acquire", "--url", "https://traviscad.org/x.zip",
         "--year", "2025", "--stage", "certified", "--workdir", "/tmp/t"]
    )
    assert args.cmd == "acquire"
    assert args.url == "https://traviscad.org/x.zip"
    assert args.year == 2025
    assert args.stage == "certified"
    assert args.workdir == "/tmp/t"


def test_cli_acquire_workdir_default():
    from atx_ingest.tcad.cli import build_parser
    args = build_parser().parse_args(
        ["acquire", "--url", "https://traviscad.org/x.zip",
         "--year", "2025", "--stage", "certified"]
    )
    assert args.workdir == "data/tcad"


def test_acquire_prop_file_orchestration(tmp_path, monkeypatch):
    """acquire_prop_file chains download -> unzip -> find_prop_file (no network)."""
    from atx_ingest.tcad import acquire as acq

    calls = {}
    fake_zip = tmp_path / "export.zip"
    fake_zip.write_text("zip", encoding="latin-1")
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    prop = extracted / "PROP.TXT"
    prop.write_text("data", encoding="latin-1")

    def fake_download(url, dest, **kw):
        calls["url"] = url
        return str(fake_zip)

    def fake_unzip(zip_path, dest_dir):
        calls["zip"] = zip_path
        return str(extracted)

    def fake_find(d):
        calls["dir"] = d
        return str(prop)

    monkeypatch.setattr(acq, "download_export", fake_download)
    monkeypatch.setattr(acq, "unzip", fake_unzip)
    monkeypatch.setattr(acq, "find_prop_file", fake_find)

    out = acq.acquire_prop_file("https://traviscad.org/x.zip", str(tmp_path))
    assert out == str(prop)
    assert calls["url"] == "https://traviscad.org/x.zip"
    assert calls["zip"] == str(fake_zip)
    assert calls["dir"] == str(extracted)


def test_check_host_allows_traviscad():
    from atx_ingest.tcad.acquire import check_host
    # traviscad.org and subdomains are allowed; returns None (no raise)
    check_host("https://traviscad.org/wp-content/largefiles/x.zip")
    check_host("https://www.traviscad.org/x.zip")


def test_check_host_rejects_other_hosts():
    import pytest as _pytest
    from atx_ingest.tcad.acquire import check_host
    for bad in ("https://evil.example.com/x.zip", "http://traviscad.org.evil.com/x.zip",
                "https://nottraviscad.org/x.zip"):
        with _pytest.raises(ValueError):
            check_host(bad)


def test_check_host_bypass_with_allow_any():
    from atx_ingest.tcad.acquire import check_host
    # explicit override does not raise
    check_host("https://evil.example.com/x.zip", allow_any_host=True)


def test_safe_extract_blocks_path_traversal(tmp_path):
    import zipfile
    import pytest as _pytest
    from atx_ingest.tcad.acquire import unzip
    # craft a zip whose member escapes the extraction dir
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("../escape.txt", "pwned")
    dest = tmp_path / "out"
    with _pytest.raises(ValueError):
        unzip(str(zpath), str(dest))
    # the traversal target was NOT written outside dest
    assert not (tmp_path / "escape.txt").exists()


def test_safe_extract_allows_normal_members(tmp_path):
    import zipfile
    from atx_ingest.tcad.acquire import unzip
    zpath = tmp_path / "good.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("PROP.TXT", "data")
        z.writestr("sub/OTHER.TXT", "more")
    dest = tmp_path / "out"
    unzip(str(zpath), str(dest))
    assert (dest / "PROP.TXT").read_text() == "data"
    assert (dest / "sub" / "OTHER.TXT").read_text() == "more"


def test_staging_paths_unique_per_year_stage():
    from atx_ingest.tcad.acquire import staging_paths
    zip_a, dir_a = staging_paths("data/tcad", 2025, "certified")
    zip_b, dir_b = staging_paths("data/tcad", 2024, "certified")
    zip_c, dir_c = staging_paths("data/tcad", 2025, "preliminary")
    # different (year, stage) -> different staging locations (no clobber)
    assert zip_a != zip_b and zip_a != zip_c
    assert dir_a != dir_b and dir_a != dir_c
    # the year/stage appear in the path
    assert "2025" in zip_a and "certified" in zip_a


def test_acquire_threads_year_stage_into_staging(tmp_path, monkeypatch):
    """When year+stage are given, download/extract use the per-roll staging dir."""
    from atx_ingest.tcad import acquire as acq
    seen = {}

    def fake_download(url, dest, **kw):
        seen["dest"] = dest
        return dest

    def fake_unzip(zip_path, dest_dir):
        seen["extract_dir"] = dest_dir
        return dest_dir

    monkeypatch.setattr(acq, "download_export", fake_download)
    monkeypatch.setattr(acq, "unzip", fake_unzip)
    monkeypatch.setattr(acq, "find_prop_file", lambda d: d + "/PROP.TXT")

    acq.acquire_prop_file("https://traviscad.org/x.zip", str(tmp_path),
                          year=2025, stage="certified")
    assert "2025" in seen["dest"] and "certified" in seen["dest"]
    assert "2025" in seen["extract_dir"] and "certified" in seen["extract_dir"]


def test_load_full_clean_run(tmp_path):
    """A first-time load (no prior sha) inserts into all four tables and completes."""
    from atx_ingest.tcad import load as load_mod
    f = tmp_path / "PROP.TXT"
    line = ("000000900008" + "R    " + "02025" + "000000000000").ljust(9247)
    f.write_text(line + "\n", encoding="latin-1")
    # fetch queue: (1) sha lookup -> None (no prior); (2) INSERT ... RETURNING -> id=5
    conn = _FakeCursor([None, (5,)])
    out = load_mod.load_prop_file(conn, str(f), 2025, "certified")
    sqls = [c[0] for c in conn.calls]
    assert any(s.startswith("INSERT INTO raw_tcad_roll") for s in sqls)
    assert any(s.startswith("INSERT INTO tcad_owner") for s in sqls)
    assert any(s.startswith("INSERT INTO parcel_value") for s in sqls)
    assert any(s.startswith("INSERT INTO parcel ") for s in sqls)
    assert any("completed_at=now()" in s for s in sqls)
    # no DELETE on a clean run (nothing to clear)
    assert not any(s.startswith("DELETE") for s in sqls)
    assert out == {"skipped": False, "roll_load_id": 5, "raw_rows": 1, "owner_rows": 1}


def test_ddl_adds_informational_columns():
    from atx_ingest.tcad.db import DDL
    # provenance flag on the load record + denormalized onto each value row
    assert "ALTER TABLE tcad_roll_load ADD COLUMN IF NOT EXISTS informational boolean NOT NULL DEFAULT false" in DDL
    assert "ALTER TABLE parcel_value ADD COLUMN IF NOT EXISTS informational boolean NOT NULL DEFAULT false" in DDL


def test_ddl_base_tables_have_informational():
    from atx_ingest.tcad.db import DDL
    # the base CREATE TABLEs also carry the column (fresh install needs no ALTER)
    # tcad_roll_load + parcel_value each declare informational boolean NOT NULL DEFAULT false
    assert DDL.count("informational boolean NOT NULL DEFAULT false") >= 4  # 2 CREATE + 2 ALTER


def test_view_prefers_authoritative_over_informational():
    from atx_ingest.tcad.db import DDL
    # parcel_value_current must order by informational BEFORE the stage CASE,
    # so an authoritative (false) row beats an informational (true) one for a year
    order = DDL[DDL.index("CREATE OR REPLACE VIEW parcel_value_current"):]
    order = order[:order.index(";")]
    i_inf = order.index("informational")
    i_case = order.index("CASE roll_stage")
    assert i_inf < i_case, "informational must sort before the stage CASE"


def test_derive_parcel_value_carries_informational():
    from atx_ingest.tcad.load import derive_parcel_value
    payload = {"prop_id": 42, "appraised_val": 100}
    pv = derive_parcel_value(payload, 2023, "certified", "tok", informational=True)
    assert pv["informational"] is True
    # default is authoritative
    pv2 = derive_parcel_value(payload, 2025, "certified", "tok")
    assert pv2["informational"] is False


def test_load_writes_informational_to_both_tables(tmp_path):
    from atx_ingest.tcad import load as load_mod
    f = tmp_path / "PROP.TXT"
    line = ("000000900008" + "R    " + "02023" + "000000000000").ljust(9247)
    f.write_text(line + "\n", encoding="latin-1")
    # fetch queue: (1) sha lookup -> None (no prior); (2) INSERT ... RETURNING -> id=7
    conn = _FakeCursor([None, (7,)])
    load_mod.load_prop_file(conn, str(f), 2023, "certified", informational=True)
    calls = conn.calls
    # the tcad_roll_load INSERT names the informational column and passes True
    roll_ins = [c for c in calls if c[0].startswith("INSERT INTO tcad_roll_load")]
    assert roll_ins and "informational" in roll_ins[0][0]
    assert True in roll_ins[0][1]
    # the parcel_value INSERT (named params) carries informational=True
    pv_ins = [c for c in calls if c[0].startswith("INSERT INTO parcel_value")]
    assert pv_ins and "informational" in pv_ins[0][0]
    assert pv_ins[0][1]["informational"] is True


def test_load_default_is_authoritative(tmp_path):
    from atx_ingest.tcad import load as load_mod
    f = tmp_path / "PROP.TXT"
    line = ("000000900008" + "R    " + "02025" + "000000000000").ljust(9247)
    f.write_text(line + "\n", encoding="latin-1")
    conn = _FakeCursor([None, (8,)])
    load_mod.load_prop_file(conn, str(f), 2025, "certified")  # no informational arg
    pv_ins = [c for c in conn.calls if c[0].startswith("INSERT INTO parcel_value")]
    assert pv_ins[0][1]["informational"] is False


def test_cli_load_prop_informational_flag():
    from atx_ingest.tcad.cli import build_parser
    args = build_parser().parse_args(
        ["load-prop", "/tmp/PROP.TXT", "--year", "2023", "--stage", "certified", "--informational"])
    assert args.informational is True
    # default is False
    args2 = build_parser().parse_args(
        ["load-prop", "/tmp/PROP.TXT", "--year", "2025", "--stage", "certified"])
    assert args2.informational is False


def test_cli_acquire_informational_flag():
    from atx_ingest.tcad.cli import build_parser
    args = build_parser().parse_args(
        ["acquire", "--url", "https://traviscad.org/x.zip", "--year", "2023",
         "--stage", "certified", "--informational"])
    assert args.informational is True
    args2 = build_parser().parse_args(
        ["acquire", "--url", "https://traviscad.org/x.zip", "--year", "2025", "--stage", "certified"])
    assert args2.informational is False


def test_propertyentity_layout_loads():
    from atx_ingest.tcad.layouts import load_layout
    lay = load_layout("propertyentity")
    assert lay["layout_version"] == "legacy_8.0.32"
    assert lay["record_length"] == 3081
    names = {f["name"]: (f["start"], f["end"]) for f in lay["fields"]}
    # the 5-part key + promoted fields, at the verified byte ranges
    assert names["prop_id"] == (1, 12)
    assert names["entity_id"] == (42, 53)
    assert names["entity_name"] == (64, 113)
    assert names["taxable_val"] == (164, 178)
    assert names["hs_amt"] == (299, 313)
    assert names["hs_local_amt"] == (479, 493)


def test_ddl_has_propertyentity_tables():
    from atx_ingest.tcad.db import DDL
    assert "raw_tcad_entity" in DDL
    assert "parcel_entity_value" in DDL
    assert "PRIMARY KEY (account_id, roll_year, roll_stage, owner_id, entity_id)" in DDL
    # entity table carries the informational flag (provenance-uniform with parcel_value)
    pev = DDL[DDL.index("parcel_entity_value"):]
    assert "informational boolean NOT NULL DEFAULT false" in pev[:pev.index(");")]


def test_derive_parcel_entity_value_maps_fields():
    from atx_ingest.tcad.load import derive_parcel_entity_value
    rec = {"prop_id": 900008, "prop_val_yr": 2025, "sup_num": 0, "owner_id": 9000001,
           "entity_id": 1001, "entity_cd": "01", "entity_name": "AUSTIN ISD",
           "taxable_val": 4000000, "hs_amt": 0, "hs_state_amt": None,
           "hs_local_amt": 100000, "hs_cap": None}
    row = derive_parcel_entity_value(rec, 2025, "certified", informational=True)
    assert row["account_id"] == "900008"        # str(prop_id)
    assert row["owner_id"] == "9000001"
    assert row["entity_id"] == "1001"
    assert row["entity_cd"] == "01"
    assert row["entity_name"] == "AUSTIN ISD"
    assert row["taxable_val"] == 4000000
    assert row["hs_local_amt"] == 100000
    assert row["informational"] is True
    # default is authoritative
    row2 = derive_parcel_entity_value(rec, 2025, "certified")
    assert row2["informational"] is False


def test_load_prop_ent_writes_raw_and_entity(tmp_path):
    from atx_ingest.tcad import load as load_mod
    # one valid PROP_ENT record: key in first 53 chars, entity_cd/name, taxable at 164-178
    line = list(" " * 3081)
    def put(s, e, v):
        v = str(v).rjust(e - s + 1, "0") if v.isdigit() else v.ljust(e - s + 1)
        line[s-1:e] = list(v[:e-s+1])
    put(1, 12, "900008")          # prop_id
    put(13, 17, "2025")           # prop_val_yr
    put(18, 29, "0")              # sup_num
    put(30, 41, "9000001")        # owner_id
    put(42, 53, "1001")           # entity_id
    line[53:63] = list("01".ljust(10))            # entity_cd (54-63)
    line[63:113] = list("AUSTIN ISD".ljust(50))   # entity_name (64-113)
    put(164, 178, "4000000")      # taxable_val
    f = tmp_path / "PROP_ENT.TXT"
    f.write_text("".join(line) + "\n", encoding="latin-1")
    # fetch queue: (1) sha lookup -> None; (2) INSERT tcad_roll_load RETURNING -> id=9
    conn = _FakeCursor([None, (9,)])
    out = load_mod.load_prop_ent_file(conn, str(f), 2025, "certified", informational=True)
    sqls = [c[0] for c in conn.calls]
    assert any(s.startswith("INSERT INTO raw_tcad_entity") for s in sqls)
    pev = [c for c in conn.calls if c[0].startswith("INSERT INTO parcel_entity_value")]
    assert pev and "informational" in pev[0][0]
    assert pev[0][1]["account_id"] == "900008"
    assert pev[0][1]["entity_name"] == "AUSTIN ISD"
    assert pev[0][1]["taxable_val"] == 4000000
    assert pev[0][1]["informational"] is True
    assert any("completed_at=now()" in s for s in sqls)
    assert out == {"skipped": False, "roll_load_id": 9, "raw_rows": 1, "entity_rows": 1}


def test_cli_parses_load_prop_ent_args():
    from atx_ingest.tcad.cli import build_parser
    args = build_parser().parse_args(
        ["load-prop-ent", "/tmp/PROP_ENT.TXT", "--year", "2025", "--stage", "certified"])
    assert args.cmd == "load-prop-ent"
    assert args.path == "/tmp/PROP_ENT.TXT"
    assert args.year == 2025
    assert args.stage == "certified"
    assert args.informational is False
    args2 = build_parser().parse_args(
        ["load-prop-ent", "/tmp/PROP_ENT.TXT", "--year", "2023", "--stage", "certified",
         "--informational"])
    assert args2.informational is True
