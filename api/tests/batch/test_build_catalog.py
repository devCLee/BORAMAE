from pathlib import Path

import pytest

from boramae import deps
from boramae.batch.build_catalog import build_catalog, main
from boramae.constants import METRIC_IDS, VARIABLE_IDS
from boramae.contracts.content import CatalogSeed
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import MetricSettings
from boramae.engine.definitions import ENGINE_VERSION
from boramae.services.catalog import CATALOG_PATH
from boramae.services.content import read_content
from tests.fakes import POWER_GRID, DictStore, FakeReader

SEED_PATH = Path(__file__).resolve().parents[3] / "content" / "catalog.seed.json"
SEED = read_content(SEED_PATH, CatalogSeed)
PIN = "2025-06"
REQUIRED_FIELDS = (
    "name",
    "definition",
    "unit",
    "dataset",
    "resolution",
    "record_start",
    "record_end",
    "min_record_years",
    "is_trend_ready",
)


class MonthlyLacksT2M(FakeReader):
    """T2M is present in the daily store and absent from the monthly one."""

    def variables(self, freq):
        units = dict(super().variables(freq))
        if freq == "monthly":
            del units["T2M"]
        return units


class NamedUnits(FakeReader):
    def variables(self, freq):
        return {var: f"unit-of-{var}" for var in super().variables(freq)}


def build(reader=None, seed=SEED):
    return build_catalog(FakeReader(PIN) if reader is None else reader, seed)


def by_id(items):
    return {item.id: item for item in items}


def missing_fields(variable):
    return [name for name in REQUIRED_FIELDS if getattr(variable, name) in (None, "")]


def seed_without_variable(var_id):
    variables = [item for item in SEED.variables if item.id != var_id]
    return SEED.model_copy(update={"variables": variables})


def seed_with_metric_twice(metric_id):
    metrics = [*SEED.metrics, by_id(SEED.metrics)[metric_id]]
    return SEED.model_copy(update={"metrics": metrics})


@pytest.fixture
def catalog():
    return build()[0]


def test_seed_holds_each_variable_id_once():
    assert sorted(item.id for item in SEED.variables) == sorted(VARIABLE_IDS)


def test_seed_holds_each_metric_id_once():
    assert sorted(item.id for item in SEED.metrics) == sorted(METRIC_IDS)


@pytest.mark.parametrize(
    ("var_id", "share_scale"),
    [
        ("GWETTOP", "fraction"),
        ("GWETROOT", "fraction"),
        ("FRSNO", "fraction"),
        ("FRSEAICE", "fraction"),
        ("RH2M", "percent"),
        ("T2M", None),
        ("PRECSNO", None),
    ],
)
def test_seed_marks_the_share_variables(var_id, share_scale):
    assert by_id(SEED.variables)[var_id].share_scale == share_scale


def test_built_catalog_validates_against_the_catalog_model(catalog):
    assert Catalog.model_validate_json(catalog.to_json_bytes()) == catalog


@pytest.mark.parametrize("var_id", VARIABLE_IDS)
def test_variable_has_no_missing_field(catalog, var_id):
    assert missing_fields(by_id(catalog.variables)[var_id]) == []


def test_record_end_equals_the_pinned_month(catalog):
    assert {item.record_end for item in catalog.variables} == {PIN}


def test_record_starts_at_the_first_complete_month(catalog):
    assert {item.record_start for item in catalog.variables} == {"1981-01"}


@pytest.mark.parametrize(
    ("last_month", "is_ready"), [("2000-12", True), ("2000-11", False)]
)
def test_trend_ready_flag_follows_the_minimum_record(last_month, is_ready):
    variables = build(FakeReader(last_month))[0].variables
    assert {item.is_trend_ready for item in variables} == {is_ready}


@pytest.mark.parametrize("freq", ["daily", "monthly"])
def test_ds_names_the_store_and_the_pinned_month(catalog, freq):
    assert getattr(catalog.datasets, freq).ds == f"power-merra2-{freq}@{PIN}"


