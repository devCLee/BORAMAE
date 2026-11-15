"""Core yearly metrics: one value per year from a daily or monthly series (TR-F-015).

A reducer takes (times, values, params) and returns a YearlySeries. The extension
modules engine/metrics_season.py and engine/metrics_more.py each hold a REDUCERS
dictionary of the same form, and reduce_yearly finds a metric there by itself.
"""

from collections.abc import Callable
from importlib import import_module

import numpy as np
import numpy.typing as npt

from boramae.engine.series import (
    Season,
    censor_dates,
    complete_seasons,
    days_in_month,
    step_freq,
)
from boramae.engine.types import MetricParams, YearlySeries

Reducer = Callable[[npt.ArrayLike, npt.ArrayLike, MetricParams], YearlySeries]

EXTENSION_MODULES = ("boramae.engine.metrics_season", "boramae.engine.metrics_more")
OPERATORS = {
    ">=": np.greater_equal,
    ">": np.greater,
    "<=": np.less_equal,
    "<": np.less,
}
DEFAULT_OP = ">="  # PRD.md:409, "days in the season at or past a threshold"


def reduce_yearly(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    """Reduce a daily or monthly series to one value per complete season year."""
    reducer = REDUCERS.get(params.metric_id) or _find_extension_reducer(
        params.metric_id
    )
    return reducer(times, values, params)


def _find_extension_reducer(metric_id: str) -> Reducer:
    # Imported here and not at module level, so that a core metric never loads an
    # extension module and no import cycle can form.
    for module_name in EXTENSION_MODULES:
        reducers = import_module(module_name).REDUCERS
        if metric_id in reducers:
            return reducers[metric_id]
    raise ValueError(f"no reducer for metric {metric_id!r}")


def _reduce_mean(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    return _reduce_seasons(times, values, params, lambda season: season.values.mean())


def _reduce_total(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    # A monthly POWER value of a flux is a daily mean, such as mm/day, so a total
    # weights each month by its day count. A daily value counts once.
    is_monthly = step_freq(times) == "monthly"

    def total(season: Season) -> float:
        step_days = days_in_month(season.times) if is_monthly else 1
        return (season.values * step_days).sum()

    return _reduce_seasons(times, values, params, total)


def _reduce_threshold_days(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    return _reduce_seasons(
        times,
        values,
        params,
        lambda season: np.count_nonzero(_is_event(season.values, params)),
    )


def _reduce_rx1day(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    return _reduce_seasons(times, values, params, lambda season: season.values.max())


def _reduce_first_date(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    seasons = complete_seasons(times, values, params.months, params.season_start)
    events = [_is_event(season.values, params) for season in seasons]
    return censor_dates(
        years=[season.year for season in seasons],
        dates=[
            int(season.days[is_event.argmax()]) if is_event.any() else None
            for season, is_event in zip(seasons, events)
        ],
        # ponytail: a censored year takes the last day of its own season year, so
        # 365 or 366 (TR-D-006, "that end date"). Two censored years then differ by
        # a day in a leap season; use one constant end day if they must tie.
        end_days=[int(season.days[-1]) for season in seasons],
        # ponytail: TRD Q-02 leaves the event-day count open. For first_date it is
        # the number of days in the season year that meet the threshold. Change it
        # here when Q-02 is decided.
        event_days=[int(np.count_nonzero(is_event)) for is_event in events],
    )


def _reduce_seasons(
    times: npt.ArrayLike,
    values: npt.ArrayLike,
    params: MetricParams,
    reduce_season: Callable[[Season], float],
) -> YearlySeries:
    seasons = complete_seasons(times, values, params.months, params.season_start)
    return YearlySeries(
        years=tuple(season.year for season in seasons),
        values=tuple(float(reduce_season(season)) for season in seasons),
        is_censored=(False,) * len(seasons),
    )


def _is_event(values: npt.NDArray[np.float64], params: MetricParams) -> npt.NDArray:
    return OPERATORS[params.op or DEFAULT_OP](values, params.threshold)


REDUCERS: dict[str, Reducer] = {
    "annual_mean": _reduce_mean,
    "annual_total": _reduce_total,
    "seasonal_mean": _reduce_mean,
    "seasonal_total": _reduce_total,
    "first_date": _reduce_first_date,
    "threshold_days": _reduce_threshold_days,
    "rx1day": _reduce_rx1day,
}
