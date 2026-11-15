"""News for a search text and a window from Google News RSS and GDELT DOC 2.0 (FR-20).

Feed bodies are untrusted: the read is capped, XML with a DOCTYPE or ENTITY is
refused before parsing, and item links are never fetched. Only the two fixed hosts
are requested and redirects are refused. Logs keep the feed, status, bytes and time,
never the search text.
"""

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime

from boramae.contracts.news import Feed, FeedReport, NewsItem, NewsResult

log = logging.getLogger(__name__)

TIMEOUT_S = 5
MAX_BODY_BYTES = 2_000_000
MAX_ITEMS = 25
CACHE_TTL_S = 24 * 3600
USER_AGENT = "news-client/1.0"
GOOGLE_HOST = "news.google.com"
GDELT_HOST = "api.gdeltproject.org"
GOOGLE_URL = f"https://{GOOGLE_HOST}/rss/search?"
GDELT_URL = f"https://{GDELT_HOST}/api/v2/doc/doc?"
ALLOWED_HOSTS = {GOOGLE_HOST, GDELT_HOST}
GOOGLE_EDITIONS = {
    "google_news_en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "google_news_ko": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
}
GDELT_SPAN = timedelta(days=90)
GDELT_FIRST_DAY = date(2017, 1, 1)
GDELT_MAX_RECORDS = 75
GDELT_MIN_INTERVAL_S = 5.0
GDELT_TIME_FORMAT = "%Y%m%dT%H%M%SZ"
GOOGLE_COVERAGE = "Google News search, about 100 items at most"
GDELT_COVERAGE = "GDELT DOC 2.0, last 3 months of the window only ({start} to {end})"
GDELT_SKIPPED = "GDELT DOC 2.0 holds no news before 2017"
UNSAFE_XML = re.compile(rb"<!(DOCTYPE|ENTITY)", re.IGNORECASE)
TITLE_SPACE = re.compile(r"\W+")

# ponytail: one process-wide lock and timestamp pace GDELT to one call per 5 s per
# task; with several ECS tasks the ceiling multiplies, so move to a shared limiter
# (or the S3 cache in front) if GDELT answers 429 under load.
_gdelt_lock = threading.Lock()
_gdelt_last_call = 0.0
# ponytail: in-process TTL cache, lost on restart and not shared across tasks; move
# to the result store under ctx/news/{hash}.json (DATA_MODEL.md) when it matters.
_cache: dict[tuple[str, date, date], tuple[float, NewsResult]] = {}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def get_news(text: str, start: date, end: date) -> tuple[NewsResult, str]:
    """The news result and the cache fact: 'hit' or 'miss'."""
    key = (" ".join(text.lower().split()), start, end)
    cached = _cache.get(key)
    if cached is not None and time.monotonic() - cached[0] < CACHE_TTL_S:
        return cached[1], "hit"
    result = _build(key[0], start, end)
    if all(report.status in {"ok", "empty", "skipped"} for report in result.feeds):
        _cache[key] = (time.monotonic(), result)
    return result, "miss"


def _build(text: str, start: date, end: date) -> NewsResult:
    with ThreadPoolExecutor(max_workers=len(GOOGLE_EDITIONS) + 1) as pool:
        futures = {
            feed: pool.submit(_fetch_google, feed, text, start, end)
            for feed in GOOGLE_EDITIONS
        }
        futures["gdelt"] = pool.submit(_fetch_gdelt, text, start, end)
        settled = [_settle(feed, future) for feed, future in futures.items()]
    items = [item for _, found in settled for item in found]
    feeds = [report for report, _ in settled]
    return NewsResult(items=_dedupe(items)[:MAX_ITEMS], feeds=feeds)


def _settle(feed: Feed, future: Future) -> tuple[FeedReport, list[NewsItem]]:
    try:
        found, coverage = future.result()
    # One feed failing must not fail the response, so any error becomes its status.
    except Exception as error:  # noqa: BLE001
        log.warning("news: %s failed (%s)", feed, type(error).__name__)
        status = "timeout" if _is_timeout(error) else "error"
        return FeedReport(feed=feed, status=status, count=0, coverage=""), []
    if found is None:
        return FeedReport(feed=feed, status="skipped", count=0, coverage=coverage), []
    status = "ok" if found else "empty"
    return FeedReport(
        feed=feed, status=status, count=len(found), coverage=coverage
    ), found


