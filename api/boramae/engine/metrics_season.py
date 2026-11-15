"""Season reducers of the P0 boards (PRD "Metric library"): season onset and length
by the KMA rule, degree-days and the frost-free season.

Pure functions with no I/O, on a daily series. engine/metrics.py finds REDUCERS by
itself. The season helpers come from engine/series.py, never from engine/metrics.py.
"""

import operator
from collections.abc import Callable

import numpy as np
import numpy.typing as npt

from boramae.engine.series import Season, censor_dates, complete_seasons
from boramae.engine.types import MetricParams, YearlySeries

RUNNING_MEAN_DAYS = 9  # PRD "Metric library", KMA rule
OPERATORS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt}
RISING_OPS = (">=", ">")
OPPOSITE_OPS = {">=": "<", ">": "<=", "<=": ">", "<": ">="}
# KMA order where the next onset has another threshold: spring (5 C rising) runs to
# summer (20 C rising), autumn (20 C falling) to winter (5 C falling). Any other
# onset, summer and winter among them, runs to the crossing of its own threshold
# the other way.
NEXT_THRESHOLD = {(5.0, True): 20.0, (20.0, False): 5.0}
MAX_SEASON = np.timedelta64(366, "D")


def _reduce_season_onset(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    """Day of the season year of the onset; a season year with none is censored."""
    seasons = _smoothed_seasons(times, values, params)
    onsets = [_onset_index(s.values, params.threshold, params.op) for s in seasons]
    return censor_dates(
        years=[season.year for season in seasons],
        dates=[
            None if index is None else int(season.days[index])
            for season, index in zip(seasons, onsets)
        ],
        end_days=[int(season.days[-1]) for season in seasons],
        # ponytail: TRD Q-02 leaves the event-day count open. As for first_date, it
        # is the count of days whose running mean meets the threshold.
        event_days=[
            int(np.count_nonzero(OPERATORS[params.op](s.values, params.threshold)))
            for s in seasons
        ],
    )


# ponytail: a season year with no onset of this season, or with no next onset
# within a year after it, gives no value, so a year with no winter at all is absent
# and not 0. Give it 0 if a vanishing season must count.
def _reduce_season_length(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    """Days from the onset of a season to the onset of the next (PRD "Metric
    library"). The next onset may fall in the next season year, as for winter."""
    seasons = _smoothed_seasons(times, values, params)
    next_threshold, next_op = _next_onset(params.threshold, params.op)
    next_onsets = np.array(
        [
            onset
            for season in seasons
            if (onset := _onset_time(season, next_threshold, next_op)) is not None
        ],
        dtype="datetime64[D]",
    )
    lengths = {
        season.year: _days_until_next(start, next_onsets)
        for season in seasons
        if (start := _onset_time(season, params.threshold, params.op)) is not None
    }
    kept = {year: days for year, days in lengths.items() if days is not None}
    return YearlySeries(
        tuple(kept), tuple(map(float, kept.values())), (False,) * len(kept)
    )


# ponytail: the reducer sums the daily value of the variable it is given. For T2M
# that is the mean of the hours, not the (max + min) / 2 of the PRD row.
def _reduce_degree_days(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    """The excess of each daily value over the base (a rising op) or under it,
    summed. A spec carries the base as its threshold; MetricParams.base wins."""
    base = params.threshold if params.base is None else params.base
    direction = 1.0 if params.op in RISING_OPS else -1.0
    return _yearly(
        complete_seasons(times, values, params.months, params.season_start),
        lambda season: np.maximum(direction * (season.values - base), 0.0).sum(),
    )


def _reduce_frost_free_length(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> YearlySeries:
    """Frost-free days between the last spring frost and the first autumn frost. A
    frost is a daily value that meets the threshold, such as T2M_MIN below 0 C."""
    return _yearly(
        complete_seasons(times, values, params.months, params.season_start),
        lambda season: _frost_free_days(season.values, params.threshold, params.op),
    )


def _smoothed_seasons(
    times: npt.ArrayLike, values: npt.ArrayLike, params: MetricParams
) -> list[Season]:
    """The complete season years of the 9-day centered running mean.

    A missing day stays missing, so a season year is complete exactly when the
    daily series is (Q-02 definition 8).
    """
    # ponytail: the PRD does not say centered or trailing; centered, as KMA's 9-day
    # mean is read. At the record edges and next to a missing day the window holds
    # only the days present.
    daily = np.asarray(values, dtype=float)
    is_valid = ~np.isnan(daily)
    window = np.ones(RUNNING_MEAN_DAYS)
    middle = slice(RUNNING_MEAN_DAYS // 2, RUNNING_MEAN_DAYS // 2 + daily.size)
    sums = np.convolve(np.where(is_valid, daily, 0.0), window)[middle]
    counts = np.convolve(is_valid.astype(float), window)[middle]
    running_mean = np.divide(
        sums, counts, out=np.full(daily.size, np.nan), where=is_valid
    )
    return complete_seasons(times, running_mean, params.months, params.season_start)


# ponytail: PRD "and stays there" is read as: from the onset to the turning day the
# running mean never returns across the threshold. A falling onset after the end of
# the season year (a winter that starts in January of a calendar season year) is
# then censored; a spec with season_start 07-01 moves that boundary.
def _onset_index(running_mean: np.ndarray, threshold: float, op: str) -> int | None:
    """Index of the onset in a season year, or None when it has none.

    The onset is the first day of the run of days that meet the threshold and end
    on the turning day: the warmest day for a rising threshold, the coldest day
    after it for a falling one. The run must start after a day that misses the
    threshold, from the season-year start (rising) or the warmest day (falling).
    """
    meets = OPERATORS[op](running_mean, threshold)
    peak = int(np.argmax(running_mean))
    if op in RISING_OPS:
        first, turn = 0, peak
    else:
        first, turn = peak, peak + int(np.argmin(running_mean[peak:]))
    misses = np.flatnonzero(~meets[first:turn])
    if not meets[turn] or not misses.size:
        return None
    return first + int(misses[-1]) + 1


def _onset_time(season: Season, threshold: float, op: str) -> np.datetime64 | None:
    index = _onset_index(season.values, threshold, op)
    return None if index is None else season.times[index]


def _next_onset(threshold: float, op: str) -> tuple[float, str]:
    """The onset that ends the season that (threshold, op) starts."""
    next_threshold = NEXT_THRESHOLD.get((threshold, op in RISING_OPS))
    if next_threshold is None:
        return threshold, OPPOSITE_OPS[op]
    return next_threshold, op


def _days_until_next(start: np.datetime64, next_onsets: np.ndarray) -> int | None:
    later = next_onsets[next_onsets > start]
    if later.size and later[0] - start <= MAX_SEASON:
        return int((later[0] - start).astype(int))
    return None


# ponytail: the warmest day of the season year splits spring frosts from autumn
# ones, and frost-free days are counted strictly between the two frosts. A season
# year with no spring or no autumn frost counts from its first or to its last day.
def _frost_free_days(values: np.ndarray, threshold: float, op: str) -> int:
    is_frost = OPERATORS[op](values, threshold)
    peak = int(np.argmax(values))
    spring = np.flatnonzero(is_frost[:peak])
    autumn = np.flatnonzero(is_frost[peak:])
    last_spring = int(spring[-1]) if spring.size else -1
    first_autumn = peak + int(autumn[0]) if autumn.size else values.size
    return first_autumn - last_spring - 1


def _yearly(
    seasons: list[Season], reduce_season: Callable[[Season], float]
) -> YearlySeries:
    return YearlySeries(
        years=tuple(season.year for season in seasons),
        values=tuple(float(reduce_season(season)) for season in seasons),
        is_censored=(False,) * len(seasons),
    )


REDUCERS = {
    "season_onset": _reduce_season_onset,
    "season_length": _reduce_season_length,
    "degree_days": _reduce_degree_days,
    "frost_free_length": _reduce_frost_free_length,
}
