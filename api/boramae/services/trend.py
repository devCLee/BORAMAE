"""Flow B: a request spec becomes a stored, tested trend (TDD.md:163-193).

get_trend validates, keys and looks the result up. On a miss one computation reads the
cells, builds the area series, reduces it to yearly values and runs the engine. The
stored body holds no request fact: the bytes fetched, the timings and the cache status
travel beside it, for the headers and the log line (TR-D-010, TR-O-003).
"""

import logging
import math
import time
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from boramae.config import load_settings
from boramae.contracts.http import CacheStatus
from boramae.contracts.results import (
    RATE_UNIT_PERCENT_POINTS,
    MonthlyForm,
    RatesPerDecade,
    StatsRecord,
    TrendFlag,
    TrendResult,
    TrendSeries,
    YearlyForm,
)
from boramae.contracts.results_catalog import Catalog, CatalogMetric, CatalogVariable
from boramae.contracts.spec import CanonicalSpec, RequestSpec, SpecMetric
from boramae.engine import series
from boramae.engine.metrics import reduce_yearly
from boramae.engine.trend import trend_stats
from boramae.engine.types import (
    CellSeries,
    MetricParams,
    TrendStats,
    Verdict,
    VerdictResult,
    YearlySeries,
)
from boramae.engine.verdict import decide_verdict, residual_phi, residual_sd
from boramae.errors import PowerUnavailable, ProblemError
from boramae.ports import Freq, SeriesReader
from boramae.services.catalog import find_metric, find_variable
from boramae.services.content import load_content
from boramae.services.provenance import build_provenance, method_constants
from boramae.spec.canonical import canonicalize, result_key
from boramae.spec.validate import BAD_REQUEST, INVALID_SPEC, validate_request
from boramae.store.results import HEADER_RETRY_AFTER, RETRY_AFTER_S, ResultService

TREND_KIND = "trend"
UNAVAILABLE_STATUS = 503
POWER_UNAVAILABLE_CODE = "power_unavailable"  # docs/BUILD_CONTRACT.md "Errors"
READ_STEP = "read"
STATS_STEP = "stats"
DECADE_YEARS = 10
MEAN_KIND = "mean"
NO_DATA = "no_data"
RECORD_TOO_SHORT = "record_too_short"
DAYS_UNIT = "days"
DAY_OF_SEASON_UNIT = "day of season"
DAILY_SUM_RULE = "daily_sum"
PER_DAY_SUFFIX = "/day"
# ponytail: no document spells the unit of a yearly value. The words follow the
# unit_rule of content/catalog.seed.json and the labels of web/src/messages/*/units.json;
# the rule "data" keeps the unit of the variable.
RULE_UNITS = {
    "day_of_season": DAY_OF_SEASON_UNIT,
    "days": DAYS_UNIT,
    "degree_days": "degree-day",
    "months": "months",
    "ratio": "1",
}

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrendFacts:
    """The facts of one request. They go to the headers and the log, never a file."""

    bytes_fetched: int  # 0 for a hit
    used_containing_cell: bool
    timings: dict[str, float]  # step name to milliseconds; empty for a hit


def get_trend(
    request_spec: RequestSpec,
    *,
    reader: SeriesReader,
    results: ResultService,
    catalog: Catalog,
    bounded: bool = True,
) -> tuple[bytes, str, CacheStatus, TrendFacts]:
    """The stored body of a trend, its key, the cache status and the request facts.

    bounded true (a public request) waits for a pool slot; a builder's leaf, which holds
    a slot already, passes false. A bad spec raises ProblemError 400 and a POWER
    failure 503 with Retry-After; neither stores anything.
    """
    if request_spec.kind != TREND_KIND:
        raise ProblemError(BAD_REQUEST, INVALID_SPEC, "the spec kind is not trend")
    validated = validate_request(request_spec, catalog)
    canonical = canonicalize(validated, catalog)
    key = result_key(canonical)
    freq = store_freq(canonical, catalog)
    timings: dict[str, float] = {}
    fetched: list[int] = []

    def compute() -> TrendResult:
        started = time.perf_counter()
        read = _read_area(canonical, reader, freq)
        timings[READ_STEP] = _ms_since(started)
        fetched.append(read.fetched_bytes)
        started = time.perf_counter()
        result = _build_result(canonical, catalog, freq, read)
        timings[STATS_STEP] = _ms_since(started)
        return result

    try:
        body, cache = results.get_or_compute(TREND_KIND, key, compute, bounded)
    except PowerUnavailable as exc:
        _log.warning("trend %s: %s", key, exc)
        raise ProblemError(
            UNAVAILABLE_STATUS,
            POWER_UNAVAILABLE_CODE,
            headers={HEADER_RETRY_AFTER: str(RETRY_AFTER_S)},
        ) from exc
    facts = TrendFacts(sum(fetched), validated.used_containing_cell, timings)
    return body, key, cache, facts


def compute_trend(
    canonical: CanonicalSpec, catalog: Catalog, reader: SeriesReader
) -> TrendResult:
    """The trend result of a canonical spec, computed with no store."""
    freq = store_freq(canonical, catalog)
    return _build_result(canonical, catalog, freq, _read_area(canonical, reader, freq))


def store_freq(canonical: CanonicalSpec, catalog: Catalog) -> Freq:
    """The store that the canonical ds names: the ds picks it, never the metric."""
    return "daily" if canonical.ds == catalog.datasets.daily.ds else "monthly"


def _read_area(
    canonical: CanonicalSpec, reader: SeriesReader, freq: Freq
) -> CellSeries:
    start_year, last_month = canonical.window
    cells = [(lat_i, lon_i) for lat_i, lon_i in canonical.cells]
    start = f"{start_year:04d}-01"
    return reader.read_cells(canonical.var, freq, cells, start, last_month)


