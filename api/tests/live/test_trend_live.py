"""Live test 1: inputs 1, 5, 10 and 44 through get_trend, straight from POWER.

Run with -m live -s. Each input is a 25 km circle on its candidate point. The store
is a tmp folder that holds a catalog built from the real stores, so no result
reaches api/.data. content/evidence/demo-candidates.json gives the points and the
single-cell verdicts to compare with; this test reads it and never writes it.
"""

import json

import pytest

from boramae.batch.build_catalog import build_catalog
from boramae.config import load_settings
from boramae.contracts.results import TrendResult
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.power.reader import PowerReader
from boramae.services.catalog import CATALOG_PATH, find_variable, load_catalog
from boramae.services.content import content_dir, load_content
from boramae.services.trend import get_trend
from boramae.store.local import LocalStore
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService

pytestmark = pytest.mark.live

INPUT_IDS = (1, 5, 10, 44)
RADIUS_KM = 25  # the default radius of a pin (FR-04)
CANDIDATES_FILE = "evidence/demo-candidates.json"
YEAR_DIGITS = 4
FULL_RECORD_VERDICTS = ("significant_rise", "significant_fall", "not_yet", "no_trend")


@pytest.fixture(scope="module")
def candidates_bytes() -> bytes:
    return (content_dir() / CANDIDATES_FILE).read_bytes()


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    settings = load_settings()
    reader = PowerReader(settings)
    store = LocalStore(tmp_path_factory.mktemp("trend-live"))
    built, _ = build_catalog(reader, load_content("catalog_seed"))
    store.put(CATALOG_PATH, built.to_json_bytes())
    pool = WorkerPool(
        settings.pool_size, settings.pool_wait_s, settings.request_timeout_s
    )
    return reader, ResultService(store, pool), load_catalog(store)


@pytest.fixture(scope="module")
def specs(service, candidates_bytes) -> dict[int, RequestSpec]:
    catalog = service[2]
    inputs = {item.id: item for item in load_content("inputs").inputs}
    points = {
        item["input_id"]: item for item in json.loads(candidates_bytes)["candidates"]
    }
    return {
        input_id: _spec(inputs[input_id].expected, points[input_id], catalog)
        for input_id in INPUT_IDS
    }


@pytest.fixture(scope="module")
def runs(service, specs, candidates_bytes) -> dict[int, tuple]:
    reader, results, catalog = service
    answers = {
        input_id: get_trend(spec, reader=reader, results=results, catalog=catalog)
        for input_id, spec in specs.items()
    }
    points = {
        item["input_id"]: item for item in json.loads(candidates_bytes)["candidates"]
    }
    print()
    for input_id, (body, _, cache, facts) in answers.items():
        result = TrendResult.model_validate_json(body)
        print(_summary(input_id, result, cache, facts, points[input_id]))
    return answers


@pytest.mark.parametrize("input_id", INPUT_IDS)
def test_should_give_the_input_a_verdict_on_its_full_record(runs, input_id):
    assert TrendResult.model_validate_json(runs[input_id][0]).verdict in (
        FULL_RECORD_VERDICTS
    )


@pytest.mark.parametrize("input_id", INPUT_IDS)
def test_should_answer_a_repeat_from_the_store(runs, service, specs, input_id):
    reader, results, catalog = service
    repeat = get_trend(specs[input_id], reader=reader, results=results, catalog=catalog)
    assert repeat[2] == "hit"


def test_should_leave_the_candidate_file_unchanged(runs, candidates_bytes):
    assert (content_dir() / CANDIDATES_FILE).read_bytes() == candidates_bytes


def _spec(expected, point: dict, catalog) -> RequestSpec:
    variable = find_variable(catalog, expected.var)
    start = expected.window_start or int(variable.record_start[:YEAR_DIGITS])
    return RequestSpec(
        v=1,
        kind="trend",
        var=expected.var,
        metric=SpecMetric(
            id=expected.metric_id,
            threshold=expected.threshold,
            op=expected.op,
            months=expected.months,
        ),
        area=Circle(lat=point["lat"], lon=point["lon"], radius_km=RADIUS_KM),
        window=RequestWindow(start=start, end="latest"),
    )


def _summary(input_id, result: TrendResult, cache, facts, candidate: dict) -> str:
    stats, rates = result.stats, result.stats.rates
    return (
        f"input {input_id} ({result.spec.var} {result.spec.metric.id},"
        f" {len(result.spec.cells)} cells, window {result.spec.window}):"
        f" verdict {result.verdict}, reason {result.reason},"
        f" metric used {result.metric_used};"
        f" Sen {_g(rates.sen)} {result.rate_unit} per decade,"
        f" 95% {_g(rates.sen_ci_low)} to {_g(rates.sen_ci_high)};"
        f" MK p {_g(stats.mk.p)}; n {stats.n}; years needed {result.years_needed};"
        f" {cache}, read {facts.timings.get('read')} ms,"
        f" stats {facts.timings.get('stats')} ms, {facts.bytes_fetched} bytes."
        f" Candidate (1 cell {candidate['cell']}): {candidate['verdict']},"
        f" Sen {_g(candidate['stats']['sen']['slope'] * 10)} per decade,"
        f" MK p {_g(candidate['stats']['mk']['p'])}"
    )


def _g(value: float | None) -> str:
    return "none" if value is None else f"{value:.4g}"
