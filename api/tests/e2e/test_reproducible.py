"""TR-D-010: a stored result comes back from its spec and versions, and one key
computes once.

Recompute: three trends go through GET /api/v1/trend into the store: the trend of each
demo case (content/demo/cases.json, daily store) and an annual mean (monthly store).
Each is computed again from the canonical spec in its file, which holds the dataset
version (ds) and the engine version (eng), on a fresh reader, and the bytes must match.

Single flight: two identical uncached requests run at once. The store holds the first
write until both requests have looked the result up, so both are in flight together.
"""

import threading
import zlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from fastapi.testclient import TestClient

from boramae.contracts.results import TrendResult
from boramae.contracts.spec import SpecMetric, encode_request_spec
from boramae.services.content import load_content
from boramae.services.trend import compute_trend
from boramae.store.results import result_path
from tests.fakes import DictStore, FakeReader, make_client
from tests.suites.catalog_suite_lib import seed_catalog

TREND_PATH = "/api/v1/trend"
DEMO_CASES = load_content("demo_cases")
SPECS = {case.id: case.specs.trend for case in DEMO_CASES} | {
    "annual-mean": DEMO_CASES[0].specs.trend.model_copy(
        update={"var": "T2M", "metric": SpecMetric(id="annual_mean")}
    )
}
# Seeded values around 20 with a spread of 15, so each metric of SPECS gets a series
# with scatter (FakeReader's own values never reach the 43.3 C of a demo case).
MEAN, SPREAD = 20.0, 15.0
# Bounds the hold, so a request that never looks the result up cannot hang the run.
HOLD_TIMEOUT_S = 10.0


def _weather(var, freq, times, cell):
    rng = np.random.default_rng(zlib.crc32(var.encode()))
    return MEAN + SPREAD * rng.standard_normal(times.size)


def _url(spec):
    return f"{TREND_PATH}?s={encode_request_spec(spec)}"


class HeldStore(DictStore):
    """Holds each write until two threads have looked a path up."""

    def __init__(self):
        super().__init__()
        self._looked_up = threading.Condition()
        self._threads = set()

    def get(self, path):
        with self._looked_up:
            self._threads.add(threading.get_ident())
            self._looked_up.notify_all()
        return super().get(path)

    def create_once(self, path, body):
        with self._looked_up:
            self._looked_up.wait_for(lambda: len(self._threads) > 1, HOLD_TIMEOUT_S)
        return super().create_once(path, body)


@pytest.fixture(scope="module")
def stored():
    """The stored body of each spec of SPECS, by name."""
    store = DictStore()
    client = make_client(
        reader=FakeReader(values_fn=_weather), store=store, catalog=seed_catalog()
    )
    keys = {
        name: client.get(_url(spec)).headers["x-result-key"]
        for name, spec in SPECS.items()
    }
    return {name: store.files[result_path("trend", key)] for name, key in keys.items()}


@pytest.fixture(scope="module")
def pair():
    """The reader and the answers of two identical uncached requests sent at once."""
    store, reader = HeldStore(), FakeReader(values_fn=_weather)
    app = make_client(reader=reader, store=store, catalog=seed_catalog()).app
    url = _url(DEMO_CASES[0].specs.trend)
    with ThreadPoolExecutor(2) as threads:
        answers = list(
            threads.map(
                lambda client: client.get(url), [TestClient(app), TestClient(app)]
            )
        )
    return reader, answers


@pytest.mark.parametrize("name", list(SPECS))
def test_recomputed_trend_equals_the_stored_bytes(stored, name):
    spec = TrendResult.model_validate_json(stored[name]).spec
    recomputed = compute_trend(spec, seed_catalog(), FakeReader(values_fn=_weather))
    assert recomputed.to_json_bytes() == stored[name]


def test_two_identical_requests_at_once_compute_once(pair):
    reader, _ = pair
    assert reader.read_count == 1


def test_two_identical_requests_at_once_answer_equal_bytes(pair):
    _, (first, second) = pair
    assert first.content == second.content
