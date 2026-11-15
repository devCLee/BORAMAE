"""The catalog suite: each catalog string through a parse function (TR-F-005, TR-F-006).

run_suite(parse_fn, out_path) is shared by the rules run of test_catalog_suite.py and
the LLM-on run of wave 6. parse_fn(text, lang) returns the JSON body of POST
/api/v1/parse. A string passes when every field of its expected outcome in
content/catalog-inputs.json matches, and an input passes when both of its strings pass
(TRD Q-15). The edge cases E1 to E20 need scripted replies (FR-29, FR-31, P1), so the
report lists them as not run.
"""

import json
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path
from typing import Any

from boramae.batch.build_catalog import build_catalog
from boramae.contracts.content import CatalogInput, ExpectedReply, ExpectedSpec
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import Lang, ParseProposal
from boramae.ports import Freq
from boramae.services.content import load_content
from tests.fakes import FakeReader

ParseFn = Callable[[str, Lang], Mapping[str, Any]]

LANGS: tuple[Lang, ...] = ("ko", "en")
NOT_IN_THIS_VERSION = "not_in_this_version"
# ponytail: a null window_start means the row names no start year, so the spec must
# hold the PRD default, the full record from 1981 (PRD "User flows"); no document
# states this reading of null.
DEFAULT_START = 1981
COUNTING_RULE = "An input passes when both of its strings pass (TRD Q-15)."
NOT_COMPARED = {
    "supported": "It marks whether the engine holds a reducer for the expected "
    "metric. A parse names no such field, and metric_id covers the metric.",
}
EDGE_CASES_REASON = "The edge cases need scripted replies, which are P1 (FR-29, FR-31)."
SAMPLE_CATALOG = (
    Path(__file__).resolve().parents[1] / "fixtures" / "catalog.sample.json"
)


def run_suite(parse_fn: ParseFn, out_path: Path) -> dict[str, Any]:
    """Parse every ko and en catalog string, write the report to out_path, return it."""
    content = load_content("inputs")
    results = [
        _string_result(item, lang, parse_fn(getattr(item.text, lang), lang))
        for item in content.inputs
        for lang in LANGS
    ]
    failing_inputs = sorted(
        {item["input_id"] for item in results if not item["passed"]}
    )
    report = {
        "counting_rule": COUNTING_RULE,
        "inputs": len(content.inputs),
        "passed_inputs": len(content.inputs) - len(failing_inputs),
        "strings": len(results),
        "passed_strings": sum(item["passed"] for item in results),
        "failing_inputs": failing_inputs,
        "board_gaps": _board_gaps(content.inputs),
        "not_compared": NOT_COMPARED,
        "edge_cases": {
            "not_run": [case.id for case in content.edge_cases],
            "reason": EDGE_CASES_REASON,
        },
        "results": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    return report


@cache
def seed_catalog() -> Catalog:
    """The catalog that build-catalog makes from content/catalog.seed.json, on fake
    stores that report the units, dataset IDs and versions of the sample catalog.

    FakeReader alone reports the unit '1', and the rules read a typed °F, °C, mm or
    inch threshold only against the POWER units C and mm/day (parser_terms.py).
    """
    sample = Catalog.model_validate_json(SAMPLE_CATALOG.read_bytes())

    def identity(freq: Freq) -> tuple[str, str]:
        dataset = getattr(sample.datasets, freq)
        return dataset.dataset_id, dataset.dataset_version

    seed = load_content("catalog_seed")
    return build_catalog(_SampleUnits(sample), seed, identity)[0]


class _SampleUnits(FakeReader):
    def __init__(self, sample: Catalog) -> None:
        super().__init__()
        self.sample = sample

    def variables(self, freq: Freq) -> dict[str, str]:
        return {var.id: var.unit for var in self.sample.variables if freq in var.stores}


def _board_gaps(inputs: list[CatalogInput]) -> dict[str, list[int]]:
    """Spec rows whose expected board this version cannot open for their expected
    pair, from the content alone: a board opens only for a (var, metric_id) of its
    focus (services/caseboard.py), and only a board of content/boards.json exists."""
    focus = {
        board.id: {(item.var, item.metric_id) for item in board.focus}
        for board in load_content("boards")
    }
    rows = [
        item
        for item in inputs
        if isinstance(item.expected, ExpectedSpec) and item.board is not None
    ]
    return {
        "board_not_in_this_version": [
            item.id for item in rows if item.board not in focus
        ],
        "pair_not_a_board_focus": [
            item.id
            for item in rows
            if item.board in focus
            and (item.expected.var, item.expected.metric_id) not in focus[item.board]
        ],
    }


def _string_result(
    item: CatalogInput, lang: Lang, body: Mapping[str, Any]
) -> dict[str, Any]:
    proposal = ParseProposal.model_validate(body)
    expected, got = _expected(item, lang), _got(proposal)
    failing = {
        name: {"expected": value, "got": got[name]}
        for name, value in expected.items()
        if got[name] != value
    }
    return {
        "input_id": item.id,
        "lang": lang,
        "text": getattr(item.text, lang),
        "source": proposal.source,
        "passed": not failing,
        "compared": list(expected),
        "failing": failing,
    }


def _expected(item: CatalogInput, lang: Lang) -> dict[str, Any]:
    """The fields of the expected outcome, in the form that _got gives them."""
    expected = item.expected
    if isinstance(expected, ExpectedReply):
        return {"reply": expected.reply, "nearest_var": expected.nearest_var}
    return {
        "var": expected.var,
        "metric_id": expected.metric_id,
        "intent": item.intent,
        # ponytail: the place compares by its name in the language of the string, so
        # the right place under another name fails. Compare the gazetteer row or the
        # coordinates if a model answers alt names.
        "place": item.place and getattr(item.place.name, lang),
        "months": _month_set(expected.months),
        "threshold": None if expected.threshold is None else float(expected.threshold),
        "op": expected.op,
        "window_start": expected.window_start or DEFAULT_START,
        "board": item.board,
    }


def _got(proposal: ParseProposal) -> dict[str, Any]:
    """Every compared field of a proposal; var and metric_id of its first variable."""
    spec, unavailable = proposal.spec, proposal.unavailable
    metric = spec.metric
    first = proposal.variables[0] if proposal.variables else None
    return {
        "var": first and first.var,
        "metric_id": first and first.metric_id,
        "intent": spec.intent,
        "place": spec.place and spec.place.name,
        "months": _month_set(metric and metric.months),
        "threshold": metric and metric.value,
        "op": metric and metric.op,
        "window_start": spec.window.start,
        "board": spec.board,
        "reply": NOT_IN_THIS_VERSION if unavailable else None,
        "nearest_var": unavailable and unavailable.nearest_var,
    }


def _month_set(months: list[int] | None) -> list[int] | None:
    """Months in a sorted, single form: the canonical spec sorts them too."""
    return None if months is None else sorted(set(months))
