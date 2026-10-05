"""Smoke tests — no network, no database. Run: python -m pytest -q"""
from atx_ingest.config import load_settings
from atx_ingest.run import _due, _fmt_counts, _parse_ts
from atx_ingest.socrata import _soql_literal
from atx_ingest.legistar import LegistarClient, _odata_dt


def test_sources_load():
    s = load_settings()
    ids = {x.dataset_id for x in s.sources}
    assert "xwdj-i9he" in ids                       # 311
    assert all(x.primary_key == ":id" for x in s.sources if x.kind == "socrata")
    assert all(x.table.replace("_", "").isalnum() for x in s.sources)


def test_crime_has_slower_cadence():
    # Crime (fdj4-gpfu) is a full-republish dataset; it must not be re-pulled
    # every pass. Everything else defaults to "poll every pass" (0).
    by_id = {x.dataset_id: x for x in load_settings().sources}
    assert by_id["fdj4-gpfu"].min_interval_seconds >= 86400
    assert by_id["xwdj-i9he"].min_interval_seconds == 0   # 311 unchanged


def test_afo_checkbook_throttled_to_daily():
    # AFO eCheckbook (8c6z-qnmj) refreshes only ~weekly (221 distinct :updated_at),
    # so it carries the daily cadence throttle — real incrementality, just no benefit
    # to 30-min polling. (NOT a full-republish; that's crime.)
    by_id = {x.dataset_id: x for x in load_settings().sources}
    afo = by_id["8c6z-qnmj"]
    assert afo.table == "afo_checkbook"
    assert afo.min_interval_seconds >= 86400


def test_due_gates_on_interval():
    assert _due(None, 86400) is True        # never run -> always due
    assert _due(10.0, 0) is True            # no min interval -> always due
    assert _due(100.0, 86400) is False      # ran recently -> skip
    assert _due(90000.0, 86400) is True     # enough time passed -> due
    assert _due(86400.0, 86400) is True     # exactly at the boundary -> due


def test_fmt_counts_distinguishes_new_from_updated():
    # cd2: a boundary re-pull surfaces rows as "updated", not "new". The report
    # must not conflate them into one "ingested N" figure.
    assert _fmt_counts(0, 89188) == "0 new, 89188 updated"
    assert _fmt_counts(355, 1645) == "355 new, 1645 updated"
    assert _fmt_counts(0, 0) == "0 new, 0 updated"


def test_parse_ts():
    assert _parse_ts("2026-05-20T13:45:00.000") is not None
    assert _parse_ts("2026-05-20T13:45:00Z") is not None
    assert _parse_ts(None) is None
    assert _parse_ts("not-a-date") is None


def test_soql_literal_escapes_quotes():
    assert _soql_literal("2026-05-20T13:45:00.000") == "'2026-05-20T13:45:00.000'"
    # A stray apostrophe must be doubled, not allowed to terminate the literal.
    assert _soql_literal("O'Brien") == "'O''Brien'"


def test_source_kind_defaults_to_socrata():
    from atx_ingest.config import Source
    s = Source(dataset_id="xwdj-i9he", name="x", table="t")
    assert s.kind == "socrata"


def test_settings_has_legistar_defaults():
    s = load_settings()
    assert s.legistar_base == "https://webapi.legistar.com/v1"
    assert s.legistar_client == "austintexas"


def test_odata_dt_formats_and_escapes():
    assert _odata_dt("2026-01-01T00:00:00") == "datetime'2026-01-01T00:00:00'"
    assert _odata_dt("a'b") == "datetime'a''b'"


def test_legistar_first_page_no_filter_when_no_since():
    c = LegistarClient("https://webapi.legistar.com/v1", "austintexas")
    calls = []
    c._get = lambda url, params: (calls.append((url, params)) or [])
    list(c.fetch_incremental("Events", "EventLastModifiedUtc", since=None, page_size=1000))
    url, params = calls[0]
    assert url.endswith("/austintexas/Events")
    assert params["$orderby"] == "EventLastModifiedUtc,EventId"
    assert params["$top"] == 1000
    assert "$filter" not in params


def test_legistar_first_page_filter_with_since():
    c = LegistarClient("https://webapi.legistar.com/v1", "austintexas")
    calls = []
    c._get = lambda url, params: (calls.append((url, params)) or [])
    list(c.fetch_incremental("Matters", "MatterLastModifiedUtc",
                             since="2026-01-01T00:00:00", page_size=500))
    url, params = calls[0]
    assert url.endswith("/austintexas/Matters")
    assert params["$top"] == 500
    assert params["$filter"] == "MatterLastModifiedUtc ge datetime'2026-01-01T00:00:00'"


