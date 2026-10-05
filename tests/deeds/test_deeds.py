from atx_deeds.normalize import legal_key, normalize_party
from atx_deeds.source import SampleSource
from atx_deeds.match import build_parcel_index, match_to_parcel
from atx_deeds.db import DDL, load_deeds


def test_legal_key_collapses_and_uppercases():
    assert legal_key("  lot 1-4   Templer Lots ") == "LOT 1-4 TEMPLER LOTS"
    assert legal_key("LOT 19-22 BLK 18 SOUTH HEIGHTS") == "LOT 19-22 BLK 18 SOUTH HEIGHTS"


def test_legal_key_strips_noise_punctuation():
    # asterisks and runs of spaces are normalized; '&' kept (it's meaningful in legals)
    assert legal_key("LOT 2-4 *  LESS 3738SF") == "LOT 2-4 LESS 3738SF"
    assert legal_key("LOTS 5-7 & 8") == "LOTS 5-7 & 8"


def test_legal_key_blank():
    assert legal_key("") == ""
    assert legal_key(None) == ""


def test_normalize_party():
    assert normalize_party("  Smith, John  ") == "SMITH JOHN"
    assert normalize_party("ACME, L.L.C.") == "ACME LLC"
    assert normalize_party(None) == ""


def test_sample_source_reads_jsonl(tmp_path):
    p = tmp_path / "deeds.jsonl"
    p.write_text(
        '{"instrument_num":"2025001","recorded_date":"2025-03-01","doc_type":"WD",'
        '"grantors":["Smith, John"],"grantees":["Doe, Jane"],'
        '"legal_desc":"LOT 1 BLK A OAKWOOD"}\n'
        '{"instrument_num":"2025002","recorded_date":"2025-03-02","doc_type":"DT",'
        '"grantors":["Acme LLC"],"grantees":["Bank NA"],"legal_desc":"LOT 2 BLK A OAKWOOD"}\n',
        encoding="utf-8",
    )
    deeds = list(SampleSource(str(p)).iter_deeds())
    assert len(deeds) == 2
    d = deeds[0]
    assert d["instrument_num"] == "2025001"
    assert d["doc_type"] == "WD"
    assert d["grantors"] == ["SMITH JOHN"]      # parties normalized
    assert d["grantees"] == ["DOE JANE"]
    assert d["legal_desc"] == "LOT 1 BLK A OAKWOOD"
    assert d["raw"]["instrument_num"] == "2025001"  # original kept under raw


