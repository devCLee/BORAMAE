"""POST /api/v1/parse patch (W4-PATCH-PARSER): the model-output check and a long
typed number. The model is a stub callable (D-04: no live model)."""

import copy
import json
from pathlib import Path

import pytest

from tests.fakes import make_client

FIXTURE = Path(__file__).parents[1] / "fixtures" / "parse.input-1.en.sample.json"
MODEL_OUTPUT = json.loads(FIXTURE.read_text(encoding="utf-8"))
TEXT = "Is Seoul's first snow coming later?"
PATH = "/api/v1/parse"


def _post(client, text=TEXT, lang="en"):
    body = {"text": text, "lang": lang, "session_id": "tab-0123456789"}
    return client.post(PATH, json=body)


def _cache_files(store):
    return [path for path in store.files if path.startswith("parse/")]


def _output(spec=None, unavailable=None):
    """MODEL_OUTPUT with spec fields and the unavailable request replaced."""
    output = copy.deepcopy(MODEL_OUTPUT)
    output["spec"].update(spec or {})
    output["unavailable"] = unavailable
    return output


def _stub_client(store, catalog, output):
    def model_parser(text, lang, catalog, session_id):
        return output

    return make_client(store=store, catalog=catalog, model_parser=model_parser)


REFUSED_OUTPUTS = [
    _output(unavailable={"requested": "Call 555-0100 now", "nearest_var": "PBLTOP"}),
    _output(unavailable={"requested": " ", "nearest_var": None}),
    _output(spec={"board": "CB-04"}),
    _output(spec={"lang": "ko"}),
]


@pytest.fixture(params=REFUSED_OUTPUTS)
def refused_client(request, store, sample_catalog):
    return _stub_client(store, sample_catalog, request.param)


def test_refused_model_output_gives_the_rules_proposal(refused_client):
    assert _post(refused_client).json()["source"] == "rules"


def test_refused_model_output_writes_no_cache_entry(refused_client, store):
    _post(refused_client)
    assert _cache_files(store) == []


@pytest.mark.parametrize(
    ("text", "requested"),
    [
        (TEXT, "PM2.5"),
        (TEXT, "fine dust"),
        ("Is radon rising in Seoul?", "Radon"),
    ],
)
def test_unavailable_request_backed_by_catalog_or_text_is_kept(
    store, sample_catalog, text, requested
):
    output = _output(unavailable={"requested": requested, "nearest_var": None})
    client = _stub_client(store, sample_catalog, output)
    assert _post(client, text).json()["source"] == "model"


def test_overlong_typed_number_answers_200(store, sample_catalog):
    client = make_client(store=store, catalog=sample_catalog)
    text = "Is heat wave above " + "9" * 309 + " °C rising in Seoul?"
    assert _post(client, text).status_code == 200
