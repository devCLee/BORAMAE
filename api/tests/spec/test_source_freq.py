"""The store that a metric on a variable reads (TODOS.md wave 3, open decision 9)."""

import pytest

from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import RequestSpec
from boramae.services.catalog import find_metric, find_variable
from boramae.spec.canonical import canonicalize, source_freq
from boramae.spec.validate import validate_request

SEOUL_MEAN = {
    "v": 1,
    "kind": "trend",
    "var": "T2M_MAX",
    "metric": {"id": "annual_mean"},
    "area": {"lat": 37.5665, "lon": 126.978, "radius_km": 25},
    "window": {"start": 1981, "end": "latest"},
}
EARLIER_MONTHLY_PIN = "2026-08"


def freq_of(catalog, var_id, metric_id):
    return source_freq(find_variable(catalog, var_id), find_metric(catalog, metric_id))


def canonical_of(catalog, var_id):
    spec = RequestSpec.model_validate(SEOUL_MEAN | {"var": var_id})
    return canonicalize(validate_request(spec, catalog), catalog)


def with_earlier_monthly_pin(catalog):
    data = catalog.model_dump()
    data["datasets"]["monthly"]["last_valid_month"] = EARLIER_MONTHLY_PIN
    return Catalog.model_validate(data)


@pytest.mark.parametrize(
    ("var_id", "metric_id", "freq"),
    [
        ("T2M_MAX", "annual_mean", "daily"),
        ("T2M_MAX", "seasonal_mean", "daily"),
        ("T2M_MIN", "annual_mean", "daily"),
        ("T2M_MIN", "seasonal_mean", "daily"),
        ("T2M", "annual_mean", "monthly"),
        ("T2M", "seasonal_mean", "monthly"),
        ("T2M_MAX", "annual_total", "monthly"),
        ("T2M_MAX", "threshold_days", "daily"),
    ],
)
def test_should_read_the_store_of_the_pair(sample_catalog, var_id, metric_id, freq):
    assert freq_of(sample_catalog, var_id, metric_id) == freq


def test_should_keep_a_daily_metric_daily_on_another_variable(sample_catalog):
    # content/catalog.seed.json holds annual_total as daily; the sample says monthly.
    daily_total = find_metric(sample_catalog, "annual_total").model_copy(
        update={"source_freq": "daily"}
    )
    variable = find_variable(sample_catalog, "PRECTOTCORR")
    assert source_freq(variable, daily_total) == "daily"


@pytest.mark.parametrize(("var_id", "freq"), [("T2M_MAX", "daily"), ("T2M", "monthly")])
def test_should_take_the_ds_of_the_store_that_the_pair_reads(
    sample_catalog, var_id, freq
):
    expected = getattr(sample_catalog.datasets, freq).ds
    assert canonical_of(sample_catalog, var_id).ds == expected


def test_should_end_latest_at_the_pinned_month_of_the_store_read(sample_catalog):
    catalog = with_earlier_monthly_pin(sample_catalog)
    end = canonical_of(catalog, "T2M_MAX").window[1]
    assert end == catalog.datasets.daily.last_valid_month
