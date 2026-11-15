import pytest

from tests.fakes import DictStore, make_client

KEY = "0123456789abcdef0123456789abcdef"
BODY = b'{"stored":"as it is","value":1.5}'
STORED_URL = f"/r/trend/{KEY}.json"


@pytest.fixture
def stored_client():
    store = DictStore()
    store.files[f"r/trend/{KEY}.json"] = BODY
    return make_client(store=store)


def test_stored_result_returns_200(stored_client):
    assert stored_client.get(STORED_URL).status_code == 200


def test_stored_result_returns_the_stored_bytes(stored_client):
    assert stored_client.get(STORED_URL).content == BODY


def test_stored_result_is_json(stored_client):
    assert stored_client.get(STORED_URL).headers["content-type"] == "application/json"


def test_stored_result_has_an_immutable_cache_header(stored_client):
    cache_control = stored_client.get(STORED_URL).headers["cache-control"]
    assert cache_control == "public, max-age=31536000, immutable"


def test_stored_result_names_its_key(stored_client):
    assert stored_client.get(STORED_URL).headers["x-result-key"] == KEY


def test_stored_result_reports_a_hit(stored_client):
    assert stored_client.get(STORED_URL).headers["x-cache"] == "hit"


def test_stored_body_is_served_with_no_validation_step():
    store = DictStore()
    store.files[f"r/scan/{KEY}.json"] = b"not a scan record"
    assert make_client(store=store).get(f"/r/scan/{KEY}.json").status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        f"/r/grid/{KEY}.json",
        f"/r/TREND/{KEY}.json",
        f"/r/meta/{KEY}.json",
        "/r/trend/0123456789ABCDEF0123456789ABCDEF.json",
        "/r/trend/0123456789abcdef.json",
        f"/r/trend/{KEY}0.json",
        "/r/trend/..%2F..%2Fmeta%2Fcatalog.json",
    ],
)
def test_bad_kind_or_key_shape_returns_404(stored_client, url):
    assert stored_client.get(url).status_code == 404


@pytest.mark.parametrize("url", [f"/r/grid/{KEY}.json", f"/r/caseboard/{KEY}.json"])
def test_unanswered_result_sends_a_problem_body(stored_client, url):
    response = stored_client.get(url)
    assert response.headers["content-type"] == "application/problem+json"


def test_missing_result_returns_404(stored_client):
    assert stored_client.get(f"/r/caseboard/{KEY}.json").status_code == 404
