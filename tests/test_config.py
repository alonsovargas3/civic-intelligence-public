from atx_ingest.config import load_settings

# Sources whose raw_* tables are archived to NAS and must never be re-ingested
# into the resident DB (the four bulk incident sets + the already-offloaded ones).
OFFLOADED = {
    "fdj4-gpfu",   # crime_reports
    "xwdj-i9he",   # austin_311
    "y2wy-tgr5",   # traffic_crashes
    "6wtj-zbtb",   # code_cases
    "3syk-w9eu",   # construction_permits (33 GB if resurrected)
    "8c6z-qnmj",   # afo_checkbook
    "3kfv-biw6",   # campaign_contributions
}


def test_offloaded_sources_are_disabled():
    by_id = {s.dataset_id: s for s in load_settings().sources}
    for ds in OFFLOADED:
        assert ds in by_id, f"{ds} missing from sources.yaml"
        assert by_id[ds].enabled is False, f"{ds} must be enabled: false (offloaded)"


def test_small_live_source_stays_enabled():
    by_id = {s.dataset_id: s for s in load_settings().sources}
    assert by_id["3c89-i35a"].enabled is True   # council_votes — served live, keep polling
