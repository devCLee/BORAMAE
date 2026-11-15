import math

import numpy as np
import pytest
from scipy.signal import lfilter

from boramae.engine import years_needed as years_needed_module
from boramae.engine.definitions import lag1_autocorr
from boramae.engine.types import YearsNeeded
from boramae.engine.years_needed import years_needed

# PRD.md:385: a warming of 0.3 per decade with a year-to-year scatter of 0.5 and
# r1 = 0.2.
SIGMA = 0.5
PHI = 0.2
OMEGA = 0.03
# ponytail: no document fixes the simulation. Seed, run count, burn-in and the
# accepted detection range of 0.75 to 0.99 were set before the first run.
SEED = 20261114
RUNS = 400
BURN_IN_YEARS = 100


# 3.3 x sqrt(12) x (0.5 / 0.03) x sqrt(1.2 / 0.8) = 233.35, and 233.35^(2/3) = 37.90.
def test_years_needed_equals_the_worked_example():
    assert years_needed(SIGMA, PHI, OMEGA, 20).total == pytest.approx(37.90, abs=0.01)


def test_more_is_the_years_still_needed_rounded_up():
    assert years_needed(SIGMA, PHI, OMEGA, 20).more == 18


# 23.335^(2/3) = 8.17 years in total; 3.17 more than 5 rounds up to 4, not down to 3.
def test_more_rounds_a_small_fraction_up():
    assert years_needed(SIGMA, PHI, 0.3, 5).more == 4


def test_estimate_above_the_record_has_no_reason():
    assert years_needed(SIGMA, PHI, OMEGA, 20).reason is None


def test_falling_trend_needs_as_many_years_as_a_rising_one():
    rising = years_needed(SIGMA, PHI, OMEGA, 20)
    assert years_needed(SIGMA, PHI, -OMEGA, 20) == rising


def test_strong_trend_on_a_long_record_is_within_the_record():
    assert years_needed(SIGMA, PHI, 0.3, 45).reason == "within_record"


def test_strong_trend_on_a_long_record_needs_no_more_years():
    assert years_needed(SIGMA, PHI, 0.3, 45).more == 0


# 3.3 x sqrt(12) x (0.5 / 0.3) x sqrt(1.5) = 23.335, and 23.335^(2/3) = 8.17.
def test_strong_trend_on_a_long_record_keeps_its_total():
    assert years_needed(SIGMA, PHI, 0.3, 45).total == pytest.approx(8.17, abs=0.01)


@pytest.mark.parametrize(
    ("sigma", "phi", "omega", "reason"),
    [
        (SIGMA, PHI, 0.0, "zero_slope"),
        (0.0, 0.0, 0.0, "zero_slope"),
        (0.0, PHI, OMEGA, "no_scatter"),
        (SIGMA, 1.0, OMEGA, "phi_out_of_range"),
        (SIGMA, -1.0, OMEGA, "phi_out_of_range"),
        (SIGMA, 1.5, OMEGA, "phi_out_of_range"),
    ],
    ids=["zero_slope", "constant", "no_scatter", "phi_1", "phi_minus_1", "phi_1.5"],
)
def test_case_without_a_finite_value_is_empty_with_its_reason(
    sigma, phi, omega, reason
):
    expected = YearsNeeded(total=None, more=None, reason=reason)
    assert years_needed(sigma, phi, omega, 30) == expected


@pytest.mark.parametrize("sigma", [0.0, 1e-12, 0.5, 1e6])
@pytest.mark.parametrize("phi", [-1.0, -0.99, 0.0, 0.99, 1.0, 2.0])
@pytest.mark.parametrize("omega", [-0.03, 0.0, 1e-12, 0.03])
def test_total_is_never_nan(sigma, phi, omega):
    total = years_needed(sigma, phi, omega, 30).total
    assert total is None or math.isfinite(total)


def test_without_the_yearly_factor_the_total_is_lower_by_the_cube_root_of_12(
    monkeypatch,
):
    with_factor = years_needed(SIGMA, PHI, OMEGA, 20).total
    monkeypatch.setattr(years_needed_module, "YEARS_NEEDED_YEARLY_SQRT12", False)
    without_factor = years_needed(SIGMA, PHI, OMEGA, 20).total
    assert with_factor / without_factor == pytest.approx(12 ** (1 / 3))


# Weatherhead's monthly form, as TDD.md:293 recalls it: sigma and phi of the monthly
# noise, omega per year. Yearly means of monthly white noise have sigma_m / sqrt(12).
def test_yearly_form_equals_the_monthly_form_on_monthly_white_noise():
    monthly = np.random.default_rng(SEED).normal(0.0, 1.0, size=(4000, 12))
    yearly = monthly.mean(axis=1)
    sigma_m = float(np.std(monthly, ddof=1))
    phi_m = lag1_autocorr(monthly.ravel())
    autocorr_factor_m = math.sqrt((1 + phi_m) / (1 - phi_m))
    monthly_form = (3.3 * sigma_m / OMEGA * autocorr_factor_m) ** (2 / 3)
    sigma_y = float(np.std(yearly, ddof=1))
    result = years_needed(sigma_y, lag1_autocorr(yearly), OMEGA, 20)
    assert result.total == pytest.approx(monthly_form, rel=0.05)


def detection_rate(n_years: int) -> float:
    """Share of yearly AR(1) series with the trend OMEGA in which the trend is found.

    A trend is found when the least-squares slope is more than 2 standard errors
    from 0, the detection rule of Weatherhead et al. 1998. The standard error comes
    from each series: the plain one times sqrt((1 + r1) / (1 - r1)).
    """
    rng = np.random.default_rng(SEED)
    innovations = rng.normal(
        0.0, SIGMA * math.sqrt(1 - PHI**2), size=(RUNS, BURN_IN_YEARS + n_years)
    )
    noise = lfilter([1.0], [1.0, -PHI], innovations, axis=1)[:, BURN_IN_YEARS:]
    t = np.arange(n_years) - (n_years - 1) / 2
    series = noise + OMEGA * t
    slopes = series @ t / (t @ t)
    residuals = series - series.mean(axis=1, keepdims=True) - np.outer(slopes, t)
    sum_sq = (residuals**2).sum(axis=1)
    r1 = (residuals[:, :-1] * residuals[:, 1:]).sum(axis=1) / sum_sq
    standard_error = np.sqrt(sum_sq / (n_years - 2) / (t @ t) * (1 + r1) / (1 - r1))
    return float(np.mean(np.abs(slopes) > 2 * standard_error))


# The 3.3 of the formula stands for a detection in 90% of cases. The range is wide,
# because r1 comes from 38 values and 400 runs give a rate within about 3 points.
def test_trend_is_detected_at_the_years_needed_in_most_simulated_series():
    n_years = math.ceil(years_needed(SIGMA, PHI, OMEGA, 20).total)
    assert 0.75 <= detection_rate(n_years) <= 0.99
