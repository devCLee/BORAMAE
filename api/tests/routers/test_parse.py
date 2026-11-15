"""POST /api/v1/parse: request checks, the model seam, the rules fallback and the cache."""

import copy
import json
import re
from pathlib import Path

import pytest

from boramae.constants import MAX_PARSE_CHARS
from tests.fakes import make_client

FIXTURE = Path(__file__).parents[1] / "fixtures" / "parse.input-1.en.sample.json"
MODEL_OUTPUT = json.loads(FIXTURE.read_text(encoding="utf-8"))
TEXT = "Is Seoul's first snow coming later?"
SESSION = "tab-0123456789"
PATH = "/api/v1/parse"


class FakeModelParser:
    """The model parser seam: parse(text, lang, catalog, session_id)."""

    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.calls = []

    def __call__(self, text, lang, catalog, session_id):
        self.calls.append((text, lang, catalog, session_id))
        if self.error is not None:
            raise self.error
        return self.output


def _post(client, text=TEXT, lang="en"):
    return client.post(PATH, json={"text": text, "lang": lang, "session_id": SESSION})


def _cache_files(store):
    return [body for path, body in store.files.items() if path.startswith("parse/")]


def _with(path, value):
    """MODEL_OUTPUT with one field replaced; path is a list of keys and indexes."""
    output = copy.deepcopy(MODEL_OUTPUT)
    target = output
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return output


@pytest.fixture
def model():
    return FakeModelParser(output=MODEL_OUTPUT)


@pytest.fixture
def model_client(store, sample_catalog, model):
    return make_client(store=store, catalog=sample_catalog, model_parser=model)


@pytest.fixture
def rules_client(store, sample_catalog):
    return make_client(store=store, catalog=sample_catalog)


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_returns_400(rules_client, text):
    assert _post(rules_client, text).status_code == 400


def test_text_over_the_cap_returns_400(rules_client):
    assert _post(rules_client, "a" * (MAX_PARSE_CHARS + 1)).status_code == 400


def test_text_at_the_cap_returns_200(rules_client):
    assert _post(rules_client, "a" * MAX_PARSE_CHARS).status_code == 200


def test_body_far_over_the_cap_returns_400(rules_client):
    assert _post(rules_client, "a" * 100 * MAX_PARSE_CHARS).status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b'{"text": "snow"}',
        b'{"text": "snow", "lang": "fr", "session_id": "tab-0123456789"}',
        b'{"text": "snow", "lang": "en", "session_id": "short"}',
    ],
)
def test_body_that_is_not_a_parse_request_returns_400(rules_client, body):
    assert rules_client.post(PATH, content=body).status_code == 400


def test_bad_request_answers_a_problem_body(rules_client):
    response = _post(rules_client, "")
    assert response.headers["content-type"] == "application/problem+json"


def test_without_a_model_parser_the_rules_answer(rules_client):
    assert _post(rules_client).json()["source"] == "rules"


def test_rules_answer_names_the_keyword_variable(rules_client):
    assert _post(rules_client).json()["variables"][0]["var"] == "PRECSNO"


def test_without_a_model_parser_no_cache_entry_is_written(rules_client, store):
    _post(rules_client)
    assert _cache_files(store) == []


def test_valid_model_output_answers_with_source_model(model_client):
    assert _post(model_client).json()["source"] == "model"


def test_valid_model_output_enters_the_cache(model_client, store):
    _post(model_client)
    assert len(_cache_files(store)) == 1


def test_model_parser_gets_text_lang_catalog_and_session(
    model_client, model, sample_catalog
):
    _post(model_client)
    assert model.calls == [(TEXT, "en", sample_catalog, SESSION)]


def test_repeated_request_calls_the_model_once(model_client, model):
    _post(model_client)
    _post(model_client)
    assert len(model.calls) == 1


def test_repeated_request_is_a_cache_hit(model_client):
    _post(model_client)
    assert _post(model_client).headers["x-cache"] == "hit"


def test_repeated_request_returns_the_cached_proposal(model_client):
    first = _post(model_client).json()
    assert _post(model_client).json() == first


def test_text_that_normalizes_equal_is_a_cache_hit(model_client, model):
    _post(model_client)
    _post(model_client, "  is SEOUL'S first   snow coming later? ")
    assert len(model.calls) == 1


def test_other_language_misses_the_cache(model_client, model):
    _post(model_client)
    _post(model_client, lang="ko")
    assert len(model.calls) == 2


def test_cached_model_proposal_answers_with_the_llm_off(
    model_client, store, sample_catalog
):
    _post(model_client)
    llm_off = make_client(store=store, catalog=sample_catalog)
    assert _post(llm_off).json()["source"] == "model"


@pytest.fixture(params=[TimeoutError("model timed out"), RuntimeError("client")])
def failing_model(request):
    return FakeModelParser(error=request.param)


@pytest.fixture
def failing_client(store, sample_catalog, failing_model):
    return make_client(store=store, catalog=sample_catalog, model_parser=failing_model)


def test_model_failure_gives_the_rules_proposal(failing_client):
    assert _post(failing_client).json()["source"] == "rules"


def test_model_failure_writes_no_cache_entry(failing_client, store):
    _post(failing_client)
    assert _cache_files(store) == []


def test_after_a_model_failure_the_next_request_calls_the_model(
    failing_client, failing_model
):
    _post(failing_client)
    _post(failing_client)
    assert len(failing_model.calls) == 2


INVALID_OUTPUTS = [
    _with(["variables", 0, "var"], "PM25"),
    _with(["variables", 1, "metric_id"], "weekly_mean"),
    _with(["spec", "metric", "var"], "NOT_A_VAR"),
    _with(["spec", "metric", "id"], "not_a_metric"),
    _with(["unavailable"], {"requested": "PM2.5", "nearest_var": "PM10"}),
    _with(["spec", "intent"], "forecast"),
    {"variables": []},
    ["not", "a", "mapping"],
]


@pytest.fixture(params=INVALID_OUTPUTS)
def invalid_client(request, store, sample_catalog):
    model = FakeModelParser(output=request.param)
    return make_client(store=store, catalog=sample_catalog, model_parser=model)


def test_model_output_outside_the_catalog_gives_the_rules_proposal(invalid_client):
    assert _post(invalid_client).json()["source"] == "rules"


def test_model_output_outside_the_catalog_writes_no_cache_entry(invalid_client, store):
    _post(invalid_client)
    assert _cache_files(store) == []


def test_cache_entry_holds_no_question_text(model_client, store):
    _post(model_client)
    assert TEXT.encode("utf-8") not in _cache_files(store)[0]


def test_cache_entry_holds_no_client_address(model_client, store):
    _post(model_client)
    assert b"testclient" not in _cache_files(store)[0]


def test_cache_path_is_a_hash(model_client, store):
    _post(model_client)
    assert re.fullmatch(r"parse/[0-9a-f]{64}\.json", *store.files)
