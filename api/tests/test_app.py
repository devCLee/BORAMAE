import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from boramae.main import create_app

DEV_ORIGIN = "http://localhost:3000"
STUB_PATHS = [
    ("POST", "/api/v1/parse"),
    ("GET", "/api/v1/trend"),
    ("GET", "/api/v1/caseboard"),
    ("GET", "/api/v1/scan"),
]


@pytest.fixture
def dev_client(monkeypatch):
    monkeypatch.setenv("BORAMAE_DEV_CORS_ORIGIN", DEV_ORIGIN)
    return TestClient(create_app())


@pytest.mark.parametrize(("method", "path"), STUB_PATHS)
def test_stub_path_answers_501(client, method, path):
    assert client.request(method, path).status_code == 501


@pytest.mark.parametrize(("method", "path"), STUB_PATHS)
def test_stub_path_sends_the_not_built_problem(client, method, path):
    assert client.request(method, path).json()["code"] == "not_built"


@pytest.mark.parametrize(("method", "path"), STUB_PATHS)
def test_stub_path_uses_the_problem_media_type(client, method, path):
    response = client.request(method, path)
    assert response.headers["content-type"] == "application/problem+json"


def test_agent_socket_sends_a_not_built_error(client):
    with client.websocket_connect("/api/v1/agent") as socket:
        assert socket.receive_json() == {"type": "error", "code": "not_built"}


def test_agent_socket_closes_after_the_error(client):
    with client.websocket_connect("/api/v1/agent") as socket:
        socket.receive_json()
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_cors_headers_are_absent_without_a_dev_origin(monkeypatch):
    monkeypatch.delenv("BORAMAE_DEV_CORS_ORIGIN", raising=False)
    response = TestClient(create_app()).get("/health", headers={"Origin": DEV_ORIGIN})
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_the_dev_origin(dev_client):
    response = dev_client.get("/health", headers={"Origin": DEV_ORIGIN})
    assert response.headers["access-control-allow-origin"] == DEV_ORIGIN


def test_cors_exposes_the_request_fact_headers(dev_client):
    response = dev_client.get("/health", headers={"Origin": DEV_ORIGIN})
    exposed = response.headers["access-control-expose-headers"].split(", ")
    assert set(exposed) == {
        "X-Request-Id",
        "X-Result-Key",
        "X-Cache",
        "X-Bytes-Fetched",
        "Server-Timing",
        "X-Containing-Cell",
    }


def test_cors_preflight_allows_the_parse_post(dev_client):
    response = dev_client.options(
        "/api/v1/parse",
        headers={
            "Origin": DEV_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
