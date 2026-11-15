"""The case board builder (DES-011, TDD.md Flow C, TR-F-026)."""

import re
import time

import numpy as np
import pytest

from boramae.contracts.content import Board, RegistryLink
from boramae.contracts.results import TrendResult
from boramae.contracts.results_board import CaseBoard
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.errors import PowerUnavailable, ProblemError
from boramae.services.caseboard import build_board
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService, result_path
from tests.fakes import DictStore, FakeReader

SEOUL = Circle(lat=37.5665, lon=126.978, radius_km=25)
DOI = "10.1000/board.test"
CASEBOARD_PREFIX = "r/caseboard/"
# Sparse yearly values: most years are 0, so most pair slopes are 0, the Sen slope
# is exactly 0 and the detrended values are the values. No two non-zero years are
# neighbors, so every lag-1 autocorrelation is 0 and n_eff is the 45 years.
FOCUS_YEARS = {1981: 1.0, 1990: 1.0, 1985: -1.0, 1995: -1.0}
NOISE_YEARS = {2000: 4.0, 2005: -4.0, 2010: 4.0, 2015: -4.0}
# FOCUS_YEARS and NOISE_YEARS share no year and both have mean 0, so the focus and
# focus + noise correlate at sqrt(4 / 68) = 0.24, p about 0.11 on 45 years.
WITH_NOISE = FOCUS_YEARS | NOISE_YEARS


def negated(table):
    return {year: -value for year, value in table.items()}


def make_spec(var="T2M", metric_id="annual_mean", kind="caseboard"):
    return RequestSpec(
        v=1,
        kind=kind,
        var=var,
        metric=SpecMetric(id=metric_id),
        area=SEOUL,
        window=RequestWindow(start=1981, end="latest"),
    )


def side(var, metric_id="annual_mean"):
    metric = {"id": metric_id, "months": None, "threshold": None, "op": None}
    return {"var": var, "metric": metric}


def make_row(row_id, driver, response, status="robust", area="user", scale="test"):
    return RegistryLink.model_validate(
        {
            "id": row_id,
            "driver": driver,
            "response": response,
            "expected_sign": "+",
            "mechanism": {"en": "A test arrow.", "ko": "시험 화살표."},
            "scale": scale,
            "area": area,
            "lag_years": 0,
            "status": status,
            "doi": DOI,
            "url": None,
            "citation": "Test 2026",
        }
    )


DRIVER = make_row("tqv-t2m", side("TQV"), side("T2M"))
SECOND_DRIVER = make_row("rh2m-t2m", side("RH2M"), side("T2M"))
SNOW_RESPONSE = make_row("t2m-snow", side("T2M"), side("PRECSNO", "first_date"))
UNTESTED_ROWS = {
    "registry_status": make_row(
        "status", side("TQV"), side("T2M"), status="not_testable_here"
    ),
    "remote_area": make_row("remote", side("TQV"), side("T2M"), area="gulf-of-mexico"),
    "focus_differs": make_row("other-focus", side("TQV"), side("T2M", "seasonal_mean")),
}
SIX_ROWS = [
    make_row("d1", side("TQV"), side("T2M")),
    make_row("d2", side("RH2M"), side("T2M")),
    make_row("d3", side("GWETTOP"), side("T2M")),
    make_row("r1", side("T2M"), side("WS10M")),
    make_row("r2", side("T2M"), side("TS")),
    make_row("r3", side("T2M"), side("EVLAND")),
]


def make_board(drivers=(), responses=()):
    return Board.model_validate(
        {
            "id": "CB-99",
            "title": {"en": "Test", "ko": "시험"},
            "focus": [{"var": "T2M", "metric_id": "annual_mean"}],
            "drivers": [row.id for row in drivers],
            "responses": [row.id for row in responses],
        }
    )


def yearly_values(tables, delay_s=0.0):
    """values_fn of FakeReader: each step holds the value of its year."""

    def values(var, freq, times, cell):
        time.sleep(delay_s)
        years = times.astype("datetime64[Y]").astype(int) + 1970
        table = tables.get(var, {})
        return np.array([table.get(int(year), 0.0) for year in years])

    return values


