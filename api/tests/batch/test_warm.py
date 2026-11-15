"""warm: each entry runs through the service of its kind, and a stored key is skipped."""

import pytest

from boramae import deps
from boramae.batch import grid
from boramae.batch.warm import grid_argv, load_entries, run_warm
from boramae.contracts.content import DemoCase, DemoSpecs
from boramae.contracts.spec import (
    Circle,
    LocalizedText,
    RequestSpec,
    RequestWindow,
    SpecMetric,
)
from boramae.errors import ProblemError
from boramae.services.catalog import CATALOG_PATH
from boramae.services.trend import TrendFacts, get_trend
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService
from tests.fakes import FakeReader

SEOUL = Circle(lat=37.5665, lon=126.978, radius_km=25)
PHOENIX = Circle(lat=33.4484, lon=-112.074, radius_km=25)
# The one cell of SEOUL: the grid command builds only this cell in a test.
SEOUL_CELL_BOX = (255, 256, 491, 492)
FIRST_SNOW = SpecMetric(id="first_date", threshold="0.1", op=">=", season_start="08-01")
FAILING_VAR = "T2M_MAX"
GRID_COMMAND = (
    "python -m boramae.batch grid --var PRECSNO --metric first_date"
    " --threshold 0.1 --window 1981 latest"
)


def make_spec(kind="trend", var="T2M", metric=None, area=SEOUL):
    return RequestSpec(
        v=1,
        kind=kind,
        var=var,
        metric=metric or SpecMetric(id="annual_mean"),
        area=area,
        window=RequestWindow(start=1981, end="latest"),
    )


SNOW_SCAN = make_spec("scan", "PRECSNO", FIRST_SNOW)
PHOENIX_SCAN = make_spec("scan", "PRECSNO", FIRST_SNOW, PHOENIX)
MIXED_SPECS = [make_spec(), make_spec("caseboard"), PHOENIX_SCAN]
FAILING_SPECS = [make_spec(var=FAILING_VAR), make_spec(), make_spec("caseboard")]


class FakeService:
    """A service of the dispatch table that records each spec it gets."""

    def __init__(self, fail_var=None):
        self.specs = []
        self.fail_var = fail_var

    def __call__(self, spec, *, reader, results, catalog):
        self.specs.append(spec)
        if spec.var == self.fail_var:
            raise ProblemError(503, "power_unavailable")
        return b"{}", f"{len(self.specs):032x}", "miss", TrendFacts(0, False, {})


def table(service):
    return dict.fromkeys(("trend", "caseboard", "scan"), service)


@pytest.fixture
def results(store, sample_catalog):
    store.put(CATALOG_PATH, sample_catalog.to_json_bytes())
    return ResultService(store, WorkerPool(4, 1.0))


@pytest.fixture
def warm(results, sample_catalog):
    def run(specs, services, reader=None) -> int:
        reader = FakeReader() if reader is None else reader
        return run_warm(
            specs, services, reader=reader, results=results, catalog=sample_catalog
        )

    return run


def make_case(specs: DemoSpecs) -> DemoCase:
    return DemoCase(
        id="first-snow-seoul",
        input_id=1,
        lang="ko",
        question=LocalizedText(en="Is it snowing later?", ko="첫눈이 늦어지나요?"),
        area=SEOUL,
        window=RequestWindow(start=1981, end="latest"),
        specs=specs,
        prompts=[],
    )


def test_should_call_the_service_once_for_each_entry(warm):
    service = FakeService()
    warm(MIXED_SPECS, table(service))
    assert service.specs == MIXED_SPECS


def test_should_report_a_stored_entry_as_already_stored(warm, capsys):
    warm([make_spec()], {"trend": get_trend})
    capsys.readouterr()
    warm([make_spec()], {"trend": get_trend})
    assert "0 computed, 1 already stored, 0 failed" in capsys.readouterr().err


def test_should_read_no_data_for_a_stored_entry(warm):
    warm([make_spec()], {"trend": get_trend})
    reader = FakeReader()
    warm([make_spec()], {"trend": get_trend}, reader)
    assert reader.read_count == 0


def test_should_exit_non_zero_when_an_entry_fails(warm):
    assert warm(FAILING_SPECS, table(FakeService(FAILING_VAR))) == 1


def test_should_run_the_entries_after_a_failing_one(warm):
    service = FakeService(FAILING_VAR)
    warm(FAILING_SPECS, table(service))
    assert service.specs == FAILING_SPECS


def test_should_exit_zero_when_every_entry_runs(warm):
    assert warm(MIXED_SPECS, table(FakeService())) == 0


def test_should_refuse_a_scan_in_the_grid_box_with_no_grid_file(warm):
    assert warm([SNOW_SCAN], table(FakeService())) == 1


def test_should_not_run_a_refused_scan(warm):
    service = FakeService()
    warm([SNOW_SCAN], table(service))
    assert service.specs == []


def test_should_name_the_grid_command_of_a_refused_scan(warm, capsys):
    warm([SNOW_SCAN], table(FakeService()))
    assert GRID_COMMAND in capsys.readouterr().err


def test_should_run_the_scan_once_the_named_grid_command_ran(warm, store, monkeypatch):
    monkeypatch.setattr(deps, "get_store", lambda: store)
    monkeypatch.setattr(deps, "get_reader", FakeReader)
    grid.main(grid_argv(SNOW_SCAN), box=SEOUL_CELL_BOX)
    service = FakeService()
    warm([SNOW_SCAN], table(service))
    assert service.specs == [SNOW_SCAN]


def test_should_run_a_scan_outside_the_grid_box_with_no_grid_file(warm):
    service = FakeService()
    warm([PHOENIX_SCAN], table(service))
    assert service.specs == [PHOENIX_SCAN]


def test_should_list_the_demo_specs_then_the_manifest_specs(tmp_path):
    manifest = tmp_path / "extra.json"
    manifest.write_text(f"[{PHOENIX_SCAN.model_dump_json()}]", encoding="utf-8")
    case = make_case(DemoSpecs(trend=make_spec(), caseboard=None, scan=SNOW_SCAN))
    assert load_entries([case], manifest) == [make_spec(), SNOW_SCAN, PHOENIX_SCAN]


def test_should_list_only_the_demo_specs_with_no_manifest():
    case = make_case(DemoSpecs(trend=make_spec(), caseboard=None, scan=None))
    assert load_entries([case], None) == [make_spec()]
