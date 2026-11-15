"""Request ID, request-fact headers and the request log line (DES-018, TR-O-003).

A router reports the facts of its request on request.state, and this middleware
copies them into the response headers and into one JSON log line on stdout:

    kind                  'trend', 'caseboard', 'scan', ...
    result_key            the key of the result file
    cache                 'hit' or 'miss'
    bytes_fetched         int, bytes read from POWER for this request
    timings               dict of a step name to milliseconds
    used_containing_cell  True when no cell center fell inside the area

The middleware sets request.state.request_id before the router runs. The log line is
an allowlist (_write_log_line): no query string, no prompt text, no client address
(TDD.md:378). Server-Timing and the log add the time to the first response byte as
'total'.
"""

import json
import sys
import time
import uuid
from collections.abc import Mapping
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from boramae.contracts.http import (
    HEADER_BYTES_FETCHED,
    HEADER_CACHE,
    HEADER_CONTAINING_CELL,
    HEADER_REQUEST_ID,
    HEADER_RESULT_KEY,
    HEADER_SERVER_TIMING,
)
from boramae.errors import ProblemError, handle_problem

EXPOSED_HEADERS = (
    HEADER_REQUEST_ID,
    HEADER_RESULT_KEY,
    HEADER_CACHE,
    HEADER_BYTES_FETCHED,
    HEADER_SERVER_TIMING,
    HEADER_CONTAINING_CELL,
)
# ponytail: no document fixes these values: the flag header reads "true" and is
# absent otherwise; "total" is the time to the response start, not to the last byte.
CONTAINING_CELL_FLAG = "true"
TOTAL_TIMING = "total"
UNANSWERED_STATUS = 500
INTERNAL_ERROR_CODE = "internal"


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        facts = scope.setdefault("state", {})
        facts["request_id"] = uuid.uuid4().hex
        answer: dict[str, Any] = {"status": UNANSWERED_STATUS, "timings": {}}

        async def send_with_facts(message: Message) -> None:
            if message["type"] == "http.response.start":
                timings = {**facts.get("timings", {}), TOTAL_TIMING: _ms_since(started)}
                answer.update(status=message["status"], timings=timings)
                message.setdefault("headers", [])
                _set_fact_headers(MutableHeaders(scope=message), facts, timings)
            await send(message)

        try:
            await self.app(scope, receive, send_with_facts)
        except Exception:
            # Starlette answers an unhandled error outside this middleware, and that
            # answer would carry no request ID (DES-018). So answer here when no
            # answer has started, then re-raise for the server's traceback log.
            if not answer["timings"]:
                error = ProblemError(UNANSWERED_STATUS, INTERNAL_ERROR_CODE)
                response = await handle_problem(Request(scope), error)
                await response(scope, receive, send_with_facts)
            raise
        finally:
            _write_log_line(scope["path"], facts, answer)


def _ms_since(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _set_fact_headers(
    headers: MutableHeaders, facts: Mapping[str, Any], timings: Mapping[str, float]
) -> None:
    headers[HEADER_REQUEST_ID] = facts["request_id"]
    if facts.get("result_key") is not None:
        headers[HEADER_RESULT_KEY] = facts["result_key"]
    if facts.get("cache") is not None:
        headers[HEADER_CACHE] = facts["cache"]
    if facts.get("bytes_fetched") is not None:
        headers[HEADER_BYTES_FETCHED] = str(facts["bytes_fetched"])
    if facts.get("used_containing_cell"):
        headers[HEADER_CONTAINING_CELL] = CONTAINING_CELL_FLAG
    headers[HEADER_SERVER_TIMING] = ", ".join(
        f"{name};dur={ms}" for name, ms in timings.items()
    )


def _write_log_line(
    path: str, facts: Mapping[str, Any], answer: Mapping[str, Any]
) -> None:
    line = {
        "request_id": facts["request_id"],
        "path": path,
        "status": answer["status"],
        "kind": facts.get("kind"),
        "result_key": facts.get("result_key"),
        "cache": facts.get("cache"),
        "bytes_fetched": facts.get("bytes_fetched"),
        "timings": answer["timings"],
    }
    sys.stdout.write(json.dumps(line, separators=(",", ":")) + "\n")
    sys.stdout.flush()
