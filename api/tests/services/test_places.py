import json
from pathlib import Path

import pytest

from boramae.services.places import find_place

# Inputs 6, 8, 38 and 60 ask for the place, so they name none.
CATALOG_PLACES = json.loads(
    (Path(__file__).parent / "catalog_places.json").read_text(encoding="utf-8")
)
ROW_IDS = [f"{row['input_id']}-{row['en']}" for row in CATALOG_PLACES]


@pytest.mark.parametrize("lang", ["en", "ko"])
@pytest.mark.parametrize("row", CATALOG_PLACES, ids=ROW_IDS)
def test_catalog_place_resolves_by_its_name(row, lang):
    assert find_place(row[lang], lang) is not None


@pytest.mark.parametrize("row", CATALOG_PLACES, ids=ROW_IDS)
def test_catalog_place_is_the_same_place_in_both_languages(row):
    assert find_place(row["en"], "en").id == find_place(row["ko"], "ko").id


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Atlantis", "en"),
        ("아틀란티스", "ko"),
        ("Is it getting hotter?", "en"),
        ("Does warming lead to more rain?", "en"),
    ],
)
def test_text_that_names_no_known_place_returns_none(text, lang):
    assert find_place(text, lang) is None


def test_seoul_resolves_to_its_coordinates():
    place = find_place("Seoul", "en")
    assert (place.lat, place.lon) == pytest.approx((37.57, 126.98), abs=0.05)


@pytest.mark.parametrize(
    ("text", "lang", "expected"),
    [
        ("Is Seoul's first snow coming later?", "en", "Seoul"),
        ("서울 첫눈이 늦어지고 있나요?", "ko", "Seoul"),
        ("Is Seoul or Busan warming faster?", "en", "Seoul"),
        ("Is the Colorado River basin losing water?", "en", "Colorado River basin"),
    ],
)
def test_question_resolves_to_its_first_and_longest_place_name(text, lang, expected):
    assert find_place(text, lang).name.en == expected
