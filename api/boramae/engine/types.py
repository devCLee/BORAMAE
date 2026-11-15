"""Value types of the engine. Frozen from wave 2: report a needed change.

A statistic that cannot be computed is None, with a reason code beside it, and never
NaN. Slopes are per year; the service turns them into rates per decade.
"""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class MkResult:
    s: float | None
    var_s: float | None
    var_star: float | None
    rho1: float | None
    z: float | None
    p: float | None


@dataclass(frozen=True)
class SenResult:
    slope: float | None
    intercept: float | None
    ci_low: float | None
    ci_high: float | None


@dataclass(frozen=True)
class OlsResult:
    slope: float | None
    intercept: float | None
    p_plain: float | None
    ci_plain_low: float | None
    ci_plain_high: float | None
    r1: float | None
    n_eff: float | None
    p_adj: float | None
    ci_adj_low: float | None
    ci_adj_high: float | None
    reason: str | None = None


@dataclass(frozen=True)
class TrendStats:
    n: int
    first_year: int | None
    last_year: int | None
    mk: MkResult
    sen: SenResult
    ols: OlsResult
    reason: str | None = None


class Verdict(StrEnum):
    SignificantRise = "significant_rise"
    SignificantFall = "significant_fall"
    NotYet = "not_yet"
    NoTrend = "no_trend"
    RecordTooShort = "record_too_short"


@dataclass(frozen=True)
class YearsNeeded:
    total: float | None
    more: int | None
    reason: str | None = None


@dataclass(frozen=True)
class VerdictResult:
    verdict: Verdict | None  # None for a context-only variable
    change: float | None
    sd: float | None
    span_years: int | None
    methods_disagree: bool
    ols_p_missing: bool
    years_needed: YearsNeeded | None
    reason: str | None = None


@dataclass(frozen=True)
class YearlySeries:
    years: tuple[int, ...]
    values: tuple[float, ...]
    is_censored: tuple[bool, ...]
    metric_used: str = ""  # 'date', 'event_days', or empty for a non-date metric
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class MetricParams:
    metric_id: str
    threshold: float | None = None  # in the data unit
    op: str | None = None  # '>=', '>', '<=' or '<'
    months: tuple[int, ...] = ()  # 1 to 12; empty means the calendar year
    season_start: str | None = None  # 'MM-DD', start of the season year
    base: float | None = None  # degree-day base, in the data unit


@dataclass(frozen=True)
class RecordCheck:
    years_covered: int
    missing_share: float
    is_missing_flagged: bool
    is_too_short: bool


@dataclass(frozen=True)
class LinkResult:
    r: float | None
    p: float | None
    n_eff: float | None
    lag_years: int
    n_overlap: int
    sign: int | None  # +1, -1 or 0, the sign of r
    label: str | None  # None for an opposite sign that is not significant
    reason: str | None = None


@dataclass(frozen=True)
class GridDef:
    lat0: float
    dlat: float
    n_lat: int
    lon0: float
    dlon: float
    n_lon: int


@dataclass(frozen=True)
class Footprint:
    chunk_count: int
    stored_bytes: int


@dataclass(frozen=True)
class CellSeries:
    times: npt.NDArray[np.datetime64]
    values: npt.NDArray[np.float64]  # [time, cell], NaN where a value is missing
    footprint: Footprint
    fetched_bytes: int
