"""The trend service: a request spec becomes a stored, tested trend (TDD.md Flow B)."""

import json
import math

import numpy as np
import pytest

from boramae import deps
from boramae.contracts.results import TrendResult
from boramae.contracts.spec import (
    Bbox,
    Circle,
    RequestSpec,
    RequestWindow,
    SpecMetric,
)
from boramae.errors import ProblemError
from boramae.power.reader import STORE_URL
from boramae.services.trend import compute_trend, get_trend
from boramae.spec.canonical import canonicalize
from boramae.spec.validate import validate_request
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService
from tests.fakes import AXES, STORED_STEP_BYTES, DictStore, FakeReader

SEOUL = Circle(lat=37.5665, lon=126.978, radius_km=25)
# Two cell centers, [254, 491] at 37.0 N and [255, 491] at 37.5 N, both at 126.875 E.
TWO_CELL_BOX = Bbox(west=126.8, south=36.9, east=126.9, north=37.6)
CELL_VALUES = {(254, 491): 10.0, (255, 491): 20.0}


def make_spec(var="T2M", metric_id="annual_mean", area=SEOUL, kind="trend", **metric):
    return RequestSpec(
        v=1,
        kind=kind,
        var=var,
        metric=SpecMetric(id=metric_id, **metric),
        area=area,
        window=RequestWindow(start=1981, end="latest"),
    )


def constant_reader(value):
    return FakeReader(
        values_fn=lambda var, freq, times, cell: np.full(times.size, value)
    )


def run(spec, catalog, reader=None, pool=None, bounded=True):
    results = ResultService(DictStore(), pool or WorkerPool(4, 1.0))
    return get_trend(
        spec,
        reader=reader or FakeReader(),
        results=results,
        catalog=catalog,
        bounded=bounded,
    )


def run_result(spec, catalog, reader=None):
    return TrendResult.model_validate_json(run(spec, catalog, reader)[0])


def canonical_on(dataset, catalog, spec=None):
    validated = validate_request(spec or make_spec(), catalog)
    ds = getattr(catalog.datasets, dataset).ds
    return canonicalize(validated, catalog).model_copy(update={"ds": ds})


def refuse_constant(name):
    raise ValueError(f"not strict JSON: {name}")


def test_should_give_two_cells_their_cos_weighted_mean(sample_catalog):
    reader = FakeReader(
        values_fn=lambda var, freq, times, cell: np.full(times.size, CELL_VALUES[cell])
    )
    w_low, w_high = math.cos(math.radians(37.0)), math.cos(math.radians(37.5))
    expected = (10.0 * w_low + 20.0 * w_high) / (w_low + w_high)
    result = run_result(make_spec(area=TWO_CELL_BOX), sample_catalog, reader)
    assert result.series.monthly.values[0] == pytest.approx(expected, rel=1e-12)


def test_should_give_an_all_missing_series_the_reason_no_data(sample_catalog):
    result = run_result(make_spec(), sample_catalog, constant_reader(np.nan))
    assert result.reason == "no_data"


def test_should_give_an_all_missing_series_no_verdict(sample_catalog):
    result = run_result(make_spec(), sample_catalog, constant_reader(np.nan))
    assert result.verdict is None


def test_should_answer_an_all_missing_series_in_strict_json(sample_catalog):
    body = run(make_spec(), sample_catalog, constant_reader(np.nan))[0]
    assert isinstance(json.loads(body, parse_constant=refuse_constant), dict)


@pytest.mark.parametrize(
    ("var", "metric_id", "threshold", "rate_unit"),
    [
        ("GWETTOP", "annual_mean", None, "percent_points"),
        ("RH2M", "threshold_days", "80", "days"),
        ("T2M", "annual_mean", None, "C"),
        ("PRECTOTCORR", "annual_total", None, "mm"),
    ],
)
def test_should_name_the_rate_unit_of_the_yearly_value(
    sample_catalog, var, metric_id, threshold, rate_unit
):
    spec = make_spec(var=var, metric_id=metric_id, threshold=threshold)
    assert run_result(spec, sample_catalog).rate_unit == rate_unit


# 0 mm every day leaves every season year with no snow day: 100% censored.
@pytest.mark.parametrize(
    ("daily_snow", "metric_used"), [(0.0, "event_days"), (1.0, "date")]
)
def test_should_switch_a_censored_first_date_to_event_days(
    sample_catalog, daily_snow, metric_used
):
    spec = make_spec(var="PRECSNO", metric_id="first_date")
    result = run_result(spec, sample_catalog, constant_reader(daily_snow))
    assert result.metric_used == metric_used


@pytest.mark.parametrize(
    ("daily_snow", "unit"), [(0.0, "days"), (1.0, "day of season")]
)
def test_should_name_the_unit_of_a_first_date_series(sample_catalog, daily_snow, unit):
    spec = make_spec(var="PRECSNO", metric_id="first_date")
    assert run_result(spec, sample_catalog, constant_reader(daily_snow)).unit == unit


