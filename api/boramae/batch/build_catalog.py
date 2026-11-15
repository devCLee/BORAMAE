"""build-catalog: the catalog file from the content seed and the POWER stores.

Run: python -m boramae.batch build-catalog [--stdout]. The reader gives the units, the
grid, the record ends and the stores of each variable (TDD.md Flow F, step 1). The
command puts meta/catalog.json, the one stored file that changes in place, so a new
dataset version runs it last. --stdout prints the catalog and stores nothing. Each
thing that the stores lack is one line on stderr.
"""

import argparse
import hashlib
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module

import numpy as np

from boramae import deps
from boramae.constants import METRIC_IDS, VARIABLE_IDS
from boramae.contracts.content import CatalogSeed, SeedMetric, SeedVariable
from boramae.contracts.results_catalog import (
    Catalog,
    CatalogMetric,
    CatalogUnavailable,
    CatalogVariable,
    Datasets,
    DatasetVersion,
)
from boramae.contracts.spec import MetricSettings
from boramae.engine import metrics
from boramae.engine.definitions import ENGINE_VERSION
from boramae.engine.series import MONTHS_IN_YEAR, present_months
from boramae.ports import Freq, SeriesReader
from boramae.power.reader import PROBE_CELL, PROBE_VARIABLE
from boramae.services.catalog import CATALOG_PATH
from boramae.services.content import load_content

FREQS: tuple[Freq, ...] = ("daily", "monthly")
# ponytail: NASA CMR holds no POWER collection (searched 2026-11-15) and the reader
# port gives no store attributes, so the ID is the name in ds and the version is the
# pinned month. Read the store attributes 'id' and 'version' once the port has them.
DATASET_ID = "power-merra2-{freq}"
AXIS_START = "1900-01"  # before the first step of every POWER store
VERSION_HEX_LEN = 12


@dataclass(frozen=True)
class _Stores:
    """What the reader gives about each store."""

    units: Mapping[Freq, Mapping[str, str]]
    record_start: Mapping[Freq, str]
    record_end: Mapping[Freq, str]
    resolution: str


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-catalog", description=__doc__)
    parser.add_argument(
        "--stdout", action="store_true", help="print the catalog and store nothing"
    )
    args = parser.parse_args(argv)
    catalog, report = build_catalog(deps.get_reader(), load_content("catalog_seed"))
    for line in report:
        print(line, file=sys.stderr)
    body = catalog.to_json_bytes()
    if args.stdout:
        sys.stdout.buffer.write(body + b"\n")
    else:
        deps.get_store().put(CATALOG_PATH, body)
        print(
            f"build-catalog: stored {CATALOG_PATH} {catalog.version}", file=sys.stderr
        )
    return 0


def build_catalog(reader: SeriesReader, seed: CatalogSeed) -> tuple[Catalog, list[str]]:
    """The catalog and one report line for each thing that the stores lack.

    Raises ValueError for a seed that does not hold each variable and metric ID once.
    """
    _check_ids("variable", [item.id for item in seed.variables], VARIABLE_IDS)
    _check_ids("metric", [item.id for item in seed.metrics], METRIC_IDS)
    grid = reader.grid()
    stores = _Stores(
        units={freq: reader.variables(freq) for freq in FREQS},
        record_start={freq: _record_start(reader, freq) for freq in FREQS},
        record_end={freq: reader.last_valid_month(freq) for freq in FREQS},
        resolution=f"{grid.dlat:g}° × {grid.dlon:g}°",
    )
    variables, report = _variables(seed, stores)
    registered = _registered_metric_ids()
    draft = Catalog(
        version="",
        datasets=Datasets(
            daily=_dataset("daily", stores.record_end["daily"]),
            monthly=_dataset("monthly", stores.record_end["monthly"]),
        ),
        eng=ENGINE_VERSION,
        grid=grid,
        variables=variables,
        metrics=[_metric(item, registered) for item in seed.metrics],
        unavailable=[
            CatalogUnavailable.model_validate(item.model_dump())
            for item in seed.unavailable
        ],
    )
    # ponytail: the version is a hash of the content, so any change gives a new one.
    version = hashlib.sha256(draft.to_json_bytes()).hexdigest()[:VERSION_HEX_LEN]
    return draft.model_copy(update={"version": version}), report


