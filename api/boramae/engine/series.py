"""Area series, seasonal removal, record check and the season helpers (DES-008).

Pure functions with no I/O. Inside a series a missing value is NaN. The metric
modules import the season helpers from here, never from engine/metrics.py.
"""

from collections.abc import Sequence
from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from boramae.engine.definitions import (
    CENSORED_SHARE_SWITCH,
    MIN_RECORD_YEARS,
    MISSING_SHARE_FLAG,
)
from boramae.engine.types import RecordCheck, YearlySeries

ALL_MONTHS = tuple(range(1, 13))
MONTHS_IN_YEAR = 12
EPOCH_YEAR = 1970  # numpy counts datetime64 years and months from 1970-01
ONE_DAY = np.timedelta64(1, "D")
ONE_MONTH = np.timedelta64(1, "M")
METRIC_USED_DATE = "date"
METRIC_USED_EVENT_DAYS = "event_days"


class Season(NamedTuple):
    """The steps of one complete season year, in time order."""

    year: int  # the calendar year in which the season year starts
    times: npt.NDArray[np.datetime64]
    days: npt.NDArray[np.int64]  # day of the season year of each step, from 1
    values: npt.NDArray[np.float64]


def cos_lat_weights(lats: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Cell weights: the cosine of each cell-center latitude, in degrees."""
    return np.cos(np.deg2rad(np.asarray(lats, dtype=float)))


def area_mean(values: npt.ArrayLike, lats: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Cos-latitude-weighted mean of values[time, cell] at each time step (FR-08)."""
    cells = np.asarray(values, dtype=float)
    weights = cos_lat_weights(lats)
    is_valid = ~np.isnan(cells)
    # ponytail: TRD Q-04 leaves the missing-cell rule open. A step averages its
    # non-missing cells and is missing only when every cell is. Change it here
    # when Q-04 is decided.
    weight_sums = is_valid @ weights
    weighted_sums = np.where(is_valid, cells, 0.0) @ weights
    return np.divide(
        weighted_sums,
        weight_sums,
        out=np.full(weight_sums.shape, np.nan),
        where=weight_sums > 0,
    )


def monthly_anomalies(
    times: npt.ArrayLike, values: npt.ArrayLike
) -> npt.NDArray[np.float64]:
    """Each value minus the window mean of its calendar month (TR-D-004, method 1)."""
    series = np.asarray(values, dtype=float)
    month_index = _month_numbers(_to_days(times)) - 1
    is_valid = ~np.isnan(series)
    sums = np.bincount(
        month_index[is_valid], weights=series[is_valid], minlength=MONTHS_IN_YEAR
    )
    counts = np.bincount(month_index[is_valid], minlength=MONTHS_IN_YEAR)
    climatology = np.divide(
        sums, counts, out=np.full(MONTHS_IN_YEAR, np.nan), where=counts > 0
    )
    return series - climatology[month_index]


def record_check(
    values: npt.ArrayLike, years: Sequence[int], min_years: int = MIN_RECORD_YEARS
) -> RecordCheck:
    """Record check of a series and the years of its yearly series (TR-D-005)."""
    series = np.asarray(values, dtype=float)
    n_missing = int(np.count_nonzero(np.isnan(series)))
    # ponytail: no document gives the share of an empty series. It reads as fully
    # missing (1.0), so the flag is set. Change it here if "no data" needs its own mark.
    missing_share = n_missing / series.size if series.size else 1.0
    return RecordCheck(
        years_covered=len(years),
        missing_share=missing_share,
        is_missing_flagged=missing_share > MISSING_SHARE_FLAG,
        is_too_short=len(years) < min_years,
    )


def step_freq(times: npt.ArrayLike) -> str:
    """'daily' when the steps are one day apart, else 'monthly'."""
    dates = _to_days(times)
    # ponytail: the first two steps decide, because a reader axis has no gaps. A
    # one-step series reads as monthly. Pass the frequency in if an axis can
    # be sparse.
    is_daily = dates.size > 1 and dates[1] - dates[0] == ONE_DAY
    return "daily" if is_daily else "monthly"


def days_in_month(times: npt.ArrayLike) -> npt.NDArray[np.int64]:
    """The day count of the calendar month of each step."""
    months = np.asarray(times).astype("datetime64[M]")
    next_months = (months + ONE_MONTH).astype("datetime64[D]")
    return (next_months - months.astype("datetime64[D]")).astype(int)


def present_months(
    times: npt.ArrayLike, values: npt.ArrayLike, freq: str
) -> npt.NDArray[np.datetime64]:
    """The calendar months that hold a value at every expected step, ascending.

    `freq` is 'daily' or 'monthly'.
    """
    months = np.asarray(times).astype("datetime64[M]")
    is_valid = ~np.isnan(np.asarray(values, dtype=float))
    found, counts = np.unique(months[is_valid], return_counts=True)
    # ponytail: TRD Q-02 definition 8 leaves a month with missing days open. One
    # missing day makes the month absent. Lower `expected` to allow gaps.
    expected = days_in_month(found) if freq == "daily" else 1
    return found[counts == expected]


def season_years(
    times: npt.ArrayLike,
    months: Sequence[int] = (),
    season_start: str | None = None,
) -> npt.NDArray[np.int64]:
    """The season year of each step: the calendar year in which it starts."""
    # ponytail: no document names the label of a season year. The start year is
    # used, so Dec 1981 to Feb 1982 is 1981. Change the label here if the cards
    # must name a winter by its January.
    start_month, start_day = _season_start(months, season_start)
    dates = _to_days(times)
    month = _month_numbers(dates)
    day = (dates - dates.astype("datetime64[M]")).astype(int) + 1
    is_before_start = (month < start_month) | (
        (month == start_month) & (day < start_day)
    )
    return dates.astype("datetime64[Y]").astype(int) + EPOCH_YEAR - is_before_start


def complete_seasons(
    times: npt.ArrayLike,
    values: npt.ArrayLike,
    months: Sequence[int] = (),
    season_start: str | None = None,
) -> list[Season]:
    """The season years that hold every month of their season (Q-02 definition 8).

    Empty `months` means all twelve. With no `season_start`, the season year is the
    calendar year, or it starts with the season when the months cross the year end.
    """
    dates = _to_days(times)
    series = np.asarray(values, dtype=float)
    season_months = tuple(months) or ALL_MONTHS
    start_month, start_day = _season_start(months, season_start)
    labels = season_years(dates, months, season_start)
    is_in_season = np.isin(_month_numbers(dates), season_months)
    present = present_months(dates, series, step_freq(dates))
    seasons = []
    # ponytail: one mask over the series per season year, about 5 ms for 45 years
    # of daily steps. Slice by sorted labels if the grid run needs it faster.
    for year in np.unique(labels[is_in_season]).tolist():
        needed = _needed_months(year, season_months, start_month, start_day)
        if not np.isin(needed, present).all():
            continue
        is_picked = is_in_season & (labels == year)
        start = np.datetime64(f"{year:04d}-{start_month:02d}-{start_day:02d}", "D")
        days = (dates[is_picked] - start).astype(int) + 1
        seasons.append(Season(year, dates[is_picked], days, series[is_picked]))
    return seasons


def censor_dates(
    years: Sequence[int],
    dates: Sequence[float | None],
    end_days: Sequence[float],
    event_days: Sequence[float],
) -> YearlySeries:
    """Yearly series of a date metric, with its event-free years censored (TR-D-006).

    `dates` holds the event day of each season year, or None for a year with no
    event. Such a year takes its season end day from `end_days` and the censored
    flag. Above CENSORED_SHARE_SWITCH censored years, the series holds
    `event_days` instead, the caller's count of event days in each season year.
    """
    is_censored = tuple(date is None for date in dates)
    n_years = len(years)
    if n_years and sum(is_censored) / n_years > CENSORED_SHARE_SWITCH:
        return YearlySeries(
            years=tuple(years),
            values=tuple(float(count) for count in event_days),
            is_censored=(False,) * n_years,
            metric_used=METRIC_USED_EVENT_DAYS,
        )
    values = tuple(
        float(end_day if date is None else date)
        for date, end_day in zip(dates, end_days)
    )
    return YearlySeries(tuple(years), values, is_censored, METRIC_USED_DATE)


def _to_days(times: npt.ArrayLike) -> npt.NDArray[np.datetime64]:
    return np.asarray(times).astype("datetime64[D]")


def _month_numbers(dates: npt.NDArray[np.datetime64]) -> npt.NDArray[np.int64]:
    return dates.astype("datetime64[M]").astype(int) % MONTHS_IN_YEAR + 1


def _season_start(months: Sequence[int], season_start: str | None) -> tuple[int, int]:
    """Month and day on which the season year starts."""
    if season_start:
        month, day = season_start.split("-")
        return int(month), int(day)
    # ponytail: no document says where a season year starts when the spec gives only
    # months. Months that hold December and January start with the run of months
    # that ends in December. Any other set uses the calendar year.
    if not {12, 1} <= set(months):
        return 1, 1
    start_month = 12
    while start_month - 1 in months:
        start_month -= 1
    return start_month, 1


def _needed_months(
    year: int, season_months: Sequence[int], start_month: int, start_day: int
) -> npt.NDArray[np.datetime64]:
    """The calendar months that the season year `year` must hold."""
    needed = [
        f"{year + (month < start_month):04d}-{month:02d}" for month in season_months
    ]
    # A season year that starts inside a month also ends inside that month.
    if start_day > 1 and start_month in season_months:
        needed.append(f"{year + 1:04d}-{start_month:02d}")
    return np.array(needed, dtype="datetime64[M]")