def failing_values(var, freq, times, cell):
    if var == "TQV":
        raise PowerUnavailable("the TQV read failed")
    return np.zeros(times.size)


def run(catalog, drivers=(), responses=(), spec=None, reader=None, results=None):
    return build_board(
        spec or make_spec(),
        [make_board(drivers, responses)],
        [*drivers, *responses],
        reader=reader or FakeReader(),
        results=results or ResultService(DictStore(), WorkerPool(4, 1.0)),
        catalog=catalog,
    )


def run_board(catalog, **kwargs):
    return CaseBoard.model_validate_json(run(catalog, **kwargs)[0])


def caseboard_paths(store):
    return [path for path in store.files if path.startswith(CASEBOARD_PREFIX)]


@pytest.fixture
def results(store):
    return ResultService(store, WorkerPool(4, 1.0))


@pytest.fixture
def one_driver(sample_catalog, results):
    return run_board(sample_catalog, drivers=[DRIVER], results=results)


def test_should_store_the_trend_of_a_testable_node(one_driver, store):
    assert result_path("trend", one_driver.nodes[0].trend_key) in store.files


def test_should_store_the_trend_of_the_focus(one_driver, store):
    assert result_path("trend", one_driver.focus_key) in store.files


def test_should_test_a_node_on_the_area_and_window_of_the_focus(one_driver, store):
    node = TrendResult.model_validate_json(
        store.files[result_path("trend", one_driver.nodes[0].trend_key)]
    )
    expected = (one_driver.spec.cells, one_driver.spec.window)
    assert (node.spec.cells, node.spec.window) == expected


def test_should_give_a_testable_arrow_its_link_numbers(one_driver):
    assert one_driver.nodes[0].link.r is not None


def test_should_give_each_arrow_its_doi(one_driver):
    assert one_driver.nodes[0].row.doi == DOI


def test_should_give_the_board_spec_its_kind(one_driver):
    assert one_driver.spec.kind == "caseboard"


def test_should_mark_the_board_content_with_12_hex_characters(one_driver):
    assert re.fullmatch("[0-9a-f]{12}", one_driver.spec.content)


@pytest.mark.parametrize(
    ("driver_years", "label"),
    [
        (FOCUS_YEARS, "consistent"),
        (WITH_NOISE, "weak"),
        (negated(FOCUS_YEARS), "contradicts"),
        (negated(WITH_NOISE), None),
    ],
)
def test_should_take_the_label_from_the_link_test(sample_catalog, driver_years, label):
    reader = FakeReader(
        values_fn=yearly_values({"T2M": FOCUS_YEARS, "TQV": driver_years})
    )
    board = run_board(sample_catalog, drivers=[DRIVER], reader=reader)
    assert board.nodes[0].link.label == label


def test_should_keep_a_contradicting_arrow(sample_catalog):
    tables = {"T2M": FOCUS_YEARS, "TQV": FOCUS_YEARS, "RH2M": negated(FOCUS_YEARS)}
    reader = FakeReader(values_fn=yearly_values(tables))
    board = run_board(sample_catalog, drivers=[DRIVER, SECOND_DRIVER], reader=reader)
    assert [node.link.label for node in board.nodes] == ["consistent", "contradicts"]


@pytest.mark.parametrize("reason", sorted(UNTESTED_ROWS))
def test_should_label_an_untested_row_not_testable_here(sample_catalog, reason):
    board = run_board(sample_catalog, drivers=[UNTESTED_ROWS[reason]])
    assert board.nodes[0].link.label == "not_testable_here"


@pytest.mark.parametrize("reason", sorted(UNTESTED_ROWS))
def test_should_name_the_reason_of_an_untested_row(sample_catalog, reason):
    board = run_board(sample_catalog, drivers=[UNTESTED_ROWS[reason]])
    assert board.nodes[0].link.reason == reason


