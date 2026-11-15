"""Flow C: the case board of a focus spec (DES-011, TDD.md:195-213, TR-F-026).

The builder finds the board of the focus in content/boards.json and tests each of
its registry rows on the user's area and window. The focus trend and every node
trend are leaves of the worker pool, so the builder holds no slot while it waits
(TDD.md:184). One failing leaf fails the whole request: no partial board is stored.
"""

import hashlib
import json
import time
from functools import partial

from boramae.contracts.content import Board, RegistryLink
from boramae.contracts.http import CacheStatus
from boramae.contracts.results import TrendResult
from boramae.contracts.results_board import (
    BoardLink,
    BoardNode,
    CaseBoard,
    NodeRole,
    RegistryRow,
    RowSide,
)
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import RequestSpec
from boramae.engine.link import NOT_TESTABLE, link_test
from boramae.engine.types import YearlySeries
from boramae.errors import ProblemError
from boramae.ports import SeriesReader
from boramae.services.content import load_content
from boramae.services.trend import TREND_KIND, TrendFacts, get_trend
from boramae.spec.canonical import canonicalize, result_key
from boramae.spec.validate import BAD_REQUEST, INVALID_SPEC, validate_request
from boramae.store.results import ResultService

CASEBOARD_KIND = "caseboard"
CONTENT_MARK_HEX_LEN = 12
USER_AREA = "user"
# Reasons of an arrow that the builder does not test (docs/BUILD_CONTRACT.md "Case
# board"). focus_differs: the focus end of the row is another (var, metric) of the
# board than the user's focus (user decision of 2026-11-15).
REGISTRY_STATUS = "registry_status"
REMOTE_AREA = "remote_area"  # remote areas are FR-33 (P1)
FOCUS_DIFFERS = "focus_differs"
# ponytail: no document names the timing steps of a board; "leaves" is the wall
# time of the focus and node trends, the rest of "total" is the link tests.
LEAVES_STEP = "leaves"

Focus = tuple[str, str]  # (var, metric ID)


def get_caseboard(
    request_spec: RequestSpec,
    *,
    reader: SeriesReader,
    results: ResultService,
    catalog: Catalog,
) -> tuple[bytes, str, CacheStatus, TrendFacts]:
    """The stored body of a case board, its key, the cache status and the facts."""
    return build_board(
        request_spec,
        load_content("boards"),
        load_content("registry"),
        reader=reader,
        results=results,
        catalog=catalog,
    )


def build_board(
    request_spec: RequestSpec,
    boards: list[Board],
    registry: list[RegistryLink],
    *,
    reader: SeriesReader,
    results: ResultService,
    catalog: Catalog,
) -> tuple[bytes, str, CacheStatus, TrendFacts]:
    """get_caseboard on the given content. A bad spec raises ProblemError 400, a
    failing leaf 503; neither stores a board."""
    if request_spec.kind != CASEBOARD_KIND:
        raise ProblemError(BAD_REQUEST, INVALID_SPEC, "the spec kind is not caseboard")
    validated = validate_request(request_spec, catalog)
    focus = (request_spec.var, request_spec.metric.id)
    board = next((item for item in boards if focus in _focus_pairs(item)), None)
    links = _board_links(board, registry)
    mark = content_mark(board, [link for _, link in links])
    canonical = canonicalize(validated, catalog, mark)
    key = result_key(canonical)
    timings: dict[str, float] = {}
    fetched: list[int] = []

    def compute() -> CaseBoard:
        rows = [
            (role, RegistryRow.model_validate(link.model_dump()))
            for role, link in links
        ]
        reasons = [_untested(role, row, focus) for role, row in rows]
        specs = [request_spec.model_copy(update={"kind": TREND_KIND})] + [
            _node_spec(request_spec, _node_side(role, row))
            for (role, row), reason in zip(rows, reasons, strict=True)
            if reason is None
        ]
        leaves = [
            partial(
                get_trend,
                spec,
                reader=reader,
                results=results,
                catalog=catalog,
                bounded=False,
            )
            for spec in specs
        ]
        started = time.perf_counter()
        answers = results.pool.run_leaves(leaves)
        timings[LEAVES_STEP] = round((time.perf_counter() - started) * 1000, 1)
        fetched.extend(facts.bytes_fetched for *_, facts in answers)
        (focus_body, focus_key, _, _), *node_answers = answers
        nodes = _nodes(rows, reasons, _yearly(focus_body), node_answers)
        board_id = None if board is None else board.id
        return CaseBoard(
            spec=canonical, board_id=board_id, focus_key=focus_key, nodes=nodes
        )

    body, cache = results.get_or_compute(CASEBOARD_KIND, key, compute, bounded=False)
    facts = TrendFacts(sum(fetched), validated.used_containing_cell, timings)
    return body, key, cache, facts


