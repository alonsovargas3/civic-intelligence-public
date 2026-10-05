"""Pure robust-statistics helpers for the anomaly layer (no DB, stdlib only).

The modified z-score is the Iglewicz-Hoaglin robust outlier statistic; the 0.6745
constant makes it comparable to a standard z under normality, so |z| >= 3.5 is the
conventional outlier cutoff.
"""
from __future__ import annotations

import statistics

_CONSTANT = 0.6745


def median(xs) -> float | None:
    """Median of xs, or None if empty."""
    xs = list(xs)
    if not xs:
        return None
    return statistics.median(xs)


def mad(xs) -> float:
    """Median absolute deviation about the median. 0.0 for empty/constant input."""
    xs = list(xs)
    if not xs:
        return 0.0
    med = statistics.median(xs)
    return statistics.median([abs(x - med) for x in xs])


def modified_z(x: float, med: float, mad_val: float) -> float:
    """Iglewicz-Hoaglin modified z-score. Returns 0.0 when mad_val == 0 (a uniform
    distribution flags nothing rather than dividing by zero)."""
    if mad_val == 0:
        return 0.0
    return _CONSTANT * (x - med) / mad_val


def percentile_rank(x: float, xs) -> float:
    """Percent of xs that are <= x, in [0, 100]."""
    xs = list(xs)
    if not xs:
        return 0.0
    return 100.0 * sum(1 for v in xs if v <= x) / len(xs)


def mix_adjusted_ratio(strata) -> float | None:
    """Indirect-standardization disparity ratio for one district (D7).

    `strata` is an iterable of (n, obs_median, metro_median) per request type:
      n            = closed-case count for that type in the district
      obs_median   = the district's median resolution days for that type
      metro_median = metro-wide median resolution days for that type (baseline)

    Returns O_d / E_d, where the shared 1/sum(n) cancels:
      O_d = sum(n * obs_median) / sum(n)   (district's mix-weighted observed pace)
      E_d = sum(n * metro_median) / sum(n) (the SAME case mix run at the metro pace)
    so the ratio is sum(n*obs) / sum(n*metro). R > 1 means the district resolves
    slower than its request mix predicts; R < 1 means faster. Because each type is
    weighted against its own metro baseline, a mix skewed toward inherently slow
    types does not by itself inflate R — that is the mix control.

    Returns None when total n == 0 or the expected denominator is 0 (no baseline).
    """
    numer = 0.0
    denom = 0.0
    for n, obs_median, metro_median in strata:
        numer += n * obs_median
        denom += n * metro_median
    if denom == 0:
        return None
    return numer / denom
