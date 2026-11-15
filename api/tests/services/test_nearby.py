"""Nearby areas of the no-trend fallback, selected on the server (DEC-007, FR-19)."""

import dataclasses
from pathlib import Path

import pytest

from boramae.contracts.content import RegistryLink
from boramae.contracts.results import TrendResult
from boramae.contracts.results_scan import GridCell, ScanResult, TrendGrid
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.services.nearby import select_nearby
from boramae.services.scan import get_scan
from boramae.spec.canonical import canonicalize, grid_path
from boramae.spec.validate import validate_request
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService
from tests.fakes import POWER_GRID, DictStore, FakeReader

FIXTURES = Path(__file__).parents[1] / "fixtures"
# GWETTOP annual_mean on Seoul cell [255, 491], window 1981 to 2026-09.
FOCUS = TrendResult.model_validate_json(
    (FIXTURES / "trend.no-trend.sample.json").read_bytes()
)
SEOUL = Circle(lat=37.5665, lon=126.978, radius_km=25)
# No cell center lies within 25 km of this pin; its containing cell is the Seoul cell.
SEOUL_SOUTH = Circle(lat=37.30, lon=127.15, radius_km=25)
# The cell of a 25 km circle on Phoenix (33.45 N, 112.07 W).
PHOENIX_CELL = (247, 109)
WINDOW = (1981, "2026-09")
SEOUL_LON_I = 491
# Cell rows north of the Seoul cell (37.5 N): row 272 (46 N) is 945 km away from its
# center, row 273 (46.5 N) 1,001 km.
ROW_945_KM = 272
ROW_1001_KM = 273
ROW = RegistryLink.model_validate(
    {
        "id": "test-precipitation-topsoil",
        "driver": {
            "var": "PRECTOTCORR",
            "metric": {
                "id": "annual_total",
                "months": None,
                "threshold": None,
                "op": None,
            },
        },
        "response": {
            "var": "GWETTOP",
            "metric": {
                "id": "annual_mean",
                "months": None,
                "threshold": None,
                "op": None,
            },
        },
        "expected_sign": "+",
        "mechanism": {"en": "Test mechanism", "ko": "시험 메커니즘"},
        "scale": "Test",
        "area": "user",
        "lag_years": 0,
        "status": "robust",
        "doi": "10.1000/test",
        "url": None,
        "citation": "Test 2026",
    }
)
OTHER_ROW = ROW.model_copy(
    update={"response": ROW.response.model_copy(update={"var": "RH2M"})}
)


def focus(slope=0.01, metric_used=None, cells=None):
    sen = dataclasses.replace(FOCUS.stats.sen, slope=slope)
    stats = FOCUS.stats.model_copy(update={"sen": sen})
    spec = FOCUS.spec.model_copy(update={"cells": cells or FOCUS.spec.cells})
    return FOCUS.model_copy(
        update={"metric_used": metric_used, "stats": stats, "spec": spec}
    )


def cell(lat_i, lon_i=SEOUL_LON_I, p=0.001, sign=1, is_significant=True, used=None):
    return GridCell(
        lat_i=lat_i,
        lon_i=lon_i,
        p=p,
        rate_per_decade=0.1 * sign,
        sign=sign,
        is_significant=is_significant,
        metric_used=used,
    )


def make_grid(*cells, window=WINDOW, var="GWETTOP", metric=None):
    return TrendGrid(
        ds="power-merra2-monthly@2026-09",
        eng="1.0.0",
        var=var,
        metric=metric or SpecMetric(id="annual_mean"),
        window=window,
        cells=list(cells),
    )


def nearby(grid, focus_result=None, registry=()):
    return select_nearby(grid, focus_result or focus(), POWER_GRID, registry)


def cells_of(selection):
    return [(area.lat_i, area.lon_i) for area in selection[0]]


