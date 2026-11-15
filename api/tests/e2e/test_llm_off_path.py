"""TR-Q-012: with the LLM off, input 1 goes from its question to its board or fallback.

Each run walks the app path on a FakeReader and a store in a temp folder that holds the
seed catalog. It posts the Korean question of input 1 to parse and builds the request
spec from the proposal as the rail does (web/src/features/rail/draft.ts toDraft,
web/src/state/run-analysis.ts encodeRequest). Then it gets the trend, and the case
board for a significant verdict or the scan otherwise (features/case/CasePanel.tsx).
The rising run moves the first snow one day later each season; the steady run keeps it
in place. The log check reads the request log lines on stdout and the app logger
(TR-Q-005).
"""

import contextlib
import io
import json
import logging
import zlib
from dataclasses import dataclass

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from boramae.contracts.results import TrendResult
from boramae.contracts.results_board import CaseBoard
from boramae.contracts.results_scan import ScanResult
from boramae.contracts.spec import (
    Circle,
    ParseProposal,
    RequestSpec,
    SpecMetric,
    encode_request_spec,
)
from boramae.services.catalog import CATALOG_PATH
from boramae.services.content import load_content
from boramae.store.local import LocalStore
from tests.fakes import FakeReader, make_client
from tests.suites.catalog_suite_lib import seed_catalog

INPUT_1 = next(item for item in load_content("inputs").inputs if item.id == 1)
QUESTION = INPUT_1.text.ko
SESSION = "e2e-llm-off-session"
PARSE_PATH = "/api/v1/parse"
# A documentation address (RFC 5737), so a leak into the log is easy to find.
CLIENT_HOST = "203.0.113.9"
CLIENT = (CLIENT_HOST, 50123)
SNOW_VAR = "PRECSNO"
SNOW_MM = 1.0  # a snow day: above the 0.1 mm threshold of input 1
SEASON_START = np.timedelta64(7, "M")  # 1 August, the PRECSNO first_date season
EPOCH_YEAR = 1970  # datetime64[Y] counts years from 1970
FIRST_SEASON = 1981
FIRST_SNOW_DAY = 100  # day of the season of the first snow in the first season
SWING_DAYS = 5  # the first snow comes this many days early, then late, in turn
# The panel that a verdict opens (CasePanel.tsx); record_too_short opens none.
PANEL_OF_VERDICT = {
    "significant_rise": "caseboard",
    "significant_fall": "caseboard",
    "not_yet": "scan",
    "no_trend": "scan",
}
PANEL_MODELS = {"caseboard": CaseBoard, "scan": ScanResult}
VERDICT_OF_RUN = {"rising": "significant_rise", "steady": "no_trend"}
PANEL_OF_RUN = {"rising": "caseboard", "steady": "scan"}


@dataclass(frozen=True)
class Walk:
    name: str
    parse: httpx.Response
    trend: httpx.Response
    panel: httpx.Response
    log: str


def _first_snow(days_later_per_season):
    """PRECSNO is SNOW_MM from the first snow day of each season on and 0 before it;
    every other variable is seeded noise."""

    def values(var, freq, times, cell):
        if var != SNOW_VAR:
            rng = np.random.default_rng(zlib.crc32(var.encode()))
            return rng.standard_normal(times.size)
        season = (times.astype("datetime64[M]") - SEASON_START).astype("datetime64[Y]")
        start = (season.astype("datetime64[M]") + SEASON_START).astype("datetime64[D]")
        years = season.astype(int) + EPOCH_YEAR
        first_day = (
            FIRST_SNOW_DAY
            + days_later_per_season * (years - FIRST_SEASON)
            + SWING_DAYS * (-1) ** years
        )
        return np.where((times - start).astype(int) >= first_day, SNOW_MM, 0.0)

    return values


def _request_spec(proposal):
    """The trend request of a confirmed proposal, as the rail builds it: the first
    variable with the parsed metric, the place as a pin with its radius, the window."""
    first, spec = proposal.variables[0], proposal.spec
    metric = spec.metric
    return RequestSpec(
        v=1,
        kind="trend",
        var=first.var,
        metric=SpecMetric(
            id=first.metric_id,
            threshold=None if metric.value is None else str(metric.value),
            op=metric.op,
            months=metric.months,
            season_start=metric.season_start,
        ),
        area=Circle(
            lat=spec.place.lat, lon=spec.place.lon, radius_km=spec.place.radius_km
        ),
        window=spec.window,
    )