@pytest.mark.parametrize("reason", sorted(UNTESTED_ROWS))
def test_should_request_no_trend_for_an_untested_row(sample_catalog, reason):
    board = run_board(sample_catalog, drivers=[UNTESTED_ROWS[reason]])
    assert board.nodes[0].trend_key is None


@pytest.mark.parametrize("reason", sorted(UNTESTED_ROWS))
def test_should_read_only_the_focus_for_an_untested_row(sample_catalog, reason):
    reader = FakeReader()
    run(sample_catalog, drivers=[UNTESTED_ROWS[reason]], reader=reader)
    assert reader.read_count == 1


def test_should_not_test_a_node_that_switched_to_event_days(sample_catalog):
    # 0 mm of snow every day censors every season year, so first_date switches.
    reader = FakeReader(values_fn=yearly_values({"T2M": FOCUS_YEARS}))
    board = run_board(sample_catalog, responses=[SNOW_RESPONSE], reader=reader)
    assert board.nodes[0].link.reason == "metric_switched"


def test_should_give_a_focus_with_no_board_a_null_board_id(sample_catalog):
    board = run_board(sample_catalog, drivers=[DRIVER], spec=make_spec(var="WS10M"))
    assert board.board_id is None


def test_should_give_a_focus_with_no_board_no_node(sample_catalog):
    board = run_board(sample_catalog, drivers=[DRIVER], spec=make_spec(var="WS10M"))
    assert board.nodes == []


def test_should_answer_503_when_a_node_fails(sample_catalog):
    with pytest.raises(ProblemError) as raised:
        run(
            sample_catalog,
            drivers=[DRIVER],
            reader=FakeReader(values_fn=failing_values),
        )
    assert raised.value.status == 503


def test_should_store_no_board_when_a_node_fails(sample_catalog, store, results):
    reader = FakeReader(values_fn=failing_values)
    with pytest.raises(ProblemError):
        run(sample_catalog, drivers=[DRIVER], reader=reader, results=results)
    assert caseboard_paths(store) == []


@pytest.fixture
def two_requests(sample_catalog, results):
    reader = FakeReader()
    first = run(sample_catalog, drivers=[DRIVER], reader=reader, results=results)
    reads_after_first = reader.read_count
    second = run(sample_catalog, drivers=[DRIVER], reader=reader, results=results)
    return first, second, reads_after_first, reader


def test_should_answer_a_stored_board_as_a_hit(two_requests):
    assert two_requests[1][2] == "hit"


def test_should_answer_a_hit_with_equal_bytes(two_requests):
    assert two_requests[1][0] == two_requests[0][0]


def test_should_request_no_node_again_for_a_hit(two_requests):
    _, _, reads_after_first, reader = two_requests
    assert reader.read_count == reads_after_first


def test_should_give_a_changed_registry_row_another_board_key(sample_catalog):
    changed = DRIVER.model_copy(update={"scale": "another scale"})
    keys = [run(sample_catalog, drivers=[row])[1] for row in (DRIVER, changed)]
    assert keys[0] != keys[1]


# A wait of 0 s makes any leaf that asks for a second slot fail at once, and a
# builder that held a slot itself would starve its leaves until the 5 s timeout.
@pytest.mark.parametrize("size", [1, 2])
def test_should_finish_six_slow_leaves_on_a_small_pool(sample_catalog, size):
    reader = FakeReader(values_fn=yearly_values({}, delay_s=0.01))
    results = ResultService(DictStore(), WorkerPool(size, 0.0, request_timeout_s=5.0))
    board = run_board(
        sample_catalog,
        drivers=SIX_ROWS[:3],
        responses=SIX_ROWS[3:],
        reader=reader,
        results=results,
    )
    assert len(board.nodes) == 6


def test_should_refuse_a_spec_of_another_kind(sample_catalog):
    with pytest.raises(ProblemError) as raised:
        run(sample_catalog, drivers=[DRIVER], spec=make_spec(kind="trend"))
    assert raised.value.status == 400
