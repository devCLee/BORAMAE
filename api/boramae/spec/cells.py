"""Grid cells of an area (FR-04, FR-08, TR-F-007).

A cell is (lat_i, lon_i) on the grid of the catalog file, and it is inside an area
when its center is. Nothing here reads POWER data. The browser previews the same
rule, and content/golden/cells.json holds the cases that both sides reproduce.
"""

import math
from itertools import product

import numpy as np
import numpy.typing as npt

from boramae.constants import EARTH_RADIUS_KM, RADIUS_MAX_KM
from boramae.engine.types import GridDef

Cell = tuple[int, int]
FULL_TURN_DEG = 360.0


def haversine_km(
    lat1: npt.ArrayLike, lon1: npt.ArrayLike, lat2: npt.ArrayLike, lon2: npt.ArrayLike
) -> npt.NDArray[np.float64]:
    """Great-circle distance in km between points in degrees. Arrays broadcast."""
    phi1, phi2 = np.deg2rad(lat1), np.deg2rad(lat2)
    half_dphi = (phi2 - phi1) / 2
    half_dlambda = np.deg2rad(np.subtract(lon2, lon1)) / 2
    chord = (
        np.sin(half_dphi) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(half_dlambda) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.minimum(chord, 1.0)))


def cells_in_circle(
    grid: GridDef, lat: float, lon: float, radius_km: float
) -> tuple[list[Cell], bool]:
    """The sorted cells whose centers lie in the circle, and the containing-cell flag.

    A center at exactly radius_km is inside. If the circle holds no center, the
    cell that contains the point takes their place and the flag is true.
    """
    reach_deg = math.degrees(radius_km / EARTH_RADIUS_KM)
    first_row = max(math.floor((lat - reach_deg - grid.lat0) / grid.dlat), 0)
    last_row = min(math.ceil((lat + reach_deg - grid.lat0) / grid.dlat), grid.n_lat - 1)
    row_lats = grid.lat0 + grid.dlat * np.arange(first_row, last_row + 1)
    col_lons = grid.lon0 + grid.dlon * np.arange(grid.n_lon)
    # Every column of a row is tested, so a circle across the 180 meridian or over
    # a pole needs no special case.
    is_inside = haversine_km(lat, lon, row_lats[:, None], col_lons) <= radius_km
    rows, cols = np.nonzero(is_inside)
    cells = list(zip((rows + first_row).tolist(), cols.tolist()))
    return _or_containing_cell(grid, cells, lat, lon)


def cells_in_bbox(
    grid: GridDef, west: float, south: float, east: float, north: float
) -> tuple[list[Cell], bool]:
    """The sorted cells whose centers lie in the box, edges included, and the flag.

    If the box holds no center, the cell that contains its center takes their place
    and the flag is true (the FR-08 cell rule, TR-F-016).
    """
    lats = grid.lat0 + grid.dlat * np.arange(grid.n_lat)
    lons = grid.lon0 + grid.dlon * np.arange(grid.n_lon)
    # ponytail: no document says what west above east means. It reads as a box
    # across the 180 meridian, which is what a wrapped map view sends.
    if west <= east:
        is_lon_inside = (lons >= west) & (lons <= east)
    else:
        is_lon_inside = (lons >= west) | (lons <= east)
    rows = np.nonzero((lats >= south) & (lats <= north))[0]
    cols = np.nonzero(is_lon_inside)[0]
    cells = list(product(rows.tolist(), cols.tolist()))
    center_lon = west + ((east - west) % FULL_TURN_DEG) / 2
    return _or_containing_cell(grid, cells, (south + north) / 2, center_lon)


# ponytail: the cap value is open (TRD Q-04). Interim rule of TDD.md:169: the cell
# count of the largest circle, taken at a cell-center longitude of the latitude.
def cell_cap(grid: GridDef, lat: float) -> int:
    """The largest cell count of an area at a latitude."""
    return len(cells_in_circle(grid, lat, grid.lon0, RADIUS_MAX_KM)[0])


def _or_containing_cell(
    grid: GridDef, cells: list[Cell], lat: float, lon: float
) -> tuple[list[Cell], bool]:
    if cells:
        return cells, False
    # ponytail: no document names the cell of a point on a cell edge. floor(x + 0.5)
    # takes the upper or eastern cell, as Math.round does in the browser preview.
    lat_i = math.floor((lat - grid.lat0) / grid.dlat + 0.5)
    lon_i = math.floor((lon - grid.lon0) / grid.dlon + 0.5)
    return [(min(max(lat_i, 0), grid.n_lat - 1), lon_i % grid.n_lon)], True
