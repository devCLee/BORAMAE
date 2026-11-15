"""Contract tests of the API records (docs/BUILD_CONTRACT.md)."""

import base64
import json
import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from boramae.contracts.agent import (
    ClientMessage,
    FinalMessage,
    ToolResultMessage,
    UserMessage,
)
from boramae.contracts.content import DemoManifest, ManifestCase
from boramae.contracts.export import (
    FIXTURE_MODELS,
    MANIFEST_FIXTURE,
    build_schema,
    dump_fixture,
)
from boramae.contracts.http import Problem
from boramae.contracts.results import StatsRecord, TrendResult
from boramae.contracts.results_board import CaseBoard
from boramae.contracts.results_scan import ScanResult, TrendGrid
from boramae.contracts.spec import (
    CanonicalSpec,
    InvestigationSpec,
    ParseProposal,
    RequestSpec,
    canonical_json,
    decode_request_spec,
    encode_request_spec,
)
from boramae.engine.types import MkResult
from boramae.errors import ProblemError

REPO = Path(__file__).resolve().parents[3]
API_FIXTURES = REPO / "api/tests/fixtures"
WEB_FIXTURES = REPO / "web/src/test/fixtures"
GOLDEN_VECTORS = json.loads(
    (REPO / "content/golden/request-spec.json").read_text(encoding="utf-8")
)
MANIFEST = json.loads((API_FIXTURES / MANIFEST_FIXTURE).read_text(encoding="utf-8"))
MANIFEST_SPECS = [
    entry["s"] for case in MANIFEST["cases"] for entry in case["kinds"].values()
]
BOARD_CASE = MANIFEST["cases"][0]
BOARD_SAMPLE = json.loads(
    (API_FIXTURES / "caseboard.sample.json").read_text(encoding="utf-8")
)
BOARD_NODE_KEYS = {
    node["trend_key"] for node in BOARD_SAMPLE["nodes"] if node["trend_key"]
}
SPEC_FIXTURES = sorted(
    name
    for name in FIXTURE_MODELS
    if name.split(".")[0] in {"trend", "caseboard", "scan"}
)
TREND_SAMPLE = "trend.significant.sample.json"
PRD_SPECS = ["prd/spec.input-1.json", "prd/spec.input-44.json"]
# Names that would make two requests for one key store unequal bodies (TR-D-010).
REQUEST_FACT_NAME = re.compile(
    r"tim(e|ing)|cache|creat|fetched|elapsed|request_id|containing"
)

EXPLORE_CLICK = {
    "v": 1,
    "kind": "trend",
    "var": "T2M",
    "metric": {"id": "annual_mean"},
    "area": {"lat": 35.0, "lon": 139.0, "radius_km": 10.0},
    "window": {"start": 1981, "end": "latest"},
}
EXPLORE_CLICK_JSON = (
    '{"area":{"lat":35,"lon":139,"radius_km":10},"kind":"trend",'
    '"metric":{"id":"annual_mean"},"v":1,"var":"T2M",'
    '"window":{"end":"latest","start":1981}}'
)


def read_fixture(name: str) -> str:
    return (API_FIXTURES / name).read_text(encoding="utf-8")


def decode_text(s: str) -> str:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8")


