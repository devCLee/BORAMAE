"""grid: the trend grid of one variable and metric over East Asia (TR-D-008).

Run: python -m boramae.batch grid --var T2M --metric annual_mean [--months 6,7,8]
[--threshold 33] [--window 1981 latest]. The command reads the box block by block and
tests every cell as the trend service tests an area of that one cell, so a cell of
the grid equals the trend of a one-cell area. It stores one TrendGrid file at
grid_path. A stored file is complete and immutable, so a second run skips it.
"""

import argparse
import sys
import time
from collections.abc import Iterator, Sequence
from itertools import product

from boramae import deps
from boramae.constants import (
    GRID_BOX_LAT_MAX,
    GRID_BOX_LAT_MIN,
    GRID_BOX_LON_MAX,
    GRID_BOX_LON_MIN,
    RADIUS_MIN_KM,
)
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.results_scan import GridCell, TrendGrid
from boramae.contracts.spec import (
    CanonicalSpec,
    Circle,
    RequestSpec,
    RequestWindow,
    SpecMetric,
)
from boramae.engine.types import CellSeries, GridDef, Verdict
from boramae.errors import PowerUnavailable, ProblemError
from boramae.ports import Freq, SeriesReader
from boramae.services.catalog import load_catalog
from boramae.services.trend import compute_trend, store_freq
from boramae.spec.canonical import canonicalize, grid_path
from boramae.spec.cells import Cell, cells_in_bbox
from boramae.spec.validate import validate_request

# lat_i0, lat_i1, lon_i0, lon_i1: a half-open index box, as SeriesReader.read_box.
Box = tuple[int, int, int, int]

# ponytail: the reader port hides the chunk layout. 15 x 15 cells is the spatial
# chunk of the daily store and divides the 30 x 30 of the monthly one (store
# metadata of 2026-11-15); read the layout from the store if a store changes it.
BLOCK_CELLS = 15
READ_ATTEMPTS = 3  # a failed block is retried twice
FAILED_EXIT_CODE = 1
INVALID_EXIT_CODE = 2
DEFAULT_WINDOW = ("1981", "latest")  # PRD "User flows": the full record from 1981
LATEST = "latest"
SIGNIFICANT_VERDICTS = (Verdict.SignificantRise.value, Verdict.SignificantFall.value)


def main(argv: list[str] | None = None, box: Box | None = None) -> int:
    """box replaces the East Asia box; only a test passes it."""
    args = _parser().parse_args(argv)
    store = deps.get_store()
    try:
        catalog = load_catalog(store)
        canonical = grid_spec(catalog, args.var, _spec_metric(args), _window(args))
    except ProblemError as exc:
        print(f"grid: {exc.detail}", file=sys.stderr)
        return INVALID_EXIT_CODE
    path = grid_path(canonical.ds, canonical.var, canonical.metric)
    if store.get(path) is not None:
        print(f"grid: {path} is stored; nothing to do", file=sys.stderr)
        return 0
    started = time.perf_counter()
    try:
        grid, fetched = build_grid(
            canonical, catalog, deps.get_reader(), box or east_asia_box(catalog.grid)
        )
    except PowerUnavailable as exc:
        print(f"grid: stopped and stored nothing: {exc}", file=sys.stderr)
        return FAILED_EXIT_CODE
    # ponytail: a stopped run starts the pair again; block-level resume is left out,
    # because TDD.md:281 promises a rerun per stored file. Add it if reruns cost.
    store.create_once(path, grid.to_json_bytes())
    significant = sum(cell.is_significant for cell in grid.cells)
    print(
        f"grid: stored {path}: {len(grid.cells)} cells, {significant} significant,"
        f" {fetched} bytes fetched in {time.perf_counter() - started:.1f} s",
        file=sys.stderr,
    )
    return 0


def grid_spec(
    catalog: Catalog, var: str, metric: SpecMetric, window: RequestWindow
) -> CanonicalSpec:
    """The canonical trend spec of the grid, built by the code of the trend service.

    So ds, metric and window equal those of a trend request with the same settings,
    and a bad setting raises the same ProblemError 400. The circle only passes the
    validator; each cell replaces the cells.
    """
    request = RequestSpec(
        v=1,
        kind="trend",
        var=var,
        metric=metric,
        area=Circle(
            lat=(GRID_BOX_LAT_MIN + GRID_BOX_LAT_MAX) / 2,
            lon=(GRID_BOX_LON_MIN + GRID_BOX_LON_MAX) / 2,
            radius_km=RADIUS_MIN_KM,
        ),
        window=window,
    )
    return canonicalize(validate_request(request, catalog), catalog)


