"""Pure ownership-concentration math (no DB, stdlib only).

Operates on a list of per-owner magnitudes within a segment (e.g. each entity's
parcel count, or each entity's total appraised value). Shares are fractions in
[0, 1]; HHI is the normalized Herfindahl-Hirschman index (sum of squared share
fractions), 1.0 for a single owner and 1/N for N equal owners.
"""
from __future__ import annotations


def shares(values) -> list[float]:
    """Each value as a fraction of the total. Empty -> []; zero total -> all 0.0."""
    values = list(values)
    if not values:
        return []
    total = sum(values)
    if total == 0:
        return [0.0 for _ in values]
    return [v / total for v in values]


def top_n_share(values, n: int) -> float:
    """Fraction of the total held by the n largest values. 0.0 if total is 0/empty."""
    values = list(values)
    total = sum(values)
    if total == 0:
        return 0.0
    return sum(sorted(values, reverse=True)[:n]) / total


def hhi(values) -> float:
    """Normalized Herfindahl-Hirschman index: sum of squared share fractions, in
    [0, 1]. 1.0 = one owner holds everything; 1/N = N equally-sized owners."""
    return sum(s * s for s in shares(values))
