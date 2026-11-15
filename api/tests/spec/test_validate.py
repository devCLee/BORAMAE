"""Validation of a request spec: the HTTP 400 rules and the derived cells."""

import base64
import json
from pathlib import Path

import pytest

from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import RequestSpec
from boramae.errors import ProblemError
from boramae.spec.validate import decode_s, validate_request

REPO = Path(__file__).resolve().parents[3]
GOLDEN_VECTORS = json.loads(
    (REPO / "content/golden/request-spec.json").read_text(encoding="utf-8")
)
BASE_SPEC = {
    "v": 1,
    "kind": "trend",
    "var": "T2M",
    "metric": {"id": "annual_mean"},
    "area": {"lat": 37.5665, "lon": 126.978, "radius_km": 25},
    "window": {"start": 1981, "end": "latest"},
}
# The view of golden vector 7: 144 cell centers, over the cap at its latitude.
KOREA_VIEW = {"west": 124.5, "south": 33, "east": 131.875, "north": 38.75}
SMALL_VIEW = {"west": 126.5, "south": 37.2, "east": 127.6, "north": 38.1}
INVALID_SPEC = (400, "invalid_spec")


def make_spec(**changes):
    return RequestSpec.model_validate(BASE_SPEC | changes)


def circle(radius_km, lat=37.5665, lon=126.978):
    return {"lat": lat, "lon": lon, "radius_km": radius_km}


def encode(text):
    return base64.urlsafe_b64encode(text.encode("utf-8")).rstrip(b"=").decode("ascii")


def with_metric_defaults(catalog, metric_id, **defaults):
    data = catalog.model_dump()
    for metric in data["metrics"]:
        if metric["id"] == metric_id:
            metric["defaults"].update(defaults)
    return Catalog.model_validate(data)


def with_variable_stores(catalog, var, stores):
    data = catalog.model_dump()
    for variable in data["variables"]:
        if variable["id"] == var:
            variable["stores"] = stores
    return Catalog.model_validate(data)


def problem_of(spec, catalog):
    with pytest.raises(ProblemError) as raised:
        validate_request(spec, catalog)
    return raised.value.status, raised.value.code


def decode_problem_of(s):
    with pytest.raises(ProblemError) as raised:
        decode_s(s)
    return raised.value.status, raised.value.code


def test_seoul_at_25_km_gives_the_one_cell_of_the_contract(sample_catalog):
    assert validate_request(make_spec(), sample_catalog).cells == ((255, 491),)


def test_circle_that_holds_a_cell_center_sets_no_flag(sample_catalog):
    validated = validate_request(make_spec(), sample_catalog)
    assert validated.used_containing_cell is False


def test_circle_with_no_cell_center_gives_the_containing_cell(sample_catalog):
    spec = make_spec(area=circle(10, lat=37.7, lon=127.2))
    assert validate_request(spec, sample_catalog).cells == ((255, 492),)


def test_circle_with_no_cell_center_sets_the_flag(sample_catalog):
    spec = make_spec(area=circle(10, lat=37.7, lon=127.2))
    assert validate_request(spec, sample_catalog).used_containing_cell is True


@pytest.mark.parametrize("radius_km", [9, 9.99, 300.01, 400])
def test_radius_outside_10_to_300_km_is_invalid(sample_catalog, radius_km):
    spec = make_spec(area=circle(radius_km))
    assert problem_of(spec, sample_catalog) == INVALID_SPEC


@pytest.mark.parametrize("radius_km", [10, 300])
def test_radius_at_a_bound_is_valid(sample_catalog, radius_km):
    spec = make_spec(area=circle(radius_km))
    assert validate_request(spec, sample_catalog).spec == spec


def test_unknown_variable_id_is_invalid(sample_catalog):
    assert problem_of(make_spec(var="T2M_MEAN"), sample_catalog) == INVALID_SPEC


def test_unknown_metric_id_is_invalid(sample_catalog):
    spec = make_spec(metric={"id": "annual_median"})
    assert problem_of(spec, sample_catalog) == INVALID_SPEC


