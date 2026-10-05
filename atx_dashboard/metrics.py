"""Pure helpers for the dashboard (no DB, no deps): ranking + district validation."""
from __future__ import annotations


def district_or_none(value) -> int | None:
    """Parse a council-district value to an int in 1..10, else None.

    Incident payloads carry council_district as text; some rows have blanks,
    '0', or non-numeric sentinels. Those map to None (excluded from district
    aggregates, counted separately as 'district unknown').
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s.isdigit():
        return None
    n = int(s)
    return n if 1 <= n <= 10 else None


def rank_and_percentile(rows: list[dict]) -> list[dict]:
    """Add `rank` (1 = highest incident_count) and `percentile` (0..100) to each row.

    Input rows each have at least `incident_count`. Returns NEW dicts (inputs
    untouched), preserving input order. Ties share the lower rank number.
    """
    if not rows:
        return []
    counts = sorted({r["incident_count"] for r in rows}, reverse=True)
    rank_of = {c: i + 1 for i, c in enumerate(counts)}
    lo, hi = min(counts), max(counts)
    span = hi - lo
    out = []
    for r in rows:
        c = r["incident_count"]
        pct = 100.0 if span == 0 else round((c - lo) / span * 100, 1)
        out.append({**r, "rank": rank_of[c], "percentile": pct})
    return out
