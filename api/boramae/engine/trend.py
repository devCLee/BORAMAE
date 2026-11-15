"""Trend statistics of one yearly series: Mann-Kendall, Sen slope and OLS.

Follows PRD "Trend analysis methodology" and the working values of TRD Q-02, which
engine/definitions.py holds. Slopes are per year, with the years as time values. A
statistic that cannot be computed is None with a reason code, and never NaN.
"""

import math
from collections.abc import Sequence

import numpy as np
from scipy import stats

from boramae.engine import definitions
from boramae.engine.types import MkResult, OlsResult, SenResult, TrendStats

# ponytail: no document names these codes, apart from too_few_values in the build plan.
TOO_FEW_VALUES = "too_few_values"
CONSTANT_SERIES = "constant_series"
N_EFF_OUT_OF_RANGE = "n_eff_out_of_range"

# Only the working value of Q-02 definition 4 is built; another value fails loudly.
_RANK_ROUNDING = {"nearest_even": np.round}

# n_eff, adjusted p, adjusted interval low and high, reason: the tail of OlsResult.
_Adjusted = tuple[float | None, float | None, float | None, float | None, str | None]


def trend_stats(values: Sequence[float], years: Sequence[int]) -> TrendStats:
    """Every trend statistic of a yearly series with no missing value.

    `years` holds the year of each value in ascending order; an absent year is
    simply not in it.
    """
    n = len(values)
    first_year = int(years[0]) if n else None
    last_year = int(years[-1]) if n else None
    if n < definitions.MIN_STAT_VALUES:
        return TrendStats(
            n,
            first_year,
            last_year,
            MkResult(*[None] * 6),
            SenResult(*[None] * 4),
            OlsResult(*[None] * 10, reason=TOO_FEW_VALUES),
            reason=TOO_FEW_VALUES,
        )
    mk = mk_test(values, years)
    slope = sen_slope(values, years)
    ci_low, ci_high = sen_interval(values, years, mk.var_star)
    # ponytail: no document fixes the Sen intercept. This is the form that scipy and
    # pymannkendall use: median value minus slope times median time.
    intercept = float(np.median(values)) - slope * float(np.median(years))
    sen = SenResult(slope, intercept, ci_low, ci_high)
    return TrendStats(n, first_year, last_year, mk, sen, ols_trend(values, years))


def mk_test(values: Sequence[float], years: Sequence[int]) -> MkResult:
    """Mann-Kendall with the lag-1 Hamed-Rao correction and a two-sided p (TR-F-019)."""
    s = mk_s(values)
    var_s = mk_variance(values)
    rho1 = rho1_of_ranks(values, years)
    var_star = corrected_variance(var_s, len(values), rho1)
    shift = math.copysign(1.0, s) if definitions.Q02_2_MK_CONTINUITY_CORRECTION else 0.0
    z = (s - shift) / math.sqrt(var_star) if s else 0.0
    return MkResult(s, var_s, var_star, rho1, z, 2 * float(stats.norm.sf(abs(z))))


def mk_s(values: Sequence[float]) -> float:
    """S, the count of rising pairs minus the count of falling pairs."""
    x = np.asarray(values, dtype=float)
    first, second = np.triu_indices(x.size, k=1)
    return float(np.sign(x[second] - x[first]).sum())


def mk_variance(values: Sequence[float]) -> float:
    """Var(S) = n(n - 1)(2n + 5)/18, with a tie term only if Q-02 definition 3 asks."""
    n = len(values)
    variance = n * (n - 1) * (2 * n + 5) / 18
    if definitions.Q02_3_VAR_S_TIE_TERM:
        ties = np.unique(values, return_counts=True)[1]
        variance -= float(np.sum(ties * (ties - 1) * (2 * ties + 5))) / 18
    return variance


def rho1_of_ranks(values: Sequence[float], years: Sequence[int]) -> float:
    """Lag-1 autocorrelation of the ranks of the series minus its Sen line.

    Tied residuals take average ranks, and equal ranks give 0 (Q-02 definition 3).
    """
    n = len(values)
    slopes = _pairwise_slopes(values, years)
    first, second = np.triu_indices(n, k=1)
    # The later residual of a pair is the higher one exactly when the slope of the
    # pair is above the Sen slope. Comparing slopes keeps the pair that defines the
    # median an exact tie; subtracting the Sen line in floats would break that tie
    # by rounding noise, and a series and its reverse would then differ.
    later_is_higher = np.sign(slopes - np.median(slopes))
    lower_minus_higher = np.bincount(second, weights=later_is_higher, minlength=n)
    lower_minus_higher -= np.bincount(first, weights=later_is_higher, minlength=n)
    # The average rank: 1 + the count of lower residuals + half the count of ties.
    return definitions.lag1_autocorr((n + 1 + lower_minus_higher) / 2)


