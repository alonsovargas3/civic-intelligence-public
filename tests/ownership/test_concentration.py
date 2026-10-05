import math

from atx_ownership.concentration import hhi, shares, top_n_share


def test_shares_sum_to_one():
    s = shares([1, 1, 2])
    assert s == [0.25, 0.25, 0.5]
    assert math.isclose(sum(s), 1.0)


def test_shares_empty_and_zero_total():
    assert shares([]) == []
    assert shares([0, 0]) == [0.0, 0.0]


def test_top_n_share():
    vals = [50, 30, 15, 5]                       # total 100
    assert top_n_share(vals, 1) == 0.5           # largest alone
    assert top_n_share(vals, 2) == 0.8           # two largest
    assert top_n_share(vals, 10) == 1.0          # n beyond len -> all
    assert top_n_share([], 3) == 0.0
    assert top_n_share([0, 0], 1) == 0.0         # zero total -> 0


def test_hhi_monopoly_and_equal_split():
    # one owner holds everything -> HHI 1.0 (max concentration)
    assert hhi([42]) == 1.0
    # four equal owners -> HHI 4 * 0.25^2 = 0.25 = 1/N
    assert math.isclose(hhi([10, 10, 10, 10]), 0.25)
    # empty / zero total -> 0.0
    assert hhi([]) == 0.0
    assert hhi([0, 0]) == 0.0
