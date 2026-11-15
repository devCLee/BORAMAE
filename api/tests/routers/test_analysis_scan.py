"""GET /api/v1/scan?s=: the no-trend fallback path, its headers and its errors."""

import pytest

from boramae.contracts.results_scan import ScanResult
from boramae.contracts.spec import RequestSpec, encode_request_spec
from boramae.store.results import result_path
from tests.fakes import DictStore, FakeReader, make_client

SCAN_PATH = "/api/v1/scan"
SPEC = {
    "v": 1,
    "kind": "scan",
    "var": "PRECTOTCORR",
    "metric": {"id": "rx1day"},
    "area": {"lat": 37.5665, "lon": 126.978, "radius_km": 25},
    "window": {"start": 1981, "end": "latest"},
}


def url(**changes):
    spec = RequestSpec.model_validate(SPEC | changes)
    return f"{SCAN_PATH}?s={encode_request_spec(spec)}"


def scan_files(store):
    return [path for path in store.files if path.startswith("r/scan/")]


@pytest.fixture
def store():
    return DictStore()


@pytest.fixture
def client(store, sample_catalog):
    return make_client(reader=FakeReader(), store=store, catalog=sample_catalog)


@pytest.fixture
def first(client):
    return client.get(url())


@pytest.fixture
def two_answers(client):
    return [client.get(url()), client.get(url())]


def test_should_answer_a_valid_scan_spec_with_200(first):
    assert first.status_code == 200


def test_should_answer_json(first):
    assert first.headers["content-type"] == "application/json"


def test_should_answer_a_scan_result(first):
    assert ScanResult.model_validate_json(first.content).spec.kind == "scan"


def test_should_store_the_scan_under_its_key(first, store):
    assert result_path("scan", first.headers["x-result-key"]) in store.files


def test_should_report_a_miss_for_a_new_scan(first):
    assert first.headers["x-cache"] == "miss"


def test_should_report_the_bytes_fetched_by_the_leaves(first):
    assert int(first.headers["x-bytes-fetched"]) > 0


def test_should_time_the_leaves(first):
    assert "leaves;dur=" in first.headers["server-timing"]


def test_should_report_a_hit_for_a_stored_scan(two_answers):
    assert two_answers[1].headers["x-cache"] == "hit"


def test_should_answer_a_hit_with_equal_bytes(two_answers):
    assert two_answers[1].content == two_answers[0].content


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "trend"},
        {"var": "PM25"},
        {"area": {"lat": 37.5665, "lon": 126.978, "radius_km": 400}},
    ],
)
def test_should_answer_an_invalid_spec_with_400(client, changes):
    assert client.get(url(**changes)).status_code == 400


@pytest.mark.parametrize("query", ["", "?s=", "?s=not-a-spec"])
def test_should_answer_a_bad_s_with_400(client, query):
    assert client.get(f"{SCAN_PATH}{query}").status_code == 400


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


def test_should_store_no_scan_after_a_power_failure(failing, store):
    assert scan_files(store) == []
