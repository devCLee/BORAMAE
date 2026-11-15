"""export-demo: the stored results of each demo case become the bundle of the web app."""

import json
from pathlib import Path

import numpy as np
import pytest

from boramae.batch.export_demo import ExportError, export_demo
from boramae.contracts.content import (
    DemoCase,
    DemoManifest,
    DemoSpecs,
    ManifestAnswers,
    ManifestFile,
)
from boramae.contracts.results_board import CaseBoard
from boramae.contracts.spec import (
    Circle,
    LocalizedText,
    RequestSpec,
    RequestWindow,
    SpecMetric,
    encode_request_spec,
)
from boramae.services.catalog import CATALOG_PATH
from boramae.services.parse_cache import parse_key, put_proposal
from boramae.services.parser_rules import parse_rules
from boramae.services.trend import TrendFacts, get_trend
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService, result_path
from tests.fakes import FakeReader

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN_PATH = Path(__file__).parents[3] / "content/golden/request-spec.json"
GOLDEN_S = {vector["s"] for vector in json.loads(GOLDEN_PATH.read_bytes())}
BOARD_BODY = (FIXTURES / "caseboard.sample.json").read_bytes()
SCAN_BODY = (FIXTURES / "scan.nearby.sample.json").read_bytes()
NODE_KEYS = [
    node.trend_key
    for node in CaseBoard.model_validate_json(BOARD_BODY).nodes
    if node.trend_key is not None
]
BOARD_KEY = "b" * 32
SCAN_KEY = "c" * 32
CASE = "warmer-pin"
# The whole-number pin of content/golden/request-spec.json, so the trend s of the
# case is one of the golden strings.
PIN = Circle(lat=35, lon=139, radius_km=10)
WINDOW = RequestWindow(start=1981, end="latest")
MEAN = SpecMetric(id="annual_mean")
QUESTION = LocalizedText(en="Is Seoul getting warmer?", ko="서울이 더워지고 있나요?")
ANSWERS_BODY = b"[]"  # export copies the answers file as it is
SHARED_FILES = [
    "catalog.json",
    "manifest.json",
    *(f"{CASE}/{name}.json" for name in ("parse.en", "parse.ko", "trend")),
]
BOARD_FILES = [
    f"{CASE}/caseboard.json",
    *(f"{CASE}/trend.{key}.json" for key in NODE_KEYS),
]
NODE_FILES = {"trend": {key: f"{CASE}/trend.{key}.json" for key in NODE_KEYS}}


def rising(var, freq, times, cell):
    return (times - times[0]) / np.timedelta64(365, "D")


def missing(var, freq, times, cell):
    return np.full(times.size, np.nan)


NOISE = None  # the seeded noise of FakeReader: no trend


def make_spec(kind="trend", var="T2M"):
    return RequestSpec(v=1, kind=kind, var=var, metric=MEAN, area=PIN, window=WINDOW)


BOARD_SPEC = make_spec("caseboard")


def make_case(trend=None, caseboard=BOARD_SPEC):
    return DemoCase(
        id=CASE,
        input_id=1,
        lang="en",
        question=QUESTION,
        area=PIN,
        window=WINDOW,
        specs=DemoSpecs(
            trend=trend or make_spec(),
            caseboard=caseboard,
            scan=make_spec("scan"),
        ),
        prompts=[],
    )


def stored_service(kind, key):
    """A board or scan service that answers its one key from the results."""

    def service(spec, *, reader, results, catalog):
        body, cache = results.get_or_compute(kind, key, lambda: None)
        return body, key, cache, TrendFacts(0, False, {})

    return service


SERVICES = {
    "trend": get_trend,
    "caseboard": stored_service("caseboard", BOARD_KEY),
    "scan": stored_service("scan", SCAN_KEY),
}


