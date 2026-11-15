"""validate_request takes the store of a spec from source_freq (wave 3 close)."""

import pytest

from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import RequestSpec
from boramae.errors import ProblemError
from boramae.spec.validate import validate_request

DAILY_HIGH_MEAN = RequestSpec.model_validate(
    {
        "v": 1,
        "kind": "trend",
        "var": "T2M_MAX",
        "metric": {"id": "annual_mean"},
        "area": {"lat": 37.5665, "lon": 126.978, "radius_km": 25},
        "window": {"start": 1981, "end": 2026},
    }
)
MONTHLY_PIN_IN_AN_EARLIER_YEAR = "2025-12"


def with_monthly_pin(catalog, month):
    data = catalog.model_dump()
    data["datasets"]["monthly"]["last_valid_month"] = month
    return Catalog.model_validate(data)


def with_stores(catalog, var_id, stores):
    data = catalog.model_dump()
    variable = next(item for item in data["variables"] if item["id"] == var_id)
    variable["stores"] = stores
    return Catalog.model_validate(data)


def test_should_check_the_window_of_a_daily_high_mean_against_the_daily_pin(
    sample_catalog,
):
    catalog = with_monthly_pin(sample_catalog, MONTHLY_PIN_IN_AN_EARLIER_YEAR)

    validated = validate_request(DAILY_HIGH_MEAN, catalog)

    assert validated.spec.window.end == 2026


def test_should_accept_a_daily_high_mean_when_only_the_daily_store_holds_it(
    sample_catalog,
):
    catalog = with_stores(sample_catalog, "T2M_MAX", ["daily"])

    validated = validate_request(DAILY_HIGH_MEAN, catalog)

    assert validated.variable.stores == ["daily"]


def test_should_refuse_a_daily_high_mean_when_the_daily_store_lacks_it(sample_catalog):
    catalog = with_stores(sample_catalog, "T2M_MAX", ["monthly"])

    with pytest.raises(ProblemError) as raised:
        validate_request(DAILY_HIGH_MEAN, catalog)

    assert raised.value.detail == "the store of the metric does not hold the variable"