def leaf_types(value: object) -> set[type]:
    if isinstance(value, dict):
        return set().union(*(leaf_types(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(leaf_types(item) for item in value))
    return {type(value)}


def property_names(schema: dict) -> set[str]:
    records = [schema, *schema.get("$defs", {}).values()]
    return {name for record in records for name in record.get("properties", {})}


@pytest.mark.parametrize("name", PRD_SPECS)
def test_prd_spec_example_loads_as_investigation_spec(name):
    data = json.loads(read_fixture(name))
    spec = InvestigationSpec.model_validate(data)
    assert spec.model_dump(exclude_unset=True) == data


@pytest.mark.parametrize("vector", GOLDEN_VECTORS, ids=lambda vector: vector["s"][:12])
def test_request_spec_round_trips_through_base64url_json(vector):
    spec = RequestSpec.model_validate(vector["spec"])
    assert decode_request_spec(encode_request_spec(spec)) == spec


@pytest.mark.parametrize("vector", GOLDEN_VECTORS, ids=lambda vector: vector["s"][:12])
def test_golden_vector_encodes_to_its_string(vector):
    assert (
        encode_request_spec(RequestSpec.model_validate(vector["spec"])) == vector["s"]
    )


@pytest.mark.parametrize("vector", GOLDEN_VECTORS, ids=lambda vector: vector["s"][:12])
def test_golden_string_uses_the_url_safe_alphabet_without_padding(vector):
    assert re.fullmatch(r"[A-Za-z0-9_-]+", vector["s"])


@pytest.mark.parametrize("vector", GOLDEN_VECTORS, ids=lambda vector: vector["s"][:12])
def test_golden_spec_is_the_object_that_its_string_holds(vector):
    assert json.loads(decode_text(vector["s"])) == vector["spec"]


def test_encoded_spec_is_sorted_compact_json_without_nulls_in_javascript_number_form():
    spec = RequestSpec.model_validate(EXPLORE_CLICK)
    assert decode_text(encode_request_spec(spec)) == EXPLORE_CLICK_JSON


@pytest.mark.parametrize(
    "s",
    ["%%%", "e30", "bm90IGpzb24", "한글"],
    ids=["bad-alphabet", "empty-object", "not-json", "not-ascii"],
)
def test_decoding_a_malformed_string_raises_value_error(s):
    with pytest.raises(ValueError):
        decode_request_spec(s)


def test_unknown_field_is_an_error():
    with pytest.raises(ValidationError):
        RequestSpec.model_validate({**EXPLORE_CLICK, "cells": [[255, 491]]})


@pytest.mark.parametrize("record", [TrendResult, CaseBoard, ScanResult, TrendGrid])
def test_stored_record_has_no_request_fact_field(record):
    names = property_names(record.model_json_schema())
    assert sorted(filter(REQUEST_FACT_NAME.search, names)) == []


@pytest.mark.parametrize("name", sorted(FIXTURE_MODELS))
def test_sample_fixture_validates_against_its_model(name):
    text = read_fixture(name)
    assert dump_fixture(FIXTURE_MODELS[name].model_validate_json(text)) == text


@pytest.mark.parametrize("name", [*sorted(FIXTURE_MODELS), MANIFEST_FIXTURE])
def test_web_fixture_equals_the_api_fixture(name):
    assert (WEB_FIXTURES / name).read_bytes() == (API_FIXTURES / name).read_bytes()


@pytest.mark.parametrize("s", MANIFEST_SPECS)
def test_manifest_sample_holds_a_decodable_request_spec(s):
    assert encode_request_spec(decode_request_spec(s)) == s


def test_manifest_sample_validates_against_its_model():
    manifest = DemoManifest.model_validate(MANIFEST)
    assert manifest.model_dump(mode="json") == MANIFEST


def test_manifest_case_lists_the_trend_file_of_every_board_node():
    assert BOARD_NODE_KEYS <= set(BOARD_CASE["referenced"]["trend"])


def test_manifest_case_without_its_referenced_files_is_an_error():
    case = {name: value for name, value in BOARD_CASE.items() if name != "referenced"}
    with pytest.raises(ValidationError):
        ManifestCase.model_validate(case)


@pytest.mark.parametrize("name", SPEC_FIXTURES)
def test_every_leaf_of_a_canonical_spec_is_an_integer_or_a_string(name):
    spec = CanonicalSpec.model_validate(json.loads(read_fixture(name))["spec"])
    assert leaf_types(json.loads(canonical_json(spec))) <= {int, str}


def test_serializing_a_result_that_holds_a_nan_raises():
    result = TrendResult.model_validate_json(read_fixture(TREND_SAMPLE))
    broken = result.model_copy(update={"sd": float("nan")})
    with pytest.raises(ValueError):
        broken.to_json_bytes()


def test_validating_a_result_that_holds_a_nan_raises():
    data = {**json.loads(read_fixture(TREND_SAMPLE)), "sd": float("nan")}
    with pytest.raises(ValidationError):
        TrendResult.model_validate(data)


def test_validating_an_engine_instance_that_holds_a_nan_raises():
    stats = json.loads(read_fixture(TREND_SAMPLE))["stats"]
    nan_mk = MkResult(**{**stats["mk"], "p": float("nan")})
    with pytest.raises(ValidationError):
        StatsRecord.model_validate({**stats, "mk": nan_mk})


def test_tool_result_takes_only_json_values():
    data = json.loads(read_fixture("agent.tool-result.sample.json"))
    with pytest.raises(ValidationError):
        ToolResultMessage.model_validate({**data, "result": {"area": {1.5, 2.5}}})


def test_stored_form_is_strict_json_with_sorted_keys():
    result = TrendResult.model_validate_json(read_fixture(TREND_SAMPLE))
    stored = json.loads(result.to_json_bytes())
    assert (
        json.dumps(
            stored, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        == result.to_json_bytes()
    )


def test_trend_result_without_a_verdict_needs_a_reason():
    data = {**json.loads(read_fixture("trend.no-data.sample.json")), "reason": None}
    with pytest.raises(ValidationError):
        TrendResult.model_validate(data)


def test_trend_result_with_a_verdict_takes_no_reason():
    data = {**json.loads(read_fixture(TREND_SAMPLE)), "reason": "no_data"}
    with pytest.raises(ValidationError):
        TrendResult.model_validate(data)


def test_parse_proposal_takes_at_most_three_variables():
    data = json.loads(read_fixture("parse.input-1.ko.sample.json"))
    data["variables"] = data["variables"][:1] * 4
    with pytest.raises(ValidationError):
        ParseProposal.model_validate(data)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("agent.user.sample.json", UserMessage),
        ("agent.tool-result.sample.json", ToolResultMessage),
    ],
)
def test_client_message_parses_by_its_type(name, expected):
    message = TypeAdapter(ClientMessage).validate_json(read_fixture(name))
    assert type(message) is expected


def test_final_message_has_no_withheld_list():
    assert "withheld" not in FinalMessage.model_fields


@pytest.mark.parametrize(
    "detail", [None, "POWER did not answer"], ids=["bare", "detail"]
)
def test_problem_model_accepts_the_body_of_a_problem_error(detail):
    body = ProblemError(503, "power_unavailable", detail=detail).to_body()
    assert Problem.model_validate(body).code == "power_unavailable"


def test_schema_names_every_record_of_the_contract():
    expected = {
        "InvestigationSpec",
        "ParseRequest",
        "ParseProposal",
        "RequestSpec",
        "CanonicalSpec",
        "Catalog",
        "TrendResult",
        "CaseBoard",
        "ScanResult",
        "TrendGrid",
        "UserMessage",
        "ToolResultMessage",
        "DeltaMessage",
        "ToolCallMessage",
        "FinalMessage",
        "ErrorMessage",
        "Problem",
    }
    assert expected <= set(build_schema()["$defs"])


def test_schema_has_no_keyword_that_the_typescript_generator_ignores():
    assert "prefixItems" not in json.dumps(build_schema())


def test_schema_keeps_the_length_of_a_list_only_when_it_is_fixed():
    # The generator turns 1 to 12 months into a union of 12 tuple types.
    assert "maxItems" not in json.dumps(build_schema()["$defs"]["SpecMetric"])


def test_schema_keeps_the_fixed_length_of_a_cell_index():
    cells = build_schema()["$defs"]["CanonicalSpec"]["properties"]["cells"]
    assert cells["items"]["maxItems"] == 2


def test_schema_gives_every_record_its_own_short_name():
    # Two records with one class name get module-qualified names with '__'.
    assert sorted(filter(lambda name: "__" in name, build_schema()["$defs"])) == []