def test_legistar_keyset_second_page_seeks_past_last():
    c = LegistarClient("https://webapi.legistar.com/v1", "austintexas")
    pages = [
        [{"EventId": 1, "EventLastModifiedUtc": "2026-01-01T00:00:00"},
         {"EventId": 2, "EventLastModifiedUtc": "2026-01-02T00:00:00"}],
        [],
    ]
    calls = []
    def fake_get(url, params):
        calls.append(params)
        return pages.pop(0)
    c._get = fake_get
    list(c.fetch_incremental("Events", "EventLastModifiedUtc", since=None, page_size=2))
    assert calls[1]["$filter"] == (
        "(EventLastModifiedUtc gt datetime'2026-01-02T00:00:00' or "
        "(EventLastModifiedUtc eq datetime'2026-01-02T00:00:00' and EventId gt 2))"
    )


def test_legistar_sources_present_and_consistent():
    legi = [x for x in load_settings().sources if x.kind == "legistar"]
    assert legi, "expected council legistar sources in sources.yaml"
    by_id = {x.dataset_id for x in legi}
    assert {"Events", "Matters", "Persons", "Bodies", "EventItems"} <= by_id
    for s in legi:
        assert s.table.startswith("council_")
        assert s.min_interval_seconds >= 86400
        if s.dataset_id == "EventItems":
            assert s.primary_key == "EventItemId"
            assert s.cursor_field == "_event_last_modified"
        elif s.dataset_id == "MatterSponsors":
            assert s.primary_key == "MatterSponsorId"
            assert s.cursor_field == "_matter_last_modified"
        else:
            endpoint, pk = LegistarClient._ENTITIES[s.dataset_id]
            assert s.primary_key == pk


def test_make_client_dispatches_on_kind():
    from atx_ingest.run import _make_client
    from atx_ingest.config import Source, Settings
    from atx_ingest.socrata import SocrataClient
    st = Settings(database_url="x", socrata_domain="d", app_token=None, sources=[])
    soc = Source(dataset_id="xwdj-i9he", name="x", table="t")
    leg = Source(dataset_id="Events", name="e", table="council_events",
                 kind="legistar", primary_key="EventId",
                 cursor_field="EventLastModifiedUtc")
    assert isinstance(_make_client(soc, st), SocrataClient)
    assert isinstance(_make_client(leg, st), LegistarClient)


def test_make_client_rejects_unknown_kind():
    import pytest
    from atx_ingest.run import _make_client
    from atx_ingest.config import Source, Settings
    st = Settings(database_url="x", socrata_domain="d", app_token=None, sources=[])
    bad = Source(dataset_id="z", name="z", table="z", kind="bogus")
    with pytest.raises(ValueError):
        _make_client(bad, st)


def test_legistar_get_retries_transient_connection_drop():
    import requests
    c = LegistarClient("https://webapi.legistar.com/v1", "austintexas")
    calls = {"n": 0}

    class _Resp:
        status_code = 200
        def json(self):
            return [{"ok": True}]

    def flaky_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.ConnectionError("Remote end closed connection")
        return _Resp()

    c.session.get = flaky_get
    # a long per-matter drill must survive a transient drop, not crash the pass
    assert c._get("https://x/Matters/1/Sponsors", {}) == [{"ok": True}]
    assert calls["n"] == 2   # retried past the ConnectionError


def test_legistar_matter_sponsors_stamps_parent_lastmod():
    c = LegistarClient("https://webapi.legistar.com/v1", "austintexas")

    def fake_get(url, params):
        if url.endswith("/austintexas/Matters"):
            return [{"MatterId": 7, "MatterLastModifiedUtc": "2026-05-02T09:00:00"}]
        if url.endswith("/Matters/7/Sponsors"):
            return [{"MatterSponsorId": 200, "MatterSponsorName": "Council Member X"},
                    {"MatterSponsorId": 201, "MatterSponsorName": "Council Member Y"}]
        return []

    c._get = fake_get
    pages = list(c.fetch_incremental("MatterSponsors", "_matter_last_modified",
                                     since=None, page_size=1000))
    rows = [r for pg in pages for r in pg]
    assert {r["MatterSponsorId"] for r in rows} == {200, 201}
    assert all(r["_matter_last_modified"] == "2026-05-02T09:00:00" for r in rows)


def test_legistar_event_items_stamps_parent_lastmod():
    c = LegistarClient("https://webapi.legistar.com/v1", "austintexas")

    def fake_get(url, params):
        if url.endswith("/austintexas/Events"):
            return [{"EventId": 42, "EventLastModifiedUtc": "2026-05-01T12:00:00"}]
        if url.endswith("/Events/42/EventItems"):
            return [{"EventItemId": 100}, {"EventItemId": 101}]
        return []

    c._get = fake_get
    pages = list(c.fetch_incremental("EventItems", "_event_last_modified",
                                     since=None, page_size=1000))
    items = [it for pg in pages for it in pg]
    assert {it["EventItemId"] for it in items} == {100, 101}
    assert all(it["_event_last_modified"] == "2026-05-01T12:00:00" for it in items)