def _is_timeout(error: Exception) -> bool:
    # urllib wraps a connect timeout in URLError(reason=TimeoutError).
    return isinstance(error, TimeoutError) or isinstance(
        getattr(error, "reason", None), TimeoutError
    )


def _fetch_google(
    feed: Feed, text: str, start: date, end: date
) -> tuple[list[NewsItem], str]:
    # before: is exclusive, so the day after the window end keeps the last day.
    before = (end + timedelta(days=1)).isoformat()
    query = f"{text} after:{start.isoformat()} before:{before}"
    url = GOOGLE_URL + urllib.parse.urlencode({"q": query, **GOOGLE_EDITIONS[feed]})
    return parse_rss(_read_url(url), feed), GOOGLE_COVERAGE


def _fetch_gdelt(
    text: str, start: date, end: date
) -> tuple[list[NewsItem] | None, str]:
    if end < GDELT_FIRST_DAY:
        return None, GDELT_SKIPPED
    first = max(start, end - GDELT_SPAN, GDELT_FIRST_DAY)
    params = {
        "query": text,
        "mode": "artlist",
        "format": "json",
        "sort": "datedesc",
        "maxrecords": GDELT_MAX_RECORDS,
        "startdatetime": first.strftime("%Y%m%d000000"),
        "enddatetime": end.strftime("%Y%m%d235959"),
    }
    body = _read_paced(GDELT_URL + urllib.parse.urlencode(params))
    coverage = GDELT_COVERAGE.format(start=first.isoformat(), end=end.isoformat())
    return parse_gdelt(body), coverage


def _read_paced(url: str) -> bytes:
    global _gdelt_last_call
    with _gdelt_lock:
        wait = GDELT_MIN_INTERVAL_S - (time.monotonic() - _gdelt_last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            return _read_url(url)
        finally:
            _gdelt_last_call = time.monotonic()


def _read_url(url: str) -> bytes:
    """The network boundary: one capped GET to an allowed host."""
    if urllib.parse.urlsplit(url).hostname not in ALLOWED_HOSTS:
        raise ValueError("host not allowed")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    began = time.monotonic()
    # NOTE: the timeout bounds each socket operation, not the whole read.
    with _opener.open(request, timeout=TIMEOUT_S) as response:
        body = response.read(MAX_BODY_BYTES + 1)
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("body too large")
    host = urllib.parse.urlsplit(url).hostname
    log.info("news: %s %d bytes in %.2f s", host, len(body), time.monotonic() - began)
    return body


def parse_rss(body: bytes, feed: Feed) -> list[NewsItem]:
    if UNSAFE_XML.search(body):
        raise ValueError("XML declares a DOCTYPE or ENTITY")
    items = []
    for node in ET.fromstring(body).iterfind("./channel/item"):
        source = (node.findtext("source") or "").strip()
        title = (node.findtext("title") or "").strip()
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        url, published = node.findtext("link"), node.findtext("pubDate")
        if title and url and published:
            when = parsedate_to_datetime(published)
            items.append(
                NewsItem(title=title, source=source, published=when, url=url, feed=feed)
            )
    return items


def parse_gdelt(body: bytes) -> list[NewsItem]:
    articles = json.loads(body).get("articles", [])
    return [
        NewsItem(
            title=article["title"].strip(),
            source=article.get("domain", ""),
            published=datetime.strptime(article["seendate"], GDELT_TIME_FORMAT).replace(
                tzinfo=UTC
            ),
            url=article["url"],
            feed="gdelt",
        )
        for article in articles
        if article.get("title") and article.get("url") and article.get("seendate")
    ]


def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
    """Newest first, dropping an item whose normalized URL or title came before."""
    seen_urls, seen_titles, kept = set(), set(), []
    for item in sorted(items, key=lambda item: item.published, reverse=True):
        parts = urllib.parse.urlsplit(item.url)
        url = f"{parts.hostname}{parts.path.rstrip('/')}".lower()
        title = TITLE_SPACE.sub(" ", item.title.lower()).strip()
        if url in seen_urls or title in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title)
        kept.append(item)
    return kept
