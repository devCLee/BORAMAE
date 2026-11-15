"""Nearby areas of the no-trend fallback, selected on the server (DEC-007, FR-19).

The test family is every grid cell within NEARBY_MAX_KM of the area center, outside
the area, with the metric_used of the focus (TDD.md:551, a Proposed working value).
Benjamini-Hochberg runs across the family, so the browser selects nothing (TR-Q-002).
"""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from boramae.constants import (
    GRID_BOX_LAT_MAX,
    GRID_BOX_LAT_MIN,
    GRID_BOX_LON_MAX,
    GRID_BOX_LON_MIN,
    MAX_NEARBY_AREAS,
    NEARBY_MAX_KM,
)
from boramae.contracts.content import RegistryLink
from boramae.contracts.results import TrendResult
from boramae.contracts.results_scan import GridCell, NearbyArea, NearbyNote, TrendGrid
from boramae.contracts.spec import CanonicalWindow, LocalizedText
from boramae.engine.multitest import bh_select
from boramae.engine.types import GridDef
from boramae.spec.cells import FULL_TURN_DEG, haversine_km

HALF_TURN_DEG = FULL_TURN_DEG / 2


def select_nearby(
    grid: TrendGrid | None,
    focus: TrendResult,
    grid_def: GridDef,
    registry: Sequence[RegistryLink],
) -> tuple[list[NearbyArea], NearbyNote | None]:
    """Up to 3 nearest significant cells of the focus grid, and why the list is empty.

    Distances run from the center of the focus cells. The note is null when the grid
    was searched, also when no cell qualified.
    """
    # ponytail: the area center is the mean of its cell centers, not the pin, so the
    # stored scan holds no request fact: two pins with the same cells share one key.
    lat, lon = focus_center(focus.spec.cells, grid_def)
    if not is_in_grid_box(lat, lon):
        return [], "outside_grid"
    if grid is None:
        return [], "no_grid"
    if grid.window != focus.spec.window:
        return [], "grid_window_differs"
    own_cells = {(lat_i, lon_i) for lat_i, lon_i in focus.spec.cells}
    cells = [
        item
        for item in grid.cells
        if (item.lat_i, item.lon_i) not in own_cells
        and item.metric_used == focus.metric_used
        and item.p is not None
    ]
    lats, lons = _centers(grid_def, [(item.lat_i, item.lon_i) for item in cells])
    distances = haversine_km(lat, lon, lats, lons)
    family = [index for index, km in enumerate(distances) if km <= NEARBY_MAX_KM]
    is_selected = bh_select([cells[index].p for index in family])
    kept = sorted(
        (distances[index], index)
        for index, selected in zip(family, is_selected, strict=True)
        if selected and cells[index].is_significant
    )
    focus_sign = int(np.sign(focus.stats.sen.slope or 0.0))
    mechanism = registry_mechanism(registry, focus.spec.var, focus.spec.metric.id)
    return [
        _nearby_area(
            cells[index],
            lats[index],
            lons[index],
            km,
            focus_sign,
            mechanism,
            grid.window,
        )
        for km, index in kept[:MAX_NEARBY_AREAS]
    ], None


def focus_center(cells: Sequence[Sequence[int]], grid: GridDef) -> tuple[float, float]:
    """The mean of the cell centers of an area, safe across the 180 meridian.

    Each longitude is unwrapped to within 180 degrees of the first cell, and the mean
    is wrapped to [-180, 180). Off the meridian neither step moves a value, so the
    center is the plain mean bit for bit and no stored scan changes.
    """
    lats, lons = _centers(grid, cells)
    lons = lons - FULL_TURN_DEG * np.round((lons - lons[0]) / FULL_TURN_DEG)
    lon = float(lons.mean())
    if lon >= HALF_TURN_DEG:
        lon -= FULL_TURN_DEG
    elif lon < -HALF_TURN_DEG:
        lon += FULL_TURN_DEG
    return float(lats.mean()), lon


def is_in_grid_box(lat: float, lon: float) -> bool:
    """Whether a point lies in the East Asia box of the trend grid, edges included."""
    return (
        GRID_BOX_LAT_MIN <= lat <= GRID_BOX_LAT_MAX
        and GRID_BOX_LON_MIN <= lon <= GRID_BOX_LON_MAX
    )


# ponytail: no document says which row explains "same process, opposite directions".
# Working value: the first registry row whose driver or response is the focus pair.
def registry_mechanism(
    registry: Sequence[RegistryLink], var: str, metric_id: str
) -> LocalizedText | None:
    return next(
        (
            row.mechanism
            for row in registry
            for side in (row.driver, row.response)
            if (side.var, side.metric.id) == (var, metric_id)
        ),
        None,
    )


def _centers(
    grid_def: GridDef, cells: Sequence[Sequence[int]]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    indexes = np.array(cells, dtype=float).reshape(-1, 2)
    return (
        grid_def.lat0 + grid_def.dlat * indexes[:, 0],
        grid_def.lon0 + grid_def.dlon * indexes[:, 1],
    )


def _nearby_area(
    cell: GridCell,
    lat: float,
    lon: float,
    distance_km: float,
    focus_sign: int,
    mechanism: LocalizedText | None,
    window: CanonicalWindow,
) -> NearbyArea:
    is_opposite = (cell.sign or 0) * focus_sign < 0
    return NearbyArea(
        lat_i=cell.lat_i,
        lon_i=cell.lon_i,
        lat=float(lat),
        lon=float(lon),
        distance_km=float(distance_km),
        sign=cell.sign,
        is_opposite=is_opposite,
        mechanism=mechanism if is_opposite else None,
        grid_window=window,
    )
