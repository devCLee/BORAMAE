"""GET /api/v1/caseboard?s=: the case board path, its headers and its errors."""

import re

import pytest

from boramae.contracts.results_board import CaseBoard
from boramae.contracts.spec import RequestSpec, encode_request_spec
from boramae.store.results import result_path
from tests.fakes import DictStore, FakeReader, make_client

CASEBOARD_PATH = "/api/v1/caseboard"
# The first snow of Seoul: a board focus in content/boards.json.
SPEC = {
    "v": 1,
    "kind": "caseboard",
    "var": "PRECSNO",
    "metric": {"id": "first_date"},
    "area": {"lat": 37.5665, "lon": 126.978, "radius_km": 25},
    "window": {"start": 1981, "end": "latest"},
}
# Midway between cell centers: the nearest one is 27.8 km away, outside 10 km.
OFF_CENTER = {"lat": 37.25, "lon": 127.1875, "radius_km": 10}


def url(**changes):
    spec = RequestSpec.model_validate(SPEC | changes)
    return f"{CASEBOARD_PATH}?s={encode_request_spec(spec)}"


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


def test_should_answer_a_case_board(first):
    assert CaseBoard.model_validate_json(first.content).spec.kind == "caseboard"


def test_should_store_the_board_under_its_key(first, store):
    assert result_path("caseboard", first.headers["x-result-key"]) in store.files


def test_should_report_a_miss_for_a_new_board(first):
    assert first.headers["x-cache"] == "miss"


def test_should_report_the_bytes_fetched_by_a_miss(first):
    assert int(first.headers["x-bytes-fetched"]) > 0


@pytest.mark.parametrize("step", ["leaves", "total"])
def test_should_time_each_step(first, step):
    assert re.search(rf"\b{step};dur=", first.headers["server-timing"])


def test_should_report_a_hit_for_a_stored_board(two_answers):
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
        {"window": {"start": 2020, "end": 2010}},
        {"kind": "trend"},
    ],
)
def test_should_answer_an_invalid_spec_with_400(client, changes):
    assert client.get(url(**changes)).status_code == 400


@pytest.mark.parametrize(
    "changes",
    [
        {"area": {"lat": 37.5665, "lon": 126.978, "radius_km": 400}},
        {"var": "PM25"},
        {"kind": "scan"},
    ],
)
def test_should_not_read_power_for_an_invalid_spec(client, reader, changes):
    client.get(url(**changes))
    assert reader.read_count == 0


@pytest.mark.parametrize("query", ["", "?s=", "?s=not-a-spec"])
def test_should_answer_a_bad_s_with_400(client, query):
    assert client.get(f"{CASEBOARD_PATH}{query}").status_code == 400


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


def test_should_flag_a_containing_cell(client):
    answer = client.get(url(area=OFF_CENTER))
    assert answer.headers["x-containing-cell"] == "true"