def _url(request_spec, kind):
    spec = request_spec.model_copy(update={"kind": kind})
    return f"/api/v1/{kind}?s={encode_request_spec(spec)}"


@contextlib.contextmanager
def _captured(buffer):
    """The request log lines on stdout and the records of the app logger."""
    handler = logging.StreamHandler(buffer)
    app_logger = logging.getLogger("boramae")
    app_logger.addHandler(handler)
    try:
        with contextlib.redirect_stdout(buffer):
            yield
    finally:
        app_logger.removeHandler(handler)


def _decoded(log):
    """The log with each JSON line printed unescaped: json.dumps writes Korean as
    \\u escapes, which a plain search for the question would miss."""
    return "\n".join(
        json.dumps(json.loads(line), ensure_ascii=False)
        if line.startswith("{")
        else line
        for line in log.splitlines()
    )


def _logged_paths(log):
    return [
        json.loads(line)["path"] for line in log.splitlines() if line.startswith("{")
    ]


def _walk(name, values_fn, root):
    store = LocalStore(root)
    store.put(CATALOG_PATH, seed_catalog().to_json_bytes())
    app = make_client(reader=FakeReader(values_fn=values_fn), store=store).app
    client = TestClient(app, client=CLIENT)
    buffer = io.StringIO()
    with _captured(buffer):
        parse = client.post(
            PARSE_PATH, json={"text": QUESTION, "lang": "ko", "session_id": SESSION}
        )
        request_spec = _request_spec(ParseProposal.model_validate_json(parse.content))
        trend = client.get(_url(request_spec, "trend"))
        verdict = TrendResult.model_validate_json(trend.content).verdict
        panel = client.get(_url(request_spec, PANEL_OF_VERDICT[verdict]))
    return Walk(name, parse, trend, panel, _decoded(buffer.getvalue()))


@pytest.fixture(scope="module")
def rising(tmp_path_factory):
    return _walk("rising", _first_snow(1), tmp_path_factory.mktemp("rising"))


@pytest.fixture(scope="module")
def steady(tmp_path_factory):
    return _walk("steady", _first_snow(0), tmp_path_factory.mktemp("steady"))


@pytest.fixture(params=["rising", "steady"])
def walk(request):
    return request.getfixturevalue(request.param)


def test_parse_answers_200(walk):
    assert walk.parse.status_code == 200


def test_parse_answers_a_rules_proposal(walk):
    assert ParseProposal.model_validate_json(walk.parse.content).source == "rules"


def test_trend_answers_200(walk):
    assert walk.trend.status_code == 200


def test_trend_answers_a_trend_of_the_input_variable(walk):
    trend = TrendResult.model_validate_json(walk.trend.content)
    assert trend.spec.var == INPUT_1.expected.var


def test_trend_gives_the_verdict_of_its_run(walk):
    trend = TrendResult.model_validate_json(walk.trend.content)
    assert trend.verdict == VERDICT_OF_RUN[walk.name]


def test_panel_answers_200(walk):
    assert walk.panel.status_code == 200


def test_panel_answers_the_result_of_its_run(walk):
    kind = PANEL_OF_RUN[walk.name]
    assert PANEL_MODELS[kind].model_validate_json(walk.panel.content).spec.kind == kind


def test_rising_run_opens_the_board_of_input_1(rising):
    assert CaseBoard.model_validate_json(rising.panel.content).board_id == INPUT_1.board


def test_log_holds_a_line_for_each_request(walk):
    panel_path = f"/api/v1/{PANEL_OF_RUN[walk.name]}"
    assert _logged_paths(walk.log) == [PARSE_PATH, "/api/v1/trend", panel_path]


def test_log_holds_no_question_text(walk):
    assert QUESTION not in walk.log


def test_log_holds_no_client_address(walk):
    assert CLIENT_HOST not in walk.log
