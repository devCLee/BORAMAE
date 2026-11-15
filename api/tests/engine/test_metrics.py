import sys

import numpy as np
import pytest

from boramae.engine import metrics_more, metrics_season
from boramae.engine.metrics import reduce_yearly
from boramae.engine.types import MetricParams, YearlySeries

SNOW_THRESHOLD_MM = 0.1
FIRST_SNOW = MetricParams(
    "first_date", threshold=SNOW_THRESHOLD_MM, op=">=", season_start="08-01"
)
HOT_DAY_C = 33.0
STUB_SERIES = YearlySeries(years=(2001,), values=(1.0,), is_censored=(False,))


def monthly_series(first_year, last_year, values_of_a_year=(1.0,) * 12):
    times = np.arange(f"{first_year}-01", f"{last_year + 1}-01", dtype="datetime64[M]")
    return times, np.tile(values_of_a_year, last_year - first_year + 1).astype(float)


def daily_series(start, stop, value=0.0):
    times = np.arange(start, stop, dtype="datetime64[D]")
    return times, np.full(times.size, value)


def with_values(series, dated_values):
    times, values = series
    changed = values.copy()
    for date, value in dated_values.items():
        changed[times == np.datetime64(date)] = value
    return times, changed


def snow_seasons(first_year, n_seasons, n_event_free):
    """Daily snow from 1 Aug of the first year, with two snow days in each season.

    The first seasons are event-free.
    """
    snow_days = {}
    for year in range(first_year + n_event_free, first_year + n_seasons):
        snow_days[f"{year}-12-01"] = 1.0
        snow_days[f"{year}-12-02"] = 1.0
    series = daily_series(f"{first_year}-08-01", f"{first_year + n_seasons}-08-01")
    return with_values(series, snow_days)


def stub_reducer(times, values, params):
    return STUB_SERIES


def test_dec_to_feb_metric_over_20_calendar_years_gives_19_seasons():
    params = MetricParams("seasonal_mean", months=(12, 1, 2))
    assert len(reduce_yearly(*monthly_series(1981, 2000), params).years) == 19


def test_dec_to_feb_season_takes_the_year_of_its_december():
    params = MetricParams("seasonal_mean", months=(12, 1, 2))
    assert reduce_yearly(*monthly_series(1981, 2000), params).years[0] == 1981


def test_spec_with_no_months_gives_one_value_for_each_calendar_year():
    result = reduce_yearly(*monthly_series(1981, 2000), MetricParams("annual_mean"))
    assert result.years == tuple(range(1981, 2001))


def test_year_that_lacks_one_season_month_is_dropped():
    series = with_values(monthly_series(1981, 2000), {"1990-07": np.nan})
    params = MetricParams("seasonal_mean", months=(6, 7, 8))
    assert 1990 not in reduce_yearly(*series, params).years


def test_year_that_lacks_a_month_outside_its_season_is_kept():
    series = with_values(monthly_series(1981, 2000), {"1990-01": np.nan})
    params = MetricParams("seasonal_mean", months=(6, 7, 8))
    assert 1990 in reduce_yearly(*series, params).years


def test_absent_middle_year_keeps_its_year_as_the_time_value():
    series = with_values(monthly_series(1981, 2000), {"1990-07": np.nan})
    result = reduce_yearly(*series, MetricParams("annual_mean"))
    assert result.years == (*range(1981, 1990), *range(1991, 2001))


# Hand value: the mean of 1 to 12 is 6.5.
def test_annual_mean_is_the_mean_of_the_twelve_months():
    series = monthly_series(1981, 1982, values_of_a_year=range(1, 13))
    assert reduce_yearly(*series, MetricParams("annual_mean")).values == (6.5, 6.5)


# Hand value: the mean of 6, 7 and 8 is 7.
def test_seasonal_mean_is_the_mean_of_the_months_asked():
    series = monthly_series(1981, 1982, values_of_a_year=range(1, 13))
    params = MetricParams("seasonal_mean", months=(6, 7, 8))
    assert reduce_yearly(*series, params).values == (7.0, 7.0)


# 1 mm/day in every month: the total is the day count of the year, and 1984
# is a leap year.
def test_annual_total_from_monthly_data_weights_each_month_by_its_days():
    result = reduce_yearly(*monthly_series(1981, 1984), MetricParams("annual_total"))
    assert result.values == (365.0, 365.0, 365.0, 366.0)


# Hand value: June, July and August hold 30 + 31 + 31 = 92 days.
def test_seasonal_total_from_monthly_data_covers_the_months_asked():
    params = MetricParams("seasonal_total", months=(6, 7, 8))
    assert reduce_yearly(*monthly_series(1981, 1981), params).values == (92.0,)


def test_annual_total_from_daily_data_sums_the_days():
    series = daily_series("1981-01-01", "1982-01-01", value=2.0)
    assert reduce_yearly(*series, MetricParams("annual_total")).values == (730.0,)


def test_year_with_a_nan_padded_tail_is_dropped_and_not_summed_as_zeros():
    series = with_values(
        monthly_series(1981, 1982), {"1982-11": np.nan, "1982-12": np.nan}
    )
    assert reduce_yearly(*series, MetricParams("annual_total")).years == (1981,)


# Hand value: 31 + 30 + 31 days from 1 Aug to 31 Oct, so 20 Nov is day 112.
def test_first_date_is_the_day_of_the_season_year():
    series = with_values(
        daily_series("1981-08-01", "1982-08-01"),
        {"1981-11-20": 2.5, "1981-12-24": 4.0},
    )
    assert reduce_yearly(*series, FIRST_SNOW).values == (112.0,)


