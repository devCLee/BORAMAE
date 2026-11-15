"""The canonical spec, the result key and the grid path."""

import hashlib
import json
import re
from pathlib import Path

import pytest

from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import (
    CanonicalSpec,
    MetricSettings,
    RequestSpec,
    SpecMetric,
    canonical_json,
)
from boramae.spec import canonical
from boramae.spec.canonical import (
    canonical_metric,
    canonicalize,
    grid_path,
    result_key,
)
from boramae.spec.validate import decode_s, validate_request

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "api/tests/fixtures"
MANIFEST = json.loads((FIXTURES / "manifest.sample.json").read_text(encoding="utf-8"))
FIRST_SNOW = {
    "v": 1,
    "kind": "trend",
    "var": "PRECSNO",
    "metric": {
        "id": "first_date",
        "threshold": "0.1",
        "op": ">=",
        "season_start": "08-01",
    },
    "area": {"lat": 37.5665, "lon": 126.978, "radius_km": 25},
    "window": {"start": 1981, "end": "latest"},
}
HOT_DAYS = FIRST_SNOW | {
    "var": "T2M_MAX",
    "metric": {"id": "threshold_days", "threshold": "33", "months": [6, 7, 8]},
}
SUMMER_MEAN = FIRST_SNOW | {"var": "T2M", "metric": {"id": "seasonal_mean"}}
WETTEST_DAY_SCAN = FIRST_SNOW | {
    "kind": "scan",
    "var": "PRECTOTCORR",
    "metric": {"id": "rx1day", "months": [6, 7, 8, 9]},
}
# Written by hand from docs/BUILD_CONTRACT.md "Canonical JSON": sorted keys, no
# spaces, and no member for the null months and the null content.
FIRST_SNOW_CANONICAL_JSON = (
    '{"cells":[[255,491]],"ds":"power-merra2-daily@2026-09","eng":"1.0.0",'
    '"kind":"trend","metric":{"id":"first_date","op":">=","season_start":"08-01",'
    '"threshold":"0.1"},"v":1,"var":"PRECSNO","window":[1981,"2026-09"]}'
)
NO_DEFAULTS = MetricSettings()


@pytest.fixture(autouse=True)
def engine_version_of_the_samples(monkeypatch):
    monkeypatch.setattr(canonical, "ENGINE_VERSION", "1.0.0")


def canonical_of(spec, catalog, content_mark=None):
    validated = validate_request(RequestSpec.model_validate(spec), catalog)
    return canonicalize(validated, catalog, content_mark)


def key_of(spec, catalog, content_mark=None):
    return result_key(canonical_of(spec, catalog, content_mark))


def with_metric(spec, **settings):
    return spec | {"metric": spec["metric"] | settings}


def with_window(spec, start, end):
    return spec | {"window": {"start": start, "end": end}}


def with_pin(spec, lat, lon):
    return spec | {"area": spec["area"] | {"lat": lat, "lon": lon}}


def with_daily_ds(catalog, ds):
    data = catalog.model_dump()
    data["datasets"]["daily"]["ds"] = ds
    return Catalog.model_validate(data)


def leaf_types(value):
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return set().union(*map(leaf_types, value))
    return {type(value)}