def test_sample_source_skips_blank_lines(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text('\n{"instrument_num":"x","legal_desc":"LOT 1"}\n\n', encoding="utf-8")
    deeds = list(SampleSource(str(p)).iter_deeds())
    assert len(deeds) == 1
    assert deeds[0]["instrument_num"] == "x"
    assert deeds[0]["grantors"] == []           # missing fields default empty


def _parcel_rows():
    # (account_id, legal) as read from the parcel table
    return [
        ("1001", "LOT 1 BLK A OAKWOOD"),
        ("1002", "LOT 2 BLK A OAKWOOD"),
        ("1003", "LOT 19-22 BLK 18 SOUTH HEIGHTS"),
    ]


def test_build_parcel_index_keys_on_legal():
    idx = build_parcel_index(_parcel_rows())
    assert idx["exact"]["LOT 1 BLK A OAKWOOD"] == "1001"
    # subdiv/lot/block partial index present for the parseable rows
    assert ("OAKWOOD", "1", "A") in idx["partial"]


def test_match_exact_legal_is_strong():
    idx = build_parcel_index(_parcel_rows())
    deed = {"legal_desc": "LOT 1 BLK A OAKWOOD"}
    acct, conf, method = match_to_parcel(deed, idx)
    assert acct == "1001"
    assert conf == "strong"
    assert method == "legal_exact"


def test_match_partial_subdiv_lot_block_is_review():
    idx = build_parcel_index(_parcel_rows())
    # same lot/block/subdivision but extra clause -> no exact hit, partial hit
    deed = {"legal_desc": "LOT 1 BLK A OAKWOOD LESS 200 SQFT"}
    acct, conf, method = match_to_parcel(deed, idx)
    assert acct == "1001"
    assert conf == "review"
    assert method == "subdiv_lot_block"


def test_match_no_hit_returns_none():
    idx = build_parcel_index(_parcel_rows())
    deed = {"legal_desc": "LOT 99 BLK Z NOWHERE"}
    acct, conf, method = match_to_parcel(deed, idx)
    assert acct is None
    assert conf is None
    assert method == "unmatched"


def test_match_blank_legal_unmatched():
    idx = build_parcel_index(_parcel_rows())
    acct, conf, method = match_to_parcel({"legal_desc": ""}, idx)
    assert acct is None and method == "unmatched"


def test_parse_lot_range_does_not_leak_into_subdivision():
    from atx_deeds.match import _parse
    assert _parse("LOT 1-4 TEMPLER LOTS") == ("TEMPLER LOTS", "1", None)
    assert _parse("LOT 19-22 BLK 18 SOUTH HEIGHTS") == ("SOUTH HEIGHTS", "19", "18")


def test_match_range_legal_partial():
    # a deed whose range legal has an extra clause partial-matches the range parcel
    idx = build_parcel_index([("2001", "LOT 1-4 TEMPLER LOTS")])
    acct, conf, method = match_to_parcel({"legal_desc": "LOT 1-4 TEMPLER LOTS LESS 200 SQFT"}, idx)
    assert acct == "2001"
    assert conf == "review"
    assert method == "subdiv_lot_block"


class _FakeCursor:
    """Records execute() calls; returns scripted fetchall()/fetchone() values."""
    def __init__(self, fetchall_queue=None):
        self.calls = []
        self._fetchall = list(fetchall_queue or [])

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchall(self):
        return self._fetchall.pop(0) if self._fetchall else []

    def fetchone(self):
        return None


class _ListSource:
    """In-memory DeedSource for tests."""
    name = "test"
    def __init__(self, deeds):
        self._deeds = deeds
    def iter_deeds(self):
        return iter(self._deeds)


def test_ddl_has_tables_and_view():
    for obj in ("raw_deeds", "deed_parcel", "parcel_transfer_history"):
        assert obj in DDL


def test_load_deeds_upserts_and_matches():
    # parcel index returned by the first fetchall (build_parcel_index input)
    conn = _FakeCursor(fetchall_queue=[[("1001", "LOT 1 BLK A OAKWOOD")]])
    deeds = [
        {"instrument_num": "i1", "recorded_date": "2025-01-01", "doc_type": "WD",
         "grantors": ["A"], "grantees": ["B"], "legal_desc": "LOT 1 BLK A OAKWOOD",
         "raw": {"x": 1}},
        {"instrument_num": "i2", "recorded_date": "2025-01-02", "doc_type": "WD",
         "grantors": ["C"], "grantees": ["D"], "legal_desc": "LOT 99 BLK Z NOWHERE",
         "raw": {"x": 2}},
    ]
    summary = load_deeds(conn, _ListSource(deeds))
    assert summary == {"deeds": 2, "matched": 1, "unmatched": 1}
    raw_inserts = [c for c in conn.calls if c[0].startswith("INSERT INTO raw_deeds")]
    dp_inserts = [c for c in conn.calls if c[0].startswith("INSERT INTO deed_parcel")]
    assert len(raw_inserts) == 2          # both deeds land raw
    assert len(dp_inserts) == 1           # only the matched one links
    assert "ON CONFLICT (instrument_num) DO UPDATE" in raw_inserts[0][0]


def test_cli_parses_load_args():
    from atx_deeds.cli import build_parser
    args = build_parser().parse_args(["load", "--source", "sample", "/tmp/d.jsonl"])
    assert args.cmd == "load"
    assert args.source == "sample"
    assert args.path == "/tmp/d.jsonl"


def test_cli_parses_stats():
    from atx_deeds.cli import build_parser
    assert build_parser().parse_args(["stats"]).cmd == "stats"
