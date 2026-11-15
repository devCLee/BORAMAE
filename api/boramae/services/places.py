"""Find the gazetteer place that a text names (TR-F-008, DEC-011). No fuzzy match at P0."""

import re
import unicodedata
from functools import cache

from boramae.contracts.content import Place
from boramae.contracts.spec import Lang
from boramae.services.content import load_content

_NON_WORD = re.compile(r"[\W_]+")


def find_place(text: str, lang: Lang) -> Place | None:
    """Return the place whose name in lang, or alt name, occurs in the text, or None.

    The earliest name in the text wins, then the longest, then the first in the file.
    """
    pattern, places = _index(lang)
    match = pattern.search(normalize(text))
    return places[match.group()] if match else None


def normalize(text: str) -> str:
    """Case-fold, unify width and turn every run of non-word characters into a space."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _NON_WORD.sub(" ", folded).strip()


@cache
def _index(lang: Lang) -> tuple[re.Pattern[str], dict[str, Place]]:
    places: dict[str, Place] = {}
    for place in load_content("gazetteer"):
        for name in (getattr(place.name, lang), *place.alt):
            key = normalize(name)
            if key:
                places.setdefault(key, place)
    # Longest first, so the alternation takes the longest name at the earliest spot.
    names = "|".join(re.escape(key) for key in sorted(places, key=len, reverse=True))
    # A name starts at a word boundary. It must end at one only after a Latin letter or
    # digit, because a Korean particle follows the name directly, as in 서울이.
    return re.compile(rf"(?<!\w)(?:{names})(?![a-z0-9])"), places
