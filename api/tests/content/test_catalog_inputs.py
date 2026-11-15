"""content/catalog-inputs.json against the PRD input catalog and its edge cases."""

import re
from collections import Counter
from pathlib import Path

import pytest

from boramae.constants import METRIC_IDS, VARIABLE_IDS
from boramae.contracts.content import ExpectedSpec
from boramae.services.content import CONTENT_FILES, read_content

_RELATIVE, _MODEL = CONTENT_FILES["inputs"]
CATALOG = read_content(Path(__file__).parents[3] / "content" / _RELATIVE, _MODEL)
INPUTS = {item.id: item for item in CATALOG.inputs}
POWER_INPUTS = [item for item in CATALOG.inputs if item.power_only]
HANGUL = re.compile(r"[가-힣]")
# Metrics with a reducer at P0 or in the planned metric work (build plan W2-INPUTS).
SUPPORTED_METRICS = {
    "annual_mean",
    "annual_total",
    "seasonal_mean",
    "seasonal_total",
    "first_date",
    "threshold_days",
    "rx1day",
    "season_onset",
    "season_length",
    "degree_days",
    "frost_free_length",
}


def _ids(items):
    return [item.id for item in items]


def test_inputs_run_from_1_to_60():
    assert _ids(CATALOG.inputs) == list(range(1, 61))


def test_edge_cases_run_from_e1_to_e20():
    assert _ids(CATALOG.edge_cases) == [f"E{n}" for n in range(1, 21)]


def test_the_120_catalog_strings_are_distinct():
    texts = {t for item in CATALOG.inputs for t in (item.text.ko, item.text.en)}
    assert len(texts) == 120


@pytest.mark.parametrize("item", CATALOG.inputs, ids=lambda item: str(item.id))
def test_korean_text_holds_hangul(item):
    assert HANGUL.search(item.text.ko)


@pytest.mark.parametrize("item", CATALOG.inputs, ids=lambda item: str(item.id))
def test_english_text_holds_no_hangul(item):
    assert not HANGUL.search(item.text.en)


def test_place_countries_split_35_korea_24_us_1_both():
    # The four "Place asked" inputs hold no place: 6, 8 and 38 in Korea, 60 in the US.
    countries = Counter(item.place.country for item in CATALOG.inputs if item.place)
    assert countries == {"KR": 32, "US": 23, "KR+US": 1}


def test_place_asked_inputs_hold_no_place():
    assert [item.id for item in CATALOG.inputs if item.place is None] == [6, 8, 38, 60]


def test_intent_counts_follow_the_prd_table():
    assert Counter(item.intent for item in CATALOG.inputs) == {
        "mean_change": 24,
        "extremes_count": 11,
        "extremes_intensity": 4,
        "timing": 5,
        "duration": 4,
        "comparison": 5,
        "place_first": 2,
        "variable_first": 2,
        "cause": 3,
    }


def test_power_alone_answers_36_inputs():
    assert len(POWER_INPUTS) == 36


@pytest.mark.parametrize("item", CATALOG.inputs, ids=lambda item: str(item.id))
def test_power_only_inputs_hold_an_expected_spec(item):
    assert item.power_only == isinstance(item.expected, ExpectedSpec)


@pytest.mark.parametrize("item", POWER_INPUTS, ids=lambda item: str(item.id))
def test_expected_var_is_a_catalog_variable(item):
    assert item.expected.var in VARIABLE_IDS


@pytest.mark.parametrize("item", POWER_INPUTS, ids=lambda item: str(item.id))
def test_expected_metric_is_a_catalog_metric(item):
    assert item.expected.metric_id in METRIC_IDS


@pytest.mark.parametrize("item", POWER_INPUTS, ids=lambda item: str(item.id))
def test_supported_marks_the_metrics_with_a_reducer(item):
    assert item.expected.supported == (item.expected.metric_id in SUPPORTED_METRICS)


@pytest.mark.parametrize(
    ("input_id", "metric_id"),
    [
        (12, "rainy_season_length"),
        (14, "spi3_months"),
        (41, "one_date_value"),
        (43, "snow_free_date"),
        (45, "spell_length"),
        (50, "spi3_months"),
    ],
)
def test_power_rows_keep_their_late_metric(input_id, metric_id):
    assert INPUTS[input_id].expected.metric_id == metric_id


@pytest.mark.parametrize(
    ("input_id", "expected"),
    [
        (
            1,
            ExpectedSpec(
                var="PRECSNO",
                metric_id="first_date",
                months=None,
                threshold="0.1",
                op=">=",
                window_start=1981,
                supported=True,
            ),
        ),
        (
            44,
            ExpectedSpec(
                var="T2M_MAX",
                metric_id="threshold_days",
                months=[5, 6, 7, 8, 9, 10],
                threshold="43.3",
                op=">=",
                window_start=1981,
                supported=True,
            ),
        ),
    ],
)
def test_expected_spec_matches_the_prd_spec(input_id, expected):
    assert INPUTS[input_id].expected == expected


@pytest.mark.parametrize(
    ("input_id", "field", "value"),
    [
        (1, "intent", "timing"),
        (1, "board", "CB-01"),
        (44, "intent", "extremes_count"),
        (44, "board", "CB-02"),
    ],
)
def test_input_fields_match_the_prd_spec(input_id, field, value):
    assert getattr(INPUTS[input_id], field) == value


@pytest.mark.parametrize(("input_id", "name"), [(1, "서울"), (44, "Phoenix")])
def test_place_matches_the_prd_spec(input_id, name):
    assert name in (INPUTS[input_id].place.name.ko, INPUTS[input_id].place.name.en)


def test_only_e12_and_e16_quote_a_reply():
    assert [case.id for case in CATALOG.edge_cases if case.reply_text] == ["E12", "E16"]