def build_grid(
    canonical: CanonicalSpec, catalog: Catalog, reader: SeriesReader, box: Box
) -> tuple[TrendGrid, int]:
    """The grid of every cell in the box and the bytes that its reads fetched.

    One block is in memory at a time. A block that fails READ_ATTEMPTS times raises
    PowerUnavailable.
    """
    freq = store_freq(canonical, catalog)
    start_year, last_month = canonical.window
    blocks = list(_blocks(box))
    cells: list[GridCell] = []
    fetched = 0
    for number, block in enumerate(blocks, start=1):
        read = _read_block(reader, canonical.var, freq, block, start_year, last_month)
        fetched += read.fetched_bytes
        cells += [
            _grid_cell(canonical, catalog, read, column, cell)
            for column, cell in enumerate(_cells(block))
        ]
        print(f"grid: block {number} of {len(blocks)} done", file=sys.stderr)
    grid = TrendGrid(
        ds=canonical.ds,
        eng=canonical.eng,
        var=canonical.var,
        metric=canonical.metric,
        window=canonical.window,
        cells=sorted(cells, key=lambda cell: (cell.lat_i, cell.lon_i)),
    )
    return grid, fetched


def east_asia_box(grid: GridDef) -> Box:
    """The index box of the cells whose centers lie in 100-150E and 20-50N."""
    cells, _ = cells_in_bbox(
        grid, GRID_BOX_LON_MIN, GRID_BOX_LAT_MIN, GRID_BOX_LON_MAX, GRID_BOX_LAT_MAX
    )
    lat_is, lon_is = zip(*cells)
    return min(lat_is), max(lat_is) + 1, min(lon_is), max(lon_is) + 1


class _OneColumn:
    """Serves compute_trend one cell of a block that read_box already read, so a
    cell costs no second read. compute_trend calls read_cells only."""

    def __init__(self, block: CellSeries, column: int) -> None:
        self._block = block
        self._column = column

    def read_cells(
        self, var: str, freq: Freq, cells: Sequence[Cell], start: str, end: str
    ) -> CellSeries:
        block = self._block
        values = block.values[:, [self._column]]
        return CellSeries(block.times, values, block.footprint, 0)


def _grid_cell(
    canonical: CanonicalSpec,
    catalog: Catalog,
    block: CellSeries,
    column: int,
    cell: Cell,
) -> GridCell:
    one_cell = canonical.model_copy(update={"cells": [list(cell)]})
    trend = compute_trend(one_cell, catalog, _OneColumn(block, column))
    rate = trend.stats.rates.sen
    return GridCell(
        lat_i=cell[0],
        lon_i=cell[1],
        p=trend.stats.mk.p,
        rate_per_decade=rate,
        sign=None if rate is None else (rate > 0) - (rate < 0),
        # The verdict rule of decide_verdict, the Sen interval rule of D-03 included.
        is_significant=trend.verdict in SIGNIFICANT_VERDICTS,
        metric_used=trend.metric_used,
    )


def _read_block(
    reader: SeriesReader,
    var: str,
    freq: Freq,
    block: Box,
    start_year: int,
    last_month: str,
) -> CellSeries:
    start = f"{start_year:04d}-01"
    for _ in range(READ_ATTEMPTS - 1):
        try:
            return reader.read_box(var, freq, *block, start, last_month)
        except PowerUnavailable as exc:
            print(f"grid: block {block} failed, retrying: {exc}", file=sys.stderr)
    return reader.read_box(var, freq, *block, start, last_month)


def _blocks(box: Box) -> Iterator[Box]:
    """The box cut along multiples of BLOCK_CELLS, latitude first."""
    lat_i0, lat_i1, lon_i0, lon_i1 = box
    for lat_b, lon_b in product(
        range(lat_i0 - lat_i0 % BLOCK_CELLS, lat_i1, BLOCK_CELLS),
        range(lon_i0 - lon_i0 % BLOCK_CELLS, lon_i1, BLOCK_CELLS),
    ):
        yield (
            max(lat_b, lat_i0),
            min(lat_b + BLOCK_CELLS, lat_i1),
            max(lon_b, lon_i0),
            min(lon_b + BLOCK_CELLS, lon_i1),
        )


def _cells(block: Box) -> Iterator[Cell]:
    """The cells of a block in the column order of read_box."""
    lat_i0, lat_i1, lon_i0, lon_i1 = block
    return product(range(lat_i0, lat_i1), range(lon_i0, lon_i1))


def _spec_metric(args: argparse.Namespace) -> SpecMetric:
    return SpecMetric(id=args.metric, threshold=args.threshold, months=args.months)


def _window(args: argparse.Namespace) -> RequestWindow:
    start, end = args.window
    return RequestWindow(start=int(start), end=end if end == LATEST else int(end))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grid", description=__doc__)
    parser.add_argument("--var", required=True, help="catalog variable ID")
    parser.add_argument("--metric", required=True, help="catalog metric ID")
    parser.add_argument(
        "--months",
        type=lambda text: [int(month) for month in text.split(",")],
        help="months of the season, such as 6,7,8",
    )
    parser.add_argument("--threshold", help="threshold as a decimal, such as 33")
    parser.add_argument(
        "--window",
        nargs=2,
        default=DEFAULT_WINDOW,
        metavar=("START", "END"),
        help="first year and last year or 'latest' (default: 1981 latest)",
    )
    return parser
