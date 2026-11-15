"""content/registry.json and content/boards.json: the cited arrows of the P0 boards
CB-01, CB-02 and CB-07 and of CB-03, which demo 2 needs (TRD R-02)."""

from pathlib import Path

import pytest

from boramae.batch.lint_content import cross_check, lint
from boramae.constants import MAX_BOARD_DRIVERS, MAX_BOARD_RESPONSES
from boramae.services.content import CONTENT_FILES, read_content

ROOT = Path(__file__).parents[3]
CONTENT = ROOT / "content"
LINT_NAMES = ["registry", "boards"]
PRD_TEXT = (ROOT / "PRD.md").read_text(encoding="utf-8")
LINKS = read_content(
    CONTENT / CONTENT_FILES["registry"][0], CONTENT_FILES["registry"][1]
)
BOARDS = read_content(CONTENT / CONTENT_FILES["boards"][0], CONTENT_FILES["boards"][1])
LINK_BY_ID = {link.id: link for link in LINKS}
BOARD_BY_ID = {board.id: board for board in BOARDS}
NOT_TESTABLE = "not_testable_here"
# Metrics with a reducer by the end of wave 3 (build plan W3-REGISTRY).
WAVE3_METRICS = {
    "annual_mean",
    "annual_total",
    "seasonal_mean",
    "seasonal_total",
    "first_date",
    "threshold_days",
    "rx1day",
    "season_onset",
    "season_length",
    "degree_days",
    "frost_free_length",
}


def _testable(link_ids):
    return [LINK_BY_ID[i] for i in link_ids if LINK_BY_ID[i].status != NOT_TESTABLE]


def _focus(board):
    return {(focus.var, focus.metric_id) for focus in board.focus}


FOCUS_PAIRS = [pair for board in BOARDS for pair in _focus(board)]
BOARD_LINK_IDS = {i for board in BOARDS for i in board.drivers + board.responses}
TESTABLE_LINKS = [link for link in LINKS if link.status != NOT_TESTABLE]
DRIVER_CASES = [(board, link) for board in BOARDS for link in _testable(board.drivers)]
RESPONSE_CASES = [
    (board, link) for board in BOARDS for link in _testable(board.responses)
]
DOIS = sorted({link.doi for link in LINKS if link.doi})


def _case_id(case):
    return getattr(case, "id", None)


def test_lint_finds_no_error():
    valid, errors, _ = lint(CONTENT, LINT_NAMES)
    assert errors + cross_check(valid) == []


def test_lint_checks_both_files():
    _, _, checked = lint(CONTENT, LINT_NAMES)
    assert checked == len(LINT_NAMES)


def test_boards_are_the_p0_boards_and_cb03():
    assert [board.id for board in BOARDS] == ["CB-01", "CB-02", "CB-03", "CB-07"]


@pytest.mark.parametrize("board", BOARDS, ids=_case_id)
def test_board_has_at_most_3_drivers(board):
    assert len(board.drivers) <= MAX_BOARD_DRIVERS


@pytest.mark.parametrize("board", BOARDS, ids=_case_id)
def test_board_has_at_most_3_responses(board):
    assert len(board.responses) <= MAX_BOARD_RESPONSES


@pytest.mark.parametrize("doi", DOIS)
def test_doi_appears_verbatim_in_the_prd(doi):
    assert f"(https://doi.org/{doi})" in PRD_TEXT


def test_cb03_holds_a_testable_arrow():
    board = BOARD_BY_ID["CB-03"]
    assert _testable(board.drivers + board.responses)


def test_registry_ids_are_distinct():
    assert len(LINK_BY_ID) == len(LINKS)


def test_every_registry_row_is_on_a_board():
    assert BOARD_LINK_IDS == set(LINK_BY_ID)


def test_no_focus_is_on_two_boards():
    # The case board matches its board by the focus variable and metric.
    assert len(set(FOCUS_PAIRS)) == len(FOCUS_PAIRS)


@pytest.mark.parametrize("pair", FOCUS_PAIRS, ids="-".join)
def test_board_focus_uses_a_wave3_metric(pair):
    assert pair[1] in WAVE3_METRICS


@pytest.mark.parametrize("link", TESTABLE_LINKS, ids=_case_id)
def test_testable_arrow_uses_wave3_metrics(link):
    assert {link.driver.metric.id, link.response.metric.id} <= WAVE3_METRICS


@pytest.mark.parametrize(("board", "link"), DRIVER_CASES, ids=_case_id)
def test_testable_driver_points_at_a_board_focus(board, link):
    assert (link.response.var, link.response.metric.id) in _focus(board)


@pytest.mark.parametrize(("board", "link"), RESPONSE_CASES, ids=_case_id)
def test_testable_response_starts_at_a_board_focus(board, link):
    assert (link.driver.var, link.driver.metric.id) in _focus(board)


@pytest.mark.parametrize("link", LINKS, ids=_case_id)
def test_mechanism_never_claims_a_cause(link):
    # Board copy says "consistent with", never "caused by" (PRD "Earth-system context").
    assert "caus" not in link.mechanism.en.lower()