def sample_spec(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["spec"]


def test_canonical_json_is_the_hand_written_text(sample_catalog):
    canonical_spec = canonical_of(FIRST_SNOW, sample_catalog)
    assert canonical_json(canonical_spec) == FIRST_SNOW_CANONICAL_JSON


def test_result_key_is_the_first_32_hex_characters_of_sha256(sample_catalog):
    digest = hashlib.sha256(FIRST_SNOW_CANONICAL_JSON.encode("utf-8")).hexdigest()
    assert key_of(FIRST_SNOW, sample_catalog) == digest[:32]


def test_result_key_is_the_key_of_the_manifest_sample(sample_catalog):
    entry = MANIFEST["cases"][0]["kinds"]["trend"]
    request = decode_s(entry["s"]).model_dump()
    assert key_of(request, sample_catalog) == entry["key"]


@pytest.mark.parametrize(
    ("spec", "content_mark", "sample"),
    [
        (FIRST_SNOW, None, "trend.significant.sample.json"),
        (FIRST_SNOW | {"kind": "caseboard"}, "ad5e8601df2b", "caseboard.sample.json"),
        (WETTEST_DAY_SCAN, "5f2c9a1e07b4", "scan.nearby.sample.json"),
    ],
)
def test_canonical_spec_is_the_spec_of_the_contract_sample(
    sample_catalog, spec, content_mark, sample
):
    assert canonical_of(
        spec, sample_catalog, content_mark
    ) == CanonicalSpec.model_validate(sample_spec(sample))


def test_two_pins_that_cover_the_same_cells_give_the_same_key(sample_catalog):
    assert key_of(with_pin(FIRST_SNOW, 37.45, 126.9), sample_catalog) == key_of(
        FIRST_SNOW, sample_catalog
    )


@pytest.mark.parametrize(
    "other",
    [
        with_pin(FIRST_SNOW, 35.1796, 129.0756),
        with_window(FIRST_SNOW, 1981, 2025),
        with_window(FIRST_SNOW, 1982, "latest"),
        with_metric(FIRST_SNOW, threshold="1"),
        with_metric(FIRST_SNOW, op=">"),
        FIRST_SNOW | {"kind": "scan"},
    ],
    ids=["cell", "end year", "start year", "threshold", "op", "kind"],
)
def test_another_request_gives_another_key(sample_catalog, other):
    assert key_of(other, sample_catalog) != key_of(FIRST_SNOW, sample_catalog)


def test_key_does_not_change_with_the_member_order(sample_catalog):
    backward = json.loads(
        json.dumps(FIRST_SNOW), object_pairs_hook=lambda pairs: dict(reversed(pairs))
    )
    assert key_of(backward, sample_catalog) == key_of(FIRST_SNOW, sample_catalog)


def test_latest_becomes_the_pinned_month_of_the_catalog(sample_catalog):
    assert canonical_of(FIRST_SNOW, sample_catalog).window == (1981, "2026-09")


def test_end_year_equal_to_the_pinned_year_gives_the_key_of_latest(sample_catalog):
    assert key_of(with_window(FIRST_SNOW, 1981, 2026), sample_catalog) == key_of(
        FIRST_SNOW, sample_catalog
    )


def test_end_year_before_the_pinned_year_becomes_its_december(sample_catalog):
    spec = with_window(FIRST_SNOW, 1991, 2020)
    assert canonical_of(spec, sample_catalog).window == (1991, "2020-12")


@pytest.mark.parametrize("threshold", ["0.10", ".1", "00.1", "0.1000"])
def test_equal_thresholds_give_one_key(sample_catalog, threshold):
    assert key_of(
        with_metric(FIRST_SNOW, threshold=threshold), sample_catalog
    ) == key_of(FIRST_SNOW, sample_catalog)


@pytest.mark.parametrize(
    ("typed", "normalized"),
    [
        ("0.1", "0.1"),
        (".5", "0.5"),
        ("5.", "5"),
        ("43.30", "43.3"),
        ("100", "100"),
        ("-10", "-10"),
        ("-10.0", "-10"),
        ("007", "7"),
        ("0", "0"),
        ("-0.0", "0"),
    ],
)
def test_threshold_is_stored_as_a_normalized_decimal_string(typed, normalized):
    metric = SpecMetric(id="threshold_days", threshold=typed)
    assert canonical_metric(metric, NO_DEFAULTS).threshold == normalized


@pytest.mark.parametrize("months", [[8, 7, 6], [7, 6, 8, 6]])
def test_months_in_any_order_give_one_key(sample_catalog, months):
    assert key_of(with_metric(HOT_DAYS, months=months), sample_catalog) == key_of(
        HOT_DAYS, sample_catalog
    )


def test_months_across_the_year_end_are_stored_sorted(sample_catalog):
    spec = with_metric(HOT_DAYS, months=[12, 1, 2])
    assert canonical_of(spec, sample_catalog).metric.months == [1, 2, 12]


def test_omitted_months_and_the_default_months_give_one_key(sample_catalog):
    assert key_of(SUMMER_MEAN, sample_catalog) == key_of(
        with_metric(SUMMER_MEAN, months=[6, 7, 8]), sample_catalog
    )


def test_omitted_settings_and_the_default_settings_give_one_key(sample_catalog):
    bare = FIRST_SNOW | {"metric": {"id": "first_date"}}
    assert key_of(bare, sample_catalog) == key_of(FIRST_SNOW, sample_catalog)


def test_canonical_metric_of_a_canonical_metric_is_unchanged():
    defaults = MetricSettings(threshold="0.10", op=">=", months=[8, 6, 7])
    once = canonical_metric(SpecMetric(id="threshold_days"), defaults)
    assert canonical_metric(once, defaults) == once


def test_every_leaf_of_the_canonical_json_is_an_integer_or_a_string(sample_catalog):
    canonical_spec = canonical_of(
        with_metric(HOT_DAYS, op=">", season_start="01-01"), sample_catalog, "ad5e8601"
    )
    assert leaf_types(json.loads(canonical_json(canonical_spec))) == {int, str}


def test_canonical_cells_are_sorted(sample_catalog):
    wide = FIRST_SNOW | {"area": FIRST_SNOW["area"] | {"radius_km": 150}}
    cells = canonical_of(wide, sample_catalog).cells
    assert cells == sorted(cells)


def test_monthly_metric_takes_the_monthly_dataset_version(sample_catalog):
    ds = canonical_of(SUMMER_MEAN, sample_catalog).ds
    assert ds == "power-merra2-monthly@2026-09"


def test_content_mark_changes_the_key(sample_catalog):
    board = FIRST_SNOW | {"kind": "caseboard"}
    assert key_of(board, sample_catalog, "ad5e8601df2b") != key_of(
        board, sample_catalog, "5f2c9a1e07b4"
    )


def test_another_engine_version_changes_the_key(sample_catalog, monkeypatch):
    before = key_of(FIRST_SNOW, sample_catalog)
    monkeypatch.setattr(canonical, "ENGINE_VERSION", "1.0.1")
    assert key_of(FIRST_SNOW, sample_catalog) != before


def test_another_dataset_version_changes_the_key(sample_catalog):
    newer = with_daily_ds(sample_catalog, "power-merra2-daily@2026-10")
    assert key_of(FIRST_SNOW, newer) != key_of(FIRST_SNOW, sample_catalog)


def test_grid_path_names_the_dataset_the_variable_and_a_16_hex_metric_key():
    metric = SpecMetric(id="first_date", threshold="0.1", op=">=")
    assert re.fullmatch(
        r"grid/power-merra2-daily@2026-09/PRECSNO/[0-9a-f]{16}\.json",
        grid_path("power-merra2-daily@2026-09", "PRECSNO", metric),
    )


def test_grid_path_differs_for_another_threshold():
    metric = SpecMetric(id="first_date", threshold="0.1", op=">=")
    other = SpecMetric(id="first_date", threshold="1", op=">=")
    assert grid_path("ds", "PRECSNO", metric) != grid_path("ds", "PRECSNO", other)


def test_grid_path_is_equal_for_equal_metrics(sample_catalog):
    canonical_spec = canonical_of(FIRST_SNOW | {"kind": "scan"}, sample_catalog)
    defaults = MetricSettings(threshold="0.10", op=">=", season_start="08-01")
    built_by_the_grid_job = canonical_metric(SpecMetric(id="first_date"), defaults)
    assert grid_path(
        canonical_spec.ds, canonical_spec.var, canonical_spec.metric
    ) == grid_path(canonical_spec.ds, canonical_spec.var, built_by_the_grid_job)
