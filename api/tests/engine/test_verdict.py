import pytest

from boramae.engine import verdict as verdict_module
from boramae.engine.types import MkResult, OlsResult, SenResult, TrendStats, Verdict
from boramae.engine.verdict import (
    change_over_record,
    decide_verdict,
    interval_includes_zero,
    residual_phi,
    residual_sd,
)
from boramae.engine.years_needed import years_needed

EMPTY_STATS = TrendStats(
    n=2,
    first_year=None,
    last_year=None,
    mk=MkResult(None, None, None, None, None, None),
    sen=SenResult(None, None, None, None),
    ols=OlsResult(None, None, None, None, None, None, None, None, None, None),
    reason="too_few_values",
)


# The default is a clear rise: 0.5 per year over a span of 20 years, a change of 10.
def make_stats(
    *,
    slope=0.5,
    ci=(0.2, 0.8),
    p=0.049,
    ols_slope=0.5,
    ols_p_plain=0.01,
    ols_p_adj=0.01,
    first_year=1981,
    last_year=2001,
):
    return TrendStats(
        n=last_year - first_year + 1,
        first_year=first_year,
        last_year=last_year,
        mk=MkResult(s=100.0, var_s=900.0, var_star=900.0, rho1=0.0, z=2.0, p=p),
        sen=SenResult(slope=slope, intercept=0.0, ci_low=ci[0], ci_high=ci[1]),
        ols=OlsResult(
            slope=ols_slope,
            intercept=0.0,
            p_plain=ols_p_plain,
            ci_plain_low=None,
            ci_plain_high=None,
            r1=0.0,
            n_eff=21.0,
            p_adj=ols_p_adj,
            ci_adj_low=None,
            ci_adj_high=None,
        ),
    )


def decide(stats, *, sd=1.0, n_values=21, min_record_years=20, is_context_only=False):
    return decide_verdict(
        stats, sd, n_values, min_record_years, is_context_only, phi=0.0
    )


CONSTANT_STATS = make_stats(
    slope=0.0, ci=(0.0, 0.0), p=1.0, ols_slope=0.0, ols_p_plain=None, ols_p_adj=None
)


@pytest.mark.parametrize(
    ("slope", "ci", "expected"),
    [
        (0.5, (0.2, 0.8), Verdict.SignificantRise),
        (-0.5, (-0.8, -0.2), Verdict.SignificantFall),
    ],
    ids=["rise", "fall"],
)
def test_p_below_alpha_with_interval_excluding_zero_is_significant_by_slope_sign(
    slope, ci, expected
):
    assert decide(make_stats(slope=slope, ci=ci, p=0.049)).verdict == expected


@pytest.mark.parametrize(
    ("slope", "ci", "sd", "expected"),
    [
        (0.5, (0.2, 0.8), 1.0, Verdict.NotYet),
        (-0.5, (-0.8, -0.2), 1.0, Verdict.NotYet),
        (0.5, (0.2, 0.8), 100.0, Verdict.NoTrend),
    ],
    ids=["rise", "fall", "small_change"],
)
def test_p_at_alpha_is_never_significant(slope, ci, sd, expected):
    stats = make_stats(slope=slope, ci=ci, p=0.05)
    assert decide(stats, sd=sd).verdict == expected


@pytest.mark.parametrize("slope", [0.5, -0.5], ids=["plus_one_sd", "minus_one_sd"])
@pytest.mark.parametrize("p", [0.05, 0.5])
def test_change_of_exactly_one_sd_without_significance_is_not_yet(slope, p):
    stats = make_stats(slope=slope, ci=(-1.0, 1.0), p=p)
    assert decide(stats, sd=10.0).verdict == Verdict.NotYet


def test_change_smaller_than_one_sd_without_significance_is_no_trend():
    stats = make_stats(ci=(-1.0, 1.0), p=0.5)
    assert decide(stats, sd=10.001).verdict == Verdict.NoTrend


