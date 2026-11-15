"""PowerReader against tiny Zarr v2 stores that the tests write into tmp_path."""

import asyncio
from contextlib import suppress
from pathlib import Path

import numpy as np
import pytest
import zarr
from zarr.storage import FsspecStore

from boramae.config import Settings
from boramae.engine.types import CellSeries, Footprint, GridDef
from boramae.errors import PowerUnavailable
from boramae.power import reader as reader_module
from boramae.power.reader import PowerReader
from tests.power.stores import write_daily_store, write_monthly_store

SEOUL = (255, 491)  # monthly chunk 0.8.16; the pinned-month probe reads this cell
EAST = (255, 510)  # monthly chunk 0.8.17
NORTH_EAST = (270, 510)  # monthly chunk 0.9.17
NO_DATA = (100, 100)  # the stores hold no chunk here
TENTH_AS_DECODED = 0.0999755859375  # float32 (-99990 / 100) + 1000, for a stored 0.10
JAN_10 = 9  # the row of 1981-01-10 in a read of January, where PRECSNO holds 0.10


@pytest.fixture
def store_root(tmp_path, monkeypatch) -> Path:
    """Point the reader at tmp_path in place of the POWER bucket."""
    url = tmp_path.as_uri() + "/power_{freq}.zarr"
    monkeypatch.setattr(reader_module, "STORE_URL", url)
    return tmp_path


@pytest.fixture
def stores(store_root) -> Path:
    write_monthly_store(store_root / "power_monthly.zarr")
    write_daily_store(store_root / "power_daily.zarr")
    return store_root


@pytest.fixture
def power_reader(stores) -> PowerReader:
    return PowerReader(Settings())


def _monthly(reader: PowerReader, cell=SEOUL, start="1981-01", end="1983-12"):
    return reader.read_cells("T2M", "monthly", [cell], start, end)


def _chunk_size(root: Path, chunk: str) -> int:
    return (root / "power_monthly.zarr" / "T2M" / chunk).stat().st_size


def test_should_pin_the_last_month_with_a_value_on_a_padded_monthly_axis(power_reader):
    assert power_reader.last_valid_month("monthly") == "1983-06"


def test_should_pin_the_month_before_a_daily_month_with_one_valid_day(power_reader):
    assert power_reader.last_valid_month("daily") == "1981-02"


@pytest.mark.parametrize(
    ("freq", "last_step"), [("monthly", "1983-06-01"), ("daily", "1981-02-28")]
)
def test_should_return_no_step_after_the_pinned_month(power_reader, freq, last_step):
    series = power_reader.read_cells("T2M", freq, [SEOUL], "1980-01", "2029-12")
    assert series.times[-1] == np.datetime64(last_step)


def test_should_return_no_step_when_the_window_starts_after_the_pinned_month(
    power_reader,
):
    assert _monthly(power_reader, start="1983-09").values.shape == (0, 1)


@pytest.mark.parametrize(
    ("freq", "first_step"), [("monthly", "1982-03-01"), ("daily", "1981-02-01")]
)
def test_should_start_at_the_first_step_of_the_start_month(
    power_reader, freq, first_step
):
    start = first_step[:7]
    series = power_reader.read_cells("T2M", freq, [SEOUL], start, "2029-12")
    assert series.times[0] == np.datetime64(first_step)


@pytest.mark.parametrize(
    ("freq", "last_step"), [("monthly", "1982-03-01"), ("daily", "1981-01-31")]
)
def test_should_end_at_the_last_step_of_the_end_month(power_reader, freq, last_step):
    end = last_step[:7]
    series = power_reader.read_cells("T2M", freq, [SEOUL], "1980-01", end)
    assert series.times[-1] == np.datetime64(last_step)


@pytest.mark.parametrize(
    ("freq", "first_step"), [("monthly", "1981-01-01"), ("daily", "1980-12-31")]
)
def test_should_decode_times_from_the_cf_units_and_calendar(
    power_reader, freq, first_step
):
    series = power_reader.read_cells("T2M", freq, [SEOUL], "1980-01", "2029-12")
    assert series.times[0] == np.datetime64(first_step)