def _check_ids(kind: str, found: list[str], expected: tuple[str, ...]) -> None:
    counts = Counter(found)
    twice = {name for name, count in counts.items() if count > 1}
    wrong = sorted((set(expected) ^ counts.keys()) | twice)
    if wrong:
        raise ValueError(f"the seed must hold each {kind} ID once: {', '.join(wrong)}")


def _record_start(reader: SeriesReader, freq: Freq) -> str:
    """The first complete month of the series that pins the last valid month.

    PowerReader holds that series in its chunk cache, so this read fetches nothing.
    """
    # ponytail: one probe series per store gives every variable the same start. Read
    # each variable if a store ever mixes record starts.
    probe = reader.read_cells(
        PROBE_VARIABLE, freq, [PROBE_CELL], AXIS_START, reader.last_valid_month(freq)
    )
    return str(present_months(probe.times, probe.values[:, 0], freq)[0])


def _variables(
    seed: CatalogSeed, stores: _Stores
) -> tuple[list[CatalogVariable], list[str]]:
    source = {item.id: item.source_freq for item in seed.metrics}
    variables: list[CatalogVariable] = []
    report: list[str] = []
    for item in seed.variables:
        carried = [freq for freq in FREQS if item.id in stores.units[freq]]
        if not carried:
            report.append(f"{item.id}: in the seed and in no store; left out")
            continue
        default_freq = source[item.default_metric]
        if item.scan_set and default_freq not in carried:
            report.append(
                f"{item.id}: scan_set false; its default metric "
                f"{item.default_metric} reads the {default_freq} store, which lacks it"
            )
        variables.append(_variable(item, carried, default_freq, stores))
    return variables, report


def _variable(
    item: SeedVariable, carried: list[Freq], default_freq: Freq, stores: _Stores
) -> CatalogVariable:
    freq = default_freq if default_freq in carried else carried[0]
    start, end = stores.record_start[freq], stores.record_end[freq]
    return CatalogVariable(
        id=item.id,
        name=item.name,
        definition=item.definition,
        unit=stores.units[freq][item.id],
        dataset=item.dataset,
        resolution=stores.resolution,
        stores=carried,
        record_start=start,
        record_end=end,
        min_record_years=item.min_record_years,
        is_trend_ready=_record_years(start, end) >= item.min_record_years,
        default_metric=item.default_metric,
        scan_set=item.scan_set and default_freq in carried,
        share_scale=item.share_scale,
        kind=item.kind,
        season_starts=item.season_starts,
    )


# ponytail: the badge counts whole years between the record ends (FR-07). The verdict
# guard counts yearly values in the engine; this count only drives the badge.
def _record_years(start: str, end: str) -> int:
    months = (np.datetime64(end, "M") - np.datetime64(start, "M")).astype(int) + 1
    return int(months) // MONTHS_IN_YEAR


def _registered_metric_ids() -> set[str]:
    """The metric IDs that the engine holds a reducer for."""
    modules = [import_module(name) for name in metrics.EXTENSION_MODULES]
    return set(metrics.REDUCERS).union(*(module.REDUCERS for module in modules))


def _metric(item: SeedMetric, registered: set[str]) -> CatalogMetric:
    return CatalogMetric(
        id=item.id,
        name=item.name,
        definition=item.definition,
        source_freq=item.source_freq,
        value_kind=item.value_kind,
        defaults=MetricSettings(
            threshold=item.default_threshold,
            op=item.op,
            months=item.default_months,
        ),
        is_available=item.id in registered,
    )


def _dataset(freq: Freq, last_month: str) -> DatasetVersion:
    dataset_id = DATASET_ID.format(freq=freq)
    return DatasetVersion(
        ds=f"{dataset_id}@{last_month}",
        dataset_id=dataset_id,
        dataset_version=last_month,
        last_valid_month=last_month,
    )
