import pytest

from boramae.errors import ProblemError
from boramae.services.catalog import (
    CATALOG_PATH,
    find_metric,
    find_variable,
    list_scan_set,
    load_catalog,
)
from tests.fakes import DictStore


def stored(catalog):
    store = DictStore()
    store.put(CATALOG_PATH, catalog.to_json_bytes())
    return store


def without_scan(catalog, var_id):
    variables = [
        item.model_copy(update={"scan_set": item.id != var_id})
        for item in catalog.variables
    ]
    return catalog.model_copy(update={"variables": variables})


@pytest.fixture
def missing():
    with pytest.raises(ProblemError) as info:
        load_catalog(DictStore())
    return info.value


def test_load_returns_the_stored_catalog(sample_catalog):
    assert load_catalog(stored(sample_catalog)) == sample_catalog


def test_load_keeps_an_in_memory_copy(sample_catalog):
    store = stored(sample_catalog)
    load_catalog(store)
    store.files.clear()
    assert load_catalog(store) == sample_catalog


def test_missing_catalog_answers_503(missing):
    assert missing.status == 503


def test_missing_catalog_has_the_code_catalog_unavailable(missing):
    assert missing.code == "catalog_unavailable"


def test_missing_catalog_carries_retry_after(missing):
    assert int(missing.headers["Retry-After"]) > 0


def test_catalog_stored_after_a_miss_loads(sample_catalog):
    store = DictStore()
    with pytest.raises(ProblemError):
        load_catalog(store)
    store.put(CATALOG_PATH, sample_catalog.to_json_bytes())
    assert load_catalog(store) == sample_catalog


def test_find_variable_returns_its_entry(sample_catalog):
    assert find_variable(sample_catalog, "PRECSNO").unit == "mm/day"


def test_find_variable_returns_none_for_an_unknown_id(sample_catalog):
    assert find_variable(sample_catalog, "PM2.5") is None


def test_find_metric_returns_its_entry(sample_catalog):
    assert find_metric(sample_catalog, "first_date").source_freq == "daily"


def test_find_metric_returns_none_for_an_unknown_id(sample_catalog):
    assert find_metric(sample_catalog, "max_wind") is None


def test_scan_set_leaves_out_a_variable_without_the_flag(sample_catalog):
    catalog = without_scan(sample_catalog, "T2M")
    assert "T2M" not in [item.id for item in list_scan_set(catalog)]


def test_scan_set_keeps_the_catalog_order(sample_catalog):
    catalog = without_scan(sample_catalog, "T2M")
    assert [item.id for item in list_scan_set(catalog)] == [
        item.id for item in catalog.variables[1:]
    ]
