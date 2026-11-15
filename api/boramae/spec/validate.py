"""Validation of a request spec against the catalog file (DES-006, TR-F-004).

An invalid spec raises a ProblemError with HTTP 400, so no analysis starts. The
cells come from the grid definition of the catalog. Nothing here reads POWER data.
"""

from dataclasses import dataclass
from http import HTTPStatus
from itertools import product

from boramae.constants import RADIUS_MAX_KM, RADIUS_MIN_KM
from boramae.contracts.results_catalog import Catalog, CatalogMetric, CatalogVariable
from boramae.contracts.spec import (
    Bbox,
    Circle,
    RequestSpec,
    RequestWindow,
    decode_request_spec,
)
from boramae.engine.types import GridDef
from boramae.errors import ProblemError
from boramae.ports import Freq
from boramae.spec.cells import Cell, cell_cap, cells_in_bbox, cells_in_circle

# ponytail: the contract names only area_too_large. Every other invalid spec gets
# this one code, and the detail says which rule failed.
INVALID_SPEC = "invalid_spec"
BAD_REQUEST = HTTPStatus.BAD_REQUEST.value
AREA_TOO_LARGE = "area_too_large"
YEAR_DIGITS = 4
# ponytail: the monthly T2M_MAX and T2M_MIN hold the month's hottest and coldest
# hour (cell_methods 'time: max' and 'time: min'; at Seoul [255, 491] and Phoenix
# [247, 109] the monthly value equals the daily extreme in all 12 months of 2020,
# checked 2026-11-15). Their means read the daily store, so a mean is one of daily
# highs or lows (TODOS.md wave 3 decisions, open decision 9). Add a pair here when
# another monthly value is not a monthly mean.
DAILY_MEAN_PAIRS = frozenset(
    product(("T2M_MAX", "T2M_MIN"), ("annual_mean", "seasonal_mean"))
)


@dataclass(frozen=True)
class ValidatedRequest:
    """A request spec that passed every check, with what the checks resolved."""

    spec: RequestSpec
    variable: CatalogVariable
    metric: CatalogMetric
    cells: tuple[Cell, ...]  # sorted
    # The flag depends on the request and not on the cells, so no spec holds it.
    used_containing_cell: bool


def decode_s(s: str) -> RequestSpec:
    """The request spec of the query parameter s, or an HTTP 400 problem."""
    try:
        return decode_request_spec(s)
    except ValueError as error:
        raise _invalid("s is not a base64url request spec") from error


def validate_request(spec: RequestSpec, catalog: Catalog) -> ValidatedRequest:
    """Check a request spec and derive its cells, or raise an HTTP 400 problem."""
    variable = next((item for item in catalog.variables if item.id == spec.var), None)
    if variable is None:
        raise _invalid("the variable ID is not in the catalog")
    metric = next((item for item in catalog.metrics if item.id == spec.metric.id), None)
    if metric is None:
        raise _invalid("the metric ID is not in the catalog")
    _check_metric(spec, variable, metric)
    freq = source_freq(variable, metric)
    pinned_month = getattr(catalog.datasets, freq).last_valid_month
    _check_window(spec.window, variable.record_start, pinned_month)
    cells, used_containing_cell = _derive_cells(spec.area, catalog.grid)
    return ValidatedRequest(spec, variable, metric, tuple(cells), used_containing_cell)


def source_freq(variable: CatalogVariable, metric: CatalogMetric) -> Freq:
    """The store that a metric on a variable reads. Every store or ds choice for a
    spec goes through here, never through metric.source_freq alone."""
    if (variable.id, metric.id) in DAILY_MEAN_PAIRS:
        return "daily"
    return metric.source_freq


def _check_metric(
    spec: RequestSpec, variable: CatalogVariable, metric: CatalogMetric
) -> None:
    # ponytail: no document names the answer for a metric with no reducer yet. It
    # is an invalid spec, because the engine cannot run it.
    if not metric.is_available:
        raise _invalid("the metric is not available in this version")
    if source_freq(variable, metric) not in variable.stores:
        raise _invalid("the store of the metric does not hold the variable")
    # ponytail: the catalog has no "needs a threshold" mark. A default comparison
    # marks a threshold metric; add a field to the catalog metric if one must not.
    has_threshold = spec.metric.threshold or metric.defaults.threshold
    if metric.defaults.op and not has_threshold:
        raise _invalid("the metric needs a threshold")


# ponytail: "outside the data coverage" (TR-F-004) is read strictly: a window that
# is partly outside is invalid too, because the slider cannot send one.
def _check_window(window: RequestWindow, record_start: str, pinned_month: str) -> None:
    first_year = int(record_start[:YEAR_DIGITS])
    last_year = int(pinned_month[:YEAR_DIGITS])
    end_year = last_year if window.end == "latest" else window.end
    if window.start > end_year:
        raise _invalid("the window ends before it starts")
    if window.start < first_year or end_year > last_year:
        raise _invalid(f"the window is outside {first_year} to {last_year}")


def _derive_cells(area: Circle | Bbox, grid: GridDef) -> tuple[list[Cell], bool]:
    if isinstance(area, Circle):
        # The radius limit is the cell cap of a circle: no circle holds more cells
        # than the largest circle on its own center.
        if not RADIUS_MIN_KM <= area.radius_km <= RADIUS_MAX_KM:
            raise _invalid(f"radius_km is outside {RADIUS_MIN_KM} to {RADIUS_MAX_KM}")
        return cells_in_circle(grid, area.lat, area.lon, area.radius_km)
    if area.south > area.north:
        raise _invalid("the bbox has its south above its north")
    cells, used_containing_cell = cells_in_bbox(
        grid, area.west, area.south, area.east, area.north
    )
    # ponytail: a map view takes the cap at the latitude of its center.
    cap = cell_cap(grid, (area.south + area.north) / 2)
    if len(cells) > cap:
        raise ProblemError(
            BAD_REQUEST,
            AREA_TOO_LARGE,
            f"the area holds {len(cells)} cells and the cap is {cap}",
        )
    return cells, used_containing_cell


def _invalid(detail: str) -> ProblemError:
    return ProblemError(BAD_REQUEST, INVALID_SPEC, detail)
