"""warm: compute and store the results of the demo cases and of a manifest (Flow F).

Run: python -m boramae.batch warm [--manifest FILE]. The entries are the request specs
of content/demo/cases.json, then those of FILE, a JSON array of request specs. Each
entry runs through the service of its kind as a request does, so a stored key answers
from the store and a second run is safe (TDD.md Flow F, step 2). A scan in the grid
box waits for its grid file: a scan stored before its grid would keep an empty nearby
list for good. A failing entry fails the run after the other entries ran.
"""

import argparse
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from statistics import fmean

from pydantic import TypeAdapter

from boramae import deps
from boramae.constants import (
    GRID_BOX_LAT_MAX,
    GRID_BOX_LAT_MIN,
    GRID_BOX_LON_MAX,
    GRID_BOX_LON_MIN,
    RESULT_KINDS,
)
from boramae.contracts.content import DemoCase
from boramae.contracts.http import CacheStatus
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import CanonicalSpec, RequestSpec
from boramae.engine.types import GridDef
from boramae.errors import ProblemError
from boramae.ports import SeriesReader
from boramae.services.catalog import load_catalog
from boramae.services.content import load_content
from boramae.services.trend import TrendFacts
from boramae.spec.canonical import canonicalize, grid_path
from boramae.spec.validate import validate_request
from boramae.store.results import ResultService

TREND_KIND, CASEBOARD_KIND, SCAN_KIND = RESULT_KINDS
FAILED_EXIT_CODE = 1
GRID_COMMAND = "python -m boramae.batch grid"
COMPUTED = "computed"
STORED = "already stored"
FAILED = "failed"
OUTCOMES: dict[CacheStatus, str] = {"hit": STORED, "miss": COMPUTED}

# A service of the dispatch table: (spec, *, reader, results, catalog) to the stored
# body, the key, the cache status and the request facts.
Service = Callable[..., tuple[bytes, str, CacheStatus, TrendFacts]]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    specs = load_entries(load_content("demo_cases"), args.manifest)
    store = deps.get_store()
    try:
        catalog = load_catalog(store)
    except ProblemError as exc:
        print(f"warm: {exc.detail}", file=sys.stderr)
        return FAILED_EXIT_CODE
    # ponytail: the leaves of a board or scan share the request timeout of the
    # settings (60 s); set BORAMAE_REQUEST_TIMEOUT_S for a long run on live POWER.
    results = ResultService(store, deps.get_pool())
    return run_warm(
        specs,
        service_table(),
        reader=deps.get_reader(),
        results=results,
        catalog=catalog,
    )


def service_table() -> dict[str, Service]:
    """The service of each result kind. The imports wait for the call, so loading
    this module loads no builder; a test passes its own table instead."""
    from boramae.services.caseboard import get_caseboard
    from boramae.services.scan import get_scan
    from boramae.services.trend import get_trend

    return {TREND_KIND: get_trend, CASEBOARD_KIND: get_caseboard, SCAN_KIND: get_scan}


def load_entries(cases: Sequence[DemoCase], manifest: Path | None) -> list[RequestSpec]:
    """The specs of each demo case, its trend first, then the specs of the manifest."""
    specs = [
        spec
        for case in cases
        for spec in (case.specs.trend, case.specs.caseboard, case.specs.scan)
        if spec is not None
    ]
    if manifest is not None:
        specs += TypeAdapter(list[RequestSpec]).validate_json(manifest.read_bytes())
    return specs


def run_warm(
    specs: Sequence[RequestSpec],
    services: Mapping[str, Service],
    *,
    reader: SeriesReader,
    results: ResultService,
    catalog: Catalog,
) -> int:
    """Run each spec through the service of its kind and return the exit code."""
    outcomes = Counter(
        _warm_one(spec, services, reader=reader, results=results, catalog=catalog)
        for spec in specs
    )
    print(
        f"warm: {len(specs)} entries, {outcomes[COMPUTED]} {COMPUTED},"
        f" {outcomes[STORED]} {STORED}, {outcomes[FAILED]} {FAILED}",
        file=sys.stderr,
    )
    return FAILED_EXIT_CODE if outcomes[FAILED] else 0


def grid_argv(spec: RequestSpec) -> list[str]:
    """The arguments of the grid command that builds the grid file of a scan."""
    metric = spec.metric
    argv = ["--var", spec.var, "--metric", metric.id]
    if metric.months:
        argv += ["--months", ",".join(str(month) for month in metric.months)]
    if metric.threshold:
        argv += ["--threshold", metric.threshold]
    return argv + ["--window", str(spec.window.start), str(spec.window.end)]


def _warm_one(
    spec: RequestSpec,
    services: Mapping[str, Service],
    *,
    reader: SeriesReader,
    results: ResultService,
    catalog: Catalog,
) -> str:
    """The outcome of one entry, printed with the entry."""
    try:
        missing = _missing_grid(spec, results, catalog)
        if missing is not None:
            command = " ".join([GRID_COMMAND, *grid_argv(spec)])
            print(
                f"warm: scan {spec.var} refused: {missing} is not stored;"
                f" run first: {command}",
                file=sys.stderr,
            )
            return FAILED
        _, key, cache, facts = services[spec.kind](
            spec, reader=reader, results=results, catalog=catalog
        )
    except ProblemError as exc:
        print(
            f"warm: {spec.kind} {spec.var} failed: {exc.code} {exc.detail or ''}",
            file=sys.stderr,
        )
        return FAILED
    print(
        f"warm: {spec.kind} {key} {OUTCOMES[cache]},"
        f" {facts.bytes_fetched} bytes fetched",
        file=sys.stderr,
    )
    return OUTCOMES[cache]


# ponytail: the grid command takes no op and no season start, so a scan with another
# op or season than the catalog default names a grid that never matches; add the two
# options to grid when a warmed scan needs them.
def _missing_grid(
    spec: RequestSpec, results: ResultService, catalog: Catalog
) -> str | None:
    """The path of the grid file that a scan in the grid box waits for, or None."""
    if spec.kind != SCAN_KIND:
        return None
    focus = canonicalize(validate_request(spec, catalog), catalog)
    if not _is_in_grid_box(focus, catalog.grid):
        return None
    path = grid_path(focus.ds, focus.var, focus.metric)
    return None if results.store.get(path) is not None else path


# NOTE: the box rule of select_nearby in services/nearby.py, which keeps it private:
# the mean of the cell centers of the area lies in the grid box.
def _is_in_grid_box(focus: CanonicalSpec, grid: GridDef) -> bool:
    lat = grid.lat0 + grid.dlat * fmean(lat_i for lat_i, _ in focus.cells)
    lon = grid.lon0 + grid.dlon * fmean(lon_i for _, lon_i in focus.cells)
    return (
        GRID_BOX_LAT_MIN <= lat <= GRID_BOX_LAT_MAX
        and GRID_BOX_LON_MIN <= lon <= GRID_BOX_LON_MAX
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="warm", description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, help="JSON array of extra request specs to warm"
    )
    return parser