def test_should_count_the_fetched_bytes_of_a_miss(sample_catalog):
    facts = run(make_spec(), sample_catalog)[3]
    assert facts.bytes_fetched == AXES["monthly"].size * STORED_STEP_BYTES


def test_should_count_no_fetched_bytes_for_a_hit(sample_catalog):
    results = ResultService(DictStore(), WorkerPool(4, 1.0))
    reader = FakeReader()
    get_trend(make_spec(), reader=reader, results=results, catalog=sample_catalog)
    facts = get_trend(
        make_spec(), reader=reader, results=results, catalog=sample_catalog
    )[3]
    assert facts.bytes_fetched == 0


@pytest.mark.parametrize("kind", ["caseboard", "scan"])
def test_should_refuse_a_spec_of_another_kind(sample_catalog, kind):
    with pytest.raises(ProblemError) as raised:
        run(make_spec(kind=kind), sample_catalog)
    assert raised.value.status == 400


def test_should_compute_an_unbounded_leaf_without_a_pool_slot(sample_catalog):
    no_slot = WorkerPool(0, 0.0)
    assert run(make_spec(), sample_catalog, pool=no_slot, bounded=False)[2] == "miss"


def test_should_answer_503_when_a_bounded_request_finds_no_slot(sample_catalog):
    with pytest.raises(ProblemError) as raised:
        run(make_spec(), sample_catalog, pool=WorkerPool(0, 0.0))
    assert raised.value.status == 503


def test_should_name_a_power_failure_power_unavailable(sample_catalog):
    with pytest.raises(ProblemError) as raised:
        run(make_spec(), sample_catalog, FakeReader(fail=True))
    assert raised.value.code == "power_unavailable"


def test_should_ask_for_a_retry_after_a_power_failure(sample_catalog):
    with pytest.raises(ProblemError) as raised:
        run(make_spec(), sample_catalog, FakeReader(fail=True))
    assert "Retry-After" in raised.value.headers


@pytest.mark.parametrize("dataset", ["daily", "monthly"])
def test_should_read_the_store_that_the_canonical_ds_names(sample_catalog, dataset):
    canonical = canonical_on(dataset, sample_catalog)
    result = compute_trend(canonical, sample_catalog, FakeReader())
    assert result.provenance.access_path == STORE_URL.format(freq=dataset)


@pytest.mark.parametrize(
    ("dataset", "has_monthly"), [("daily", False), ("monthly", True)]
)
def test_should_hold_the_monthly_form_only_for_a_monthly_source(
    sample_catalog, dataset, has_monthly
):
    canonical = canonical_on(dataset, sample_catalog)
    result = compute_trend(canonical, sample_catalog, FakeReader())
    assert (result.series.monthly is not None) == has_monthly


@pytest.mark.parametrize(
    ("dataset", "day_basis"), [("daily", "UTC"), ("monthly", None)]
)
def test_should_name_the_utc_day_basis_of_a_daily_source(
    sample_catalog, dataset, day_basis
):
    canonical = canonical_on(dataset, sample_catalog)
    result = compute_trend(canonical, sample_catalog, FakeReader())
    assert result.provenance.day_basis == day_basis


@pytest.mark.parametrize("field", ["dataset_id", "dataset_version"])
def test_should_take_the_dataset_of_the_provenance_from_the_catalog(
    sample_catalog, field
):
    canonical = canonical_on("daily", sample_catalog)
    result = compute_trend(canonical, sample_catalog, FakeReader())
    expected = getattr(sample_catalog.datasets.daily, field)
    assert getattr(result.provenance, field) == expected


def test_should_take_the_compute_location_from_the_settings(
    sample_catalog, monkeypatch
):
    monkeypatch.setenv("BORAMAE_COMPUTE_LOCATION", "us-west-2")
    assert run_result(make_spec(), sample_catalog).provenance.compute_location == (
        "us-west-2"
    )


def test_should_name_the_method_text_key(sample_catalog):
    result = run_result(make_spec(), sample_catalog)
    assert result.provenance.method == "sen_mk_hamed_rao_lag1"


def test_should_give_the_period_of_the_window(sample_catalog):
    period = run_result(make_spec(), sample_catalog).provenance.period
    assert (period.start, period.end) == ("1981-01", "2026-09")


def test_should_name_the_cells_used(sample_catalog):
    assert run_result(make_spec(), sample_catalog).provenance.cells == [[255, 491]]


def test_should_give_rates_per_decade(sample_catalog):
    stats = run_result(make_spec(), sample_catalog).stats
    assert stats.rates.sen == pytest.approx(stats.sen.slope * 10)


def test_should_take_the_minimum_record_of_the_variable(sample_catalog):
    result = run_result(make_spec(), sample_catalog)
    assert result.method.min_record_years == 20


@pytest.fixture
def fresh_pool():
    deps.get_pool.cache_clear()
    yield
    deps.get_pool.cache_clear()


def test_should_give_the_pool_the_request_timeout(fresh_pool, monkeypatch):
    monkeypatch.setenv("BORAMAE_REQUEST_TIMEOUT_S", "7")
    assert deps.get_pool().request_timeout_s == 7.0
