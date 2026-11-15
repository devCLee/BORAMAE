"""Formula, OLS and guard tests of the trend engine (TR-F-018, TR-F-019, TRD Q-02)."""

import dataclasses
import json
import math
from pathlib import Path

import pytest
from scipy import stats

from boramae.engine import definitions, trend
from boramae.engine.types import MkResult, OlsResult, SenResult, TrendStats

DATA = json.loads(
    Path(__file__).parent.joinpath("data", "reference_series.json").read_text("utf-8")
)
REFERENCE = {series["id"]: series for series in DATA["reference"]}
NEGATIVE_RHO1 = [series for series in DATA["reference"] if series["rho1"] < 0]
SMALL_RHO1 = REFERENCE["ref10_small_positive_rho1"]
COUNTS = REFERENCE["ref07_counts_with_ties"]
# 31 values make 465 pairs. With an odd pair count, one pair lies exactly on the Sen
# line. Float residuals lose that tie in this series, and its reverse then gets
# another rho1; an engine that keeps the tie gives both the same p.
ODD_PAIR_COUNT = DATA["odd_pair_count"]
TEN = DATA["ten_values"]
HAND = DATA["hand_six"]

# Hand statistics of the 6-value series 2, 1, 6, 8, 7, 5 in the years 2001 to 2006.
# S = 10 rising pairs - 5 falling pairs = 5.
# Sorted pairwise slopes: -2, -1.5, -1, -1, -1/3, 0.5, 0.6, 1, 1.25, 2, 2, 2, 2, 3.5, 5.
# The Sen slope is the 8th of 15, which is 1. Median value 5.5, median year 2003.5,
# so the intercept is 5.5 - 2003.5 = -1998.
# Series minus the Sen line, with the years counted from 0: 2, 0, 4, 5, 3, 0.
# Ranks with the tie averaged: 3, 1.5, 5, 6, 4, 1.5. Their mean is 3.5.
# Deviations: -0.5, -2, 1.5, 2.5, 0.5, -2. Sum of squares 17, lag-1 sum of products 2.
# rho1 = 2/17.
# Var(S) = 6 x 5 x 17 / 18 = 85/3. Var*(S) = 85/3 x (1 + 2 x 3/6 x 2/17) = 95/3.
# Z = (5 - 1) / sqrt(95/3) = 0.710819, and p = 2 x (1 - Phi(Z)) = 0.477197.
# Sen ranks: C = 1.959964 x sqrt(95/3) = 11.029. (15 - C)/2 = 1.99 and
# (15 + C)/2 + 1 = 14.01, so the bounds are the 2nd and the 14th slope.
HAND_MK = {
    "s": 5.0,
    "var_s": 85 / 3,
    "rho1": 2 / 17,
    "var_star": 95 / 3,
    "z": 0.7108186533109109,
    "p": 0.4771966199887701,
}
HAND_SEN = {"slope": 1.0, "intercept": -1998.0, "ci_low": -1.5, "ci_high": 3.5}
HAND_RANKS = (2, 14)

# OLS inputs of the adjustment tests.
N = 30
SLOPE = 0.5
SE = 0.1
T_PLAIN = stats.t.ppf(0.975, N - 2)

EDGE_SERIES = {
    "constant": [4.0] * 8,
    "exact_line": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    "line_with_rounding_noise": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
    "two_levels": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
    "minimum_length": [1.0, 3.0, 2.0],
}


def years_for(values):
    return list(range(2001, 2001 + len(values)))


def mk_of(series):
    return trend.mk_test(series["values"], series["years"])


def non_finite_numbers(result):
    numbers = [
        *dataclasses.astuple(result.mk),
        *dataclasses.astuple(result.sen),
        *dataclasses.astuple(result.ols)[:-1],
    ]
    return [x for x in numbers if x is not None and not math.isfinite(x)]


@pytest.mark.parametrize(("field", "expected"), HAND_MK.items(), ids=HAND_MK.keys())
def test_mann_kendall_of_the_hand_series_equals_the_hand_value(field, expected):
    assert getattr(mk_of(HAND), field) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize(("field", "expected"), HAND_SEN.items(), ids=HAND_SEN.keys())
def test_sen_line_of_the_hand_series_equals_the_hand_value(field, expected):
    result = trend.trend_stats(HAND["values"], HAND["years"])
    assert getattr(result.sen, field) == pytest.approx(expected, rel=1e-12)


def test_sen_ranks_of_the_hand_series_equal_the_hand_ranks():
    assert trend.sen_rank_bounds(15, 95 / 3) == HAND_RANKS


