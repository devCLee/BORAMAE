"""Header names and the error body of the HTTP paths (docs/BUILD_CONTRACT.md).

Frozen from wave 2: report a needed change. The facts of one request (key, cache
status, bytes fetched, timings, containing-cell flag) travel in these headers
and never in a stored file (TDD.md:182).
"""

from typing import Literal

from boramae.contracts.spec import ContractModel

HEADER_RESULT_KEY = "X-Result-Key"
HEADER_REQUEST_ID = "X-Request-Id"
HEADER_CACHE = "X-Cache"
HEADER_BYTES_FETCHED = "X-Bytes-Fetched"
HEADER_SERVER_TIMING = "Server-Timing"
# Sent with the value 'true' only when no cell center fell inside the area.
HEADER_CONTAINING_CELL = "X-Containing-Cell"

CacheStatus = Literal["hit", "miss"]


class Problem(ContractModel):
    """The RFC 9457 body that errors.ProblemError sends as application/problem+json."""

    type: str
    title: str
    status: int
    code: str  # stable and machine-readable, such as 'area_too_large'
    detail: str | None = None
