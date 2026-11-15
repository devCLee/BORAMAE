"""Live test: the Korean text of input 1 through the model parser and the parse router
on Amazon Bedrock (TR-F-003, acceptance 1).

Run it only after decision D-04 allows a live Bedrock call; until then it stays
deselected. Set BORAMAE_LLM_ENABLED=on and BORAMAE_MODEL_ID, then run
uv run --directory api pytest tests/live/test_parse_llm_live.py -m live -q -s
It makes one model call, on the sample catalog and a dict store, so nothing reaches
api/.data.
"""

from pathlib import Path

import pytest

from boramae.config import load_settings
from boramae.contracts.results_catalog import Catalog
from boramae.services.content import load_content
from boramae.services.parser_llm import make_model_parser
from tests.fakes import DictStore, make_client

pytestmark = pytest.mark.live

INPUT_ID = 1
SAMPLE_CATALOG = Path(__file__).parents[1] / "fixtures" / "catalog.sample.json"
SESSION = "live-parse-0001"


@pytest.fixture(scope="module")
def case():
    return next(item for item in load_content("inputs").inputs if item.id == INPUT_ID)


@pytest.fixture(scope="module")
def answer(case):
    """The parse answer of the one model call."""
    parser = make_model_parser(load_settings())
    if parser is None:
        pytest.skip("set BORAMAE_LLM_ENABLED=on and BORAMAE_MODEL_ID")
    catalog = Catalog.model_validate_json(SAMPLE_CATALOG.read_bytes())
    client = make_client(store=DictStore(), catalog=catalog, model_parser=parser)
    body = {"text": case.text.ko, "lang": "ko", "session_id": SESSION}
    return client.post("/api/v1/parse", json=body).json()


def test_input_1_is_answered_by_the_model(answer):
    assert answer["source"] == "model"


FIELDS = [
    pytest.param(
        lambda a: a["variables"][0]["var"], lambda c: c.expected.var, id="var"
    ),
    pytest.param(
        lambda a: a["variables"][0]["metric_id"],
        lambda c: c.expected.metric_id,
        id="metric",
    ),
    pytest.param(lambda a: a["spec"]["intent"], lambda c: c.intent, id="intent"),
    pytest.param(
        lambda a: a["spec"]["place"]["name"], lambda c: c.place.name.ko, id="place"
    ),
    pytest.param(lambda a: a["spec"]["board"], lambda c: c.board, id="board"),
]


@pytest.mark.parametrize(("read", "expected"), FIELDS)
def test_input_1_matches_the_catalog_input(answer, case, read, expected):
    assert read(answer) == expected(case)
