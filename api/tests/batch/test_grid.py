from itertools import product

import numpy as np
import pytest

from boramae import deps
from boramae.batch.grid import east_asia_box, main
from boramae.constants import RADIUS_MIN_KM
from boramae.contracts.results import TrendResult
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.results_scan import GridCell, TrendGrid
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.errors import PowerUnavailable
from boramae.services.catalog import CATALOG_PATH, find_metric, find_variable
from boramae.services.trend import compute_trend
from boramae.spec.canonical import (
    canonical_metric,
    canonicalize,
    grid_path,
    metric_defaults,
    source_freq,
)
from boramae.spec.validate import validate_request
from tests.fakes import POWER_GRID, FakeReader

# A 3 x 3 box across two latitude blocks: row 254 and rows 255 to 256.
TEST_BOX = (254, 257, 490, 493)
BOX_CELLS = list(product(range(254, 257), range(490, 493)))
TRENDING = (255, 491)
CONSTANT = (255, 492)
SHORT = (256, 492)  # two complete years, then no data
PARITY_CELLS = [(254, 490), (255, 491), (256, 490)]
T2M_MEAN = ["--var", "T2M", "--metric", "annual_mean"]
EPOCH_YEAR = 1970
TREND_START_YEAR = 1981
SHORT_END_YEAR = 1983
CELL_VALUES = {
    TRENDING: lambda years, noise: 0.1 * (years - TREND_START_YEAR) + 0.1 * noise,
    CONSTANT: lambda years, noise: np.full(years.size, 5.0),
    SHORT: lambda years, noise: np.where(years < SHORT_END_YEAR, noise, np.nan),
}


def _values(var, freq, times, cell):
    years = times.astype("datetime64[Y]").astype(int) + EPOCH_YEAR
    noise = np.random.default_rng(list(cell)).standard_normal(times.size)
    return CELL_VALUES.get(cell, lambda years, noise: noise)(years, noise)


class FlakyReader(FakeReader):
    """Fails the read_box calls whose number, counted from 1, is in fail_calls."""

    def __init__(self, fail_calls: set[int]) -> None:
        super().__init__(values_fn=_values)
        self.fail_calls = fail_calls
        self.box_calls = 0

    def read_box(self, *args):
        self.box_calls += 1
        if self.box_calls in self.fail_calls:
            raise PowerUnavailable("flaky block")
        return super().read_box(*args)


@pytest.fixture
def run_grid(monkeypatch, store, sample_catalog):
    store.put(CATALOG_PATH, sample_catalog.to_json_bytes())
    monkeypatch.setattr(deps, "get_store", lambda: store)

    def run(argv=T2M_MEAN, reader=None) -> int:
        reader = FakeReader(values_fn=_values) if reader is None else reader
        monkeypatch.setattr(deps, "get_reader", lambda: reader)
        return main(argv, box=TEST_BOX)

    return run


def _grid_paths(store) -> list[str]:
    return [path for path in store.files if path.startswith("grid/")]


def _stored_grid(store) -> TrendGrid:
    (path,) = _grid_paths(store)
    return TrendGrid.model_validate_json(store.files[path])


def _cell(grid: TrendGrid, cell: tuple[int, int]) -> GridCell:
    return next(item for item in grid.cells if (item.lat_i, item.lon_i) == cell)


def _expected_path(catalog: Catalog, var: str, spec_metric: SpecMetric) -> str:
    variable = find_variable(catalog, var)
    metric = find_metric(catalog, spec_metric.id)
    ds = getattr(catalog.datasets, source_freq(variable, metric)).ds
    defaults = metric_defaults(variable, metric)
    return grid_path(ds, var, canonical_metric(spec_metric, defaults))


def _one_cell_trend(catalog: Catalog, cell: tuple[int, int]) -> TrendResult:
    grid = catalog.grid
    spec = RequestSpec(
        v=1,
        kind="trend",
        var="T2M",
        metric=SpecMetric(id="annual_mean"),
        area=Circle(
            lat=grid.lat0 + grid.dlat * cell[0],
            lon=grid.lon0 + grid.dlon * cell[1],
            radius_km=RADIUS_MIN_KM,
        ),
        window=RequestWindow(start=TREND_START_YEAR, end="latest"),
    )
    canonical = canonicalize(validate_request(spec, catalog), catalog)
    return compute_trend(canonical, catalog, FakeReader(values_fn=_values))


def test_east_asia_box_holds_the_cell_centers_of_100_to_150_e_and_20_to_50_n():
    assert east_asia_box(POWER_GRID) == (220, 281, 448, 529)


def test_grid_holds_every_cell_of_the_box(run_grid, store):
    run_grid()
    grid = _stored_grid(store)
    assert sorted((item.lat_i, item.lon_i) for item in grid.cells) == BOX_CELLS


