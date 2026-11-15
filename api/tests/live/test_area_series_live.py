"""Live test 2, the FR-08 proof: the service's area series against xarray.

Run with -m live -s. For each area the service builds the monthly T2M series through
get_trend, and an independent xarray computation averages the same cells of the
store with cos-latitude weights. Each saved file in tests/fixtures/area_series holds
the cells, their latitudes, the per-cell values that the service read and both
series; test_area_series_replay.py replays them with no network.
"""

import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from boramae.batch.build_catalog import build_catalog
from boramae.config import load_settings
from boramae.contracts.results import TrendResult
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.power.reader import STORE_URL, PowerReader
from boramae.services.catalog import CATALOG_PATH, load_catalog
from boramae.services.content import load_content
from boramae.services.trend import get_trend
from boramae.store.local import LocalStore
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService

pytestmark = pytest.mark.live

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "area_series"
# Name, gazetteer row and radius of the three test areas (TRD TR-D-003 names none).
AREAS = (
    ("seoul-25km", "kr-seoul", 25),
    ("seoul-150km", "kr-seoul", 150),
    ("jeju-100km", "kr-jeju", 100),
)
AREA_NAMES = tuple(name for name, _, _ in AREAS)
VARIABLE, FREQ = "T2M", "monthly"
# ponytail: TRD Q-14 leaves 0.1% near zero undefined; the bound is 0.1% of the larger
# of the reference and 1 unit. The replay test uses the same rule.
RELATIVE_TOLERANCE = 0.001
TOLERANCE_FLOOR = 1.0
# These two change with every run, so the summary prints them and no file holds them.
RUN_FACTS = ("read_ms", "bytes_fetched")


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    settings = load_settings()
    reader = PowerReader(settings)
    store = LocalStore(tmp_path_factory.mktemp("area-series-live"))
    built, _ = build_catalog(reader, load_content("catalog_seed"))
    store.put(CATALOG_PATH, built.to_json_bytes())
    pool = WorkerPool(
        settings.pool_size, settings.pool_wait_s, settings.request_timeout_s
    )
    return reader, ResultService(store, pool), load_catalog(store)


@pytest.fixture(scope="module")
def reference_store() -> xr.Dataset:
    return xr.open_zarr(
        STORE_URL.format(freq=FREQ), consolidated=True, zarr_format=2, chunks=None
    )


@pytest.fixture(scope="module")
def saved(service, reference_store) -> dict[str, dict]:
    places = {place.id: place for place in load_content("gazetteer")}
    records = {
        name: _compare(service, reference_store, places[place_id], radius_km)
        for name, place_id, radius_km in AREAS
    }
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    print()
    for name, record in records.items():
        kept = {key: value for key, value in record.items() if key not in RUN_FACTS}
        text = json.dumps(kept, allow_nan=False, separators=(",", ":"))
        (FIXTURE_DIR / f"{name}.json").write_text(text + "\n", encoding="utf-8")
        print(_summary(name, record))
    return records


@pytest.mark.parametrize("name", AREA_NAMES)
def test_should_match_the_independent_series_value_by_value(saved, name):
    service = np.array(saved[name]["service_series"], dtype=float)
    reference = np.array(saved[name]["reference_series"], dtype=float)
    bound = RELATIVE_TOLERANCE * np.maximum(np.abs(reference), TOLERANCE_FLOOR)
    assert np.all(np.abs(service - reference) <= bound)


@pytest.mark.parametrize("name", AREA_NAMES)
def test_should_compare_every_month_of_the_series(saved, name):
    assert len(saved[name]["reference_series"]) == len(saved[name]["months"])


def _compare(service, reference_store: xr.Dataset, place, radius_km: int) -> dict:
    reader, results, catalog = service
    variable = next(item for item in catalog.variables if item.id == VARIABLE)
    spec = RequestSpec(
        v=1,
        kind="trend",
        var=VARIABLE,
        metric=SpecMetric(id="annual_mean"),
        area=Circle(lat=place.lat, lon=place.lon, radius_km=radius_km),
        window=RequestWindow(start=int(variable.record_start[:4]), end="latest"),
    )
    body, _, _, facts = get_trend(spec, reader=reader, results=results, catalog=catalog)
    result = TrendResult.model_validate_json(body)
    months = result.series.monthly.months
    cells = [tuple(cell) for cell in result.spec.cells]
    # The chunks are in the reader's cache now, so this read fetches nothing.
    cell_read = reader.read_cells(VARIABLE, FREQ, cells, months[0], months[-1])
    latitudes, reference = _reference(reference_store, cells, months)
    return {
        "place": place.id,
        "lat": place.lat,
        "lon": place.lon,
        "radius_km": radius_km,
        "cells": [list(cell) for cell in cells],
        "latitudes": latitudes,
        "months": months,
        "cell_values": cell_read.values.tolist(),
        "service_series": result.series.monthly.values,
        "reference_series": reference,
        "read_ms": facts.timings.get("read"),
        "bytes_fetched": facts.bytes_fetched,
    }


def _reference(
    store: xr.Dataset, cells: list[tuple[int, int]], months: list[str]
) -> tuple[list[float], list[float]]:
    """Latitudes of the cells and their cos-weighted monthly mean, read by xarray."""
    lat_i = xr.DataArray([cell[0] for cell in cells], dims="cell")
    lon_i = xr.DataArray([cell[1] for cell in cells], dims="cell")
    store_months = np.datetime_as_string(store["time"].values, unit="M")
    steps = np.flatnonzero(np.isin(store_months, months))
    values = store[VARIABLE].isel(time=steps, lat=lat_i, lon=lon_i).load()
    weights = np.cos(np.deg2rad(values["lat"]))
    mean = values.weighted(weights).mean("cell")
    return values["lat"].values.tolist(), mean.values.tolist()


def _summary(name: str, record: dict) -> str:
    service = np.array(record["service_series"], dtype=float)
    reference = np.array(record["reference_series"], dtype=float)
    return (
        f"{name}: {len(record['cells'])} cells, {len(record['months'])} months"
        f" ({record['months'][0]} to {record['months'][-1]}), largest difference"
        f" {np.max(np.abs(service - reference)):.3g} C; read {record['read_ms']} ms,"
        f" {record['bytes_fetched']} bytes"
    )
