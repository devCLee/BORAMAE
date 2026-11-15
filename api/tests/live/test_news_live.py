"""Live news feeds: one real request per source. Deselected by default."""

from datetime import date, timedelta

import pytest

from boramae.services import news

pytestmark = pytest.mark.live


def test_should_read_items_from_google_news_korean_edition():
    items, _ = news._fetch_google(
        "google_news_ko", "서울 폭염", date(2024, 6, 1), date(2024, 8, 31)
    )
    assert items


def test_should_answer_gdelt_artlist_as_json():
    end = date.today()
    items, _ = news._fetch_gdelt("Seoul weather", end - timedelta(days=30), end)
    assert isinstance(items, list)