def content_mark(board: Board | None, links: list[RegistryLink]) -> str:
    """The first 12 hex characters of the SHA-256 of the board and its rows."""
    record = {
        "board": None if board is None else board.model_dump(mode="json"),
        "rows": [link.model_dump(mode="json") for link in links],
    }
    text = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:CONTENT_MARK_HEX_LEN]


def _focus_pairs(board: Board) -> set[Focus]:
    return {(item.var, item.metric_id) for item in board.focus}


def _board_links(
    board: Board | None, registry: list[RegistryLink]
) -> list[tuple[NodeRole, RegistryLink]]:
    """The rows of a board with their roles: the drivers, then the responses."""
    if board is None:
        return []
    by_id = {link.id: link for link in registry}
    roles: list[tuple[NodeRole, list[str]]] = [
        ("driver", board.drivers),
        ("response", board.responses),
    ]
    return [(role, by_id[row_id]) for role, row_ids in roles for row_id in row_ids]


def _nodes(
    rows: list[tuple[NodeRole, RegistryRow]],
    reasons: list[str | None],
    focus: YearlySeries,
    answers: list[tuple[bytes, str, CacheStatus, TrendFacts]],
) -> list[BoardNode]:
    """One node per row, in board order. `answers` holds the trends of the tested
    rows, in the same order."""
    tested = iter(answers)
    nodes = []
    for (role, row), reason in zip(rows, reasons, strict=True):
        if reason is None:
            body, trend_key, _, _ = next(tested)
            link = _link(role, row, focus, _yearly(body))
        else:
            trend_key, link = None, _untested_link(row, reason)
        nodes.append(BoardNode(role=role, row=row, trend_key=trend_key, link=link))
    return nodes


def _node_side(role: NodeRole, row: RegistryRow) -> RowSide:
    return row.driver if role == "driver" else row.response


def _focus_side(role: NodeRole, row: RegistryRow) -> RowSide:
    return row.response if role == "driver" else row.driver


def _untested(role: NodeRole, row: RegistryRow, focus: Focus) -> str | None:
    """The reason that a row gets no test, or None for a row to test."""
    if row.status == NOT_TESTABLE:
        return REGISTRY_STATUS
    if row.area != USER_AREA:
        return REMOTE_AREA
    focus_side = _focus_side(role, row)
    if (focus_side.var, focus_side.metric.id) != focus:
        return FOCUS_DIFFERS
    return None


def _node_spec(request_spec: RequestSpec, node: RowSide) -> RequestSpec:
    """The trend spec of a node: its metric on the user's area and window. The
    season start comes from canonicalize, as for a hand-picked spec."""
    return RequestSpec(
        v=request_spec.v,
        kind=TREND_KIND,
        var=node.var,
        metric=node.metric,
        area=request_spec.area,
        window=request_spec.window,
    )


def _yearly(body: bytes) -> YearlySeries:
    result = TrendResult.model_validate_json(body)
    yearly = result.series.yearly
    return YearlySeries(
        years=tuple(yearly.years),
        values=tuple(yearly.values),
        is_censored=tuple(yearly.is_censored),
        metric_used=result.metric_used or "",
    )


def _link(
    role: NodeRole, row: RegistryRow, focus: YearlySeries, node: YearlySeries
) -> BoardLink:
    driver, response = (node, focus) if role == "driver" else (focus, node)
    result = link_test(driver, response, row.lag_years, row.expected_sign)
    return BoardLink.model_validate(result)


def _untested_link(row: RegistryRow, reason: str) -> BoardLink:
    return BoardLink(
        r=None,
        p=None,
        n_eff=None,
        lag_years=row.lag_years,
        n_overlap=0,
        sign=None,
        label=NOT_TESTABLE,
        reason=reason,
    )
