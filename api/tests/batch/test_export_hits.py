"""export-demo: the stored trend of each scan hit joins the bundle of its case.

The fallback reads a hit trend by its key to show the rate of the hit
(web/src/features/fallback/ScanLists.tsx), so the bundle lists it under
referenced.trend, as it lists the trend of each board node.
"""

from pathlib import Path

import pytest

from boramae.batch.export_demo import export_demo
from boramae.contracts.content import DemoCase, DemoManifest, DemoSpecs
from boramae.contracts.results_scan import ScanResult
from boramae.contracts.spec import (
    Circle,
    LocalizedText,
    RequestSpec,
    RequestWindow,
    SpecMetric,
)
from boramae.services.catalog import CATALOG_PATH
from boramae.services.trend import TrendFacts, get_trend
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService, result_path
from tests.fakes import FakeReader

SCAN_BODY = (
    Path(__file__).parents[1] / "fixtures/scan.nearby.sample.json"
).read_bytes()
HIT_KEYS = [hit.trend_key for hit in ScanResult.model_validate_json(SCAN_BODY).hits]
SCAN_KEY = "c" * 32
CASE = "quiet-pin"
HIT_FILES = {key: f"{CASE}/trend.{key}.json" for key in HIT_KEYS}
# The whole-number pin and the question of test_export_demo.py: the rules parse the
# question to T2M annual mean, the trend of the case.
PIN = Circle(lat=35, lon=139, radius_km=10)
WINDOW = RequestWindow(start=1981, end="latest")
QUESTION = LocalizedText(en="Is Seoul getting warmer?", ko="서울이 더워지고 있나요?")


def make_spec(kind):
    metric = SpecMetric(id="annual_mean")
    return RequestSpec(
        v=1, kind=kind, var="T2M", metric=metric, area=PIN, window=WINDOW
    )


# The seeded noise of FakeReader has no trend, so the verdict opens the scan.
QUIET_CASE = DemoCase(
    id=CASE,
    input_id=1,
    lang="en",
    question=QUESTION,
    area=PIN,
    window=WINDOW,
    specs=DemoSpecs(trend=make_spec("trend"), caseboard=None, scan=make_spec("scan")),
    prompts=[],
)


def stored_scan(spec, *, reader, results, catalog):
    body, cache = results.get_or_compute("scan", SCAN_KEY, lambda: None)
    return body, SCAN_KEY, cache, TrendFacts(0, False, {})


SERVICES = {"trend": get_trend, "scan": stored_scan}


@pytest.fixture
def out(tmp_path):
    return tmp_path / "out"


@pytest.fixture
def export(store, sample_catalog, tmp_path, out):
    """Stores the catalog, the trend and the scan of the case; returns an export run
    that first stores the trends of the given hit keys."""
    store.put(CATALOG_PATH, sample_catalog.to_json_bytes())
    store.put(result_path("scan", SCAN_KEY), SCAN_BODY)
    results = ResultService(store, WorkerPool(4, 1.0))
    get_trend(
        make_spec("trend"), reader=FakeReader(), results=results, catalog=sample_catalog
    )

    def run(stored_hits=HIT_KEYS) -> DemoManifest:
        for key in stored_hits:
            store.put(result_path("trend", key), key.encode())
        return export_demo(
            [QUIET_CASE],
            out,
            store=store,
            reader=FakeReader(),
            services=SERVICES,
            answers_dir=tmp_path / "answers",
        )

    return run


def test_should_list_each_hit_trend_under_referenced(export):
    assert export().cases[0].referenced == {"trend": HIT_FILES}


@pytest.mark.parametrize("key", HIT_KEYS)
def test_should_copy_the_stored_bytes_of_each_hit_trend(export, out, key):
    export()
    assert (out / HIT_FILES[key]).read_bytes() == key.encode()


def test_should_skip_a_hit_trend_that_is_not_stored(export):
    expected = {"trend": {key: HIT_FILES[key] for key in HIT_KEYS[1:]}}
    assert export(stored_hits=HIT_KEYS[1:]).cases[0].referenced == expected


def test_should_name_the_skipped_hit_trend(export, capsys):
    export(stored_hits=HIT_KEYS[1:])
    assert HIT_KEYS[0] in capsys.readouterr().err


def test_should_list_no_reference_when_no_hit_trend_is_stored(export):
    assert export(stored_hits=[]).cases[0].referenced == {}