# 50 tests at p 0.5 around Seoul and one significant cell at p 0.04.
def crowded_grid():
    family = [
        cell(256 + index // 10, 489 + index % 10, p=0.5, is_significant=False)
        for index in range(50)
    ]
    return make_grid(*family, cell(262, p=0.04))


def test_should_return_the_3_nearest_cells_nearest_first():
    grid = make_grid(cell(259), cell(256), cell(258), cell(257))
    assert cells_of(nearby(grid)) == [(256, 491), (257, 491), (258, 491)]


@pytest.mark.parametrize(("lat_i", "count"), [(ROW_945_KM, 1), (ROW_1001_KM, 0)])
def test_should_take_only_cells_within_1000_km(lat_i, count):
    assert len(nearby(make_grid(cell(lat_i)))[0]) == count


def test_should_give_the_distance_from_the_center_of_the_area_cells():
    area = nearby(make_grid(cell(ROW_945_KM)))[0][0]
    assert area.distance_km == pytest.approx(945.2, abs=0.5)


def test_should_give_the_center_of_the_cell():
    area = nearby(make_grid(cell(256)))[0][0]
    assert (area.lat, area.lon) == (38.0, 126.875)


def test_should_consider_only_cells_with_the_metric_used_of_the_focus():
    grid = make_grid(cell(256, used="event_days"), cell(257, used="date"))
    assert cells_of(nearby(grid, focus(metric_used="date"))) == [(257, 491)]


def test_should_leave_out_the_cells_of_the_area():
    assert nearby(make_grid(cell(255))) == ([], None)


def test_should_leave_out_a_cell_that_is_not_significant():
    assert nearby(make_grid(cell(256, is_significant=False))) == ([], None)


def test_should_leave_out_a_significant_cell_that_bh_does_not_select():
    assert nearby(crowded_grid()) == ([], None)


@pytest.mark.parametrize(("sign", "is_opposite"), [(-1, True), (1, False)])
def test_should_mark_a_cell_that_trends_the_other_way(sign, is_opposite):
    assert nearby(make_grid(cell(256, sign=sign)))[0][0].is_opposite is is_opposite


@pytest.mark.parametrize(
    ("sign", "registry", "mechanism"),
    [
        (-1, [OTHER_ROW, ROW], ROW.mechanism),
        (1, [ROW], None),
        (-1, [OTHER_ROW], None),
    ],
    ids=["opposite-with-row", "same-sign", "no-row-names-the-focus"],
)
def test_should_give_an_opposite_cell_the_registry_mechanism(sign, registry, mechanism):
    selection = nearby(make_grid(cell(256, sign=sign)), registry=registry)
    assert selection[0][0].mechanism == mechanism


def test_should_give_each_entry_the_grid_window():
    assert nearby(make_grid(cell(256)))[0][0].grid_window == WINDOW


def test_should_note_a_center_outside_the_grid_box():
    phoenix = focus(cells=[PHOENIX_CELL])
    assert nearby(make_grid(cell(256)), phoenix) == ([], "outside_grid")


def test_should_note_a_missing_grid():
    assert nearby(None) == ([], "no_grid")


def test_should_note_a_grid_of_another_window():
    grid = make_grid(cell(256), window=(1991, "2026-09"))
    assert nearby(grid) == ([], "grid_window_differs")


SCAN_SPEC = RequestSpec(
    v=1,
    kind="scan",
    var="PRECTOTCORR",
    metric=SpecMetric(id="rx1day"),
    area=SEOUL,
    window=RequestWindow(start=1981, end="latest"),
)


def scan(catalog, store, area=SEOUL):
    return get_scan(
        SCAN_SPEC.model_copy(update={"area": area}),
        reader=FakeReader(),
        results=ResultService(store, WorkerPool(4, 1.0)),
        catalog=catalog,
    )


def store_focus_grid(catalog, store):
    canonical = canonicalize(validate_request(SCAN_SPEC, catalog), catalog)
    grid = make_grid(cell(256), var=canonical.var, metric=canonical.metric)
    path = grid_path(canonical.ds, canonical.var, canonical.metric)
    store.put(path, grid.to_json_bytes())


def test_should_read_the_grid_of_the_focus_pair(sample_catalog):
    store = DictStore()
    store_focus_grid(sample_catalog, store)
    result = ScanResult.model_validate_json(scan(sample_catalog, store)[0])
    assert [(area.lat_i, area.lon_i) for area in result.nearby] == [(256, 491)]


def test_should_answer_no_grid_when_the_focus_pair_has_no_grid(sample_catalog):
    result = ScanResult.model_validate_json(scan(sample_catalog, DictStore())[0])
    assert result.nearby_note == "no_grid"


def scan_body_with_grid(catalog, area):
    store = DictStore()
    store_focus_grid(catalog, store)
    return scan(catalog, store, area)[0]


# The two pins share one key, so a stored scan must not depend on the pin.
def test_should_store_one_body_for_two_pins_with_the_same_cells(sample_catalog):
    assert scan_body_with_grid(sample_catalog, SEOUL) == scan_body_with_grid(
        sample_catalog, SEOUL_SOUTH
    )


def test_should_change_the_scan_key_when_the_grid_file_appears(sample_catalog):
    store = DictStore()
    before = scan(sample_catalog, store)[1]
    store_focus_grid(sample_catalog, store)
    assert scan(sample_catalog, store)[1] != before
