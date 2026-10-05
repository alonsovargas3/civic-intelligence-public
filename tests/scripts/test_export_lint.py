"""Offline tests for the export dek/body lint (no net, no DB)."""
from scripts.export_stories import check_registry_sync, lint_dek


def test_exact_tokens_match():
    assert lint_dek("The largest 1% of gifts supply 56% of every dollar.",
                    "the top 1% supplied 56% of funds") == []


def test_drift_is_flagged():
    # the real 60-vs-56 drift this lint exists to catch
    assert lint_dek("supply 60% of every dollar", "the top 1% supplied 56%") == ["60%"]


def test_rounding_at_dek_precision_matches():
    assert lint_dek("About 91% left alive", "the live-release rate was 90.6%") == []
    assert lint_dek("shields ~$10B of value", "a total of $10.04B is shielded") == []
    assert lint_dek("about 1.7× the complaints", "an index of 1.72× vs peers") == []


def test_rounding_does_not_mask_real_drift():
    assert lint_dek("casts 44% of all No votes", "cast 45% of every No vote") == ["44%"]


def test_money_multiplier_bignum_ratio_classes():
    body = "held $2.2M across fights; 2,630 clients; r=0.89 correlation; 2.5× more"
    assert lint_dek("$2.2M lost; 2,630 clients; r=0.89; 2.5× gap", body) == []
    assert lint_dek("$3.5M lost", body) == ["$3.5M"]


def test_years_and_single_digits_ignored():
    assert lint_dek("won 4 of 8 fights since 2016", "no numbers here at all") == []


def test_x_and_times_symbol_equivalent():
    assert lint_dek("2.5x more listings", "the gap is 2.5×") == []


def test_registry_sync_normalizes_curly_quotes():
    jsx = "slug: 'who-pays',\n    dek: 'Most money isn’t small.',"
    ok = [("who-pays", "t", "e", "Most money isn't small.", "/x", None)]
    bad = [("who-pays", "t", "e", "Most money is not small.", "/x", None)]
    assert check_registry_sync(jsx, ok) == []
    assert check_registry_sync(jsx, bad) == ["who-pays"]
