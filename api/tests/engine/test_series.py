import math

import numpy as np
import pytest

from boramae.engine.series import (
    area_mean,
    censor_dates,
    complete_seasons,
    cos_lat_weights,
    monthly_anomalies,
    present_months,
    record_check,
    season_years,
)

SEASONAL_CYCLE = 10.0 * np.cos(2 * np.pi * np.arange(12) / 12)
SEASONAL_YEARS = 10
NOISE = np.random.default_rng(7).normal(0.0, 1.0, SEASONAL_YEARS * 12)

# Arguments of censor_dates: years, event dates, season end days, event-day counts.
ONE_CENSORED_OF_FIVE = (
    [1981, 1982, 1983, 1984, 1985],
    [112, 120, None, 99, 130],
    [365, 365, 366, 365, 365],
    [3, 2, 0, 4, 1],
)
TWO_CENSORED_OF_THREE = (
    [1981, 1982, 1983],
    [None, None, 100],
    [365, 365, 365],
    [0, 0, 4],
)


def monthly_times(first_year, last_year):
    return np.arange(f"{first_year}-01", f"{last_year + 1}-01", dtype="datetime64[M]")


def daily_times(start, stop):
    return np.arange(start, stop, dtype="datetime64[D]")


def reference_area_mean(values, lats):
    """The weighted mean coded cell by cell, with no numpy call of the engine."""
    weights = [math.cos(math.radians(lat)) for lat in lats]
    return [
        sum(weight * value for weight, value in zip(weights, row)) / sum(weights)
        for row in values.tolist()
    ]


def fixed_cells(seed, n_steps, n_cells):
    return np.random.default_rng(seed).uniform(-30.0, 40.0, (n_steps, n_cells))


def with_missing(values, indices):
    series = np.array(values, dtype=float)
    series[indices] = np.nan
    return series


def valid_until(times, last_valid_date):
    return np.where(times <= np.datetime64(last_valid_date), 1.0, np.nan)


def months_of(values):
    return [str(month) for month in values]


# Hand values: cos 0 = 1, cos 60 = 0.5 and cos 90 = 0.
def test_cos_lat_weights_equal_the_hand_values():
    assert cos_lat_weights([0.0, 60.0, -60.0, 90.0]) == pytest.approx(
        [1.0, 0.5, 0.5, 0.0], abs=1e-12
    )


# Hand value: (10 x 1 + 40 x 0.5) / (1 + 0.5) = 20.
def test_area_mean_of_two_cells_at_different_latitudes_is_the_weighted_value():
    assert area_mean([[10.0, 40.0]], [0.0, 60.0]) == pytest.approx([20.0])


@pytest.mark.parametrize(
    ("values", "lats"),
    [
        (fixed_cells(1, 5, 3), [37.0, 37.5, 38.0]),
        (fixed_cells(2, 4, 6), [33.0, 33.0, 33.5, 33.5, 34.0, 34.0]),
        (fixed_cells(3, 10, 12), np.linspace(-72.0, 81.5, 12).tolist()),
    ],
    ids=["three_cells", "six_cells", "wide_latitude_range"],
)
def test_area_mean_matches_an_independent_reference_within_a_tenth_percent(
    values, lats
):
    assert area_mean(values, lats) == pytest.approx(
        reference_area_mean(values, lats), rel=1e-3
    )


def test_area_mean_of_a_step_with_a_missing_cell_uses_the_other_cells():
    assert area_mean([[np.nan, 40.0]], [0.0, 60.0]) == pytest.approx([40.0])


def test_area_mean_of_a_step_with_every_cell_missing_is_missing():
    assert np.isnan(area_mean([[np.nan, np.nan]], [0.0, 60.0])[0])


@pytest.mark.parametrize(
    "values",
    [
        np.tile(SEASONAL_CYCLE, SEASONAL_YEARS),
        np.tile(SEASONAL_CYCLE, SEASONAL_YEARS) + NOISE,
    ],
    ids=["seasonal_only", "seasonal_plus_noise"],
)
def test_monthly_anomalies_have_a_zero_mean_in_each_calendar_month(values):
    anomalies = monthly_anomalies(monthly_times(1981, 1990), values)
    assert anomalies.reshape(SEASONAL_YEARS, 12).mean(axis=0) == pytest.approx(
        np.zeros(12), abs=1e-9
    )


def test_monthly_anomalies_of_a_seasonal_only_series_are_zero():
    anomalies = monthly_anomalies(
        monthly_times(1981, 1990), np.tile(SEASONAL_CYCLE, SEASONAL_YEARS)
    )
    assert anomalies == pytest.approx(np.zeros(SEASONAL_YEARS * 12), abs=1e-9)


def test_monthly_anomaly_of_a_missing_month_stays_missing():
    values = with_missing(np.tile(SEASONAL_CYCLE, SEASONAL_YEARS), [5])
    assert np.isnan(monthly_anomalies(monthly_times(1981, 1990), values)[5])


@pytest.mark.parametrize(
    ("n_missing", "expected"),
    [(11, True), (10, False)],
    ids=["11_percent", "exactly_10_percent"],
)
def test_record_check_flags_a_missing_share_above_10_percent(n_missing, expected):
    values = with_missing(np.ones(100), slice(0, n_missing))
    assert record_check(values, range(1981, 2026)).is_missing_flagged is expected


def test_record_check_reports_the_missing_share():
    values = with_missing(np.ones(100), slice(0, 11))
    assert record_check(values, range(1981, 2026)).missing_share == pytest.approx(0.11)