def _build_result(
    canonical: CanonicalSpec, catalog: Catalog, freq: Freq, read: CellSeries
) -> TrendResult:
    variable = find_variable(catalog, canonical.var)
    metric = find_metric(catalog, canonical.metric.id)
    grid = catalog.grid
    lats = [grid.lat0 + grid.dlat * lat_i for lat_i, _ in canonical.cells]
    area = series.area_mean(read.values, lats)
    yearly = reduce_yearly(read.times, area, _metric_params(canonical.metric))
    stats = trend_stats(yearly.values, yearly.years)
    verdict = _verdict(yearly, stats, variable.min_record_years)
    has_verdict = verdict.verdict is not Verdict.RecordTooShort
    no_verdict_reason = RECORD_TOO_SHORT if yearly.values else NO_DATA
    metric_used = yearly.metric_used or None
    unit = _yearly_unit(metric.id, variable.unit, metric_used)
    dataset = getattr(catalog.datasets, freq)
    return TrendResult(
        spec=canonical,
        unit=unit,
        rate_unit=_rate_unit(metric, variable, unit),
        metric_used=metric_used,
        series=TrendSeries(
            yearly=YearlyForm(
                years=list(yearly.years),
                values=list(yearly.values),
                is_censored=list(yearly.is_censored),
            ),
            monthly=_monthly_form(read.times, area) if freq == "monthly" else None,
        ),
        record=series.record_check(area, yearly.years, variable.min_record_years),
        stats=_stats_record(stats),
        change_over_record=verdict.change,
        sd=verdict.sd,
        span_years=verdict.span_years,
        verdict=verdict.verdict.value if has_verdict else None,
        reason=None if has_verdict else no_verdict_reason,
        flags=_flags(verdict) if has_verdict else [],
        years_needed=verdict.years_needed,
        method=method_constants(variable.min_record_years),
        provenance=build_provenance(
            canonical, dataset, freq, load_settings().compute_location
        ),
        footprint=read.footprint,
    )


def _metric_params(metric: SpecMetric) -> MetricParams:
    threshold = None if metric.threshold is None else float(metric.threshold)
    return MetricParams(
        metric_id=metric.id,
        threshold=threshold,
        op=metric.op,
        months=tuple(metric.months or ()),
        season_start=metric.season_start,
        # ponytail: the spec has one threshold slot, so a degree-day metric reads it
        # as its base. Add a base to SpecMetric if a metric needs both.
        base=threshold,
    )


def _verdict(
    yearly: YearlySeries, stats: TrendStats, min_record_years: int
) -> VerdictResult:
    slope = stats.sen.slope
    return decide_verdict(
        stats,
        residual_sd(yearly.values, yearly.years, slope),
        len(yearly.values),
        min_record_years,
        False,  # no P0 variable is context-only (docs/BUILD_CONTRACT.md)
        phi=residual_phi(yearly.values, yearly.years, slope),
    )


def _flags(verdict: VerdictResult) -> list[TrendFlag]:
    flags: list[TrendFlag] = []
    if verdict.methods_disagree:
        flags.append("methods_disagree")
    if verdict.ols_p_missing:
        flags.append("ols_p_missing")
    return flags


def _yearly_unit(metric_id: str, data_unit: str, metric_used: str | None) -> str:
    if metric_used == series.METRIC_USED_EVENT_DAYS:
        return DAYS_UNIT
    rule = {item.id: item.unit_rule for item in load_content("catalog_seed").metrics}[
        metric_id
    ]
    if rule == DAILY_SUM_RULE:
        return data_unit.removesuffix(PER_DAY_SUFFIX)
    return RULE_UNITS.get(rule, data_unit)


def _rate_unit(metric: CatalogMetric, variable: CatalogVariable, unit: str) -> str:
    """The bounded mark sits on the yearly value (TRD Q-02 definition 9)."""
    if metric.value_kind == MEAN_KIND and variable.share_scale is not None:
        return RATE_UNIT_PERCENT_POINTS
    # A day of the season moves by days.
    return DAYS_UNIT if unit == DAY_OF_SEASON_UNIT else unit


def _stats_record(stats: TrendStats) -> StatsRecord:
    sen, ols = stats.sen, stats.ols
    return StatsRecord(
        n=stats.n,
        first_year=stats.first_year,
        last_year=stats.last_year,
        mk=stats.mk,
        sen=sen,
        ols=ols,
        rates=RatesPerDecade(
            sen=_per_decade(sen.slope),
            sen_ci_low=_per_decade(sen.ci_low),
            sen_ci_high=_per_decade(sen.ci_high),
            ols=_per_decade(ols.slope),
            ols_ci_plain_low=_per_decade(ols.ci_plain_low),
            ols_ci_plain_high=_per_decade(ols.ci_plain_high),
            ols_ci_adj_low=_per_decade(ols.ci_adj_low),
            ols_ci_adj_high=_per_decade(ols.ci_adj_high),
        ),
        reason=stats.reason,
    )


def _per_decade(per_year: float | None) -> float | None:
    return None if per_year is None else per_year * DECADE_YEARS


def _monthly_form(
    times: npt.NDArray[np.datetime64], area: npt.NDArray[np.float64]
) -> MonthlyForm:
    return MonthlyForm(
        months=np.datetime_as_string(times, unit="M").tolist(),
        values=_nullable(area),
        anomalies=_nullable(series.monthly_anomalies(times, area)),
    )


def _nullable(values: npt.NDArray[np.float64]) -> list[float | None]:
    return [None if math.isnan(value) else value for value in values.tolist()]


def _ms_since(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)