@pytest.mark.parametrize("freq", ["monthly", "daily"])
def test_should_return_times_in_days(power_reader, freq):
    series = power_reader.read_cells("T2M", freq, [SEOUL], "1980-01", "2029-12")
    assert series.times.dtype == np.dtype("datetime64[D]")


def test_should_map_each_cell_index_to_its_values(power_reader):
    cells = [SEOUL, NORTH_EAST, (250, 485)]
    series = power_reader.read_cells("T2M", "monthly", cells, "1981-01", "1981-02")
    assert series.values.tolist() == [
        [25549100.0, 27051000.0, 25048500.0],
        [25549101.0, 27051001.0, 25048501.0],
    ]


def test_should_read_a_box_with_the_latitude_index_running_first(power_reader):
    series = power_reader.read_box(
        "T2M", "monthly", 269, 271, 509, 511, "1981-01", "1981-01"
    )
    assert series.values.tolist() == [[26950900.0, 26951000.0, 27050900.0, 27051000.0]]


def test_should_return_values_as_float64(power_reader):
    assert _monthly(power_reader).values.dtype == np.float64


def test_should_return_nan_where_the_store_holds_no_chunk(power_reader):
    assert np.isnan(_monthly(power_reader, cell=NO_DATA).values).all()


def _snow(reader: PowerReader, month="1981-01"):
    """The fake PRECSNO holds (step % 20) / 100, and 1981-01-01 is step 1."""
    return reader.read_cells("PRECSNO", "daily", [SEOUL], month, month)


def test_should_hold_a_stored_tenth_that_decodes_below_the_threshold(stores):
    stored = zarr.open_array(str(stores / "power_daily.zarr" / "PRECSNO"), mode="r")
    assert float(stored[10, SEOUL[0], SEOUL[1]]) == TENTH_AS_DECODED


def test_should_return_a_stored_tenth_at_the_threshold_from_a_cell_read(power_reader):
    assert _snow(power_reader).values[JAN_10, 0] >= 0.1


def test_should_return_a_stored_tenth_at_the_threshold_from_a_box_read(power_reader):
    series = power_reader.read_box(
        "PRECSNO", "daily", 255, 256, 491, 492, "1981-01", "1981-01"
    )
    assert series.values[JAN_10, 0] >= 0.1


def test_should_count_every_day_at_or_above_a_threshold(power_reader):
    assert int((_snow(power_reader).values >= 0.1).sum()) == 12


def test_should_return_each_value_at_the_decimal_digits_that_the_store_declares(
    power_reader,
):
    assert _snow(power_reader).values[:5, 0].tolist() == [0.01, 0.02, 0.03, 0.04, 0.05]


def test_should_keep_a_missing_value_of_a_rounded_variable_as_nan(power_reader):
    assert np.isnan(_snow(power_reader, month="1981-02").values[-1, 0])


def test_should_return_rounded_values_as_float64(power_reader):
    assert _snow(power_reader).values.dtype == np.float64


def test_should_report_the_power_grid(power_reader):
    assert power_reader.grid() == GridDef(-90.0, 0.5, 361, -180.0, 0.625, 576)


def test_should_list_each_variable_with_its_unit(power_reader):
    assert power_reader.variables("monthly") == {"T2M": "C"}


def test_should_raise_key_error_for_a_variable_that_the_store_lacks(power_reader):
    with pytest.raises(KeyError):
        power_reader.read_cells("PRECSNO", "monthly", [SEOUL], "1981-01", "1981-12")


def test_should_report_the_count_and_stored_size_of_the_chunk_it_needs(
    power_reader, stores
):
    stored = _chunk_size(stores, "0.9.17")
    assert _monthly(power_reader, cell=NORTH_EAST).footprint == Footprint(1, stored)


@pytest.mark.parametrize(
    ("freq", "cells", "end", "chunk_count"),
    [
        ("monthly", [SEOUL, NORTH_EAST], "1983-12", 2),
        ("daily", [SEOUL], "1981-01", 1),
        ("daily", [SEOUL], "1981-02", 2),
    ],
    ids=["two spatial chunks", "one time chunk", "two time chunks"],
)
def test_should_count_each_needed_chunk_once(
    power_reader, freq, cells, end, chunk_count
):
    series = power_reader.read_cells("T2M", freq, cells, "1980-01", end)
    assert series.footprint.chunk_count == chunk_count