def test_metric_with_no_reducer_yet_is_invalid(sample_catalog):
    spec = make_spec(metric={"id": "last_date"})
    assert problem_of(spec, sample_catalog) == INVALID_SPEC


def test_variable_absent_from_the_store_of_the_metric_is_invalid(sample_catalog):
    catalog = with_variable_stores(sample_catalog, "T2M", ["daily"])
    assert problem_of(make_spec(), catalog) == INVALID_SPEC


def test_threshold_metric_with_no_threshold_and_no_default_is_invalid(sample_catalog):
    catalog = with_metric_defaults(sample_catalog, "threshold_days", threshold=None)
    spec = make_spec(var="T2M_MAX", metric={"id": "threshold_days"})
    assert problem_of(spec, catalog) == INVALID_SPEC


def test_threshold_of_the_request_stands_in_for_a_missing_default(sample_catalog):
    catalog = with_metric_defaults(sample_catalog, "threshold_days", threshold=None)
    spec = make_spec(var="T2M_MAX", metric={"id": "threshold_days", "threshold": "33"})
    assert validate_request(spec, catalog).spec == spec


def test_validated_request_carries_the_catalog_variable(sample_catalog):
    assert validate_request(make_spec(), sample_catalog).variable.id == "T2M"


def test_validated_request_carries_the_catalog_metric(sample_catalog):
    validated = validate_request(make_spec(), sample_catalog)
    assert validated.metric.source_freq == "monthly"


def test_reversed_window_is_invalid(sample_catalog):
    spec = make_spec(window={"start": 2020, "end": 2010})
    assert problem_of(spec, sample_catalog) == INVALID_SPEC


@pytest.mark.parametrize(
    ("start", "end"),
    [(1970, 2000), (1980, "latest"), (1981, 2027), (1981, 2030), (2027, "latest")],
)
def test_window_outside_the_coverage_is_invalid(sample_catalog, start, end):
    spec = make_spec(window={"start": start, "end": end})
    assert problem_of(spec, sample_catalog) == INVALID_SPEC


@pytest.mark.parametrize(
    ("start", "end"), [(1981, 2026), (2000, 2000), (2026, "latest")]
)
def test_window_inside_the_coverage_is_valid(sample_catalog, start, end):
    spec = make_spec(window={"start": start, "end": end})
    assert validate_request(spec, sample_catalog).spec == spec


def test_bbox_over_the_cap_is_too_large(sample_catalog):
    spec = make_spec(area=KOREA_VIEW)
    assert problem_of(spec, sample_catalog) == (400, "area_too_large")


def test_bbox_under_the_cap_gives_the_cells_whose_centers_lie_inside(sample_catalog):
    spec = make_spec(area=SMALL_VIEW)
    assert validate_request(spec, sample_catalog).cells == (
        (255, 491),
        (255, 492),
        (256, 491),
        (256, 492),
    )


def test_bbox_with_south_above_north_is_invalid(sample_catalog):
    spec = make_spec(area=SMALL_VIEW | {"south": 38.1, "north": 37.2})
    assert problem_of(spec, sample_catalog) == INVALID_SPEC


@pytest.mark.parametrize(
    "s",
    [
        "",
        "!!!",
        "a",
        "\u00e9",
        encode("not json"),
        encode('{"v":1}'),
        encode(json.dumps(BASE_SPEC | {"cells": [[255, 491]]})),
        encode(json.dumps(BASE_SPEC | {"kind": "compare"})),
        encode(json.dumps(BASE_SPEC | {"area": circle(25, lat=91)})),
    ],
    ids=[
        "empty",
        "not base64url",
        "bad length",
        "not ASCII",
        "not JSON",
        "missing fields",
        "unknown field",
        "unknown kind",
        "latitude out of range",
    ],
)
def test_malformed_s_is_invalid(s):
    assert decode_problem_of(s) == INVALID_SPEC


@pytest.mark.parametrize("vector", GOLDEN_VECTORS)
def test_decode_s_reproduces_the_golden_vector(vector):
    assert decode_s(vector["s"]) == RequestSpec.model_validate(vector["spec"])