@pytest.mark.parametrize(
    "ci",
    [(-0.1, 0.8), (0.0, 0.8), (-0.8, 0.0)],
    ids=["zero_inside", "lower_bound_at_zero", "upper_bound_at_zero"],
)
def test_p_below_alpha_with_interval_including_zero_is_not_yet(ci):
    # sd 100 keeps the one-SD row out, so only the OD-02 row can give this verdict.
    assert decide(make_stats(ci=ci, p=0.049), sd=100.0).verdict == Verdict.NotYet


@pytest.mark.parametrize(
    ("ci_low", "ci_high", "expected"),
    [
        (-0.1, 0.1, True),
        (0.0, 0.8, True),
        (-0.8, 0.0, True),
        (0.1, 0.8, False),
        (-0.8, -0.1, False),
    ],
)
def test_interval_includes_zero_counts_a_bound_at_zero(ci_low, ci_high, expected):
    assert interval_includes_zero(ci_low, ci_high) is expected


def test_interval_with_a_bound_at_zero_excludes_zero_when_the_switch_is_off(
    monkeypatch,
):
    monkeypatch.setattr(verdict_module, "SEN_BOUND_AT_ZERO_INCLUDES_ZERO", False)
    assert interval_includes_zero(0.0, 0.8) is False


def test_zero_slope_is_never_significant_when_the_switch_is_off(monkeypatch):
    monkeypatch.setattr(verdict_module, "SEN_BOUND_AT_ZERO_INCLUDES_ZERO", False)
    stats = make_stats(slope=0.0, ci=(0.0, 0.4), p=0.01, ols_slope=0.0)
    assert decide(stats).verdict is Verdict.NotYet


@pytest.mark.parametrize(
    ("first_year", "last_year", "n_values", "expected"),
    [
        (1981, 1999, 19, Verdict.RecordTooShort),
        (1981, 2000, 20, Verdict.SignificantRise),
        (1981, 2006, 19, Verdict.RecordTooShort),
    ],
    ids=["19_values", "20_values_span_19", "19_values_span_25"],
)
def test_record_guard_counts_values(first_year, last_year, n_values, expected):
    stats = make_stats(first_year=first_year, last_year=last_year)
    assert decide(stats, n_values=n_values).verdict == expected


def test_record_too_short_keeps_the_statistics():
    assert decide(make_stats(), n_values=19).change == pytest.approx(10.0)


def test_constant_series_is_not_yet():
    assert decide(CONSTANT_STATS, sd=0.0).verdict == Verdict.NotYet


def test_constant_series_has_no_years_needed_value():
    assert decide(CONSTANT_STATS, sd=0.0).years_needed.reason == "zero_slope"


def test_empty_statistics_are_record_too_short():
    result = decide_verdict(EMPTY_STATS, None, 2, 20, False, phi=None)
    assert result.verdict == Verdict.RecordTooShort


def test_empty_statistics_carry_their_reason():
    result = decide_verdict(EMPTY_STATS, None, 2, 20, False, phi=None)
    assert result.reason == "too_few_values"


def test_context_only_variable_gets_no_verdict():
    assert decide(make_stats(), is_context_only=True).verdict is None


def test_context_only_variable_names_its_reason():
    assert decide(make_stats(), is_context_only=True).reason == "context_only"


def test_context_only_variable_keeps_the_statistics():
    assert decide(make_stats(), is_context_only=True).change == pytest.approx(10.0)


@pytest.mark.parametrize(
    ("stats", "sd", "n_values", "has_years_needed"),
    [
        (make_stats(ci=(-1.0, 1.0), p=0.5), 1.0, 21, True),
        (make_stats(ci=(-1.0, 1.0), p=0.5), 100.0, 21, True),
        (make_stats(ci=(-0.1, 0.8), p=0.049), 100.0, 21, True),
        (make_stats(), 1.0, 21, False),
        (make_stats(), 1.0, 19, False),
    ],
    ids=["not_yet", "no_trend", "p_below_alpha_zero_inside", "significant", "short"],
)
def test_years_needed_is_filled_for_every_not_significant_verdict(
    stats, sd, n_values, has_years_needed
):
    result = decide(stats, sd=sd, n_values=n_values)
    assert (result.years_needed is not None) is has_years_needed