def test_first_date_skips_a_day_under_the_threshold():
    series = with_values(
        daily_series("1981-08-01", "1982-08-01"),
        {"1981-10-01": 0.05, "1981-11-20": SNOW_THRESHOLD_MM},
    )
    assert reduce_yearly(*series, FIRST_SNOW).values == (112.0,)


def test_first_date_drops_the_incomplete_first_and_last_season_of_a_window():
    series = daily_series("1981-01-01", "2001-01-01", value=1.0)
    assert reduce_yearly(*series, FIRST_SNOW).years == tuple(range(1981, 2000))


# One event-free season in ten. It runs from 1 Aug 1983 to 31 Jul 1984 and holds
# 29 Feb 1984, so its end date is day 366.
def test_year_with_no_first_snow_takes_the_season_end_date():
    assert reduce_yearly(*snow_seasons(1983, 10, 1), FIRST_SNOW).values[0] == 366.0


def test_year_with_no_first_snow_takes_the_censored_flag():
    result = reduce_yearly(*snow_seasons(1983, 10, 1), FIRST_SNOW)
    assert result.is_censored == (True, *[False] * 9)


@pytest.mark.parametrize(
    ("n_event_free", "expected"),
    [(21, "event_days"), (20, "date")],
    ids=["21_percent_censored", "exactly_20_percent_censored"],
)
def test_first_date_switches_to_the_event_day_count_above_20_percent_censored(
    n_event_free, expected
):
    result = reduce_yearly(*snow_seasons(1900, 100, n_event_free), FIRST_SNOW)
    assert result.metric_used == expected


def test_first_date_after_the_switch_counts_the_event_days_of_each_season():
    result = reduce_yearly(*snow_seasons(1983, 4, 1), FIRST_SNOW)
    assert result.values == (0.0, 2.0, 2.0, 2.0)


def test_threshold_days_count_the_days_at_or_past_the_threshold():
    series = with_values(
        daily_series("1981-01-01", "1982-01-01", value=20.0),
        {"1981-07-30": 33.0, "1981-07-31": 35.5, "1981-08-01": 32.9},
    )
    params = MetricParams("threshold_days", threshold=HOT_DAY_C)
    assert reduce_yearly(*series, params).values == (2.0,)


def test_threshold_days_follow_the_operator_of_the_spec():
    series = with_values(
        daily_series("1981-01-01", "1982-01-01", value=5.0),
        {"1981-01-10": -2.0, "1981-01-11": 0.0, "1981-12-20": -0.1},
    )
    params = MetricParams("threshold_days", threshold=0.0, op="<")
    assert reduce_yearly(*series, params).values == (2.0,)


def test_threshold_days_count_only_the_months_asked():
    series = with_values(
        daily_series("1981-01-01", "1982-01-01", value=20.0),
        {"1981-05-31": 34.0, "1981-06-01": 34.0},
    )
    params = MetricParams("threshold_days", threshold=HOT_DAY_C, months=(6, 7, 8))
    assert reduce_yearly(*series, params).values == (1.0,)


def test_rx1day_over_jun_to_sep_is_the_largest_daily_value_of_those_months():
    series = with_values(
        daily_series("1981-01-01", "1983-01-01", value=1.0),
        {
            "1981-05-20": 99.0,
            "1981-07-15": 50.0,
            "1982-06-01": 30.0,
            "1982-10-01": 80.0,
        },
    )
    params = MetricParams("rx1day", months=(6, 7, 8, 9))
    assert reduce_yearly(*series, params).values == (50.0, 30.0)


@pytest.mark.parametrize(
    "metric_id",
    [
        "annual_mean",
        "annual_total",
        "seasonal_mean",
        "seasonal_total",
        "threshold_days",
        "rx1day",
    ],
)
def test_metric_that_is_not_a_date_has_an_empty_metric_used(metric_id):
    params = MetricParams(metric_id, threshold=HOT_DAY_C)
    assert reduce_yearly(*monthly_series(1981, 1982), params).metric_used == ""


def test_series_with_no_complete_year_gives_no_years():
    series = monthly_series(1981, 1982, values_of_a_year=(np.nan,) * 12)
    assert reduce_yearly(*series, MetricParams("annual_mean")).years == ()


@pytest.mark.parametrize(
    ("module", "metric_id"),
    [(metrics_season, "season_onset"), (metrics_more, "spell_length")],
    ids=["metrics_season", "metrics_more"],
)
def test_metric_that_only_an_extension_module_holds_is_found_there(
    monkeypatch, module, metric_id
):
    monkeypatch.setitem(module.REDUCERS, metric_id, stub_reducer)
    series = monthly_series(1981, 1982)
    assert reduce_yearly(*series, MetricParams(metric_id)) is STUB_SERIES


# None in sys.modules makes any import of the module fail.
def test_core_metric_reduces_without_loading_an_extension_module(monkeypatch):
    monkeypatch.setitem(sys.modules, metrics_season.__name__, None)
    monkeypatch.setitem(sys.modules, metrics_more.__name__, None)
    result = reduce_yearly(*monthly_series(1981, 1982), MetricParams("annual_mean"))
    assert result.years == (1981, 1982)


def test_metric_that_no_module_holds_raises_with_its_id():
    with pytest.raises(ValueError, match="snow_share"):
        reduce_yearly(*monthly_series(1981, 1982), MetricParams("snow_share"))