@pytest.mark.parametrize("freq", ["daily", "monthly"])
def test_dataset_holds_the_pinned_month(catalog, freq):
    assert getattr(catalog.datasets, freq).last_valid_month == PIN


def test_unit_comes_from_the_store():
    catalog = build(NamedUnits(PIN))[0]
    assert by_id(catalog.variables)["PRECSNO"].unit == "unit-of-PRECSNO"


def test_variable_lists_the_stores_that_carry_it():
    catalog = build(MonthlyLacksT2M(PIN))[0]
    assert by_id(catalog.variables)["T2M"].stores == ["daily"]


def test_variable_missing_from_every_store_is_reported():
    report = build(FakeReader(PIN, missing_vars={"TO3"}))[1]
    assert ["TO3" in line for line in report] == [True]


def test_variable_missing_from_every_store_is_left_out():
    catalog = build(FakeReader(PIN, missing_vars={"TO3"}))[0]
    assert "TO3" not in by_id(catalog.variables)


def test_store_gap_of_the_default_metric_clears_scan_set():
    catalog = build(MonthlyLacksT2M(PIN))[0]
    assert by_id(catalog.variables)["T2M"].scan_set is False


def test_store_gap_of_the_default_metric_is_reported():
    report = build(MonthlyLacksT2M(PIN))[1]
    assert ["T2M" in line for line in report] == [True]


def test_full_stores_give_an_empty_report():
    assert build()[1] == []


@pytest.mark.parametrize(
    ("metric_id", "is_available"),
    [
        ("annual_mean", True),
        ("first_date", True),
        ("rx1day", True),
        ("snow_share", False),
    ],
)
def test_metric_is_available_only_with_a_registered_reducer(
    catalog, metric_id, is_available
):
    assert by_id(catalog.metrics)[metric_id].is_available is is_available


def test_metric_defaults_come_from_the_seed(catalog):
    expected = MetricSettings(threshold="0.1", op=">=")
    assert by_id(catalog.metrics)["first_date"].defaults == expected


def test_unavailable_list_comes_from_the_seed(catalog):
    assert [item.id for item in catalog.unavailable] == [
        item.id for item in SEED.unavailable
    ]


def test_grid_comes_from_the_reader(catalog):
    assert catalog.grid == POWER_GRID


def test_resolution_reads_from_the_grid_steps(catalog):
    assert by_id(catalog.variables)["T2M"].resolution == "0.5° × 0.625°"


def test_catalog_carries_the_engine_version(catalog):
    assert catalog.eng == ENGINE_VERSION


def test_version_is_the_same_for_the_same_inputs(catalog):
    assert build()[0].version == catalog.version


def test_version_changes_with_the_pinned_month(catalog):
    assert build(FakeReader("2025-07"))[0].version != catalog.version


def test_seed_without_a_variable_id_is_refused():
    with pytest.raises(ValueError, match="T2M"):
        build(seed=seed_without_variable("T2M"))


def test_seed_with_a_metric_id_twice_is_refused():
    with pytest.raises(ValueError, match="rx1day"):
        build(seed=seed_with_metric_twice("rx1day"))


@pytest.fixture
def stores(monkeypatch):
    store = DictStore()
    monkeypatch.setattr(deps, "get_reader", lambda: FakeReader(PIN))
    monkeypatch.setattr(deps, "get_store", lambda: store)
    return store


def test_stdout_prints_a_valid_catalog(stores, capsys):
    main(["--stdout"])
    printed = Catalog.model_validate_json(capsys.readouterr().out)
    assert printed.datasets.daily.last_valid_month == PIN


def test_stdout_writes_no_store_file(stores):
    main(["--stdout"])
    assert stores.files == {}


def test_main_puts_the_catalog_in_the_store(stores):
    main([])
    stored = Catalog.model_validate_json(stores.files[CATALOG_PATH])
    assert stored.datasets.daily.last_valid_month == PIN


def test_main_exits_with_code_0(stores):
    assert main([]) == 0
