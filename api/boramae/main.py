from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from boramae.deps import get_settings
from boramae.errors import ProblemError, handle_problem
from boramae.observability import EXPOSED_HEADERS, RequestLogMiddleware
from boramae.routers import (
    agent,
    analysis_caseboard,
    analysis_scan,
    analysis_trend,
    health,
    meta,
    parse,
    results,
)

ROUTER_MODULES = (
    health,
    meta,
    results,
    parse,
    analysis_trend,
    analysis_caseboard,
    analysis_scan,
    agent,
)
DEV_CORS_METHODS = ("GET", "POST")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="BORAMAE API")
    app.add_exception_handler(ProblemError, handle_problem)
    for module in ROUTER_MODULES:
        app.include_router(module.router)
    app.add_middleware(RequestLogMiddleware)
    # App and API share one domain in production; CORS is only for next dev.
    if settings.dev_cors_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.dev_cors_origin],
            allow_methods=DEV_CORS_METHODS,
            expose_headers=EXPOSED_HEADERS,
        )
    return app


app = create_app()
