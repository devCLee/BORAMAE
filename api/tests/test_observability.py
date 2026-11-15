import json
import re

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from boramae.main import create_app

RESULT_KEY = "0123456789abcdef0123456789abcdef"
LOG_FIELDS = {
    "request_id",
    "path",
    "status",
    "kind",
    "result_key",
    "cache",
    "bytes_fetched",
    "timings",
}


@pytest.fixture
def probe_client():
    app = create_app()

    @app.get("/probe")
    def probe(request: Request) -> dict[str, str]:
        request.state.kind = "trend"
        request.state.result_key = RESULT_KEY
        request.state.cache = "miss"
        request.state.bytes_fetched = 4096
        request.state.timings = {"read": 12.5}
        request.state.used_containing_cell = True
        return {"status": "ok"}

    return TestClient(app)


def _last_log_line(capsys) -> str:
    return capsys.readouterr().out.strip().splitlines()[-1]


def test_log_line_holds_only_allowlisted_keys(probe_client, capsys):
    probe_client.get("/probe?text=first-snow-in-seoul")
    assert set(json.loads(_last_log_line(capsys))) == LOG_FIELDS


def test_log_line_path_has_no_query_string(probe_client, capsys):
    probe_client.get("/probe?text=first-snow-in-seoul")
    assert json.loads(_last_log_line(capsys))["path"] == "/probe"


def test_log_line_holds_no_query_text(probe_client, capsys):
    probe_client.get("/probe?text=first-snow-in-seoul")
    assert "first-snow-in-seoul" not in _last_log_line(capsys)


def test_log_line_holds_no_client_address(probe_client, capsys):
    probe_client.get("/probe")
    assert "testclient" not in _last_log_line(capsys)


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("status", 200),
        ("kind", "trend"),
        ("result_key", RESULT_KEY),
        ("cache", "miss"),
        ("bytes_fetched", 4096),
    ],
)
def test_log_line_copies_the_request_fact(probe_client, capsys, field, expected):
    probe_client.get("/probe")
    assert json.loads(_last_log_line(capsys))[field] == expected


def test_log_line_keeps_the_router_timing(probe_client, capsys):
    probe_client.get("/probe")
    assert json.loads(_last_log_line(capsys))["timings"]["read"] == 12.5


def test_log_line_request_id_equals_the_header(probe_client, capsys):
    response = probe_client.get("/probe")
    line = json.loads(_last_log_line(capsys))
    assert line["request_id"] == response.headers["x-request-id"]


def test_response_carries_a_request_id(probe_client):
    response = probe_client.get("/health")
    assert re.fullmatch("[0-9a-f]{32}", response.headers["x-request-id"])


def test_each_response_gets_its_own_request_id(probe_client):
    first = probe_client.get("/health").headers["x-request-id"]
    assert probe_client.get("/health").headers["x-request-id"] != first


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("x-result-key", RESULT_KEY),
        ("x-cache", "miss"),
        ("x-bytes-fetched", "4096"),
        ("x-containing-cell", "true"),
    ],
)
def test_response_header_copies_the_request_fact(probe_client, header, expected):
    assert probe_client.get("/probe").headers[header] == expected


def test_server_timing_holds_the_router_timing(probe_client):
    header = probe_client.get("/probe").headers["server-timing"]
    assert "read;dur=12.5" in header.split(", ")


def test_server_timing_holds_the_total(probe_client):
    header = probe_client.get("/probe").headers["server-timing"]
    assert re.search(r"(^|, )total;dur=\d+(\.\d+)?($|, )", header)


def test_unhandled_error_answer_carries_the_logged_request_id(capsys):
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    logged = json.loads(_last_log_line(capsys))["request_id"]
    assert response.headers.get("x-request-id") == logged


def test_response_without_facts_has_no_result_key_header(probe_client):
    assert "x-result-key" not in probe_client.get("/health").headers


def test_response_without_containing_cell_has_no_flag_header(probe_client):
    assert "x-containing-cell" not in probe_client.get("/health").headers
