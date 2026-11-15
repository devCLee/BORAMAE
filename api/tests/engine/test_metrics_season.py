"""Season reducers of the P0 boards (PRD "Metric library", KMA rule, TR-F-015)."""

import numpy as np
import pytest

from boramae.engine.metrics import reduce_yearly
from boramae.engine.types import MetricParams

# Daily mean temperature of a year as steps: from each day of the year on, the
# value holds until the next key. Every step sits halfway across a threshold (0 to
# 10 across 5 C, 15 to 25 across 20 C), so the 9-day running mean crosses it on
# the step day itself: spring 90, summer 180, autumn 240, winter 300.
YEAR = {1: 0.0, 90: 10.0, 150: 15.0, 180: 25.0, 240: 15.0, 270: 10.0, 300: 0.0}
# A warm spell from day 60 that falls back below 5 C on day 80, before spring.
FALSE_SPRING = {1: 0.0, 60: 10.0, 80: 0.0, **{k: v for k, v in YEAR.items() if k > 1}}
NO_SUMMER = {1: 0.0, 90: 10.0, 150: 15.0, 300: 0.0}
# Daily minimum temperature: frost (below 0 C) up to day 100 and from day 300 on.
FROSTS = {1: -5.0, 101: 10.0, 180: 20.0, 241: 10.0, 300: -5.0}
NO_FROST = {1: 5.0, 180: 20.0, 241: 5.0}


def daily(levels_by_year):
    """A daily series from the levels of each year, in day-of-year steps."""
    years = [_year_of_levels(year, levels) for year, levels in levels_by_year.items()]
    return np.concatenate([t for t, _ in years]), np.concatenate([v for _, v in years])


def same_years(first_year, n_years, levels=YEAR):
    return daily(dict.fromkeys(range(first_year, first_year + n_years), levels))


def with_values(series, dated_values):
    times, values = series
    changed = values.copy()
    for date, value in dated_values.items():
        changed[times == np.datetime64(date)] = value
    return times, changed


def constant(year, value):
    return daily({year: {1: value}})


def _year_of_levels(year, levels):
    times = np.arange(f"{year}-01-01", f"{year + 1}-01-01", dtype="datetime64[D]")
    days = np.arange(1, times.size + 1)
    keys = np.array(sorted(levels))
    steps = np.searchsorted(keys, days, side="right") - 1
    return times, np.array([levels[key] for key in keys])[steps]


def onset(threshold, op, **fields):
    return MetricParams("season_onset", threshold=threshold, op=op, **fields)


def length(threshold, op):
    return MetricParams("season_length", threshold=threshold, op=op)


# 2001 to 2003 hold no leap day, so a winter runs 365 - 300 + 90 = 155 days.
@pytest.mark.parametrize(
    ("threshold", "op", "day"),
    [(5.0, ">=", 90), (20.0, ">=", 180), (20.0, "<", 240), (5.0, "<", 300)],
    ids=["spring", "summer", "autumn", "winter"],
)
def test_onset_is_the_day_the_running_mean_crosses_and_stays(threshold, op, day):
    assert reduce_yearly(*same_years(2001, 1), onset(threshold, op)).values == (day,)


def test_warm_spell_that_falls_back_before_spring_does_not_start_it():
    series = same_years(2001, 1, FALSE_SPRING)
    assert reduce_yearly(*series, onset(5.0, ">=")).values == (90,)


def test_warm_spell_that_stays_starts_spring_on_its_first_day():
    series = same_years(2001, 1, {**YEAR, 60: 10.0})
    assert reduce_yearly(*series, onset(5.0, ">=")).values == (60,)


# One day at 0 C on day 120 (30 Apr) lifts the 9-day mean to 80/9, still past 5 C;
# a rule on the daily values would move spring to day 121.
def test_onset_reads_the_running_mean_and_not_one_cold_day():
    series = with_values(same_years(2001, 1), {"2001-04-30": 0.0})
    assert reduce_yearly(*series, onset(5.0, ">=")).values == (90,)


def test_onset_is_a_date_metric():
    result = reduce_yearly(*same_years(2001, 2), onset(5.0, ">="))
    assert result.metric_used == "date"


FIVE_YEARS_ONE_COOL = daily(
    {2001: YEAR, 2002: YEAR, 2003: NO_SUMMER, 2004: YEAR, 2005: YEAR}
)


def test_season_year_with_no_onset_is_censored():
    result = reduce_yearly(*FIVE_YEARS_ONE_COOL, onset(20.0, ">="))
    assert result.is_censored == (False, False, True, False, False)


