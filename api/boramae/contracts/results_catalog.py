"""Catalog record of the API contract: the file meta/catalog.json.

Frozen from wave 2: report a needed change. It is the only stored file that
changes in place (TDD.md:282).
"""

from typing import Literal

from boramae.contracts.spec import (
    ContractModel,
    LocalizedText,
    MetricSettings,
    YearMonth,
)
from boramae.engine.types import GridDef
from boramae.ports import Freq

# How the store holds a share: 0 to 1, or 0 to 100. Null for every other variable.
ShareScale = Literal["fraction", "percent"]
ValueKind = Literal["mean", "total", "count", "date", "max", "length", "index"]


class DatasetVersion(ContractModel):
    ds: str  # part of every canonical spec, such as 'power-merra2-daily@2026-09'
    dataset_id: str
    dataset_version: str
    last_valid_month: YearMonth  # the pinned month; no read returns a later step


class Datasets(ContractModel):
    daily: DatasetVersion
    monthly: DatasetVersion


class CatalogVariable(ContractModel):
    id: str  # the POWER variable name
    name: LocalizedText
    definition: LocalizedText
    unit: str
    dataset: str
    resolution: str
    stores: list[Freq]
    record_start: YearMonth
    record_end: YearMonth
    min_record_years: int
    is_trend_ready: bool
    default_metric: str
    scan_set: bool
    share_scale: ShareScale | None
    kind: Literal["model"]


class CatalogMetric(ContractModel):
    id: str
    name: LocalizedText
    definition: LocalizedText
    source_freq: Freq
    value_kind: ValueKind
    defaults: MetricSettings
    is_available: bool  # false until the engine holds a reducer for the metric


class CatalogTerms(ContractModel):
    en: list[str]
    ko: list[str]


class CatalogUnavailable(ContractModel):
    """A variable that this version does not load, with the nearest one it has."""

    id: str
    names: CatalogTerms
    nearest_var: str | None


class Catalog(ContractModel):
    version: str
    datasets: Datasets
    eng: str
    grid: GridDef  # lat0 and lon0 are the center of cell [0, 0]
    variables: list[CatalogVariable]
    metrics: list[CatalogMetric]
    unavailable: list[CatalogUnavailable]
