import math

from atx_anomaly.stats import (
    mad,
    median,
    mix_adjusted_ratio,
    modified_z,
    percentile_rank,
)


def test_median_basic_and_empty():
    assert median([3, 1, 2]) == 2
    assert median([1, 2, 3, 4]) == 2.5
    assert median([]) is None


def test_mad_basic_and_constant():
    # values 1,2,3,4,5 -> median 3 -> abs devs 2,1,0,1,2 -> MAD 1
    assert mad([1, 2, 3, 4, 5]) == 1
    # constant input -> MAD 0 (degenerate)
    assert mad([7, 7, 7]) == 0
    assert mad([]) == 0


def test_modified_z_and_zero_mad():
    # x above the median by 3 MADs: 0.6745*(x-med)/mad
    assert math.isclose(modified_z(10, med=4, mad_val=2), 0.6745 * 3)
    # negative direction
    assert modified_z(1, med=4, mad_val=2) < 0
    # MAD 0 -> 0.0, never division by zero
    assert modified_z(99, med=4, mad_val=0) == 0.0


def test_percentile_rank():
    xs = [10, 20, 30, 40]
    assert percentile_rank(30, xs) == 75.0   # 3 of 4 are <= 30
    assert percentile_rank(10, xs) == 25.0
    assert percentile_rank(40, xs) == 100.0
    assert percentile_rank(5, xs) == 0.0


# --- mix_adjusted_ratio (D7 indirect standardization) ---
# strata: iterable of (n, obs_median, metro_median) per request type.

def test_mix_adjusted_ratio_at_metro_pace_is_one():
    # Every type performed exactly at its metro median -> ratio 1.0,
    # regardless of how the district's case mix is distributed.
    strata = [(100, 5.0, 5.0), (10, 40.0, 40.0)]
    assert mix_adjusted_ratio(strata) == 1.0


def test_mix_adjusted_ratio_uniform_slowdown():
    # District runs 2x slow on every type -> ratio 2.0 independent of mix.
    strata = [(100, 10.0, 5.0), (10, 80.0, 40.0)]
    assert math.isclose(mix_adjusted_ratio(strata), 2.0)


def test_mix_adjusted_ratio_controls_for_request_mix():
    # The whole point: a district whose mix is dominated by an inherently slow
    # type is NOT flagged slow if it runs each type at the metro pace.
    slow_heavy = [(5, 5.0, 5.0), (200, 40.0, 40.0)]   # mostly the 40-day type
    fast_heavy = [(200, 5.0, 5.0), (5, 40.0, 40.0)]   # mostly the 5-day type
    # Raw mix-weighted medians differ wildly, but mix-adjusted ratio is 1.0 for both.
    assert mix_adjusted_ratio(slow_heavy) == 1.0
    assert mix_adjusted_ratio(fast_heavy) == 1.0


def test_mix_adjusted_ratio_empty_or_zero_baseline_is_none():
    assert mix_adjusted_ratio([]) is None
    assert mix_adjusted_ratio([(0, 5.0, 5.0)]) is None      # no cases
    assert mix_adjusted_ratio([(10, 5.0, 0.0)]) is None     # no metro baseline
