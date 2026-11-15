"""The canonical spec, the result key and the grid path (DES-006, DEC-003).

Only this module computes a result key or names a grid file. The canonical JSON
holds integers and strings only, so no float format can change a key.
"""

import hashlib
from decimal import Decimal
from typing import Literal

from boramae.constants import KEY_HEX_LEN
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import (
    CanonicalSpec,
    ContractModel,
    MetricSettings,
    SpecMetric,
    canonical_json,
)
from boramae.engine.definitions import ENGINE_VERSION
from boramae.spec.validate import ValidatedRequest

GRID_METRIC_KEY_HEX_LEN = 16


def canonicalize(
    validated: ValidatedRequest, catalog: Catalog, content_mark: str | None = None
) -> CanonicalSpec:
    """The spec behind a result key.

    `content_mark` is the mark of the board or scan content. A trend passes none.
    """
    spec = validated.spec
    dataset = getattr(catalog.datasets, validated.metric.source_freq)
    return CanonicalSpec(
        v=spec.v,
        kind=spec.kind,
        ds=dataset.ds,
        eng=ENGINE_VERSION,
        var=spec.var,
        metric=canonical_metric(spec.metric, validated.metric.defaults),
        cells=[list(cell) for cell in validated.cells],
        window=(
            spec.window.start,
            _last_month(spec.window.end, dataset.last_valid_month),
        ),
        content=content_mark,
    )


def canonical_metric(metric: SpecMetric, defaults: MetricSettings) -> SpecMetric:
    """The one spelling of a metric: the defaults of the catalog metric filled in,
    the threshold as a normalized decimal string and the months sorted."""
    threshold = metric.threshold or defaults.threshold
    months = metric.months or defaults.months
    return SpecMetric(
        id=metric.id,
        threshold=threshold and _normalize_decimal(threshold),
        op=metric.op or defaults.op,
        months=months and sorted(set(months)),
        season_start=metric.season_start or defaults.season_start,
    )


def result_key(canonical: CanonicalSpec) -> str:
    """The key of the result that a canonical spec names."""
    return _sha256_hex(canonical)[:KEY_HEX_LEN]


def grid_path(ds: str, var: str, metric: SpecMetric) -> str:
    """The store path of a trend grid. `metric` must come from canonical_metric
    or from a canonical spec, or the writer and the reader name different files."""
    return f"grid/{ds}/{var}/{_sha256_hex(metric)[:GRID_METRIC_KEY_HEX_LEN]}.json"


def _last_month(end: int | Literal["latest"], pinned_month: str) -> str:
    if end == "latest":
        return pinned_month
    return min(f"{end:04d}-12", pinned_month)


def _normalize_decimal(text: str) -> str:
    value = Decimal(text)
    # normalize() alone prints 100 as 1E+2 and keeps the sign of -0.
    return format(value.normalize(), "f") if value else "0"


def _sha256_hex(record: ContractModel) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()
