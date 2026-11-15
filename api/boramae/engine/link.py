"""Link test of a case-board arrow (TR-F-026, PRD "Earth-system context").

The correlation of the detrended yearly values of a driver and a response at the
registry lag, tested on an effective sample size. Any two trending series
correlate, so only the co-variation about each Sen line counts. Pure, no I/O.
"""

import math
from typing import Literal

import numpy as np
from scipy import stats

from boramae.engine.definitions import (
    LINK_ALPHA,
    LINK_MIN_OVERLAP_YEARS,
    lag1_autocorr,
)
from boramae.engine.series import METRIC_USED_EVENT_DAYS
from boramae.engine.trend import CONSTANT_SERIES, N_EFF_OUT_OF_RANGE, sen_slope
from boramae.engine.types import LinkResult, YearlySeries

NOT_TESTABLE = "not_testable_here"
# ponytail: no document names this code; BUILD_CONTRACT.md names metric_switched.
TOO_FEW_OVERLAP_YEARS = "too_few_overlap_years"
METRIC_SWITCHED = "metric_switched"
# (significant, expected sign) to the arrow label (PRD step 5). The PRD names no
# label for an opposite sign that is not significant (TRD Q-16), so it is None. An
# r of exactly 0 has no expected sign and is never significant, so it gets None too.
LABELS = {
    (True, True): "consistent",
    (False, True): "weak",
    (True, False): "contradicts",
    (False, False): None,
}


# ponytail: TRD Q-16 leaves the test open. Working values: each whole series minus
# its own Sen line, response[t] paired with driver[t - lag_years], Pearson r,
# n_eff = n(1 - r1a r1b)/(1 + r1a r1b) with definitions.lag1_autocorr of each paired
# residual series, and a two-sided Student t on n_eff - 2 degrees of freedom at
# LINK_ALPHA. Settle them in definitions.py when Q-16 is decided.
def link_test(
    driver: YearlySeries,
    response: YearlySeries,
    lag_years: int,
    expected_sign: Literal["+", "-"],
) -> LinkResult:
    """Link test and label of one arrow. `expected_sign` is the registry sign."""
    years = sorted(set(response.years) & {year + lag_years for year in driver.years})
    n = len(years)
    # An event-day count has the opposite sign convention of the date it replaced
    # (TR-D-006), so the registry sign cannot be tested on it.
    if METRIC_USED_EVENT_DAYS in (driver.metric_used, response.metric_used):
        return _not_testable(lag_years, n, METRIC_SWITCHED)
    if n < LINK_MIN_OVERLAP_YEARS:
        return _not_testable(lag_years, n, TOO_FEW_OVERLAP_YEARS)
    driver_residuals = _detrended(driver)
    response_residuals = _detrended(response)
    a = np.array([driver_residuals[year - lag_years] for year in years])
    b = np.array([response_residuals[year] for year in years])
    if np.ptp(a) == 0.0 or np.ptp(b) == 0.0:
        return _not_testable(lag_years, n, CONSTANT_SERIES)
    r = float(np.corrcoef(a, b)[0, 1])
    autocorr_product = lag1_autocorr(a) * lag1_autocorr(b)
    n_eff = n * (1 - autocorr_product) / (1 + autocorr_product)
    sign = int(np.sign(r))
    if n_eff <= 2:
        return LinkResult(
            r, None, n_eff, lag_years, n, sign, NOT_TESTABLE, N_EFF_OUT_OF_RANGE
        )
    t = abs(r) * math.sqrt((n_eff - 2) / (1 - r * r)) if abs(r) < 1 else math.inf
    p = 2 * float(stats.t.sf(t, n_eff - 2))
    has_expected_sign = sign == (1 if expected_sign == "+" else -1)
    label = LABELS[(p < LINK_ALPHA, has_expected_sign)]
    return LinkResult(r, p, n_eff, lag_years, n, sign, label)


def _detrended(series: YearlySeries) -> dict[int, float]:
    """Each value minus the Sen line of the series, by year. The intercept cancels
    in r and in the lag-1 autocorrelation, so only the slope is removed."""
    values = np.asarray(series.values, dtype=float)
    years = np.asarray(series.years, dtype=float)
    residuals = values - sen_slope(values, years) * years
    return dict(zip(series.years, residuals.tolist()))


def _not_testable(lag_years: int, n_overlap: int, reason: str) -> LinkResult:
    return LinkResult(
        None, None, None, lag_years, n_overlap, None, NOT_TESTABLE, reason
    )
