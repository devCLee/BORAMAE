"""Scan result and trend grid records of the API contract (docs/BUILD_CONTRACT.md).

Frozen from wave 2: report a needed change. The service selects the nearby
areas (DEC-007), so the browser only shows the list.
"""

from typing import Annotated, Literal

from pydantic import Field

from boramae.constants import MAX_NEARBY_AREAS, MAX_SCAN_HITS
from boramae.contracts.results import MetricUsed, Sign
from boramae.contracts.spec import (
    CanonicalSpec,
    CanonicalWindow,
    ContractModel,
    LocalizedText,
    ResultKey,
    SpecMetric,
)

CheckedStatus = Literal["tested", "not_testable"]
NearbyNote = Literal["no_grid", "outside_grid", "grid_window_differs"]


class ScanHit(ContractModel):
    var: str
    metric_id: str
    trend_key: ResultKey
    p: float
    q: float  # Benjamini-Hochberg value across every tested variable
    rate_per_decade: float | None
    rate_unit: str
    sign: Sign
    label: Literal["found_by_scan"]


class ScanChecked(ContractModel):
    var: str
    status: CheckedStatus
    reason: str | None  # why a variable was not testable, such as 'no_data'
    p: float | None
    q: float | None


class NearbyArea(ContractModel):
    lat_i: int
    lon_i: int
    lat: float
    lon: float
    distance_km: float
    sign: Sign
    is_opposite: bool  # the trend sign is opposite to the focus
    mechanism: LocalizedText | None  # registry mechanism, when a row names the variable
    grid_window: CanonicalWindow


class ScanResult(ContractModel):
    spec: CanonicalSpec
    hits: Annotated[list[ScanHit], Field(max_length=MAX_SCAN_HITS)]
    checked: list[ScanChecked]
    nearby: Annotated[list[NearbyArea], Field(max_length=MAX_NEARBY_AREAS)]
    nearby_note: NearbyNote | None  # why the nearby list is empty


class GridCell(ContractModel):
    lat_i: int
    lon_i: int
    p: float | None
    rate_per_decade: float | None
    sign: Sign | None
    is_significant: bool
    metric_used: MetricUsed | None


class TrendGrid(ContractModel):
    """One file per dataset version, variable and canonical metric. The browser
    has no route to it at P0."""

    ds: str
    eng: str
    var: str
    metric: SpecMetric
    window: CanonicalWindow
    cells: list[GridCell]
