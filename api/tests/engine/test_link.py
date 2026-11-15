"""Link test of a case-board arrow (TR-F-026, PRD "Earth-system context")."""

import numpy as np
import pytest

from boramae.engine.definitions import LINK_ALPHA, LINK_MIN_OVERLAP_YEARS
from boramae.engine.link import link_test
from boramae.engine.types import YearlySeries

FIRST_YEAR = 1981
N_YEARS = 40
RNG = np.random.default_rng(20261115)
NOISE_A, NOISE_B = RNG.standard_normal((2, N_YEARS))
LAG_BASE = RNG.standard_normal(N_YEARS + 1)
LAG_NOISE = RNG.standard_normal(N_YEARS)
# 0.3 per year over 40 years: without the detrending, any two series that share it
# correlate far past LINK_ALPHA.
SHARED_TREND = 0.3 * np.arange(N_YEARS)
# Two series that swing every other year in step: the lag-1 autocorrelation of each
# is about -0.9, so n_eff = 10 x (1 - 0.81) / (1 + 0.81) is about 1.3.
ALTERNATING = [1.0, -1.0] * 5
ALTERNATING_SCALED = [1.0, -1.2, 0.8, -1.1, 0.9, -1.0, 1.3, -0.7, 1.0, -1.1]


def yearly(values, first_year=FIRST_YEAR, metric_used=""):
    years = tuple(range(first_year, first_year + len(values)))
    return YearlySeries(
        years, tuple(float(v) for v in values), (False,) * len(values), metric_used
    )


DRIVER = yearly(NOISE_A + SHARED_TREND)
# The response follows the driver year by year (r about 0.95).
STRONG = yearly(NOISE_A + 0.3 * NOISE_B + SHARED_TREND)
# The response shares the trend and follows the driver only a little (r about 0.09).
WEAK = yearly(0.2 * NOISE_A + NOISE_B + SHARED_TREND)
TREND_ONLY = yearly(NOISE_B + SHARED_TREND)
# The response of year t is the driver of year t - 1 plus noise.
LAG_DRIVER = yearly(LAG_BASE[1:])
LAG_RESPONSE = yearly(LAG_BASE[:-1] + 0.3 * LAG_NOISE)


@pytest.mark.parametrize(
    ("response", "expected_sign", "label"),
    [
        (STRONG, "+", "consistent"),
        (WEAK, "+", "weak"),
        (STRONG, "-", "contradicts"),
        (WEAK, "-", None),
    ],
    ids=["consistent", "weak", "contradicts", "opposite_not_significant"],
)
def test_label_follows_the_expected_sign_and_the_significance(
    response, expected_sign, label
):
    assert link_test(DRIVER, response, 0, expected_sign).label == label


@pytest.mark.parametrize("field", ["r", "p", "n_eff", "sign"])
def test_opposite_sign_that_is_not_significant_keeps_its_numbers(field):
    assert getattr(link_test(DRIVER, WEAK, 0, "-"), field) is not None


def test_shared_trend_alone_is_not_significant():
    assert link_test(DRIVER, TREND_ONLY, 0, "+").p >= LINK_ALPHA


@pytest.mark.parametrize(
    ("response", "sign"),
    [(STRONG, 1), (yearly(-np.array(STRONG.values)), -1)],
    ids=["follows", "mirrors"],
)
def test_sign_is_the_sign_of_the_correlation(response, sign):
    assert link_test(DRIVER, response, 0, "+").sign == sign


def test_response_that_follows_the_driver_of_the_year_before_is_significant():
    assert link_test(LAG_DRIVER, LAG_RESPONSE, 1, "+").p < LINK_ALPHA


def test_same_pair_with_the_lag_direction_reversed_is_not_significant():
    assert link_test(LAG_RESPONSE, LAG_DRIVER, 1, "+").p >= LINK_ALPHA


def test_lag_of_one_year_drops_one_year_from_the_overlap():
    assert link_test(LAG_DRIVER, LAG_RESPONSE, 1, "+").n_overlap == N_YEARS - 1


def test_fewer_overlapping_years_than_the_minimum_is_not_testable():
    n_years = LINK_MIN_OVERLAP_YEARS - 1
    result = link_test(yearly(NOISE_A[:n_years]), yearly(NOISE_B[:n_years]), 0, "+")
    assert (result.label, result.reason, result.p) == (
        "not_testable_here",
        "too_few_overlap_years",
        None,
    )


def test_overlap_of_exactly_the_minimum_is_tested():
    n_years = LINK_MIN_OVERLAP_YEARS
    result = link_test(yearly(NOISE_A[:n_years]), yearly(NOISE_B[:n_years]), 0, "+")
    assert result.reason is None


def test_overlap_counts_only_the_years_that_both_series_hold():
    result = link_test(DRIVER, yearly(STRONG.values, first_year=FIRST_YEAR + 5), 0, "+")
    assert result.n_overlap == N_YEARS - 5


def test_effective_sample_size_of_2_or_less_is_not_testable():
    result = link_test(yearly(ALTERNATING), yearly(ALTERNATING_SCALED), 0, "+")
    assert (result.label, result.reason, result.p) == (
        "not_testable_here",
        "n_eff_out_of_range",
        None,
    )


def test_effective_sample_size_of_2_or_less_keeps_its_value():
    result = link_test(yearly(ALTERNATING), yearly(ALTERNATING_SCALED), 0, "+")
    assert result.n_eff <= 2


@pytest.mark.parametrize(
    ("driver", "response"),
    [
        (yearly(DRIVER.values, metric_used="event_days"), STRONG),
        (DRIVER, yearly(STRONG.values, metric_used="event_days")),
    ],
    ids=["driver_switched", "response_switched"],
)
def test_side_that_switched_to_the_event_day_count_is_not_testable(driver, response):
    result = link_test(driver, response, 0, "+")
    assert (result.label, result.reason, result.r) == (
        "not_testable_here",
        "metric_switched",
        None,
    )


def test_date_metric_that_did_not_switch_is_tested():
    result = link_test(DRIVER, yearly(STRONG.values, metric_used="date"), 0, "+")
    assert result.label == "consistent"


def test_constant_series_is_not_testable():
    result = link_test(DRIVER, yearly([3.0] * N_YEARS), 0, "+")
    assert (result.label, result.reason, result.r) == (
        "not_testable_here",
        "constant_series",
        None,
    )
