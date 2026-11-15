"""GET /api/v1/context/news: news for a search text and a window (FR-20, P1).

The query is untrusted: the text is capped and limited to letters, digits, spaces and
light punctuation, and the window must fall inside the POWER record. The text is
never logged.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.concurrency import run_in_threadpool

from boramae.contracts.news import NewsResult
from boramae.errors import ProblemError
from boramae.services.news import get_news

router = APIRouter()

BAD_REQUEST = 400
INVALID_WINDOW = "invalid_window"
FIRST_DAY = date(1981, 1, 1)
MIN_TEXT_CHARS = 2
MAX_TEXT_CHARS = 80
TEXT_PATTERN = r"^[\p{L}\p{N} .,'-]+$"
KIND = "news"


@router.get("/api/v1/context/news")
async def get_context_news(
    request: Request,
    q: Annotated[
        str,
        Query(
            min_length=MIN_TEXT_CHARS, max_length=MAX_TEXT_CHARS, pattern=TEXT_PATTERN
        ),
    ],
    start: date,
    end: date,
) -> NewsResult:
    if not FIRST_DAY <= start <= end <= date.today():
        detail = (
            f"the window must run from {FIRST_DAY.isoformat()} to today, start first"
        )
        raise ProblemError(BAD_REQUEST, INVALID_WINDOW, detail)
    request.state.kind = KIND
    result, cache = await run_in_threadpool(get_news, q, start, end)
    request.state.cache = cache
    return result
