import pytest

from tests.fakes import DictStore, make_client

CATALOG_BODY = b'{"catalog":"stored bytes"}'


@pytest.fixture
def catalog_client():
    store = DictStore()
    store.put("meta/catalog.json", CATALOG_BODY)
    return make_client(store=store)


def test_stored_catalog_returns_200(catalog_client):
    assert catalog_client.get("/meta/catalog.json").status_code == 200


def test_stored_catalog_returns_the_stored_bytes(catalog_client):
    assert catalog_client.get("/meta/catalog.json").content == CATALOG_BODY


def test_stored_catalog_is_json(catalog_client):
    response = catalog_client.get("/meta/catalog.json")
    assert response.headers["content-type"] == "application/json"


def test_stored_catalog_has_a_five_minute_cache_header(catalog_client):
    cache_control = catalog_client.get("/meta/catalog.json").headers["cache-control"]
    assert "max-age=300" in cache_control.split(", ")


def test_missing_catalog_returns_503(client):
    assert client.get("/meta/catalog.json").status_code == 503


def test_missing_catalog_sends_retry_after(client):
    assert int(client.get("/meta/catalog.json").headers["retry-after"]) > 0


def test_missing_catalog_sends_a_problem_body(client):
    response = client.get("/meta/catalog.json")
    assert response.headers["content-type"] == "application/problem+json"
