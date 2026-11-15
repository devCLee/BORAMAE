"""News service: feed parsing, de-duplication, feed failures, GDELT pacing and cache."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest

from boramae.services import news

FIXTURES = Path(__file__).parents[1] / "fixtures"
RSS = (FIXTURES / "news.google.sample.xml").read_bytes()
GDELT = (FIXTURES / "news.gdelt.sample.json").read_bytes()
START, END = date(2024, 6, 1), date(2024, 8, 31)
TEST_INTERVAL_S = 0.3


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    news._cache.clear()
    monkeypatch.setattr(news, "_gdelt_last_call", 0.0)
    monkeypatch.setattr(news, "GDELT_MIN_INTERVAL_S", 0.0)


def _network(google=RSS, gdelt=GDELT, calls=None):
    """A fake _read_url: a body, or an exception to raise, per host."""

    def read(url):
        if calls is not None:
            calls.append(url)
        answer = google if news.GOOGLE_HOST in url else gdelt
        if isinstance(answer, Exception):
            raise answer
        return answer

    return read


def _statuses(result):
    return {report.feed: report.status for report in result.feeds}


def test_should_read_title_without_source_suffix_from_rss():
    items = news.parse_rss(RSS, "google_news_en")
    assert items[0].title == "Seoul swelters through record heat wave"


def test_should_read_source_name_from_rss():
    items = news.parse_rss(RSS, "google_news_en")
    assert items[0].source == "Example Times"


def test_should_refuse_rss_with_entity_declaration():
    body = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x "y">]><rss/>'
    with pytest.raises(ValueError):
        news.parse_rss(body, "google_news_en")


def test_should_read_utc_date_from_gdelt():
    items = news.parse_gdelt(GDELT)
    assert items[0].published.isoformat() == "2024-08-20T03:15:00+00:00"


def test_should_read_no_items_from_empty_gdelt_answer():
    assert news.parse_gdelt(b"{}") == []


def test_should_drop_same_title_from_another_feed(monkeypatch):
    monkeypatch.setattr(news, "_read_url", _network())
    result, _ = news.get_news("Seoul heat", START, END)
    titles = [item.title for item in result.items]
    assert titles.count("Seoul swelters through record heat wave") == 1


def test_should_sort_items_newest_first(monkeypatch):
    monkeypatch.setattr(news, "_read_url", _network())
    result, _ = news.get_news("Seoul heat", START, END)
    dates = [item.published for item in result.items]
    assert dates == sorted(dates, reverse=True)


def test_should_keep_google_items_when_gdelt_times_out(monkeypatch):
    monkeypatch.setattr(news, "_read_url", _network(gdelt=TimeoutError()))
    result, _ = news.get_news("Seoul heat", START, END)
    # Both editions answer the same sample, so de-duplication leaves its 2 items.
    assert len(result.items) == 2


def test_should_report_timeout_for_the_feed_that_timed_out(monkeypatch):
    monkeypatch.setattr(news, "_read_url", _network(gdelt=TimeoutError()))
    result, _ = news.get_news("Seoul heat", START, END)
    assert _statuses(result)["gdelt"] == "timeout"


def test_should_return_empty_items_when_all_feeds_fail(monkeypatch):
    failing = _network(google=OSError("down"), gdelt=OSError("down"))
    monkeypatch.setattr(news, "_read_url", failing)
    result, _ = news.get_news("Seoul heat", START, END)
    assert result.items == []


def test_should_report_error_for_every_feed_when_all_fail(monkeypatch):
    failing = _network(google=OSError("down"), gdelt=OSError("down"))
    monkeypatch.setattr(news, "_read_url", failing)
    result, _ = news.get_news("Seoul heat", START, END)
    assert set(_statuses(result).values()) == {"error"}


def test_should_label_gdelt_coverage_as_last_three_months(monkeypatch):
    monkeypatch.setattr(news, "_read_url", _network())
    result, _ = news.get_news("Seoul heat", date(2020, 1, 1), END)
    gdelt = next(report for report in result.feeds if report.feed == "gdelt")
    assert gdelt.coverage == news.GDELT_COVERAGE.format(
        start="2024-06-02", end="2024-08-31"
    )


def test_should_skip_gdelt_for_window_before_2017(monkeypatch):
    monkeypatch.setattr(news, "_read_url", _network())
    result, _ = news.get_news("Seoul heat", date(2000, 1, 1), date(2010, 12, 31))
    assert _statuses(result)["gdelt"] == "skipped"


def test_should_space_gdelt_calls_by_the_minimum_interval(monkeypatch):
    stamps = []
    monkeypatch.setattr(news, "GDELT_MIN_INTERVAL_S", TEST_INTERVAL_S)
    monkeypatch.setattr(news, "_read_url", lambda url: stamps.append(time.monotonic()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: news._read_paced(news.GDELT_URL), range(2)))
    assert stamps[1] - stamps[0] >= TEST_INTERVAL_S


def test_should_answer_repeat_request_from_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(news, "_read_url", _network(calls=calls))
    news.get_news("Seoul heat", START, END)
    news.get_news("  seoul   HEAT ", START, END)
    assert len(calls) == 3


def test_should_refuse_a_host_outside_the_allowlist():
    with pytest.raises(ValueError):
        news._read_url("https://example.com/rss")