def test_sen_ranks_stay_inside_1_to_the_pair_count():
    # 3 values: Var(S) = 11/3, C = 3.75, raw ranks -0.38 and 4.38.
    assert trend.sen_rank_bounds(3, 11 / 3) == (1, 3)


@pytest.mark.parametrize(
    ("var_s", "n", "rho1", "expected"),
    [(100.0, 20, 0.05, 108.5), (100.0, 20, -0.3, 100.0), (100.0, 3, 0.9, 100.0)],
    ids=["positive_rho1", "negative_rho1", "three_values"],
)
def test_corrected_variance_equals_the_prd_formula(var_s, n, rho1, expected):
    assert trend.corrected_variance(var_s, n, rho1) == pytest.approx(expected)


def test_positive_rho1_puts_the_corrected_variance_above_the_plain_one():
    assert mk_of(TEN).var_star > mk_of(TEN).var_s


def test_a_small_positive_rho1_inflates_the_variance_with_no_significance_screen():
    n = len(SMALL_RHO1["values"])
    expected = 1 + 2 * (n - 3) / n * SMALL_RHO1["rho1"]
    mk = mk_of(SMALL_RHO1)
    assert mk.var_star / mk.var_s == pytest.approx(expected)


@pytest.mark.parametrize("series", NEGATIVE_RHO1, ids=[s["id"] for s in NEGATIVE_RHO1])
def test_negative_rho1_never_shrinks_the_variance(series):
    assert mk_of(series).var_star == mk_of(series).var_s


def test_s_of_0_gives_p_of_1():
    assert trend.mk_test([1.0, 3.0, 0.0, 2.0], [2001, 2002, 2003, 2004]).p == 1.0


@pytest.mark.parametrize(
    "transform",
    [lambda values: [-value for value in values], lambda values: values[::-1]],
    ids=["negative", "reverse"],
)
def test_p_is_the_same_for_a_series_its_negative_and_its_reverse(transform):
    values, years = ODD_PAIR_COUNT["values"], ODD_PAIR_COUNT["years"]
    expected = trend.mk_test(values, years).p
    actual = trend.mk_test(transform(values), years).p
    assert actual == pytest.approx(expected, rel=1e-9)


def test_var_s_of_a_tied_series_has_no_tie_term():
    assert mk_of(COUNTS).var_s == pytest.approx(44 * 43 * 93 / 18)


def test_sen_interval_of_the_result_uses_the_corrected_variance():
    result = trend.trend_stats(TEN["values"], TEN["years"])
    expected = trend.sen_interval(TEN["values"], TEN["years"], result.mk.var_star)
    assert (result.sen.ci_low, result.sen.ci_high) == expected


def test_sen_interval_is_wider_with_the_corrected_variance_than_without():
    mk = mk_of(TEN)
    low_star, high_star = trend.sen_interval(TEN["values"], TEN["years"], mk.var_star)
    low, high = trend.sen_interval(TEN["values"], TEN["years"], mk.var_s)
    assert high_star - low_star > high - low


def test_adjusted_interval_equals_the_plain_one_when_r1_is_0():
    _, _, low, high, _ = trend.ols_adjust(SLOPE, SE, N, 0.0)
    assert (low, high) == pytest.approx((SLOPE - T_PLAIN * SE, SLOPE + T_PLAIN * SE))


def test_adjusted_p_equals_the_plain_t_test_when_r1_is_0():
    expected = 2 * stats.t.sf(SLOPE / SE, N - 2)
    assert trend.ols_adjust(SLOPE, SE, N, 0.0)[1] == pytest.approx(expected)


def test_adjusted_half_width_ratio_equals_the_hand_value_when_r1_is_03():
    n_eff = N * 0.7 / 1.3
    expected = (
        math.sqrt((N - 2) / (n_eff - 2)) * stats.t.ppf(0.975, n_eff - 2) / T_PLAIN
    )
    _, _, low, high, _ = trend.ols_adjust(SLOPE, SE, N, 0.3)
    assert (high - low) / 2 / (T_PLAIN * SE) == pytest.approx(expected)


def test_n_eff_has_no_cap_when_r1_is_negative():
    assert trend.ols_adjust(SLOPE, SE, N, -0.3)[0] == pytest.approx(N * 1.3 / 0.7)


# n_eff is 1.76 for (10, 0.7) and exactly 2 for (6, 0.5).
OUT_OF_RANGE = pytest.mark.parametrize(
    ("n", "r1"),
    [(10, 0.7), (6, 0.5), (30, 1.0), (30, -1.0), (30, 1.2)],
    ids=["n_eff_below_2", "n_eff_of_2", "r1_of_1", "r1_of_minus_1", "r1_above_1"],
)


