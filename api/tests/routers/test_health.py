from fastapi import APIRouter
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from boramae.main import create_app
from boramae.routers import health


def test_health_returns_200():
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200


def test_health_body_reports_ok():
    response = TestClient(create_app()).get("/health")
    assert response.json() == {"status": "ok"}


def test_health_route_declares_no_dependency():
    route = _find_route(health.router, "/health")
    assert route.dependant.dependencies == []


def _find_route(router: APIRouter, path: str) -> APIRoute:
    routes = {
        route.path: route for route in router.routes if isinstance(route, APIRoute)
    }
    return routes[path]
