"""The model parser behind the parse seam (W5-PARSE-LLM). D-04 allows no live
Bedrock call, so a fake bedrock-runtime client stands at the network boundary."""

import contextlib
import copy
import json
import logging
import subprocess
import sys
from functools import reduce
from operator import getitem
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError

from boramae.config import Settings
from boramae.constants import INTENT_IDS, METRIC_IDS
from boramae.contracts.spec import ReasonCode
from boramae.llm import bedrock
from boramae.services import parser_llm
from boramae.services.content import load_content
from tests.fakes import make_client

API_DIR = Path(__file__).parents[2]
FIXTURE = API_DIR / "tests" / "fixtures" / "parse.input-1.ko.sample.json"
TOOL_INPUT = json.loads(FIXTURE.read_text(encoding="utf-8"))
del TOOL_INPUT["source"]  # the router sets the source of a model answer
TEXT = "서울 첫눈이 늦어지고 있나요?"
SEOUL_EN = "Is Seoul's first snow coming later?"
PHOENIX_EN = "Is Phoenix getting more 110-degree days?"
PHOENIX_KO = "피닉스에 43.3 °C 넘는 날이 늘었나요?"
SESSION = "tab-0123456789"
MODEL_ID = "test-model"
CALL_LINE = f"parse: model call 1 to {MODEL_ID}"
TWO_VARIABLES = ["T2M", "T2M_MAX"]
TIMEOUT = ReadTimeoutError(endpoint_url="bedrock-runtime")
TIMEOUT_S = 2.5
LLM_OFF_PROBE = (
    "import sys, boramae.config as c, boramae.services.parser_llm as p;"
    " p.make_model_parser(c.Settings()); print('boto3' in sys.modules)"
)


def _answer(tool_input, stop_reason="tool_use"):
    use = {"toolUseId": "t1", "name": parser_llm.TOOL_NAME, "input": tool_input}
    message = {"role": "assistant", "content": [{"toolUse": use}]}
    return {"output": {"message": message}, "stopReason": stop_reason}


