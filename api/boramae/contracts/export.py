"""Writes the generated side of the contract. Run: python -m boramae.contracts.export

- web/src/contracts/schema.json holds the JSON Schema of every contract record.
  The script gen:contracts of web/ turns it into TypeScript types.
- Each sample fixture of api/tests/fixtures is checked against its model and
  written in one form to api/tests/fixtures and to web/src/test/fixtures. Edit a
  sample in api/tests/fixtures, then run this command.
- content/golden/request-spec.json holds request specs with their encoded form,
  for the Python codec and the TypeScript codec.
"""

import functools
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, models_json_schema
from pydantic_core import CoreSchema

from boramae.contracts import (
    agent,
    http,
    results,
    results_board,
    results_catalog,
    results_scan,
    spec,
)
from boramae.contracts.agent import ToolResultMessage, UserMessage
from boramae.contracts.results import TrendResult
from boramae.contracts.results_board import CaseBoard
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.results_scan import ScanResult
from boramae.contracts.spec import (
    SPEC_VERSION,
    ContractModel,
    ParseProposal,
    RequestSpec,
    canonical_json,
    encode_request_spec,
)

API_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = API_DIR.parent
API_FIXTURES_DIR = API_DIR / "tests/fixtures"
WEB_FIXTURES_DIR = REPO_DIR / "web/src/test/fixtures"
SCHEMA_PATH = REPO_DIR / "web/src/contracts/schema.json"
GOLDEN_PATH = REPO_DIR / "content/golden/request-spec.json"
SCHEMA_TITLE = "BoramaeContract"
CONTENT_MODULE = "boramae.contracts.content"
OWN_MODULES = (spec, results_catalog, results, results_board, results_scan, agent, http)

FIXTURE_MODELS: dict[str, type[ContractModel]] = {
    "catalog.sample.json": Catalog,
    "parse.input-1.ko.sample.json": ParseProposal,
    "parse.input-1.en.sample.json": ParseProposal,
    "trend.significant.sample.json": TrendResult,
    "trend.not-yet.sample.json": TrendResult,
    "trend.zero-inside.sample.json": TrendResult,
    "trend.no-trend.sample.json": TrendResult,
    "trend.too-short.sample.json": TrendResult,
    "trend.no-data.sample.json": TrendResult,
    "caseboard.sample.json": CaseBoard,
    "scan.nearby.sample.json": ScanResult,
    "scan.note.sample.json": ScanResult,
    "agent.user.sample.json": UserMessage,
    "agent.tool-result.sample.json": ToolResultMessage,
}
# Its model, DemoManifest, belongs to contracts/content.py.
MANIFEST_FIXTURE = "manifest.sample.json"

_SEOUL = {"lat": 37.5665, "lon": 126.978, "radius_km": 25}
_PHOENIX = {"lat": 33.4484, "lon": -112.074, "radius_km": 25}
_FULL_RECORD = {"start": 1981, "end": "latest"}
_FIRST_SNOW = {
    "id": "first_date",
    "threshold": "0.1",
    "op": ">=",
    "season_start": "08-01",
}
_WETTEST_DAY = {"id": "rx1day", "months": [6, 7, 8, 9]}
_HOT_DAYS = {
    "id": "threshold_days",
    "threshold": "43.3",
    "op": ">=",
    "months": [5, 6, 7, 8, 9, 10],
}
# The codec keeps a spec as typed: months stay unsorted and '-10' stays as written.
_COLD_DAYS = {
    "id": "threshold_days",
    "threshold": "-10",
    "op": "<",
    "months": [12, 1, 2],
}
_ANNUAL_MEAN = {"id": "annual_mean"}
_MAP_VIEW = {"west": 124.5, "south": 33, "east": 131.875, "north": 38.75}
_WHOLE_NUMBER_PIN = {"lat": 35, "lon": 139, "radius_km": 10}
_GOLDEN_CASES = (
    ("trend", "PRECSNO", _FIRST_SNOW, _SEOUL, _FULL_RECORD),
    ("caseboard", "PRECSNO", _FIRST_SNOW, _SEOUL, _FULL_RECORD),
    ("trend", "PRECTOTCORR", _WETTEST_DAY, _SEOUL, _FULL_RECORD),
    ("scan", "PRECTOTCORR", _WETTEST_DAY, _SEOUL, _FULL_RECORD),
    ("trend", "T2M_MAX", _HOT_DAYS, _PHOENIX, _FULL_RECORD),
    ("trend", "T2M", _ANNUAL_MEAN, _WHOLE_NUMBER_PIN, _FULL_RECORD),
    ("trend", "T2M", _ANNUAL_MEAN, _MAP_VIEW, {"start": 1991, "end": 2020}),
    (
        "trend",
        "T2M_MIN",
        _COLD_DAYS,
        {"lat": 37.75, "lon": 128.875, "radius_km": 150.5},
        {"start": 1981, "end": 2025},
    ),
)