def test_censored_onset_takes_the_last_day_of_its_season_year():
    result = reduce_yearly(*FIVE_YEARS_ONE_COOL, onset(20.0, ">="))
    assert result.values[2] == 365.0


def test_onset_switches_to_event_days_above_20_percent_censored():
    series = daily({2001: YEAR, 2002: NO_SUMMER, 2003: YEAR})
    assert reduce_yearly(*series, onset(20.0, ">=")).metric_used == "event_days"


# 1 Jul is day 182 of 2001, so the autumn onset on day 240 is day 59 of the season.
def test_onset_counts_from_the_season_start_of_the_spec():
    series = same_years(2001, 2)
    params = onset(20.0, "<", season_start="07-01")
    assert reduce_yearly(*series, params).values == (240 - 182 + 1,)


@pytest.mark.parametrize(
    ("threshold", "op", "days"),
    [
        (5.0, ">=", 180 - 90),
        (20.0, ">=", 240 - 180),
        (20.0, "<", 300 - 240),
        (5.0, "<", 365 - 300 + 90),
        (12.5, ">=", 270 - 150),
    ],
    ids=["spring", "summer", "autumn", "winter", "past_other_threshold"],
)
def test_season_length_runs_from_its_onset_to_the_next(threshold, op, days):
    result = reduce_yearly(*same_years(2001, 3), length(threshold, op))
    assert result.values[0] == days


def test_winter_with_no_spring_after_it_gives_no_value():
    result = reduce_yearly(*same_years(2001, 3), length(5.0, "<"))
    assert result.years == (2001, 2002)


def test_season_that_never_starts_gives_no_value():
    series = daily({2001: YEAR, 2002: NO_SUMMER, 2003: YEAR})
    assert reduce_yearly(*series, length(20.0, ">=")).years == (2001, 2003)


def test_season_length_is_not_a_date_metric():
    result = reduce_yearly(*same_years(2001, 2), length(5.0, ">="))
    assert result.metric_used == ""


@pytest.mark.parametrize(
    "params",
    [
        MetricParams("degree_days", threshold=18.0, op=">="),
        MetricParams("degree_days", base=18.0, op=">="),
    ],
    ids=["base_as_threshold", "base_field"],
)
def test_degree_days_sum_the_excess_over_the_base(params):
    hot_days = {f"2001-07-{day:02d}": 20.0 for day in range(1, 11)}
    series = with_values(constant(2001, 15.0), hot_days)
    assert reduce_yearly(*series, params).values == (20.0,)


def test_freezing_degree_days_sum_the_shortfall_under_the_base():
    cold_days = {f"2001-01-{day:02d}": -3.0 for day in range(1, 6)}
    series = with_values(constant(2001, 2.0), cold_days)
    params = MetricParams("degree_days", threshold=0.0, op="<")
    assert reduce_yearly(*series, params).values == (15.0,)


def test_degree_days_count_only_the_months_asked():
    hot_days = {"2001-05-31": 20.0, "2001-06-01": 20.0}
    series = with_values(constant(2001, 15.0), hot_days)
    params = MetricParams("degree_days", threshold=18.0, op=">=", months=(6, 7, 8))
    assert reduce_yearly(*series, params).values == (2.0,)


FROST = MetricParams("frost_free_length", threshold=0.0, op="<")


def test_frost_free_season_spans_the_days_between_the_two_frosts():
    assert reduce_yearly(*daily({2001: FROSTS}), FROST).values == (299 - 100,)


def test_late_spring_frost_shortens_the_frost_free_season():
    series = with_values(daily({2001: FROSTS}), {"2001-05-30": -1.0})
    assert reduce_yearly(*series, FROST).values == (299 - 150,)


def test_minimum_of_exactly_0_c_is_no_frost():
    series = with_values(daily({2001: FROSTS}), {"2001-05-30": 0.0})
    assert reduce_yearly(*series, FROST).values == (299 - 100,)


def test_year_with_no_frost_is_frost_free_all_year():
    assert reduce_yearly(*daily({2001: NO_FROST}), FROST).values == (365,)


@pytest.mark.parametrize(
    "params",
    [onset(5.0, ">="), length(5.0, ">="), MetricParams("degree_days", 0.0, "<"), FROST],
    ids=["season_onset", "season_length", "degree_days", "frost_free_length"],
)
def test_year_that_lacks_a_day_of_a_season_month_is_dropped(params):
    series = with_values(same_years(2001, 3), {"2002-03-15": np.nan})
    assert reduce_yearly(*series, params).years == (2001, 2003)