class FakeRuntime:
    def __init__(self, tool_input=TOOL_INPUT, response=None, error=None):
        self.requests = []
        self.response = response or _answer(tool_input)
        self.error = error

    def converse(self, **request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def _with(lang, name, typed):
    tool_input = copy.deepcopy(TOOL_INPUT)
    tool_input["spec"]["lang"] = lang
    tool_input["spec"]["place"]["name"] = name
    tool_input["spec"]["metric"]["typed"] = typed
    return tool_input


def _parser(monkeypatch, runtime, **caps):
    monkeypatch.setattr(bedrock, "make_runtime_client", lambda settings: runtime)
    settings = Settings(llm_enabled=True, model_id=MODEL_ID, **caps)
    return parser_llm.make_model_parser(settings)


def _property(request, path):
    schema = request["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]
    for name in path:
        schema = schema["properties"][name]
        schema = schema.get("items", schema)
    return schema


@pytest.fixture
def runtime():
    return FakeRuntime()


@pytest.fixture
def parser(monkeypatch, runtime):
    return _parser(monkeypatch, runtime)


@pytest.fixture
def sent_request(parser, runtime, sample_catalog):
    two = sample_catalog.model_copy(update={"variables": sample_catalog.variables[:2]})
    parser(TEXT, "ko", two, SESSION)
    return runtime.requests[0]


@pytest.mark.parametrize("settings", [Settings(), Settings(llm_enabled=True)])
def test_llm_off_gives_no_model_parser(settings):
    assert parser_llm.make_model_parser(settings) is None


def test_llm_off_loads_no_aws_sdk():
    probe = [sys.executable, "-c", LLM_OFF_PROBE]
    run = subprocess.run(probe, cwd=API_DIR, capture_output=True, text=True, check=True)
    assert run.stdout.strip() == "False"


UNBACKED_INPUT = _with("ko", "Call now", None)
ROUTER_CASES = [
    pytest.param({}, TEXT, "ko", "model", id="valid"),
    *(
        pytest.param({"tool_input": tool_input}, question, lang, "model", id=lang)
        for lang, question, tool_input in parser_llm.EXAMPLES
    ),
    pytest.param({"error": TIMEOUT}, TEXT, "ko", "rules", id="timeout"),
    pytest.param({"tool_input": UNBACKED_INPUT}, TEXT, "ko", "rules", id="unbacked"),
]


@pytest.mark.parametrize(("answer", "text", "lang", "source"), ROUTER_CASES)
def test_parse_router_answers_from_the_model_or_the_rules(
    monkeypatch, store, sample_catalog, answer, text, lang, source
):
    parser = _parser(monkeypatch, FakeRuntime(**answer))
    client = make_client(store=store, catalog=sample_catalog, model_parser=parser)
    body = {"text": text, "lang": lang, "session_id": SESSION}
    assert client.post("/api/v1/parse", json=body).json()["source"] == source


# sent_request runs on a catalog of the variables TWO_VARIABLES.
ENUMS = [
    (("spec", "lang"), ["ko"]),
    (("spec", "intent"), [*INTENT_IDS, None]),
    (("spec", "metric", "var"), TWO_VARIABLES),
    (("spec", "metric", "id"), list(METRIC_IDS)),
    (("spec", "board"), [*(board.id for board in load_content("boards")), None]),
    (("variables", "var"), TWO_VARIABLES),
    (("variables", "metric_id"), list(METRIC_IDS)),
    (("variables", "reason_code"), [code.value for code in ReasonCode]),
    (("unavailable", "nearest_var"), [*TWO_VARIABLES, None]),
]


@pytest.mark.parametrize(("path", "ids"), ENUMS)
def test_tool_schema_enum_lists_the_catalog_ids(sent_request, path, ids):
    assert _property(sent_request, path)["enum"] == ids


REQUEST_FIELDS = [
    (("modelId",), MODEL_ID),
    (("messages", 0, "content", 0, "text"), TEXT),
    (("toolConfig", "toolChoice"), {"any": {}}),
    (("toolConfig", "tools", 0, "toolSpec", "name"), parser_llm.TOOL_NAME),
    (("inferenceConfig", "maxTokens"), parser_llm.MAX_TOKENS),
]


@pytest.mark.parametrize(("path", "expected"), REQUEST_FIELDS)
def test_request_carries_the_field(sent_request, path, expected):
    assert reduce(getitem, path, sent_request) == expected


THROTTLED = {"Error": {"Code": "ThrottlingException", "Message": "slow down"}}
TEXT_ONLY = {"role": "assistant", "content": [{"text": "서울"}]}
TEXT_ANSWER = {"output": {"message": TEXT_ONLY}, "stopReason": "end_turn"}
FAILED_ANSWERS = [
    pytest.param({"error": TIMEOUT}, id="read_timeout"),
    pytest.param({"error": ConnectTimeoutError(endpoint_url="x")}, id="connect"),
    pytest.param({"error": ClientError(THROTTLED, "Converse")}, id="client_error"),
    pytest.param({"response": TEXT_ANSWER}, id="text"),
    pytest.param({"response": _answer({"spec": {}}, "max_tokens")}, id="cut_off"),
    pytest.param({"tool_input": {"variables": []}}, id="no_spec"),
    pytest.param({"tool_input": ["a", "list"]}, id="not_a_mapping"),
    pytest.param({"tool_input": {**TOOL_INPUT, "extra": 1}}, id="extra_field"),
]


@pytest.mark.parametrize("answer", FAILED_ANSWERS)
def test_failed_model_answer_raises_the_parser_error(
    monkeypatch, sample_catalog, answer
):
    parser = _parser(monkeypatch, FakeRuntime(**answer))
    with pytest.raises(parser_llm.ModelParseError):
        parser(TEXT, "ko", sample_catalog, SESSION)


@pytest.mark.parametrize("caps", [{"llm_session_cap": 0}, {"llm_daily_budget": 0}])
def test_call_past_a_cap_raises(monkeypatch, runtime, sample_catalog, caps):
    parser = _parser(monkeypatch, runtime, **caps)
    with pytest.raises(parser_llm.ModelParseError):
        parser(TEXT, "ko", sample_catalog, SESSION)


# Two calls, the second from session; a refused call never reaches the client.
CALLS = [
    pytest.param({"llm_session_cap": 1}, SESSION, {}, 1, id="session_cap"),
    pytest.param({"llm_daily_budget": 1}, "tab-9876543210", {}, 1, id="daily_budget"),
    pytest.param({"llm_session_cap": 2}, SESSION, {}, 2, id="within_the_cap"),
    pytest.param({"llm_session_cap": 1}, SESSION, {"error": TIMEOUT}, 1, id="failed"),
]


@pytest.mark.parametrize(("caps", "session", "answer", "calls"), CALLS)
def test_client_gets_each_call_within_the_budget(
    monkeypatch, sample_catalog, caps, session, answer, calls
):
    runtime = FakeRuntime(**answer)
    parser = _parser(monkeypatch, runtime, **caps)
    with contextlib.suppress(parser_llm.ModelParseError):
        parser(TEXT, "ko", sample_catalog, SESSION)
    with contextlib.suppress(parser_llm.ModelParseError):
        parser(TEXT, "ko", sample_catalog, session)
    assert len(runtime.requests) == calls


LOGS = [
    pytest.param(TOOL_INPUT, [CALL_LINE], id="valid"),
    pytest.param(UNBACKED_INPUT, [CALL_LINE, parser_llm.UNBACKED_LINE], id="unbacked"),
]


@pytest.mark.parametrize(("tool_input", "lines"), LOGS)
def test_log_names_the_call_and_the_model_and_no_text(
    monkeypatch, sample_catalog, caplog, tool_input, lines
):
    caplog.set_level(logging.INFO, logger=parser_llm.__name__)
    parser = _parser(monkeypatch, FakeRuntime(tool_input))
    parser(TEXT, "ko", sample_catalog, SESSION)
    assert caplog.messages == lines


# User decision 3 of wave 5: a place name is a gazetteer name or whole words of the
# question, and a typed threshold is null or whole words of the question.
BACKED = [
    pytest.param(TEXT, "ko", "서울", None, id="gazetteer_name"),
    pytest.param("서울의 첫눈이 늦어지나요?", "ko", "서울", None, id="before_particle"),
    pytest.param(SEOUL_EN, "en", "BUSAN", None, id="gazetteer_name_elsewhere"),
    pytest.param(SEOUL_EN, "en", "first snow", None, id="words_of_the_question"),
    pytest.param(PHOENIX_EN, "en", "Phoenix", "110-degree", id="typed_words"),
    pytest.param(PHOENIX_KO, "ko", "피닉스", "43.3 °C", id="typed_number_and_unit"),
]
UNBACKED = [
    pytest.param(SEOUL_EN, "en", "Call 555-0100 now", None, id="name_from_nowhere"),
    pytest.param(SEOUL_EN, "en", "Seo", None, id="name_part_of_a_word"),
    pytest.param(PHOENIX_EN, "en", "Phoenix", "45 °C", id="typed_from_nowhere"),
    pytest.param(PHOENIX_EN, "en", "Phoenix", "1", id="typed_part_of_a_number"),
    pytest.param(PHOENIX_EN, "en", "Phoenix", "°", id="typed_without_a_word"),
]


@pytest.mark.parametrize(("text", "lang", "name", "typed"), BACKED)
def test_backed_place_and_threshold_give_the_proposal_mapping(
    monkeypatch, sample_catalog, text, lang, name, typed
):
    tool_input = _with(lang, name, typed)
    parser = _parser(monkeypatch, FakeRuntime(tool_input))
    assert parser(text, lang, sample_catalog, SESSION) == tool_input


@pytest.mark.parametrize(("text", "lang", "name", "typed"), UNBACKED)
def test_unbacked_place_or_threshold_gives_no_proposal(
    monkeypatch, sample_catalog, text, lang, name, typed
):
    parser = _parser(monkeypatch, FakeRuntime(_with(lang, name, typed)))
    assert parser(text, lang, sample_catalog, SESSION) is None


@pytest.fixture
def runtime_client(monkeypatch, tmp_path):
    # Dummy keys come first in the default chain and the AWS files point into
    # tmp_path; a fresh default session keeps the keys out of other tests.
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    return bedrock.make_runtime_client(Settings(parse_model_timeout_s=TIMEOUT_S))


CLIENT_FIELDS = [
    (lambda client: client.meta.service_model.service_name, "bedrock-runtime"),
    (lambda client: client.meta.region_name, "us-west-2"),
    (lambda client: client.meta.config.connect_timeout, TIMEOUT_S),
    (lambda client: client.meta.config.read_timeout, TIMEOUT_S),
    (lambda client: client.meta.config.retries["total_max_attempts"], 1),
]


@pytest.mark.parametrize(("read", "expected"), CLIENT_FIELDS)
def test_runtime_client_has_the_parse_setting(runtime_client, read, expected):
    assert read(runtime_client) == expected