@pytest.mark.parametrize(
    ("window_args", "window"),
    [([], (1981, "2026-09")), (["--window", "1990", "2020"], (1990, "2020-12"))],
    ids=["full record", "end year"],
)
def test_grid_file_holds_its_window(run_grid, store, window_args, window):
    run_grid(T2M_MEAN + window_args)
    assert _stored_grid(store).window == window


@pytest.mark.parametrize(
    ("var", "spec_metric", "args"),
    [
        ("T2M", SpecMetric(id="annual_mean"), []),
        ("T2M_MAX", SpecMetric(id="annual_mean"), []),
        ("T2M_MAX", SpecMetric(id="threshold_days", threshold="35.0"), ["35.0"]),
    ],
    ids=["monthly store", "daily mean pair", "threshold"],
)
def test_grid_file_sits_at_the_grid_path_of_the_canonical_metric(
    run_grid, store, sample_catalog, var, spec_metric, args
):
    threshold_args = ["--threshold", *args] if args else []
    run_grid(["--var", var, "--metric", spec_metric.id, *threshold_args])
    assert _expected_path(sample_catalog, var, spec_metric) in store.files


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (
            ["threshold_days", "--threshold", "33"],
            ["threshold_days", "--threshold", "35"],
        ),
        (
            ["seasonal_mean", "--months", "6,7,8"],
            ["seasonal_mean", "--months", "12,1,2"],
        ),
    ],
    ids=["threshold", "months"],
)
def test_two_settings_of_a_metric_store_two_files(run_grid, store, first, second):
    run_grid(["--var", "T2M_MAX", "--metric", *first])
    run_grid(["--var", "T2M_MAX", "--metric", *second])
    assert len(_grid_paths(store)) == 2


@pytest.mark.parametrize("cell", PARITY_CELLS)
def test_cell_statistics_equal_the_trend_of_that_one_cell(
    run_grid, store, sample_catalog, cell
):
    run_grid()
    stored = _cell(_stored_grid(store), cell)
    trend = _one_cell_trend(sample_catalog, cell)
    assert (stored.p, stored.rate_per_decade) == (
        trend.stats.mk.p,
        trend.stats.rates.sen,
    )


def test_trending_cell_is_marked_significant(run_grid, store):
    run_grid()
    assert _cell(_stored_grid(store), TRENDING).is_significant is True


def test_trending_cell_carries_the_sign_of_its_rate(run_grid, store):
    run_grid()
    assert _cell(_stored_grid(store), TRENDING).sign == 1


def test_constant_cell_is_not_marked_significant(run_grid, store):
    run_grid()
    assert _cell(_stored_grid(store), CONSTANT).is_significant is False


def test_cell_with_fewer_than_3_values_is_stored_with_empty_statistics(run_grid, store):
    run_grid()
    assert _cell(_stored_grid(store), SHORT) == GridCell(
        lat_i=SHORT[0],
        lon_i=SHORT[1],
        p=None,
        rate_per_decade=None,
        sign=None,
        is_significant=False,
        metric_used=None,
    )


def test_each_cell_of_a_date_metric_carries_metric_used(run_grid, store):
    run_grid(["--var", "PRECSNO", "--metric", "first_date"], FakeReader())
    assert [item.metric_used for item in _stored_grid(store).cells] == ["date"] * 9


def test_second_run_reads_nothing(run_grid):
    run_grid()
    reader = FakeReader(values_fn=_values)
    run_grid(reader=reader)
    assert reader.read_count == 0


def test_second_run_skips_the_stored_file_with_exit_code_0(run_grid):
    run_grid()
    assert run_grid(reader=FakeReader(fail=True)) == 0


def test_block_that_fails_twice_is_retried_and_the_run_completes(run_grid):
    assert run_grid(reader=FlakyReader({1, 2})) == 0


def test_retried_run_stores_every_cell(run_grid, store):
    run_grid(reader=FlakyReader({1, 2}))
    assert len(_stored_grid(store).cells) == len(BOX_CELLS)


@pytest.mark.parametrize(
    "fail_calls", [{1, 2, 3}, {2, 3, 4}], ids=["first block", "second block"]
)
def test_block_that_fails_three_times_ends_the_run_with_exit_code_1(
    run_grid, fail_calls
):
    assert run_grid(reader=FlakyReader(fail_calls)) == 1


@pytest.mark.parametrize(
    "fail_calls", [{1, 2, 3}, {2, 3, 4}], ids=["first block", "second block"]
)
def test_failed_run_stores_nothing(run_grid, store, fail_calls):
    run_grid(reader=FlakyReader(fail_calls))
    assert _grid_paths(store) == []


def test_window_outside_the_record_exits_with_code_2(run_grid):
    assert run_grid(T2M_MEAN + ["--window", "1975", "latest"]) == 2
