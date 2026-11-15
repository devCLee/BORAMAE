from typing import Annotated

import numpy as np
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from boramae import deps
from boramae.engine.types import GridDef
from boramae.errors import PowerUnavailable
from tests.fakes import DictStore, FakeReader, make_client

SEOUL = (255, 491)
BUSAN = (250, 497)


def _resolve(client: TestClient, dependency):
    seen = {}

    @client.app.get("/probe-dependency")
    def probe(value: Annotated[object, Depends(dependency)]) -> None:
        seen["value"] = value

    client.get("/probe-dependency")
    return seen["value"]


def _monthly(reader: FakeReader, start="1981-01", end="2029-12", cells=(SEOUL,)):
    return reader.read_cells("T2M", "monthly", list(cells), start, end)


@pytest.mark.parametrize(
    ("dependency", "name"),
    [
        (deps.get_reader, "reader"),
        (deps.get_store, "store"),
        (deps.get_catalog, "catalog"),
        (deps.get_model_parser, "model_parser"),
    ],
)
def test_make_client_hands_the_given_object_to_a_router(dependency, name):
    given = object()
    assert _resolve(make_client(**{name: given}), dependency) is given


def test_make_client_defaults_to_a_fake_reader():
    assert isinstance(_resolve(make_client(), deps.get_reader), FakeReader)


def test_make_client_defaults_to_a_dict_store():
    assert isinstance(_resolve(make_client(), deps.get_store), DictStore)


def test_make_client_defaults_to_no_model_parser():
    assert _resolve(make_client(), deps.get_model_parser) is None


def test_fake_grid_is_the_power_grid():
    assert FakeReader().grid() == GridDef(-90.0, 0.5, 361, -180.0, 0.625, 576)


def test_fake_monthly_axis_starts_in_1981_01():
    assert _monthly(FakeReader(), start="1970-01").times[0] == np.datetime64(
        "1981-01-01"
    )


def test_fake_daily_axis_starts_on_1980_12_31():
    series = FakeReader().read_cells("T2M", "daily", [SEOUL], "1980-01", "1981-01")
    assert series.times[0] == np.datetime64("1980-12-31")


@pytest.mark.parametrize("freq", ["monthly", "daily"])
def test_fake_pinned_month_defaults_to_2026_09(freq):
    assert FakeReader().last_valid_month(freq) == "2026-09"


def test_fake_read_returns_no_step_after_the_last_month():
    series = _monthly(FakeReader(last_month="2025-03"))
    assert series.times[-1] == np.datetime64("2025-03-01")


def test_fake_daily_read_ends_on_the_last_day_of_the_last_month():
    series = FakeReader().read_cells("T2M", "daily", [SEOUL], "2026-01", "2029-12")
    assert series.times[-1] == np.datetime64("2026-09-30")


def test_fake_read_after_the_last_month_returns_no_step():
    assert _monthly(FakeReader(), start="2027-01").values.shape == (0, 1)


def test_fake_read_holds_one_column_per_cell():
    assert _monthly(FakeReader(), cells=(SEOUL, BUSAN)).values.shape == (549, 2)


def test_fake_box_read_holds_every_cell_of_the_box():
    series = FakeReader().read_box(
        "T2M", "monthly", 250, 253, 490, 492, "2000-01", "2000-12"
    )
    assert series.values.shape == (12, 6)


def test_fake_box_columns_run_latitude_first():
    reader = FakeReader()
    box = reader.read_box("T2M", "monthly", 250, 252, 490, 492, "2000-01", "2000-12")
    cell = _monthly(reader, start="2000-01", end="2000-12", cells=((250, 491),))
    assert np.array_equal(box.values[:, 1], cell.values[:, 0])


def test_fake_values_repeat_for_the_same_cell():
    first = _monthly(FakeReader())
    assert np.array_equal(_monthly(FakeReader()).values, first.values)


def test_fake_values_differ_between_cells():
    series = _monthly(FakeReader(), cells=(SEOUL, BUSAN))
    assert not np.array_equal(series.values[:, 0], series.values[:, 1])


def test_fake_values_do_not_depend_on_the_window():
    whole = _monthly(FakeReader(), start="2000-01", end="2000-12")
    part = _monthly(FakeReader(), start="2000-06", end="2000-06")
    assert part.values[0, 0] == whole.values[5, 0]


def test_fake_values_hold_no_nan_inside_the_record():
    assert not np.isnan(_monthly(FakeReader()).values).any()


def test_values_fn_gives_exact_values():
    def years(var, freq, times, cell):
        return times.astype("datetime64[Y]").astype(float) + 1970.0

    series = _monthly(FakeReader(values_fn=years), start="1990-01", end="1990-01")
    assert series.values[0, 0] == 1990.0


@pytest.mark.parametrize(
    "call",
    [
        lambda reader: _monthly(reader),
        lambda reader: reader.read_box(
            "T2M", "daily", 0, 1, 0, 1, "2000-01", "2000-01"
        ),
        lambda reader: reader.last_valid_month("monthly"),
        lambda reader: reader.variables("daily"),
        lambda reader: reader.grid(),
    ],
    ids=["read_cells", "read_box", "last_valid_month", "variables", "grid"],
)
def test_fail_raises_power_unavailable(call):
    with pytest.raises(PowerUnavailable):
        call(FakeReader(fail=True))


def test_missing_variable_is_absent_from_the_store():
    assert "PRECSNO" not in FakeReader(missing_vars={"PRECSNO"}).variables("daily")


def test_store_lists_every_other_variable():
    assert len(FakeReader(missing_vars={"PRECSNO"}).variables("monthly")) == 19


def test_reading_a_missing_variable_raises_key_error():
    reader = FakeReader(missing_vars={"PRECSNO"})
    with pytest.raises(KeyError):
        reader.read_cells("PRECSNO", "daily", [SEOUL], "2000-01", "2000-12")


def test_first_read_fetches_its_stored_bytes():
    series = _monthly(FakeReader())
    assert series.fetched_bytes == series.footprint.stored_bytes


def test_repeated_read_fetches_zero_bytes():
    reader = FakeReader()
    _monthly(reader)
    assert _monthly(reader).fetched_bytes == 0


def test_repeated_read_reports_the_same_footprint():
    reader = FakeReader()
    first = _monthly(reader)
    assert _monthly(reader).footprint == first.footprint


def test_read_count_counts_every_read():
    reader = FakeReader()
    _monthly(reader)
    reader.read_box("T2M", "monthly", 0, 1, 0, 1, "2000-01", "2000-12")
    assert reader.read_count == 2


def test_dict_store_returns_none_for_a_missing_path():
    assert DictStore().get("r/trend/missing.json") is None


def test_dict_store_create_once_reports_the_first_write():
    assert DictStore().create_once("r/trend/a.json", b"{}") is True


def test_dict_store_create_once_refuses_a_second_write():
    store = DictStore()
    store.create_once("r/trend/a.json", b"{}")
    assert store.create_once("r/trend/a.json", b"[]") is False


def test_dict_store_create_once_keeps_the_first_body():
    store = DictStore()
    store.create_once("r/trend/a.json", b"{}")
    store.create_once("r/trend/a.json", b"[]")
    assert store.get("r/trend/a.json") == b"{}"


def test_dict_store_put_replaces_the_body():
    store = DictStore()
    store.put("meta/catalog.json", b"{}")
    store.put("meta/catalog.json", b"[]")
    assert store.get("meta/catalog.json") == b"[]"
