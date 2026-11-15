"""Live grid test: one block of the monthly store, straight from POWER.

Run with -m live -s. The block (15 x 15 cells near 23 N, 102 E) lies in one monthly
T2M chunk, away from the pinned-month probe chunk, so the run fetches one chunk. The
store is a tmp folder that holds the sample catalog, which has the POWER grid, so no
grid file reaches api/.data. Three cells are checked against the trend of a one-cell
area (TDD.md:644), which the reader serves from its chunk cache.
"""

import time
from pathlib import Path

import pytest

from boramae import deps
from boramae.batch.grid import main
from boramae.config import load_settings
from boramae.constants import RADIUS_MIN_KM
from boramae.contracts.results_scan import GridCell, TrendGrid
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.power.reader import PowerReader
from boramae.services.catalog import CATALOG_PATH, load_catalog
from boramae.services.trend import compute_trend
from boramae.spec.canonical import canonicalize
from boramae.spec.validate import validate_request
from boramae.store.local import LocalStore

pytestmark = pytest.mark.live

SAMPLE_CATALOG = Path(__file__).parents[1] / "fixtures" / "catalog.sample.json"

BLOCK = (225, 240, 450, 465)
BLOCK_CELL_COUNT = 225
SPOT_CELLS = [(225, 450), (232, 457), (239, 464)]
VAR = "T2M"
METRIC = "annual_mean"
FIRST_YEAR = 1981


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    reader = PowerReader(load_settings())
    store = LocalStore(tmp_path_factory.mktemp("grid-live"))
    store.put(CATALOG_PATH, SAMPLE_CATALOG.read_bytes())
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(deps, "get_reader", lambda: reader)
        patch.setattr(deps, "get_store", lambda: store)
        started = time.perf_counter()
        exit_code = main(["--var", VAR, "--metric", METRIC], box=BLOCK)
    print(f"\ngrid live: one monthly block in {time.perf_counter() - started:.1f} s")
    (grid_file,) = (store.root / "grid").rglob("*.json")
    grid = TrendGrid.model_validate_json(grid_file.read_bytes())
    return exit_code, grid, reader, load_catalog(store)


def _one_cell_trend(catalog, reader, cell):
    grid = catalog.grid
    spec = RequestSpec(
        v=1,
        kind="trend",
        var=VAR,
        metric=SpecMetric(id=METRIC),
        area=Circle(
            lat=grid.lat0 + grid.dlat * cell[0],
            lon=grid.lon0 + grid.dlon * cell[1],
            radius_km=RADIUS_MIN_KM,
        ),
        window=RequestWindow(start=FIRST_YEAR, end="latest"),
    )
    canonical = canonicalize(validate_request(spec, catalog), catalog)
    return compute_trend(canonical, catalog, reader)


def _cell(grid: TrendGrid, cell: tuple[int, int]) -> GridCell:
    return next(item for item in grid.cells if (item.lat_i, item.lon_i) == cell)


def test_live_grid_run_exits_with_code_0(run):
    assert run[0] == 0


def test_live_grid_holds_every_cell_of_the_block(run):
    assert len(run[1].cells) == BLOCK_CELL_COUNT


@pytest.mark.parametrize("cell", SPOT_CELLS)
def test_live_grid_cell_equals_the_live_trend_of_that_cell(run, cell):
    _, grid, reader, catalog = run
    stored = _cell(grid, cell)
    trend = _one_cell_trend(catalog, reader, cell)
    assert (stored.p, stored.rate_per_decade) == (
        trend.stats.mk.p,
        trend.stats.rates.sen,
    )
