"""The catalog suite in rules mode: every catalog string through POST /api/v1/parse.

The run has no model parser and reads the real gazetteer, keywords and boards. It
writes content/evidence/catalog-suite.rules.json. The keyword fallback has no pass
threshold (TRD Q-26), and the 54 of 60 target belongs to the LLM-on run (TR-F-006), so
these tests check that the report is complete and leave its pass count to the report.
"""

import json

import pytest

from boramae.contracts.content import ExpectedSpec
from boramae.services.content import content_dir, load_content
from tests.fakes import make_client
from tests.suites.catalog_suite_lib import run_suite, seed_catalog

PARSE_PATH = "/api/v1/parse"
SESSION = "catalog-suite-rules"
REPORT_PATH = content_dir() / "evidence" / "catalog-suite.rules.json"
CATALOG_STRINGS = 120
LANGS = ("ko", "en")
# Every field that an expected outcome holds (build plan W5-E2E-API step 4, user
# decision 7 of wave 5): a spec row also holds the intent, place and board of its row.
SPEC_FIELDS = {
    "var",
    "metric_id",
    "intent",
    "place",
    "months",
    "threshold",
    "op",
    "window_start",
    "board",
}
REPLY_FIELDS = {"reply", "nearest_var"}
INPUTS = load_content("inputs")
EXPECTED_FIELDS = {
    (item.id, lang): SPEC_FIELDS
    if isinstance(item.expected, ExpectedSpec)
    else REPLY_FIELDS
    for item in INPUTS.inputs
    for lang in LANGS
}
EDGE_CASE_IDS = [case.id for case in INPUTS.edge_cases]
# User decision 7 of wave 5: their board lists no focus of their pair at P0.
KNOWN_BOARD_GAPS = {2, 3, 4, 6, 7, 26, 42}


def _parse_through(client):
    def parse(text, lang):
        answer = client.post(
            PARSE_PATH, json={"text": text, "lang": lang, "session_id": SESSION}
        )
        answer.raise_for_status()
        return answer.json()

    return parse


def _empty_proposal(text, lang):
    """A proposal with no variable and every slot of the spec empty."""
    return {
        "spec": {
            "lang": lang,
            "intent": None,
            "place": None,
            "metric": None,
            "window": {"start": 1981, "end": "latest"},
            "compare_to": None,
            "board": None,
            "clarify": None,
        },
        "variables": [],
        "source": "rules",
        "unavailable": None,
        "clarify": None,
    }


def _compared(report):
    return {
        (result["input_id"], result["lang"]): set(result["compared"])
        for result in report["results"]
    }


def _passed_langs(report, input_id):
    return {
        result["lang"]: result["passed"]
        for result in report["results"]
        if result["input_id"] == input_id
    }


def _proposed_vars(client, text, lang):
    return {item["var"] for item in _parse_through(client)(text, lang)["variables"]}


@pytest.fixture(scope="module")
def client():
    return make_client(catalog=seed_catalog())


@pytest.fixture(scope="module")
def report(client):
    return run_suite(_parse_through(client), REPORT_PATH)


def test_report_holds_a_result_for_each_catalog_string(report):
    assert len(report["results"]) == CATALOG_STRINGS


def test_each_string_compares_every_field_of_its_expected_outcome(report):
    assert _compared(report) == EXPECTED_FIELDS


def test_report_file_holds_the_report(report):
    assert json.loads(REPORT_PATH.read_text(encoding="utf-8")) == report


def test_report_lists_the_edge_cases_as_not_run(report):
    assert report["edge_cases"]["not_run"] == EDGE_CASE_IDS


def test_report_marks_the_known_board_gaps(report):
    assert KNOWN_BOARD_GAPS <= set(report["board_gaps"]["pair_not_a_board_focus"])


def test_input_1_passes_in_both_languages(report):
    assert _passed_langs(report, 1) == {"ko": True, "en": True}


def test_suite_passes_no_string_for_an_empty_proposal(tmp_path):
    assert run_suite(_empty_proposal, tmp_path / "empty.json")["passed_strings"] == 0


# TR-F-005: with the LLM off, each keyword alone yields its variable.
@pytest.mark.parametrize(
    ("text", "lang", "variables"),
    [
        ("첫눈", "ko", {"PRECSNO"}),  # snowfall
        ("폭염", "ko", {"T2M_MAX"}),  # hot days
        ("가뭄", "ko", {"PRECTOTCORR", "GWETROOT"}),  # precipitation, soil wetness
        ("snowpack", "en", {"SNODP"}),  # snow depth
        ("downpour", "en", {"PRECTOTCORR"}),  # heavy-rain days
    ],
)
def test_keyword_yields_its_variable(client, text, lang, variables):
    assert variables <= _proposed_vars(client, text, lang)
