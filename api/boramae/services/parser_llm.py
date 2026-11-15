"""The model parser behind the parse seam (DES-015, TDD.md Flow A step 3, DEC-002).

With the LLM on, make_model_parser returns parse(text, lang, catalog, session_id): one
Converse call to the configured Bedrock model, counted against the session and daily
budgets (DEC-009). Its one tool takes the ParseProposal shape with every ID as an
enum, so the model returns IDs and a reason code and writes no sentence that the app
shows. parse returns that mapping, or None when the question does not back its place
name or typed threshold; a spent budget, a timeout, a client error or another answer
raises ModelParseError. The router checks the catalog, caches the proposal and falls
back to the rules (routers/parse.py). With the LLM off boto3 is never imported.
"""

import json
import logging
from collections.abc import Callable
from functools import cache
from itertools import count
from typing import TYPE_CHECKING, get_args

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from boramae.config import Settings
from boramae.constants import INTENT_IDS, MAX_PROPOSED_VARIABLES
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import (
    InvestigationMetric,
    Lang,
    Op,
    ParseProposal,
    ReasonCode,
    SpecPlace,
    Units,
)
from boramae.llm import bedrock
from boramae.llm.budget import LlmBudget
from boramae.services.content import load_content
from boramae.services.parse_cache import MODEL_SOURCE
from boramae.services.places import normalize

if TYPE_CHECKING:
    from botocore.client import BaseClient

# parse(text, lang, catalog, session_id) -> proposal. It raises on a timeout, a
# client error or a refused budget, and the parse router then runs the rules.
ModelParser = Callable[..., object]
Schema = dict[str, object]

log = logging.getLogger(__name__)

TOOL_NAME = "propose_spec"
# ponytail: no document fixes the output cap; a proposal is about 300 tokens.
MAX_TOKENS = 1024
UNBACKED_LINE = "parse: the question does not back the model's place or threshold"
NULL: Schema = {"type": "null"}
NUMBER: Schema = {"type": "number"}
MONTH: Schema = {"type": "integer", "minimum": 1, "maximum": 12}

# Raise parse_cache.PROMPT_VERSION with every change of RULES, EXAMPLES or the tool
# schema, so that no cached answer of an older prompt answers.
RULES = (
    "Read one question about a place for BORAMAE, an app that tests trends in NASA"
    f" POWER data, and call {TOOL_NAME} once. Write no other text.\n"
    "- Use only the IDs that the schema lists. Propose 1 to 3 variables, the best match"
    " first; spec.metric is the measure of the first one. reason_code: direct_match is"
    " the measure that the question asks for, closest_measure another measure of it,"
    " related_driver a driver of it, place_default a question that names only a place.\n"
    "- place.name is the place as the question writes it, without a particle or a"
    " possessive; lat and lon are its center in degrees; radius_km is 25 unless the"
    " question gives one.\n"
    "- metric.value is the threshold in the unit of the data, a converted value rounded"
    " to one decimal; metric.typed is the threshold word for word as the question"
    " writes it. display_units is imperial for a threshold in °F or inches, or for a"
    " bare number at a US place.\n"
    '- The window starts in 1981 and ends at "latest" unless the question names years.\n'
    "- Leave a slot null when neither the question nor an example sets it.\n"
    "- For a variable that the schema does not list, unavailable.requested names it as"
    " the question does and unavailable.nearest_var is the closest listed variable or"
    " null; propose that variable with the reason code nearest_available.\n"
    "Examples, each a question and its tool input:"
)
# PRD "The spec the parser fills": inputs 1 and 44 of content/catalog-inputs.json.
# ponytail: input 44 keeps its threshold as the question types it, "110-degree" where
# the PRD shows "110 °F", because decision 3 of wave 5 refuses a typed text that is not
# words of the question; its unit is the catalog unit C.
EXAMPLE_INPUTS = json.loads("""[
{"spec": {"lang": "ko", "intent": "timing",
  "place": {"name": "서울", "lat": 37.5665, "lon": 126.978, "radius_km": 25},
  "metric": {"id": "first_date", "var": "PRECSNO", "op": ">=", "value": 0.1,
    "unit": "mm/day", "typed": null, "months": null, "season_start": "08-01"},
  "display_units": null, "window": {"start": 1981, "end": "latest"},
  "compare_to": null, "board": "CB-01", "clarify": null},
 "variables": [
  {"var": "PRECSNO", "metric_id": "first_date", "reason_code": "direct_match"},
  {"var": "SNODP", "metric_id": "seasonal_mean", "reason_code": "closest_measure"}],
 "unavailable": null, "clarify": null},
{"spec": {"lang": "en", "intent": "extremes_count",
  "place": {"name": "Phoenix", "lat": 33.4484, "lon": -112.074, "radius_km": 25},
  "metric": {"id": "threshold_days", "var": "T2M_MAX", "op": ">=", "value": 43.3,
    "unit": "C", "typed": "110-degree", "months": [5, 6, 7, 8, 9, 10],
    "season_start": null},
  "display_units": "imperial", "window": {"start": 1981, "end": "latest"},
  "compare_to": null, "board": "CB-02", "clarify": null},
 "variables": [
  {"var": "T2M_MAX", "metric_id": "threshold_days", "reason_code": "direct_match"}],
 "unavailable": null, "clarify": null}
]""")
EXAMPLE_QUESTIONS = (
    "서울 첫눈이 늦어지고 있나요?",
    "Is Phoenix getting more 110-degree days?",
)
EXAMPLES: tuple[tuple[Lang, str, Schema], ...] = tuple(
    zip(("ko", "en"), EXAMPLE_QUESTIONS, EXAMPLE_INPUTS, strict=True)
)
SYSTEM_PROMPT = "\n".join(
    [RULES, *(f"{q}\n{json.dumps(i, ensure_ascii=False)}" for _, q, i in EXAMPLES)]
)