@OUT_OF_RANGE
def test_adjusted_p_is_empty_when_n_eff_is_out_of_range(n, r1):
    assert trend.ols_adjust(SLOPE, SE, n, r1)[1] is None


@OUT_OF_RANGE
def test_adjusted_ols_names_the_reason_when_n_eff_is_out_of_range(n, r1):
    assert trend.ols_adjust(SLOPE, SE, n, r1)[4] == "n_eff_out_of_range"


def test_constant_series_has_no_ols_p():
    values = EDGE_SERIES["constant"]
    assert trend.ols_trend(values, years_for(values)).p_plain is None


def test_constant_series_names_the_reason_for_the_missing_ols_p():
    values = EDGE_SERIES["constant"]
    assert trend.ols_trend(values, years_for(values)).reason == "constant_series"


def test_exact_line_has_an_ols_p_of_0():
    values = EDGE_SERIES["exact_line"]
    assert trend.ols_trend(values, years_for(values)).p_plain == 0.0


@pytest.mark.parametrize("values", EDGE_SERIES.values(), ids=EDGE_SERIES.keys())
def test_no_statistic_is_nan_or_infinite(values):
    assert non_finite_numbers(trend.trend_stats(values, years_for(values))) == []


def test_the_minimum_number_of_values_gives_statistics():
    values = EDGE_SERIES["minimum_length"]
    assert trend.trend_stats(values, years_for(values)).reason is None


def test_fewer_values_than_the_minimum_give_empty_statistics():
    expected = TrendStats(
        n=2,
        first_year=2001,
        last_year=2002,
        mk=MkResult(*[None] * 6),
        sen=SenResult(*[None] * 4),
        ols=OlsResult(*[None] * 10, reason="too_few_values"),
        reason="too_few_values",
    )
    assert trend.trend_stats([1.0, 2.0], [2001, 2002]) == expected


def test_no_values_give_no_years():
    result = trend.trend_stats([], [])
    assert (result.n, result.first_year, result.last_year) == (0, None, None)


def test_z_has_no_continuity_correction_when_the_switch_is_off(monkeypatch):
    monkeypatch.setattr(definitions, "Q02_2_MK_CONTINUITY_CORRECTION", False)
    assert mk_of(HAND).z == pytest.approx(5 / math.sqrt(95 / 3))


def test_var_s_subtracts_the_tie_term_when_the_switch_is_on(monkeypatch):
    monkeypatch.setattr(definitions, "Q02_3_VAR_S_TIE_TERM", True)
    # 1, 1, 2 holds one tie of 2 values: (3 x 2 x 11 - 2 x 1 x 9) / 18 = 8/3.
    assert trend.mk_variance([1.0, 1.0, 2.0]) == pytest.approx(8 / 3)


def test_an_unbuilt_rank_rounding_is_refused(monkeypatch):
    monkeypatch.setattr(definitions, "Q02_4_SEN_RANK_ROUNDING", "outward")
    with pytest.raises(KeyError):
        trend.sen_rank_bounds(15, 95 / 3)


def test_n_eff_stops_at_the_cap_when_one_is_set(monkeypatch):
    monkeypatch.setattr(definitions, "NEFF_CAP", float(N))
    assert trend.ols_adjust(SLOPE, SE, N, -0.3)[0] == float(N)


# C = 1.644854 x sqrt(95/3) = 9.256. (15 - C)/2 = 2.87 and (15 + C)/2 + 1 = 13.13.
def test_sen_ranks_follow_the_interval_level(monkeypatch):
    monkeypatch.setattr(definitions, "CI_LEVEL", 0.90)
    assert trend.sen_rank_bounds(15, 95 / 3) == (3, 13)


def test_adjusted_ols_interval_follows_the_interval_level(monkeypatch):
    monkeypatch.setattr(definitions, "CI_LEVEL", 0.90)
    _, _, low, high, _ = trend.ols_adjust(SLOPE, SE, N, 0.0)
    assert high - low == pytest.approx(2 * stats.t.ppf(0.95, N - 2) * SE)


def test_fewer_values_than_the_minimum_give_a_reason(monkeypatch):
    monkeypatch.setattr(definitions, "MIN_STAT_VALUES", 4)
    result = trend.trend_stats([1.0, 3.0, 2.0], [2001, 2002, 2003])
    assert result.reason == "too_few_values"