def test_years_needed_uses_the_sd_the_phi_and_the_sen_slope():
    stats = make_stats(slope=0.03, ci=(-0.01, 0.07), p=0.2, ols_slope=0.03)
    result = decide_verdict(stats, 0.5, 25, 20, False, phi=0.2)
    assert result.years_needed == years_needed(0.5, 0.2, 0.03, 25)


# TRD.md:1313: 0.1 x 44 gives 4.4 for the 45 values from 1981 to 2025.
def test_change_over_record_is_the_sen_slope_times_the_span():
    assert change_over_record(0.1, 1981, 2025) == pytest.approx(4.4)


def test_result_holds_the_span_not_the_record_length():
    stats = make_stats(first_year=1981, last_year=2025)
    assert decide(stats, n_values=45).span_years == 44


YEARS = [2000, 2001, 2002, 2003, 2004]


# The values lie on a line of slope 2 plus the residuals 1, -1, 0, 2, -2, whose sum
# of squares is 10: the sample SD is sqrt(10 / 4).
def test_residual_sd_is_the_sample_sd_of_the_series_minus_its_sen_line():
    values = [1.0, 1.0, 4.0, 8.0, 6.0]
    assert residual_sd(values, YEARS, 2.0) == pytest.approx(2.5**0.5)


def test_residual_sd_of_a_constant_series_is_exactly_zero():
    assert residual_sd([0.1] * 6, [2000, 2001, 2002, 2003, 2004, 2005], 0.0) == 0.0


@pytest.mark.parametrize(
    ("values", "years", "sen_slope"),
    [([1.0, 2.0], [2000, 2001], None), ([1.0], [2000], 0.0)],
    ids=["no_slope", "one_value"],
)
def test_residual_sd_is_empty_when_it_cannot_be_computed(values, years, sen_slope):
    assert residual_sd(values, years, sen_slope) is None


# The values are the year index plus 2, 4, 1, 5, 3, 6; test_definitions.py holds the
# hand value -31/70 for these residuals.
def test_residual_phi_is_the_lag1_autocorrelation_of_the_sen_residuals():
    values = [2.0, 5.0, 3.0, 8.0, 7.0, 11.0]
    assert residual_phi(values, [0, 1, 2, 3, 4, 5], 1.0) == pytest.approx(-31 / 70)


def test_residual_phi_is_empty_without_a_sen_slope():
    assert residual_phi([1.0, 2.0], [2000, 2001], None) is None


# TRD.md:1341, Q-02 definition 7. Every case has 21 values, so a verdict exists.
@pytest.mark.parametrize(
    ("stats", "expected"),
    [
        (make_stats(p=0.03, ols_p_adj=0.2), True),
        (make_stats(p=0.2, ols_p_adj=0.03), True),
        (make_stats(slope=0.1, p=0.5, ols_slope=-0.1, ols_p_adj=0.6), True),
        (make_stats(slope=-0.1, p=0.5, ols_slope=0.1, ols_p_adj=0.6), True),
        (make_stats(slope=0.0, p=0.5, ols_slope=0.3, ols_p_adj=0.6), False),
        (make_stats(slope=0.1, p=0.01, ols_slope=-0.1, ols_p_adj=None), False),
        (make_stats(p=0.01, ols_p_adj=0.02), False),
        (make_stats(p=0.5, ols_p_adj=0.6), False),
        (make_stats(p=0.2, ols_p_plain=0.01, ols_p_adj=0.2), False),
    ],
    ids=[
        "only_mk_p_below_alpha",
        "only_ols_p_below_alpha",
        "sen_up_ols_down",
        "sen_down_ols_up",
        "sen_zero_beside_nonzero_ols",
        "no_ols_p",
        "both_significant_same_sign",
        "neither_significant_same_sign",
        "adjusted_ols_p_decides_not_the_plain_one",
    ],
)
def test_methods_disagree_on_significance_or_on_strictly_opposite_signs(
    stats, expected
):
    assert decide(stats).methods_disagree is expected


@pytest.mark.parametrize(
    ("ols_p_adj", "expected"), [(None, True), (0.2, False)], ids=["missing", "present"]
)
def test_missing_ols_p_sets_the_flag(ols_p_adj, expected):
    assert decide(make_stats(ols_p_adj=ols_p_adj)).ols_p_missing is expected
