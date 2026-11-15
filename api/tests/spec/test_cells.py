"""Cell derivation: the cell-center rule, the containing cell and the cell cap."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from boramae.constants import EARTH_RADIUS_KM, RADIUS_MAX_KM
from boramae.engine.types import GridDef
from boramae.spec.cells import cell_cap, cells_in_bbox, cells_in_circle, haversine_km

REPO = Path(__file__).resolve().parents[3]
GOLDEN = json.loads((REPO / "content/golden/cells.json").read_text(encoding="utf-8"))
GOLDEN_GRID = GridDef(**GOLDEN["grid"])
GOLDEN_CASES = GOLDEN["cases"]
ONE_DEGREE_KM = EARTH_RADIUS_KM * math.pi / 180
SEOUL = (37.5665, 126.978)


def case_id(case):
    return f"{case['lat']},{case['lon']},{case['radius_km']}km"


def expected_of(case):
    return [tuple(cell) for cell in case["cells"]], case["used_containing_cell"]


def oracle_cells(grid, lat, lon, radius_km):
    """Every cell of the grid, tested with the spherical law of cosines.

    A second formula over the whole grid, so it shares no step with cells.py.
    """
    lats = np.deg2rad(grid.lat0 + grid.dlat * np.arange(grid.n_lat))[:, None]
    lons = np.deg2rad(grid.lon0 + grid.dlon * np.arange(grid.n_lon))
    lat_rad, lon_rad = math.radians(lat), math.radians(lon)
    cosine = math.sin(lat_rad) * np.sin(lats) + math.cos(lat_rad) * np.cos(
        lats
    ) * np.cos(lons - lon_rad)
    distance = EARTH_RADIUS_KM * np.arccos(np.clip(cosine, -1.0, 1.0))
    return np.argwhere(distance <= radius_km).tolist()


def test_haversine_gives_one_degree_on_the_equator():
    assert haversine_km(0.0, 10.0, 0.0, 11.0) == pytest.approx(ONE_DEGREE_KM)


def test_haversine_gives_half_the_circumference_between_the_poles():
    assert haversine_km(-90.0, 0.0, 90.0, 0.0) == pytest.approx(
        math.pi * EARTH_RADIUS_KM
    )


def test_haversine_takes_the_short_way_across_the_180_meridian():
    assert haversine_km(0.0, 179.5, 0.0, -179.5) == pytest.approx(ONE_DEGREE_KM)


def test_seoul_at_25_km_is_the_one_cell_of_the_contract(sample_catalog):
    assert cells_in_circle(sample_catalog.grid, *SEOUL, 25) == ([(255, 491)], False)


def test_circle_with_no_cell_center_gives_the_containing_cell_and_the_flag(
    sample_catalog,
):
    assert cells_in_circle(sample_catalog.grid, 37.7, 127.2, 10) == ([(255, 492)], True)


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (37.75, 126.875, (256, 491)),  # on a latitude edge: the upper cell
        (37.5, 127.1875, (255, 492)),  # on a longitude edge: the eastern cell
        (0.2, 180.0, (180, 0)),  # longitude 180 is the cell centered at -180
    ],
)
def test_containing_cell_rounds_half_up_and_wraps_the_longitude(
    sample_catalog, lat, lon, expected
):
    assert cells_in_circle(sample_catalog.grid, lat, lon, 10) == ([expected], True)


def test_golden_grid_is_the_grid_of_the_sample_catalog(sample_catalog):
    assert GOLDEN_GRID == sample_catalog.grid


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=case_id)
def test_cells_in_circle_reproduces_the_golden_case(case):
    assert cells_in_circle(
        GOLDEN_GRID, case["lat"], case["lon"], case["radius_km"]
    ) == expected_of(case)


@pytest.mark.parametrize(
    "case",
    [case for case in GOLDEN_CASES if not case["used_containing_cell"]],
    ids=case_id,
)
def test_golden_case_equals_a_whole_grid_check_with_a_second_formula(case):
    assert (
        oracle_cells(GOLDEN_GRID, case["lat"], case["lon"], case["radius_km"])
        == case["cells"]
    )


@pytest.mark.parametrize(
    "case",
    [case for case in GOLDEN_CASES if case["used_containing_cell"]],
    ids=case_id,
)
def test_golden_case_with_the_flag_holds_no_cell_center(case):
    assert oracle_cells(GOLDEN_GRID, case["lat"], case["lon"], case["radius_km"]) == []


def test_bbox_gives_the_cells_whose_centers_lie_inside(sample_catalog):
    assert cells_in_bbox(sample_catalog.grid, 126.5, 37.2, 127.6, 38.1) == (
        [(255, 491), (255, 492), (256, 491), (256, 492)],
        False,
    )


def test_bbox_counts_a_center_on_its_edge(sample_catalog):
    assert cells_in_bbox(sample_catalog.grid, 126.875, 37.5, 127.0, 37.6) == (
        [(255, 491)],
        False,
    )


def test_bbox_with_no_cell_center_gives_the_containing_cell_of_its_center(
    sample_catalog,
):
    assert cells_in_bbox(sample_catalog.grid, 127.0, 37.6, 127.1, 37.7) == (
        [(255, 491)],
        True,
    )


def test_bbox_with_west_above_east_crosses_the_180_meridian(sample_catalog):
    assert cells_in_bbox(sample_catalog.grid, 179.0, -0.2, -179.0, 0.2) == (
        [(180, 0), (180, 1), (180, 575)],
        False,
    )


def test_bbox_across_the_180_meridian_takes_the_containing_cell_of_its_center(
    sample_catalog,
):
    assert cells_in_bbox(sample_catalog.grid, 179.9, 0.1, -179.9, 0.2) == (
        [(180, 0)],
        True,
    )


def test_cell_cap_is_the_cell_count_of_the_largest_circle_at_the_latitude(
    sample_catalog,
):
    grid = sample_catalog.grid
    assert cell_cap(grid, 37.5) == len(
        oracle_cells(grid, 37.5, grid.lon0, RADIUS_MAX_KM)
    )


def test_cell_cap_grows_toward_the_pole(sample_catalog):
    assert cell_cap(sample_catalog.grid, 60.0) > cell_cap(sample_catalog.grid, 0.0)
