"""GET /api/v1/context/news: query checks and the empty state."""

import pytest

from boramae.services import news
from tests.fakes import make_client

PATH = "/api/v1/context/news"
GOOD = {"q": "Seoul heat", "start": "2024-06-01", "end": "2024-08-31"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    news._cache.clear()
    monkeypatch.setattr(news, "GDELT_MIN_INTERVAL_S", 0.0)

    def down(url):
        raise OSError("down")

    monkeypatch.setattr(news, "_read_url", down)


@pytest.mark.parametrize(
    "params",
    [
        {**GOOD, "q": "x"},
        {**GOOD, "q": "a" * 81},
        {**GOOD, "q": "heat <script>"},
        {**GOOD, "q": "heat site:evil.com"},
        {**GOOD, "start": "1970-01-01"},
        {**GOOD, "start": "2024-09-01"},
        {**GOOD, "end": "2999-01-01"},
        {**GOOD, "end": "not-a-date"},
    ],
)
def test_should_reject_bad_query(params):
    response = make_client().get(PATH, params=params)
    assert response.status_code in {400, 422}


def test_should_accept_korean_text():
    response = make_client().get(PATH, params={**GOOD, "q": "서울 폭염"})
    assert response.status_code == 200


def test_should_answer_200_with_empty_items_when_all_feeds_fail():
    response = make_client().get(PATH, params=GOOD)
    assert response.json()["items"] == []