def corrected_variance(var_s: float, n: int, rho1: float) -> float:
    """Var*(S), the one variance behind both the p-value and the Sen interval.

    The lag-1 term applies at every record length with no significance screen, and
    it never shrinks the variance (FR-12).
    """
    return var_s * max(1.0, 1 + 2 * (n - 3) / n * rho1)


def sen_slope(values: Sequence[float], years: Sequence[int]) -> float:
    """Theil-Sen slope per year: the median slope of all pairs of points."""
    return float(np.median(_pairwise_slopes(values, years)))


def sen_interval(
    values: Sequence[float], years: Sequence[int], var_star: float
) -> tuple[float, float]:
    """Rank-based interval of the Sen slope at CI_LEVEL (Q-02 definition 4)."""
    slopes = np.sort(_pairwise_slopes(values, years))
    low_rank, high_rank = sen_rank_bounds(slopes.size, var_star)
    return float(slopes[low_rank - 1]), float(slopes[high_rank - 1])


def sen_rank_bounds(n_pairs: int, var_star: float) -> tuple[int, int]:
    """Ranks, counted from 1, of the interval bounds among the sorted pair slopes."""
    span = float(stats.norm.ppf((1 + definitions.CI_LEVEL) / 2)) * math.sqrt(var_star)
    to_whole = _RANK_ROUNDING[definitions.Q02_4_SEN_RANK_ROUNDING]
    raw_ranks = np.array([(n_pairs - span) / 2, (n_pairs + span) / 2 + 1])
    low_rank, high_rank = np.clip(to_whole(raw_ranks), 1, n_pairs)
    return int(low_rank), int(high_rank)


def ols_trend(values: Sequence[float], years: Sequence[int]) -> OlsResult:
    """OLS slope with the plain t-test and the one on the effective sample size."""
    y = np.asarray(values, dtype=float)
    t = np.asarray(years, dtype=float)
    if np.ptp(y) == 0.0:
        return OlsResult(0.0, float(y[0]), *[None] * 8, reason=CONSTANT_SERIES)
    n = y.size
    y_centered = y - y.mean()
    t_centered = t - t.mean()
    t_sum_of_squares = float(t_centered @ t_centered)
    slope = float(t_centered @ y_centered) / t_sum_of_squares
    intercept = float(y.mean()) - slope * float(t.mean())
    residuals = y_centered - slope * t_centered
    se = math.sqrt(float(residuals @ residuals) / (n - 2) / t_sum_of_squares)
    p_plain, ci_low, ci_high = _slope_test(slope, se, n - 2)
    r1 = definitions.lag1_autocorr(residuals)
    adjusted = ols_adjust(slope, se, n, r1)
    return OlsResult(slope, intercept, p_plain, ci_low, ci_high, r1, *adjusted)


# ponytail: the adjusted formula is a working value, because the comparison basis is
# open (TRD Q-14): the plain standard error scaled to n_eff - 2 degrees of freedom,
# with Student t on n_eff - 2. n_eff has no cap unless definitions.NEFF_CAP sets one,
# so a negative r1 gives an adjusted test that is looser than the plain one (Q-026).
def ols_adjust(slope: float, se_plain: float, n: int, r1: float) -> _Adjusted:
    """Test and interval of an OLS slope on n_eff = n(1 - r1)/(1 + r1) (TR-F-018)."""
    if abs(r1) >= 1:
        return None, None, None, None, N_EFF_OUT_OF_RANGE
    n_eff = n * (1 - r1) / (1 + r1)
    if definitions.NEFF_CAP is not None:
        n_eff = min(n_eff, definitions.NEFF_CAP)
    if n_eff <= 2:
        return n_eff, None, None, None, N_EFF_OUT_OF_RANGE
    se_adjusted = se_plain * math.sqrt((n - 2) / (n_eff - 2))
    return n_eff, *_slope_test(slope, se_adjusted, n_eff - 2), None


def _pairwise_slopes(values: Sequence[float], years: Sequence[int]) -> np.ndarray:
    """Slope of every pair of points, in the pair order of numpy.triu_indices."""
    y = np.asarray(values, dtype=float)
    t = np.asarray(years, dtype=float)
    first, second = np.triu_indices(y.size, k=1)
    return (y[second] - y[first]) / (t[second] - t[first])


def _slope_test(slope: float, se: float, dof: float) -> tuple[float, float, float]:
    """Two-sided Student t p-value and the CI_LEVEL interval of a slope."""
    half_width = float(stats.t.ppf((1 + definitions.CI_LEVEL) / 2, dof)) * se
    # A standard error of 0 means that every point lies on the line.
    p = 2 * float(stats.t.sf(abs(slope) / se, dof)) if se > 0 else 0.0
    return p, slope - half_width, slope + half_width
