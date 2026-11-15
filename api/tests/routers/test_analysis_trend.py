"""GET /api/v1/trend?s=: the trend path, its headers and its errors."""

import json
import re

import numpy as np
import pytest

from boramae.contracts.results import TrendResult
from boramae.contracts.spec import RequestSpec, encode_request_spec
from boramae.store.results import result_path
from tests.fakes import AXES, STORED_STEP_BYTES, DictStore, FakeReader, make_client

TREND_PATH = "/api/v1/trend"
SPEC = {
    "v": 1,
    "kind": "trend",
    "var": "T2M",
    "metric": {"id": "annual_mean"},
    "area": {"lat": 37.5665, "lon": 126.978, "radius_km": 25},
    "window": {"start": 1981, "end": "latest"},
}
# Midway between cell centers: the nearest one is 27.8 km away, outside 10 km.
OFF_CENTER = {"lat": 37.25, "lon": 127.1875, "radius_km": 10}
# 2007 to 2025: 19 complete years before the pinned month 2026-09.
NINETEEN_YEARS = {"start": 2007, "end": "latest"}
ONE_CELL_BYTES = AXES["monthly"].size * STORED_STEP_BYTES


def url(**changes):
    spec = RequestSpec.model_validate(SPEC | changes)
    return f"{TREND_PATH}?s={encode_request_spec(spec)}"


@pytest.fixture
def reader():
    return FakeReader()


@pytest.fixture
def store():
    return DictStore()


@pytest.fixture
def client(reader, store, sample_catalog):
    return make_client(reader=reader, store=store, catalog=sample_catalog)


@pytest.fixture
def first(client):
    return client.get(url())


@pytest.fixture
def two_answers(client):
    return [client.get(url()), client.get(url())]


def test_should_answer_a_valid_spec_with_200(first):
    assert first.status_code == 200


def test_should_answer_json(first):
    assert first.headers["content-type"] == "application/json"


def test_should_store_the_result_under_its_key(first, store):
    assert result_path("trend", first.headers["x-result-key"]) in store.files


def test_should_report_a_miss_for_a_new_result(first):
    assert first.headers["x-cache"] == "miss"


def test_should_report_the_bytes_fetched(first):
    assert first.headers["x-bytes-fetched"] == str(ONE_CELL_BYTES)


@pytest.mark.parametrize("step", ["read", "stats", "total"])
def test_should_time_each_step(first, step):
    assert re.search(rf"\b{step};dur=", first.headers["server-timing"])


def test_should_answer_a_trend_result(first):
    assert TrendResult.model_validate_json(first.content).spec.kind == "trend"


def test_should_report_a_hit_for_a_stored_result(two_answers):
    assert two_answers[1].headers["x-cache"] == "hit"


def test_should_answer_a_hit_with_equal_bytes(two_answers):
    assert two_answers[1].content == two_answers[0].content


def test_should_report_no_fetched_bytes_for_a_hit(two_answers):
    assert two_answers[1].headers["x-bytes-fetched"] == "0"


@pytest.mark.parametrize(
    "changes",
    [
        {"area": {"lat": 37.5665, "lon": 126.978, "radius_km": 400}},
        {"var": "PM25"},
        {"metric": {"id": "no_such_metric"}},
        {"window": {"start": 2020, "end": 2010}},
        {"kind": "caseboard"},
    ],
)
def test_should_answer_an_invalid_spec_with_400(client, changes):
    assert client.get(url(**changes)).status_code == 400


@pytest.mark.parametrize(
    "changes",
    [
        {"area": {"lat": 37.5665, "lon": 126.978, "radius_km": 400}},
        {"var": "PM25"},
        {"window": {"start": 2020, "end": 2010}},
        {"kind": "scan"},
    ],
)
def test_should_not_read_power_for_an_invalid_spec(client, reader, changes):
    client.get(url(**changes))
    assert reader.read_count == 0


@pytest.mark.parametrize("query", ["", "?s=", "?s=not-a-spec"])
def test_should_answer_a_bad_s_with_400(client, query):
    assert client.get(f"{TREND_PATH}{query}").status_code == 400


def test_should_answer_a_19_year_window_with_200(client):
    assert client.get(url(window=NINETEEN_YEARS)).status_code == 200


def test_should_withhold_the_verdict_of_a_19_year_window(client):
    body = client.get(url(window=NINETEEN_YEARS)).json()
    assert body["verdict"] is None


def test_should_label_a_19_year_window_too_short(client):
    body = client.get(url(window=NINETEEN_YEARS)).json()
    assert body["reason"] == "record_too_short"


def test_should_answer_an_all_missing_series_with_200(sample_catalog):
    reader = FakeReader(
        values_fn=lambda var, freq, times, cell: np.full(times.size, np.nan)
    )
    client = make_client(reader=reader, catalog=sample_catalog)
    assert client.get(url()).status_code == 200


@pytest.fixture
def failing(store, sample_catalog):
    client = make_client(
        reader=FakeReader(fail=True), store=store, catalog=sample_catalog
    )
    return client.get(url())


def test_should_answer_a_power_failure_with_503(failing):
    assert failing.status_code == 503


def test_should_ask_for_a_retry_after_a_power_failure(failing):
    assert int(failing.headers["retry-after"]) > 0


def test_should_store_nothing_after_a_power_failure(failing, store):
    assert store.files == {}


def test_should_store_only_the_fields_of_a_trend_result(first, store):
    stored = store.files[result_path("trend", first.headers["x-result-key"])]
    assert set(json.loads(stored)) == set(TrendResult.model_fields)


def test_should_flag_a_containing_cell(client):
    answer = client.get(url(area=OFF_CENTER))
    assert answer.headers["x-containing-cell"] == "true"


def test_should_not_flag_an_area_with_a_cell_center(first):
    assert "x-containing-cell" not in first.headers


@pytest.fixture
def logged(client, capsys):
    answers = [client.get(url()), client.get(url())]
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    return answers, [line for line in lines if line["path"] == TREND_PATH]


@pytest.mark.parametrize("index", [0, 1], ids=["miss", "hit"])
@pytest.mark.parametrize(
    ("field", "header"),
    [
        ("request_id", "x-request-id"),
        ("cache", "x-cache"),
        ("bytes_fetched", "x-bytes-fetched"),
    ],
)
def test_should_log_the_facts_of_the_headers(logged, index, field, header):
    answers, lines = logged
    assert str(lines[index][field]) == answers[index].headers[header]