class _NoFieldTitles(GenerateJsonSchema):
    """A field title would become one more named TypeScript type for each field."""

    def field_title_should_be_set(self, schema: CoreSchema) -> bool:
        return False


def build_schema() -> dict:
    """The JSON Schema of every record of the contract modules, under $defs."""
    records = [
        (value, "validation")
        for module in _contract_modules()
        for value in vars(module).values()
        if _is_record_of(value, module)
    ]
    _, schema = models_json_schema(
        records, schema_generator=_NoFieldTitles, title=SCHEMA_TITLE
    )
    return _for_typescript(schema)


def golden_vectors() -> list[dict]:
    """Each vector holds the object behind the string, so a codec that sorts the
    keys and prints no spaces reproduces it with no further rule."""
    specs = [
        RequestSpec(
            v=SPEC_VERSION, kind=kind, var=var, metric=metric, area=area, window=window
        )
        for kind, var, metric, area, window in _GOLDEN_CASES
    ]
    return [
        {"spec": json.loads(canonical_json(item)), "s": encode_request_spec(item)}
        for item in specs
    ]


def dump_fixture(record: ContractModel) -> str:
    return _dump_pretty(record.model_dump(mode="json"))


def main() -> int:
    _write(SCHEMA_PATH, _dump_pretty(build_schema()))
    for name, model in FIXTURE_MODELS.items():
        source = (API_FIXTURES_DIR / name).read_bytes()
        _write_fixture(name, dump_fixture(model.model_validate_json(source)))
    manifest = json.loads((API_FIXTURES_DIR / MANIFEST_FIXTURE).read_bytes())
    content = _load_content()
    if content is not None:
        content.DemoManifest.model_validate(manifest)
    _write_fixture(MANIFEST_FIXTURE, _dump_pretty(manifest))
    _write(GOLDEN_PATH, _dump_pretty(golden_vectors()))
    sys.stdout.write(
        f"export wrote the schema, {len(FIXTURE_MODELS) + 1} fixtures in two folders "
        f"and {len(_GOLDEN_CASES)} golden vectors\n"
    )
    return 0


def _contract_modules() -> list[ModuleType]:
    content = _load_content()
    return [*OWN_MODULES, *([] if content is None else [content])]


@functools.cache
def _load_content() -> ModuleType | None:
    try:
        return importlib.import_module(CONTENT_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != CONTENT_MODULE:
            raise
        sys.stdout.write(
            f"note: {CONTENT_MODULE} is not there yet; its models are skipped\n"
        )
        return None


def _is_record_of(value: object, module: ModuleType) -> bool:
    return (
        isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == module.__name__
        and bool(value.model_fields)
    )


def _for_typescript[Node](node: Node) -> Node:
    """Fit the schema to json-schema-to-typescript.

    It reads a tuple from 'items', not from 'prefixItems'. It turns a list with
    length bounds into a union of tuples, which no plain array fits, so a list
    keeps its bounds only when they fix one length.
    """
    if isinstance(node, list):
        return [_for_typescript(value) for value in node]
    if not isinstance(node, dict):
        return node
    has_fixed_length = "minItems" in node and node["minItems"] == node.get("maxItems")
    return {
        ("items" if key == "prefixItems" else key): _for_typescript(value)
        for key, value in node.items()
        if has_fixed_length or key not in ("minItems", "maxItems")
    }


def _dump_pretty(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _write_fixture(name: str, text: str) -> None:
    _write(API_FIXTURES_DIR / name, text)
    _write(WEB_FIXTURES_DIR / name, text)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
