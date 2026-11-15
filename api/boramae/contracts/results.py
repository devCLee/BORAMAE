"""Trend result record of the API contract (docs/BUILD_CONTRACT.md).

Frozen from wave 2: report a needed change. A stored result holds no timing, no
cache state and no creation time, so two requests for one key get equal bodies
(TR-D-010). Those request facts travel in the response headers (contracts/http.py).
The statistics records are the frozen engine dataclasses of engine/types.py.
"""

from typing import Literal, Self

from pydantic import model_validator

from boramae.contracts.spec import CanonicalSpec, CellIndex, ContractModel, YearMonth
from boramae.engine.types import (
    Footprint,
    MkResult,
    OlsResult,
    RecordCheck,
    SenResult,
    YearsNeeded,
)

Verdict = Literal["significant_rise", "significant_fall", "not_yet", "no_trend"]
# Why a result holds no verdict. The engine verdict 'record_too_short' is stored
# as an empty verdict with this reason (TR-F-021).
# ponytail: no document names these codes or the flag codes below. Add a code
# here when the service gains another case, such as a context-only variable.
NoVerdictReason = Literal["record_too_short", "no_data"]
MetricUsed = Literal["date", "event_days"]
TrendFlag = Literal["methods_disagree", "ols_p_missing"]
Sign = Literal[-1, 0, 1]
DataKind = Literal["model"]
# The rate of a mean-type metric of a share variable (TRD Q-02 definition 9).
# Every other rate_unit is the unit of the yearly value, read as per decade.
RATE_UNIT_PERCENT_POINTS = "percent_points"


class YearlyForm(ContractModel):
    """The tested series: one value per year. A dropped year is absent."""

    years: list[int]
    values: list[float]
    is_censored: list[bool]


class MonthlyForm(ContractModel):
    """Chart form of a monthly source. A missing month is null."""

    months: list[YearMonth]
    values: list[float | None]
    anomalies: list[float | None]


class TrendSeries(ContractModel):
    yearly: YearlyForm
    monthly: MonthlyForm | None


class RatesPerDecade(ContractModel):
    """The slopes and interval bounds of the statistics, times 10 years."""

    sen: float | None
    sen_ci_low: float | None
    sen_ci_high: float | None
    ols: float | None
    ols_ci_plain_low: float | None
    ols_ci_plain_high: float | None
    ols_ci_adj_low: float | None
    ols_ci_adj_high: float | None


class StatsRecord(ContractModel):
    """engine TrendStats plus the rates. Slopes are per year, and a line is
    intercept + slope x year. A statistic with no value is null, with a reason."""

    n: int
    first_year: int | None
    last_year: int | None
    mk: MkResult
    sen: SenResult
    ols: OlsResult
    rates: RatesPerDecade
    reason: str | None


class MethodConstants(ContractModel):
    alpha: float
    ci_level: float
    min_record_years: int
    missing_share_flag: float
    censored_share_switch: float


class Period(ContractModel):
    start: YearMonth
    end: YearMonth


class Provenance(ContractModel):
    dataset_id: str
    dataset_version: str
    access_path: str
    period: Period
    cells: list[CellIndex]
    method: str  # key of the method text in the message files
    compute_location: str
    day_basis: Literal["UTC"] | None  # null for a monthly source
    data_kind: DataKind


class TrendResult(ContractModel):
    spec: CanonicalSpec
    unit: str  # unit of the yearly value
    rate_unit: str
    metric_used: MetricUsed | None  # null for a metric that is not a date
    series: TrendSeries
    record: RecordCheck
    stats: StatsRecord
    change_over_record: float | None  # Sen slope x span_years
    sd: float | None  # scatter of the series about its Sen line
    span_years: int | None
    verdict: Verdict | None
    reason: NoVerdictReason | None
    flags: list[TrendFlag]
    years_needed: YearsNeeded | None  # for every verdict that is not significant
    method: MethodConstants
    provenance: Provenance
    footprint: Footprint

    @model_validator(mode="after")
    def _has_a_verdict_or_a_reason(self) -> Self:
        if (self.verdict is None) == (self.reason is None):
            raise ValueError("a result holds either a verdict or the reason for none")
        return self
