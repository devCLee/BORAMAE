"""Library comparison of the trend engine on the reference series.

PRD.md:389, TR-F-018 and TR-F-019. pymannkendall serves S and the Sen slope only;
its Hamed-Rao test is never a reference (FR-12).
"""

import json
import math
from pathlib import Path

import pymannkendall
import pytest
import statsmodels.api as sm
from scipy import stats

from boramae.engine.definitions import CI_LEVEL, lag1_autocorr
from boramae.engine.trend import trend_stats

DATA = json.loads(
    Path(__file__).parent.joinpath("data", "reference_series.json").read_text("utf-8")
)
REFERENCE = DATA["reference"]
# scipy's Sen interval holds tie terms and no autocorrelation term, so it can serve
# only where both are absent (TRD.md:447).
TIE_FREE_WITH_RHO1_AT_MOST_0 = [
    series for series in REFERENCE if not series["has_ties"] and series["rho1"] <= 0
]
MISSING_YEAR = DATA["missing_year"]
# Tighter than the 3 decimals that TRD.md:446 asks for.
TOLERANCE = 1e-6

on_each_reference = pytest.mark.parametrize(
    "series", REFERENCE, ids=[series["id"] for series in REFERENCE]
)
on_each_scipy_reference = pytest.mark.parametrize(
    "series",
    TIE_FREE_WITH_RHO1_AT_MOST_0,
    ids=[series["id"] for series in TIE_FREE_WITH_RHO1_AT_MOST_0],
)


def engine(series):
    return trend_stats(series["values"], series["years"])


def statsmodels_fit(series):
    return sm.OLS(series["values"], sm.add_constant(series["years"])).fit()


def statsmodels_slope_interval(series):
    return statsmodels_fit(series).conf_int(alpha=1 - CI_LEVEL)[1]


def scipy_sen(series):
    return stats.theilslopes(series["values"], series["years"], alpha=CI_LEVEL)


def test_the_file_holds_10_reference_series():
    assert len(REFERENCE) == 10


@on_each_reference
def test_s_equals_pymannkendall(series):
    assert engine(series).mk.s == pymannkendall.original_test(series["values"]).s


@on_each_reference
def test_sen_slope_equals_pymannkendall(series):
    expected = pymannkendall.original_test(series["values"]).slope
    assert engine(series).sen.slope == pytest.approx(expected, abs=TOLERANCE)


@on_each_reference
def test_ols_slope_equals_statsmodels(series):
    expected = statsmodels_fit(series).params[1]
    assert engine(series).ols.slope == pytest.approx(expected, abs=TOLERANCE)


@on_each_reference
def test_plain_ols_interval_low_equals_statsmodels(series):
    expected = statsmodels_slope_interval(series)[0]
    assert engine(series).ols.ci_plain_low == pytest.approx(expected, abs=TOLERANCE)


@on_each_reference
def test_plain_ols_interval_high_equals_statsmodels(series):
    expected = statsmodels_slope_interval(series)[1]
    assert engine(series).ols.ci_plain_high == pytest.approx(expected, abs=TOLERANCE)


@on_each_reference
def test_plain_ols_p_equals_statsmodels(series):
    expected = statsmodels_fit(series).pvalues[1]
    assert engine(series).ols.p_plain == pytest.approx(expected, abs=TOLERANCE)


@on_each_reference
def test_r1_is_the_lag_1_autocorrelation_of_the_statsmodels_residuals(series):
    expected = lag1_autocorr(statsmodels_fit(series).resid)
    assert engine(series).ols.r1 == pytest.approx(expected, abs=TOLERANCE)


@on_each_reference
def test_adjusted_ols_interval_follows_n_eff_of_the_statsmodels_residuals(series):
    n = len(series["values"])
    r1 = lag1_autocorr(statsmodels_fit(series).resid)
    n_eff = n * (1 - r1) / (1 + r1)
    expected = (
        math.sqrt((n - 2) / (n_eff - 2))
        * stats.t.ppf((1 + CI_LEVEL) / 2, n_eff - 2)
        / stats.t.ppf((1 + CI_LEVEL) / 2, n - 2)
    )
    ols = engine(series).ols
    plain_width = ols.ci_plain_high - ols.ci_plain_low
    assert (ols.ci_adj_high - ols.ci_adj_low) / plain_width == pytest.approx(expected)


@on_each_scipy_reference
def test_sen_interval_low_equals_scipy_without_ties_and_correction(series):
    expected = scipy_sen(series).low_slope
    assert engine(series).sen.ci_low == pytest.approx(expected, abs=TOLERANCE)


@on_each_scipy_reference
def test_sen_interval_high_equals_scipy_without_ties_and_correction(series):
    expected = scipy_sen(series).high_slope
    assert engine(series).sen.ci_high == pytest.approx(expected, abs=TOLERANCE)


def test_sen_slope_uses_the_years_when_a_year_is_missing():
    expected = scipy_sen(MISSING_YEAR).slope
    assert engine(MISSING_YEAR).sen.slope == pytest.approx(expected, abs=TOLERANCE)