def test_record_check_of_an_empty_series_reports_everything_missing():
    assert record_check([], []).missing_share == 1.0


def test_record_check_counts_the_years_of_the_tested_series():
    assert record_check(np.ones(12), [1981, 1982, 1984]).years_covered == 3


@pytest.mark.parametrize(
    ("n_years", "expected"),
    [(19, True), (20, False)],
    ids=["19_years", "20_years"],
)
def test_record_check_marks_a_series_under_the_minimum_record(n_years, expected):
    assert record_check(np.ones(12), range(n_years)).is_too_short is expected


def test_record_check_takes_the_minimum_record_of_the_variable():
    assert record_check(np.ones(12), range(25), min_years=30).is_too_short is True


@pytest.mark.parametrize(
    ("last_valid_date", "expected"),
    [("2026-09-30", ["2026-08", "2026-09"]), ("2026-10-01", ["2026-08", "2026-09"])],
    ids=["nan_padded_tail", "last_month_with_one_valid_day"],
)
def test_present_months_of_a_daily_series_leave_out_a_month_with_a_missing_day(
    last_valid_date, expected
):
    times = daily_times("2026-08-01", "2027-01-01")
    present = present_months(times, valid_until(times, last_valid_date), "daily")
    assert months_of(present) == expected


def test_present_months_of_a_daily_series_leave_out_a_month_with_one_gap():
    times = daily_times("2026-08-01", "2026-10-01")
    values = with_missing(np.ones(times.size), [40])
    assert months_of(present_months(times, values, "daily")) == ["2026-08"]


def test_present_months_of_a_monthly_series_leave_out_the_nan_padded_tail():
    times = monthly_times(2026, 2026)
    values = valid_until(times, "2026-08")
    assert months_of(present_months(times, values, "monthly"))[-1] == "2026-08"


@pytest.mark.parametrize(
    ("dates", "months", "season_start", "expected"),
    [
        (["1981-01-01", "1981-12-31"], (), None, [1981, 1981]),
        (
            ["1981-11-30", "1981-12-01", "1982-02-28"],
            (12, 1, 2),
            None,
            [1980, 1981, 1981],
        ),
        (
            ["1981-10-31", "1981-11-01", "1982-03-31"],
            (11, 12, 1, 2, 3),
            None,
            [1980, 1981, 1981],
        ),
        (["1981-07-31", "1981-08-01", "1982-07-31"], (), "08-01", [1980, 1981, 1981]),
        (["1981-08-14", "1981-08-15"], (), "08-15", [1980, 1981]),
    ],
    ids=["calendar_year", "dec_to_feb", "nov_to_mar", "from_1_aug", "from_mid_month"],
)
# In each case but the first, the first date is the day before a season year
# starts, so it belongs to the season year before.
def test_season_years_label_each_step_by_the_year_its_season_year_starts_in(
    dates, months, season_start, expected
):
    times = np.array(dates, dtype="datetime64[D]")
    assert season_years(times, months, season_start).tolist() == expected


def test_complete_seasons_number_the_days_from_the_season_start():
    times = daily_times("1981-08-01", "1982-08-01")
    season = complete_seasons(times, np.ones(times.size), season_start="08-01")[0]
    assert (int(season.days[0]), int(season.days[-1])) == (1, 365)


def test_complete_seasons_keep_only_the_steps_of_the_season_months():
    times = daily_times("1981-01-01", "1982-01-01")
    season = complete_seasons(times, np.ones(times.size), months=(6, 7, 8))[0]
    assert (str(season.times[0]), str(season.times[-1])) == ("1981-06-01", "1981-08-31")


def test_complete_seasons_drop_a_season_that_lacks_a_month():
    times = monthly_times(1981, 1983)
    values = with_missing(np.ones(times.size), [18])
    assert [season.year for season in complete_seasons(times, values)] == [1981, 1983]


# The season year from 15 Aug 1982 ends on 14 Aug 1983, after the last step.
def test_complete_seasons_from_mid_month_need_the_start_month_of_both_years():
    times = daily_times("1981-08-01", "1983-08-01")
    seasons = complete_seasons(times, np.ones(times.size), season_start="08-15")
    assert [season.year for season in seasons] == [1981]


def test_censor_dates_gives_an_event_free_year_the_season_end_date():
    series = censor_dates(*ONE_CENSORED_OF_FIVE)
    assert series.values == (112.0, 120.0, 366.0, 99.0, 130.0)


def test_censor_dates_flags_an_event_free_year():
    series = censor_dates(*ONE_CENSORED_OF_FIVE)
    assert series.is_censored == (False, False, True, False, False)


@pytest.mark.parametrize(
    ("n_censored", "expected"),
    [(21, "event_days"), (20, "date")],
    ids=["21_percent", "exactly_20_percent"],
)
def test_censor_dates_switches_to_event_days_above_20_percent_censored(
    n_censored, expected
):
    dates = [None] * n_censored + [100] * (100 - n_censored)
    series = censor_dates(range(1901, 2001), dates, [365] * 100, [1] * 100)
    assert series.metric_used == expected


def test_censor_dates_after_the_switch_holds_the_event_day_counts():
    series = censor_dates(*TWO_CENSORED_OF_THREE)
    assert series.values == (0.0, 0.0, 4.0)


def test_censor_dates_after_the_switch_flags_no_year():
    series = censor_dates(*TWO_CENSORED_OF_THREE)
    assert series.is_censored == (False, False, False)


def test_censor_dates_of_no_years_is_an_empty_date_series():
    assert censor_dates([], [], [], []).metric_used == "date"