def files_under(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in folder.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def stored(store, sample_catalog):
    """Stores the board, its node trends and the scan; returns a trend writer."""
    store.put(CATALOG_PATH, sample_catalog.to_json_bytes())
    store.put(result_path("caseboard", BOARD_KEY), BOARD_BODY)
    store.put(result_path("scan", SCAN_KEY), SCAN_BODY)
    for key in NODE_KEYS:
        store.put(result_path("trend", key), key.encode())

    def store_trend(values_fn, spec=None) -> str:
        results = ResultService(store, WorkerPool(4, 1.0))
        return get_trend(
            spec or make_spec(),
            reader=FakeReader(values_fn=values_fn),
            results=results,
            catalog=sample_catalog,
        )[1]

    return store_trend


@pytest.fixture
def out(tmp_path):
    return tmp_path / "out"


@pytest.fixture
def export(store, tmp_path, out):
    def run(case=None, folder=None) -> DemoManifest:
        """Export one case and return the manifest file that it wrote."""
        folder = folder or out
        export_demo(
            [case or make_case()],
            folder,
            store=store,
            reader=FakeReader(),
            services=SERVICES,
            answers_dir=tmp_path / "answers",
        )
        return DemoManifest.model_validate_json((folder / "manifest.json").read_bytes())

    return run


@pytest.mark.parametrize(
    "values_fn, opened",
    [(rising, BOARD_FILES), (NOISE, [f"{CASE}/scan.json"]), (missing, [])],
)
def test_should_write_the_files_that_the_verdict_opens(
    stored, export, out, values_fn, opened
):
    stored(values_fn)
    export()
    assert sorted(files_under(out)) == sorted(SHARED_FILES + opened)


def test_should_list_the_trend_file_with_its_key_and_s(stored, export):
    key = stored(NOISE)
    expected = ManifestFile(
        file=f"{CASE}/trend.json", key=key, s=encode_request_spec(make_spec())
    )
    assert export().cases[0].kinds["trend"] == expected


def test_should_write_s_as_the_browser_codec_does(stored, export):
    stored(NOISE)
    assert export().cases[0].kinds["trend"].s in GOLDEN_S


def test_should_list_the_board_file_with_its_key_and_s(stored, export):
    stored(rising)
    expected = ManifestFile(
        file=f"{CASE}/caseboard.json",
        key=BOARD_KEY,
        s=encode_request_spec(BOARD_SPEC),
    )
    assert export().cases[0].kinds["caseboard"] == expected


def test_should_list_each_node_trend_under_referenced(stored, export):
    stored(rising)
    assert export().cases[0].referenced == NODE_FILES


@pytest.mark.parametrize(
    "file, body",
    [
        (f"{CASE}/caseboard.json", BOARD_BODY),
        (f"{CASE}/trend.{NODE_KEYS[0]}.json", NODE_KEYS[0].encode()),
    ],
)
def test_should_copy_the_stored_bytes(stored, export, out, file, body):
    stored(rising)
    export()
    assert (out / file).read_bytes() == body


def test_should_copy_the_stored_catalog(stored, export, out, store):
    stored(NOISE)
    export()
    assert (out / "catalog.json").read_bytes() == store.get(CATALOG_PATH)


@pytest.mark.parametrize(
    "path_of",
    [
        lambda trend_key: CATALOG_PATH,
        lambda trend_key: result_path("trend", trend_key),
        lambda trend_key: result_path("caseboard", BOARD_KEY),
        lambda trend_key: result_path("trend", NODE_KEYS[0]),
    ],
)
def test_should_fail_when_a_stored_file_is_missing(stored, export, store, path_of):
    store.files.pop(path_of(stored(rising)))
    with pytest.raises(ExportError):
        export()


def test_should_write_nothing_when_the_export_fails(stored, export, out, store):
    stored(rising)
    store.files.pop(result_path("trend", NODE_KEYS[0]))
    with pytest.raises(ExportError):
        export()
    assert not out.exists()


def test_should_fail_when_the_verdict_opens_a_kind_the_case_lacks(stored, export):
    stored(rising)
    with pytest.raises(ExportError):
        export(make_case(caseboard=None))


def test_should_give_the_same_bytes_on_a_second_export(stored, export, tmp_path):
    stored(rising)
    export(folder=tmp_path / "first")
    export(folder=tmp_path / "second")
    assert files_under(tmp_path / "first") == files_under(tmp_path / "second")


def test_should_fail_when_the_parse_leads_to_another_trend(stored, export):
    # The question parses to T2M, and the stored trend of the case is T2M_MAX.
    other = make_spec(var="T2M_MAX")
    stored(rising, other)
    with pytest.raises(ExportError):
        export(make_case(trend=other))


def test_should_use_a_stored_model_proposal(stored, export, out, store, sample_catalog):
    stored(NOISE)
    proposal = parse_rules(QUESTION.en, "en", sample_catalog)
    key = parse_key(QUESTION.en, "en", sample_catalog.version)
    put_proposal(store, key, proposal.model_copy(update={"source": "model"}))
    export()
    assert json.loads((out / CASE / "parse.en.json").read_bytes())["source"] == "model"


def test_should_copy_an_answers_file_that_exists(stored, export, out, tmp_path):
    stored(NOISE)
    (tmp_path / "answers").mkdir()
    (tmp_path / "answers" / f"{CASE}.ko.json").write_bytes(ANSWERS_BODY)
    export()
    assert (out / CASE / "answers.ko.json").read_bytes() == ANSWERS_BODY


def test_should_list_an_answers_file_that_exists(stored, export, tmp_path):
    stored(NOISE)
    (tmp_path / "answers").mkdir()
    (tmp_path / "answers" / f"{CASE}.ko.json").write_bytes(ANSWERS_BODY)
    expected = ManifestAnswers(ko=f"{CASE}/answers.ko.json", en=None)
    assert export().cases[0].answers == expected


def test_should_list_no_answers_when_none_exist(stored, export):
    stored(NOISE)
    assert export().cases[0].answers == ManifestAnswers(ko=None, en=None)
