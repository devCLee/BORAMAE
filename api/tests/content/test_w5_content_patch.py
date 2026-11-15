"""W5-PATCH-CONTENT: rules-mode recall of catalog inputs 25, 28, 29, 30, 31, 32, 54, 58.

The places of inputs 29, 31 and 58, and the Korean place of input 32, resolve to a
gazetteer row that holds the exact name (wave 4 open decision 8). The seed names of
wave 3 open decision 14 make inputs 25, 28, 30 and 54 name their unavailable variable.
"""

from pathlib import Path

import pytest

from boramae.batch.build_catalog import build_catalog
from boramae.contracts.spec import UnavailableRequest
from boramae.services.content import CONTENT_FILES, read_content
from boramae.services.parser_rules import parse_rules
from boramae.services.places import find_place, normalize
from tests.fakes import FakeReader

CONTENT = Path(__file__).parents[3] / "content"


def _content(name):
    relative, model = CONTENT_FILES[name]
    return read_content(CONTENT / relative, model)


INPUTS = {item.id: item for item in _content("inputs").inputs}
# The catalog that build-catalog makes from the seed; it copies the unavailable list.
SEED_CATALOG = build_catalog(
    FakeReader(), _content("catalog_seed"), lambda freq: ("fake-id", "fake-version")
)[0]


def _row_names(text, lang):
    """Every normalized name of the row that find_place gives for the text."""
    place = find_place(text, lang)
    names = (place.name.en, place.name.ko, *place.alt) if place else ()
    return {normalize(name) for name in names}


@pytest.mark.parametrize(
    ("input_id", "lang"),
    [
        (29, "en"),
        (29, "ko"),
        (31, "en"),
        (31, "ko"),
        (58, "en"),
        (58, "ko"),
        (32, "ko"),
    ],
)
def test_input_place_resolves_to_a_row_that_holds_its_exact_name(input_id, lang):
    name = getattr(INPUTS[input_id].place.name, lang)
    assert normalize(name) in _row_names(name, lang)


@pytest.mark.parametrize(
    ("input_id", "lang", "requested"),
    [
        (25, "en", "NDVI"),
        (25, "ko", "NDVI"),
        (28, "en", "NDVI"),
        (28, "ko", "NDVI"),
        (30, "ko", "MHW"),
        (54, "en", "NO2"),
        (54, "ko", "NO2"),
    ],
)
def test_question_gives_not_in_this_version_with_its_unavailable_id(
    input_id, lang, requested
):
    item = INPUTS[input_id]
    proposal = parse_rules(getattr(item.text, lang), lang, SEED_CATALOG)
    assert proposal.unavailable == UnavailableRequest(
        requested=requested, nearest_var=item.expected.nearest_var
    )
