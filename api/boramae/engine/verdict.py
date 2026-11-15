"""The verdict rules of PRD "Trend analysis methodology" (TR-F-020, TR-F-021).

One rule function gives a tested series exactly one verdict, or withholds it.
"""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from .definitions import (
    ALPHA,
    Q02_6_SD_DDOF,
    SEN_BOUND_AT_ZERO_INCLUDES_ZERO,
    lag1_autocorr,
)
from .types import TrendStats, Verdict, VerdictResult
from .years_needed import years_needed

# ponytail: no document names this code, and the API contract has no stored form
# for it at P0. Add it to contracts/results.py when a context-only variable loads.
CONTEXT_ONLY = "context_only"


def decide_verdict(
    stats: TrendStats,
    sd: float | None,
    n_values: int,
    min_record_years: int,
    is_context_only: bool,
    *,
    phi: float | None,
) -> VerdictResult:
    """Apply the verdict rules to the statistics of one yearly series.

    sd and phi come from residual_sd and residual_phi. The record guard counts
    n_values, not the span. A context-only variable keeps its statistics and gets no
    verdict. Every not-significant verdict carries the years needed.
    """
    sen, p = stats.sen, stats.mk.p
    withheld_reason = CONTEXT_ONLY if is_context_only else None
    is_ols_p_missing = stats.ols.p_adj is None
    if (
        sen.slope is None
        or sen.ci_low is None
        or sen.ci_high is None
        or p is None
        or stats.first_year is None
        or stats.last_year is None
        or sd is None
        or phi is None
    ):
        return VerdictResult(
            verdict=None if is_context_only else Verdict.RecordTooShort,
            change=None,
            sd=None,
            span_years=None,
            methods_disagree=False,
            ols_p_missing=is_ols_p_missing,
            years_needed=None,
            reason=withheld_reason or stats.reason,
        )

    change = change_over_record(sen.slope, stats.first_year, stats.last_year)
    # A slope of exactly 0 has no direction. The check matters only when the D-03
    # switch is off, where a count series with an interval of (0, x) would pass.
    is_significant = (
        p < ALPHA
        and sen.slope != 0
        and not interval_includes_zero(sen.ci_low, sen.ci_high)
    )
    if is_context_only:
        verdict = None
    elif n_values < min_record_years:
        verdict = Verdict.RecordTooShort
    elif is_significant:
        verdict = Verdict.SignificantRise if sen.slope > 0 else Verdict.SignificantFall
    elif p < ALPHA or abs(change) >= sd:
        verdict = Verdict.NotYet
    else:
        verdict = Verdict.NoTrend
    is_not_significant = verdict in (Verdict.NotYet, Verdict.NoTrend)
    return VerdictResult(
        verdict=verdict,
        change=change,
        sd=sd,
        span_years=stats.last_year - stats.first_year,
        methods_disagree=methods_disagree(stats),
        ols_p_missing=is_ols_p_missing,
        years_needed=(
            years_needed(sd, phi, sen.slope, n_values) if is_not_significant else None
        ),
        reason=withheld_reason,
    )


def change_over_record(sen_slope: float, first_year: int, last_year: int) -> float:
    """Sen slope per year times the span, the last year minus the first year."""
    return sen_slope * (last_year - first_year)


def interval_includes_zero(ci_low: float, ci_high: float) -> bool:
    """Whether the Sen 95% interval includes zero; a bound at 0 follows D-03."""
    if SEN_BOUND_AT_ZERO_INCLUDES_ZERO:
        return ci_low <= 0 <= ci_high
    return ci_low < 0 < ci_high


def methods_disagree(stats: TrendStats) -> bool:
    """Whether Mann-Kendall and OLS disagree on significance or on the slope sign.

    The OLS p-value is the one from the effective sample size. A slope of exactly 0
    never differs in sign, and a series with no OLS p-value reports no disagreement.
    """
    mk_p, ols_p = stats.mk.p, stats.ols.p_adj
    sen_slope, ols_slope = stats.sen.slope, stats.ols.slope
    if mk_p is None or ols_p is None or sen_slope is None or ols_slope is None:
        return False
    differs_in_significance = (mk_p < ALPHA) != (ols_p < ALPHA)
    differs_in_sign = sen_slope > 0 > ols_slope or sen_slope < 0 < ols_slope
    return differs_in_significance or differs_in_sign


def residual_sd(
    values: Sequence[float], years: Sequence[int], sen_slope: float | None
) -> float | None:
    """Sample standard deviation of the yearly series minus its Sen line."""
    if sen_slope is None or len(values) <= Q02_6_SD_DDOF:
        return None
    residuals = _sen_residuals(values, years, sen_slope)
    # A float mean can miss a constant value by one ulp, which gives a nonzero SD.
    if np.ptp(residuals) == 0.0:
        return 0.0
    return float(np.std(residuals, ddof=Q02_6_SD_DDOF))


def residual_phi(
    values: Sequence[float], years: Sequence[int], sen_slope: float | None
) -> float | None:
    """Lag-1 autocorrelation of the yearly series minus its Sen line."""
    if sen_slope is None:
        return None
    return lag1_autocorr(_sen_residuals(values, years, sen_slope))


def _sen_residuals(
    values: Sequence[float], years: Sequence[int], sen_slope: float
) -> npt.NDArray[np.float64]:
    return np.asarray(values, dtype=float) - sen_slope * np.asarray(years, dtype=float)
