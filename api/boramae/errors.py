"""Errors of the API. Frozen from wave 2: report a needed change."""

from collections.abc import Mapping
from http import HTTPStatus

from fastapi import Request
from fastapi.responses import JSONResponse

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemError(Exception):
    """An HTTP error that the handler sends as an RFC 9457 problem+json body.

    `code` is a stable machine-readable member beside the RFC fields, such as
    'area_too_large' or 'not_built'.
    """

    def __init__(
        self,
        status: int,
        code: str,
        detail: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.detail = detail
        self.headers = dict(headers or {})

    def to_body(self) -> dict[str, object]:
        body: dict[str, object] = {
            "type": "about:blank",
            "title": HTTPStatus(self.status).phrase,
            "status": self.status,
            "code": self.code,
        }
        if self.detail is not None:
            body["detail"] = self.detail
        return body


async def handle_problem(request: Request, exc: ProblemError) -> JSONResponse:
    return JSONResponse(
        exc.to_body(),
        status_code=exc.status,
        headers=exc.headers,
        media_type=PROBLEM_MEDIA_TYPE,
    )


class PowerUnavailable(Exception):
    """A POWER store could not be opened or read in time."""


class Overloaded(Exception):
    """The worker pool had no free slot within its wait limit."""