def test_should_count_no_chunk_where_the_store_holds_none(power_reader):
    assert _monthly(power_reader, cell=NO_DATA).footprint == Footprint(0, 0)


def test_should_fetch_its_stored_bytes_on_a_first_read(power_reader):
    series = _monthly(power_reader, cell=NORTH_EAST)
    assert series.fetched_bytes == series.footprint.stored_bytes


def test_should_fetch_no_bytes_on_a_second_identical_read(power_reader):
    _monthly(power_reader, cell=NORTH_EAST)
    assert _monthly(power_reader, cell=NORTH_EAST).fetched_bytes == 0


@pytest.mark.parametrize("chunk_cache_bytes", [2**30, 0], ids=["cached", "uncached"])
def test_should_report_the_same_footprint_on_a_second_identical_read(
    stores, chunk_cache_bytes
):
    reader = PowerReader(Settings(chunk_cache_bytes=chunk_cache_bytes))
    first = _monthly(reader, cell=NORTH_EAST)
    assert _monthly(reader, cell=NORTH_EAST).footprint == first.footprint


def test_should_fetch_again_when_the_cache_cannot_keep_the_chunk(stores):
    reader = PowerReader(Settings(chunk_cache_bytes=0))
    _monthly(reader, cell=NORTH_EAST)
    second = _monthly(reader, cell=NORTH_EAST)
    assert second.fetched_bytes == second.footprint.stored_bytes


@pytest.fixture
def reader_past_its_cache_limit(stores) -> PowerReader:
    """A cache that keeps two chunks, after reads of SEOUL, EAST, SEOUL, NORTH_EAST."""
    sizes = [_chunk_size(stores, chunk) for chunk in ("0.8.16", "0.8.17", "0.9.17")]
    reader = PowerReader(Settings(chunk_cache_bytes=sum(sizes) - 1))
    _monthly(reader, cell=SEOUL)
    _monthly(reader, cell=EAST)
    _monthly(reader, cell=SEOUL)
    _monthly(reader, cell=NORTH_EAST)
    return reader


def test_should_keep_the_recently_used_chunk_past_the_cache_limit(
    reader_past_its_cache_limit,
):
    assert _monthly(reader_past_its_cache_limit, cell=SEOUL).fetched_bytes == 0


def test_should_evict_the_least_recently_used_chunk_past_the_cache_limit(
    reader_past_its_cache_limit, stores
):
    series: CellSeries = _monthly(reader_past_its_cache_limit, cell=EAST)
    assert series.fetched_bytes == _chunk_size(stores, "0.8.17")


async def _fail(self, key, prototype, byte_range=None):
    raise OSError("connection reset")


async def _stall(self, key, prototype, byte_range=None):
    await asyncio.sleep(60)


def test_should_raise_power_unavailable_when_a_chunk_read_fails(
    power_reader, monkeypatch
):
    power_reader.variables("monthly")
    monkeypatch.setattr(FsspecStore, "get", _fail)
    with pytest.raises(PowerUnavailable):
        _monthly(power_reader)


def test_should_stop_a_read_at_the_chunk_timeout(stores, monkeypatch):
    monkeypatch.setattr(FsspecStore, "get", _stall)
    reader = PowerReader(Settings(power_chunk_timeout_s=0.05))
    with pytest.raises(PowerUnavailable) as caught:
        reader.grid()
    assert isinstance(caught.value.__cause__, TimeoutError)


def test_should_raise_power_unavailable_on_first_use_when_the_open_fails(store_root):
    reader = PowerReader(Settings())
    with pytest.raises(PowerUnavailable):
        reader.grid()


def test_should_open_on_a_later_call_when_the_first_open_failed(store_root):
    reader = PowerReader(Settings())
    with suppress(PowerUnavailable):
        reader.grid()
    write_monthly_store(store_root / "power_monthly.zarr")
    assert reader.last_valid_month("monthly") == "1983-06"


@pytest.mark.parametrize("dlat", [0.25, -0.5], ids=["finer", "descending"])
def test_should_refuse_a_store_with_another_latitude_step(store_root, dlat):
    write_monthly_store(store_root / "power_monthly.zarr", dlat=dlat)
    with pytest.raises(PowerUnavailable):
        PowerReader(Settings()).grid()
