import pytest
from fastapi.testclient import TestClient

from boramae.errors import ProblemError
from boramae.main import create_app


@pytest.fixture
def response():
    app = create_app()

    @app.get("/raise-problem")
    def raise_problem():
        raise ProblemError(
            503,
            "power_unavailable",
            detail="POWER did not answer",
            headers={"Retry-After": "30"},
        )

    return TestClient(app).get("/raise-problem")


def test_problem_sets_the_status(response):
    assert response.status_code == 503


def test_problem_uses_the_problem_media_type(response):
    assert response.headers["content-type"] == "application/problem+json"


def test_problem_body_follows_rfc_9457(response):
    assert response.json() == {
        "type": "about:blank",
        "title": "Service Unavailable",
        "status": 503,
        "code": "power_unavailable",
        "detail": "POWER did not answer",
    }


def test_problem_keeps_its_headers(response):
    assert response.headers["retry-after"] == "30"


def test_problem_without_detail_omits_the_detail_member():
    assert ProblemError(400, "invalid_spec").to_body() == {
        "type": "about:blank",
        "title": "Bad Request",
        "status": 400,
        "code": "invalid_spec",
    }
