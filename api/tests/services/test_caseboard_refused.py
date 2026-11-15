"""A board node whose trend spec the validator refuses (user decision 5).

The node stays on the board as a not_testable_here row with the problem code of the
refusal, as a scan lists a refused leaf, and the rest of the board is tested.
"""

import pytest

from boramae.contracts.content import Board, RegistryLink
from boramae.contracts.results_board import CaseBoard
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.services.caseboard import build_board
from boramae.spec.validate import INVALID_SPEC
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService
from tests.fakes import DictStore, FakeReader

FOCUS_SPEC = RequestSpec(
    v=1,
    kind="caseboard",
    var="T2M",
    metric=SpecMetric(id="annual_mean"),
    area=Circle(lat=37.5665, lon=126.978, radius_km=25),
    window=RequestWindow(start=1981, end="latest"),
)


def side(var, metric_id="annual_mean"):
    metric = {"id": metric_id, "months": None, "threshold": None, "op": None}
    return {"var": var, "metric": metric}


def make_row(row_id, driver, response):
    return RegistryLink.model_validate(
        {
            "id": row_id,
            "driver": driver,
            "response": response,
            "expected_sign": "+",
            "mechanism": {"en": "A test arrow.", "ko": "시험 화살표."},
            "scale": "test",
            "area": "user",
            "lag_years": 0,
            "status": "robust",
            "doi": "10.1000/board.test",
            "url": None,
            "citation": "Test 2026",
        }
    )


TESTED = make_row("tqv-t2m", side("TQV"), side("T2M"))
# The focus end of each row is the focus, so only the validator refuses the node: in
# the sample catalog last_date has no reducer yet, and FROST_DAYS has no daily store.
REFUSED_ROWS = [
    make_row("t2m-last-snow", side("T2M"), side("PRECSNO", "last_date")),
    make_row("t2m-frost-days", side("T2M"), side("FROST_DAYS", "threshold_days")),
]


class CountingPool(WorkerPool):
    """The real pool; it also records how many leaves each run_leaves call gets."""

    def __init__(self):
        super().__init__(4, 1.0)
        self.leaf_counts = []

    def run_leaves(self, fns):
        self.leaf_counts.append(len(fns))
        return super().run_leaves(fns)


@pytest.fixture
def pool():
    return CountingPool()


@pytest.fixture(params=REFUSED_ROWS, ids=lambda row: row.id)
def refused_row(request):
    return request.param


@pytest.fixture
def board(sample_catalog, pool, refused_row):
    content = Board.model_validate(
        {
            "id": "CB-99",
            "title": {"en": "Test", "ko": "시험"},
            "focus": [{"var": "T2M", "metric_id": "annual_mean"}],
            "drivers": [TESTED.id],
            "responses": [refused_row.id],
        }
    )
    body, *_ = build_board(
        FOCUS_SPEC,
        [content],
        [TESTED, refused_row],
        reader=FakeReader(),
        results=ResultService(DictStore(), pool),
        catalog=sample_catalog,
    )
    return CaseBoard.model_validate_json(body)


# Board order: the drivers, then the responses.
@pytest.fixture
def tested_node(board):
    return board.nodes[0]


@pytest.fixture
def refused_node(board):
    return board.nodes[1]


def test_should_keep_a_refused_node_on_the_board(refused_node, refused_row):
    assert refused_node.row.id == refused_row.id


def test_should_label_a_refused_node_not_testable_here(refused_node):
    assert refused_node.link.label == "not_testable_here"


def test_should_give_a_refused_node_the_code_of_the_refusal(refused_node):
    assert refused_node.link.reason == INVALID_SPEC


def test_should_request_no_trend_for_a_refused_node(refused_node):
    assert refused_node.trend_key is None


@pytest.mark.parametrize("field", ["r", "p", "n_eff", "sign"])
def test_should_give_a_refused_node_no_link_number(refused_node, field):
    assert getattr(refused_node.link, field) is None


def test_should_give_a_refused_node_no_overlap_year(refused_node):
    assert refused_node.link.n_overlap == 0


def test_should_still_test_the_other_node(tested_node):
    assert tested_node.link.r is not None


def test_should_send_only_the_focus_and_the_tested_node_to_the_pool(board, pool):
    assert pool.leaf_counts == [2]
