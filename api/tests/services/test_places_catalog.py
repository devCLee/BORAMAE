import pytest

from boramae.services.content import load_content
from boramae.services.places import find_place

# The closer runs this file after wave 2, once content/catalog-inputs.json exists.
INPUT_PLACES = [
    (item.id, item.place.name) for item in load_content("inputs").inputs if item.place
]


@pytest.mark.parametrize("lang", ["en", "ko"])
@pytest.mark.parametrize(
    ("input_id", "name"), INPUT_PLACES, ids=[str(i) for i, _ in INPUT_PLACES]
)
def test_input_place_resolves_by_its_name(input_id, name, lang):
    assert find_place(getattr(name, lang), lang) is not None