class ModelParseError(Exception):
    """The model gave no proposal: the parse router answers with the rules."""


def make_model_parser(settings: Settings) -> ModelParser | None:
    """None with the LLM off, else the model parser. deps caches it, so one budget
    counts the calls of the process (DEC-009)."""
    if not settings.llm_enabled:
        return None
    if settings.model_id is None:
        log.warning("parse: the LLM is on with no model ID, so the rules answer")
        return None
    budget = LlmBudget(settings.llm_session_cap, settings.llm_daily_budget)
    client = bedrock.make_runtime_client(settings)
    return _BedrockParser(client, settings.model_id, budget)


class _BedrockParser:
    def __init__(self, client: "BaseClient", model_id: str, budget: LlmBudget) -> None:
        self._client = client
        self._model_id = model_id
        self._budget = budget
        self._calls = count(1)

    def __call__(
        self, text: str, lang: Lang, catalog: Catalog, session_id: str
    ) -> Schema | None:
        if not self._budget.allow(session_id):
            raise ModelParseError("the session cap or the daily budget is spent")
        # The log names the call and the model, never the text (TR-Q-005).
        log.info("parse: model call %d to %s", next(self._calls), self._model_id)
        request = _request(self._model_id, text, lang, catalog)
        try:
            response = self._client.converse(**request)
        except (BotoCoreError, ClientError) as error:
            raise ModelParseError(
                f"the call failed ({type(error).__name__})"
            ) from error
        return _checked(_tool_input(response), text)


def _request(model_id: str, text: str, lang: Lang, catalog: Catalog) -> Schema:
    """The Converse request: the question as the user turn and one forced tool."""
    tool = {"name": TOOL_NAME, "inputSchema": {"json": _tool_schema(catalog, lang)}}
    return {
        "modelId": model_id,
        "system": [{"text": SYSTEM_PROMPT}],
        "messages": [{"role": "user", "content": [{"text": text}]}],
        # With one tool, "any" forces it, and more models take it than a named choice.
        "toolConfig": {"tools": [{"toolSpec": tool}], "toolChoice": {"any": {}}},
        # ponytail: no document fixes the temperature; 0 makes the answer as
        # repeatable as the model allows.
        "inferenceConfig": {"maxTokens": MAX_TOKENS, "temperature": 0},
    }


def _tool_input(response: dict) -> object:
    """The input of the tool call; a cut or text-only answer raises."""
    blocks = response["output"]["message"]["content"]
    inputs = [block["toolUse"]["input"] for block in blocks if "toolUse" in block]
    if response["stopReason"] != "tool_use" or not inputs:
        raise ModelParseError(f"no whole tool call ({response['stopReason']})")
    return inputs[0]


