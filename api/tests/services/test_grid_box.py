"""One grid-box rule for the scan and warm, safe across the 180 meridian (FR-19)."""

import numpy as np
import pytest

from boramae.batch.warm import FAILED_EXIT_CODE, run_warm
from boramae.contracts.results_scan import ScanResult
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.services.nearby import focus_center, is_in_grid_box
from boramae.services.scan import get_scan
from boramae.spec.cells import cells_in_circle
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService
from tests.fakes import POWER_GRID, DictStore, FakeReader

MERIDIAN_LON = 180.0
# (lat, lon, radius_km) of real areas whose cells do not cross the 180 meridian.
OFF_MERIDIAN_AREAS = {
    "seoul-25-km-one-cell": (37.5665, 126.978, 25),
    "seoul-150-km": (37.5665, 126.978, 150),
    "jeju-100-km": (33.4996, 126.5312, 100),
    "phoenix-25-km": (33.4484, -112.074, 25),
    "london-150-km-across-0": (51.5074, -0.1278, 150),
    "west-of-180-60-km": (35.0, 179.3, 60),
}
# One cell just east of the 180 meridian, first in cell order, and five just west of
# it. The plain mean of their longitudes, 119.6 E, lies in the grid box.
ACROSS_MERIDIAN = [(248, 1)] + [(lat_i, 575) for lat_i in range(248, 253)]
SEOUL = Circle(lat=37.5665, lon=126.978, radius_km=25)
# Four cells west of the 180 meridian and one on it. The plain mean of their
# longitudes, 107.4 E, lies in the grid box.
ACROSS_MERIDIAN_CIRCLE = Circle(lat=35.0, lon=179.4, radius_km=70)
SCAN_SPEC = RequestSpec(
    v=1,
    kind="scan",
    var="PRECTOTCORR",
    metric=SpecMetric(id="rx1day"),
    area=SEOUL,
    window=RequestWindow(start=1981, end="latest"),
)


def plain_mean(cells):
    """The plain mean of the cell centers: the center of every stored scan."""
    indexes = np.array(cells, dtype=float).reshape(-1, 2)
    lats = POWER_GRID.lat0 + POWER_GRID.dlat * indexes[:, 0]
    lons = POWER_GRID.lon0 + POWER_GRID.dlon * indexes[:, 1]
    return float(lats.mean()), float(lons.mean())


@pytest.mark.parametrize(
    "area", list(OFF_MERIDIAN_AREAS.values()), ids=list(OFF_MERIDIAN_AREAS)
)
def test_should_keep_the_plain_mean_bit_for_bit_off_the_180_meridian(area):
    cells = cells_in_circle(POWER_GRID, *area)[0]
    assert focus_center(cells, POWER_GRID) == plain_mean(cells)


def test_should_find_the_plain_mean_of_the_cells_across_the_meridian_in_the_box():
    assert is_in_grid_box(*plain_mean(ACROSS_MERIDIAN))


def test_should_place_the_center_across_the_meridian_within_one_cell_of_it():
    _, lon = focus_center(ACROSS_MERIDIAN, POWER_GRID)
    assert MERIDIAN_LON - abs(lon) <= POWER_GRID.dlon


def test_should_place_the_center_across_the_meridian_outside_the_box():
    assert not is_in_grid_box(*focus_center(ACROSS_MERIDIAN, POWER_GRID))


def test_should_wrap_the_center_across_the_meridian_into_minus_180_to_180():
    _, lon = focus_center(ACROSS_MERIDIAN, POWER_GRID)
    assert -MERIDIAN_LON <= lon < MERIDIAN_LON


# With no grid file stored, warm waits for the grid exactly when the scan finds the
# center in the box: the scan then notes no_grid, not outside_grid.
@pytest.mark.parametrize(
    "area", [SEOUL, ACROSS_MERIDIAN_CIRCLE], ids=["seoul", "across-180"]
)
def test_warm_should_wait_for_the_grid_only_when_the_scan_center_is_in_the_box(
    area, sample_catalog
):
    spec = SCAN_SPEC.model_copy(update={"area": area})
    results = ResultService(DictStore(), WorkerPool(4, 1.0))
    exit_code = run_warm(
        [spec],
        {"scan": get_scan},
        reader=FakeReader(),
        results=results,
        catalog=sample_catalog,
    )
    body = get_scan(spec, reader=FakeReader(), results=results, catalog=sample_catalog)
    is_in_box = ScanResult.model_validate_json(body[0]).nearby_note != "outside_grid"
    assert (exit_code == FAILED_EXIT_CODE) == is_in_box
