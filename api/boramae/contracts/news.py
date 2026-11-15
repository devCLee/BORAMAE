"""News records of GET /api/v1/context/news (FR-20, API_SPEC.md "news").

Non-NASA context only: each item is a link to an outside article, never an input to
the statistics.
"""

from datetime import datetime
from typing import Literal

from boramae.contracts.spec import ContractModel

Feed = Literal["google_news_en", "google_news_ko", "gdelt"]
FeedStatus = Literal["ok", "empty", "timeout", "error", "skipped"]


class NewsItem(ContractModel):
    title: str
    source: str
    published: datetime
    url: str
    feed: Feed


class FeedReport(ContractModel):
    feed: Feed
    status: FeedStatus
    count: int
    coverage: str


class NewsResult(ContractModel):
    items: list[NewsItem]
    feeds: list[FeedReport]