def _checked(tool_input: object, text: str) -> Schema | None:
    """The proposal mapping, or None when the question does not back the place name
    or the typed threshold (user decision 3 of wave 5), so that the rules answer."""
    try:
        proposal = ParseProposal.model_validate({**tool_input, "source": MODEL_SOURCE})
    except (TypeError, ValidationError) as error:
        raise ModelParseError("the tool input is not a proposal") from error
    spec = proposal.spec
    if not (_is_backed_place(spec.place, text) and _is_backed_typed(spec.metric, text)):
        log.warning(UNBACKED_LINE)
        return None
    return proposal.model_dump(mode="json", exclude={"source"})


def _is_backed_place(place: SpecPlace | None, text: str) -> bool:
    if place is None:
        return True
    return normalize(place.name) in _gazetteer_names() or _is_words_of(place.name, text)


def _is_backed_typed(metric: InvestigationMetric | None, text: str) -> bool:
    return metric is None or metric.typed is None or _is_words_of(metric.typed, text)


def _is_words_of(phrase: str, text: str) -> bool:
    """True when the words of phrase stand in a row in text. normalize turns each run
    of other characters into one space, so the padded test never matches a part of a
    word (accepted item 3 of wave 4)."""
    words = normalize(phrase)
    return bool(words) and f" {words} " in f" {normalize(text)} "


@cache
def _gazetteer_names() -> frozenset[str]:
    """Every gazetteer name in both languages and every alt name, normalized."""
    names = (
        normalize(name)
        for place in load_content("gazetteer")
        for name in (place.name.en, place.name.ko, *place.alt)
    )
    return frozenset(names) - {""}


def _tool_schema(catalog: Catalog, lang: Lang) -> Schema:
    """The ParseProposal shape without source, which the router sets. Every ID is an
    enum of the catalog, INTENT_IDS, the reason codes or the boards (TDD.md Flow A)."""
    var_ids = [item.id for item in catalog.variables]
    metric_ids = [item.id for item in catalog.metrics]
    boards = load_content("boards")
    focus = "; ".join(
        f"{board.id} "
        + ", ".join(f"{item.var} {item.metric_id}" for item in board.focus)
        for board in boards
    )
    var_names = "; ".join(f"{v.id} {v.name.en} ({v.unit})" for v in catalog.variables)
    metric_names = "; ".join(f"{m.id} {m.name.en}" for m in catalog.metrics)
    variable = _object(
        var={"enum": var_ids, "description": var_names},
        metric_id={"enum": metric_ids, "description": metric_names},
        reason_code={"enum": [code.value for code in ReasonCode]},
    )
    metric = _object(
        id={"enum": metric_ids},
        var={"enum": var_ids},
        op={"enum": [*get_args(Op), None]},
        value={"type": ["number", "null"], "description": "In the unit of the data"},
        unit={"type": ["string", "null"]},
        typed={"type": ["string", "null"], "description": "Word for word as typed"},
        months={"type": ["array", "null"], "items": MONTH},
        season_start={"type": ["string", "null"], "description": "MM-DD"},
    )
    place = _object(name={"type": "string"}, lat=NUMBER, lon=NUMBER, radius_km=NUMBER)
    spec = _object(
        lang={"enum": [lang]},
        intent={"enum": [*INTENT_IDS, None]},
        place=_nullable(place),
        metric=_nullable(metric),
        display_units={"enum": [*get_args(Units), None]},
        window=_object(start={"type": "integer"}, end={"type": ["integer", "string"]}),
        compare_to=NULL,
        board={
            "enum": [*(board.id for board in boards), None],
            "description": f"The board whose focus holds the metric: {focus}",
        },
        clarify=NULL,
    )
    unavailable = _object(
        requested={"type": "string"}, nearest_var={"enum": [*var_ids, None]}
    )
    return _object(
        spec=spec,
        variables={
            "type": "array",
            "maxItems": MAX_PROPOSED_VARIABLES,
            "items": variable,
        },
        unavailable=_nullable(unavailable),
        clarify=NULL,
    )


def _object(**properties: object) -> Schema:
    """A closed object whose every property is required; null marks an empty slot."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable(schema: Schema) -> Schema:
    return {**schema, "type": [schema["type"], "null"]}
