"""Mean metrics over a daily series, as T2M_MAX and T2M_MIN read them (decision 9)."""

import numpy as np
import pytest

from boramae.engine.metrics import reduce_yearly
from boramae.engine.types import MetricParams

ANNUAL_MEAN = MetricParams("annual_mean")
SUMMER_MEAN = MetricParams("seasonal_mean", months=(6, 7, 8))


def daily_series(first_year, last_year, value_of_month):
    """One value per day from 1 Jan of the first year; each month holds its value."""
    times = np.arange(
        f"{first_year}-01-01", f"{last_year + 1}-01-01", dtype="datetime64[D]"
    )
    month_numbers = times.astype("datetime64[M]").astype(int) % 12 + 1
    return times, np.array([value_of_month.get(m, 0.0) for m in month_numbers])


def without_month(series, month):
    times, values = series
    changed = values.copy()
    changed[times.astype("datetime64[M]") == np.datetime64(month)] = np.nan
    return times, changed


FEBRUARY_ONLY = daily_series(2001, 2004, {2: 1.0})
SUMMER_STEPS = daily_series(2001, 2004, {6: 1.0, 7: 2.0, 8: 3.0})


@pytest.mark.parametrize(
    ("year_index", "mean"), [(0, 28 / 365), (3, 29 / 366)], ids=["2001", "2004 leap"]
)
def test_annual_mean_is_the_mean_of_the_days_of_the_year(year_index, mean):
    result = reduce_yearly(*FEBRUARY_ONLY, ANNUAL_MEAN)
    assert result.values[year_index] == pytest.approx(mean)


def test_annual_mean_gives_one_value_for_each_complete_year():
    assert reduce_yearly(*FEBRUARY_ONLY, ANNUAL_MEAN).years == (2001, 2002, 2003, 2004)


def test_seasonal_mean_is_the_mean_of_the_days_of_the_season_months():
    result = reduce_yearly(*SUMMER_STEPS, SUMMER_MEAN)
    assert result.values[0] == pytest.approx((30 * 1 + 31 * 2 + 31 * 3) / 92)


@pytest.mark.parametrize(
    ("params", "missing_month"),
    [(ANNUAL_MEAN, "2002-03"), (SUMMER_MEAN, "2002-07")],
    ids=["annual_mean", "seasonal_mean"],
)
def test_year_that_lacks_a_month_of_its_season_is_dropped(params, missing_month):
    series = without_month(SUMMER_STEPS, missing_month)
    assert 2002 not in reduce_yearly(*series, params).years
