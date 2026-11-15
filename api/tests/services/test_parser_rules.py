"""The rule-based parser: keywords, place, months, threshold, years and defaults."""

from pathlib import Path

import pytest

from boramae.contracts.content import Place
from boramae.contracts.spec import (
    InvestigationMetric,
    InvestigationSpec,
    LocalizedText,
    ParseProposal,
    ProposedVariable,
    ReasonCode,
    RequestWindow,
    SpecPlace,
    UnavailableRequest,
)
from boramae.services.content import CONTENT_FILES, read_content
from boramae.services.parser_rules import normalize, parse_rules

_RELATIVE, _MODEL = CONTENT_FILES["inputs"]
INPUTS = {
    item.id: item
    for item in read_content(
        Path(__file__).parents[3] / "content" / _RELATIVE, _MODEL
    ).inputs
}
# The places of the PRD specs of inputs 1 and 44 (PRD "The spec the parser fills").
SEOUL = Place(
    id="kr-seoul",
    name=LocalizedText(en="Seoul", ko="서울"),
    alt=[],
    lat=37.5665,
    lon=126.978,
    country="KR",
    kind="city",
)
PHOENIX = Place(
    id="us-phoenix",
    name=LocalizedText(en="Phoenix", ko="피닉스"),
    alt=[],
    lat=33.4484,
    lon=-112.074,
    country="US",
    kind="city",
)
FULL_RECORD = RequestWindow(start=1981, end="latest")


def _at(place):
    return lambda text, lang: place


def _nowhere(text, lang):
    return None


def _first_pick(proposal):
    first = proposal.variables[0]
    return first.var, first.metric_id


@pytest.mark.parametrize(
    ("text", "lang", "expected"),
    [
        ("서울 첫눈이 늦어지고 있나요?", "ko", ("PRECSNO", "first_date")),
        ("대구 폭염 일수가 늘었나요?", "ko", ("T2M_MAX", "threshold_days")),
        ("Is California's snowpack shrinking?", "en", ("SNODP", "annual_mean")),
        (
            "Are heavy downpours increasing in New England?",
            "en",
            ("PRECTOTCORR", "threshold_days"),
        ),
    ],
)
def test_keyword_pair_gives_its_variable(sample_catalog, text, lang, expected):
    proposal = parse_rules(text, lang, sample_catalog, _nowhere)
    assert _first_pick(proposal) == expected


@pytest.mark.parametrize(
    ("text", "lang"), [("전남 가뭄이 잦아졌나요?", "ko"), ("Is drought worse?", "en")]
)
def test_drought_gives_precipitation_and_soil_wetness(sample_catalog, text, lang):
    proposal = parse_rules(text, lang, sample_catalog, _nowhere)
    assert [item.var for item in proposal.variables] == ["PRECTOTCORR", "GWETROOT"]


@pytest.mark.parametrize(("lang", "name"), [("ko", "서울"), ("en", "Seoul")])
def test_input_1_gives_the_prd_spec(sample_catalog, lang, name):
    text = getattr(INPUTS[1].text, lang)
    proposal = parse_rules(text, lang, sample_catalog, _at(SEOUL))
    assert proposal.spec == InvestigationSpec(
        lang=lang,
        intent="timing",
        place=SpecPlace(name=name, lat=37.5665, lon=126.978, radius_km=25),
        metric=InvestigationMetric(
            id="first_date",
            var="PRECSNO",
            op=">=",
            value=0.1,
            unit="mm/day",
            season_start="08-01",
        ),
        window=FULL_RECORD,
        compare_to=None,
        board="CB-01",
        clarify=None,
    )


def test_input_44_gives_the_prd_spec(sample_catalog):
    proposal = parse_rules(INPUTS[44].text.en, "en", sample_catalog, _at(PHOENIX))
    # The unit is the catalog spelling of the data unit: C, which the PRD prints as °C.
    assert proposal.spec == InvestigationSpec(
        lang="en",
        intent="extremes_count",
        place=SpecPlace(name="Phoenix", lat=33.4484, lon=-112.074, radius_km=25),
        metric=InvestigationMetric(
            id="threshold_days",
            var="T2M_MAX",
            op=">=",
            value=43.3,
            unit="C",
            typed="110 °F",
            months=[5, 6, 7, 8, 9, 10],
        ),
        display_units="imperial",
        window=FULL_RECORD,
        compare_to=None,
        board="CB-02",
        clarify=None,
    )


@pytest.mark.parametrize(("field", "expected"), [("typed", "43.3 °C"), ("value", 43.3)])
def test_input_44_in_korean_keeps_the_typed_celsius(sample_catalog, field, expected):
    proposal = parse_rules(INPUTS[44].text.ko, "ko", sample_catalog, _at(PHOENIX))
    assert getattr(proposal.spec.metric, field) == expected


def test_korean_threshold_in_degrees_takes_celsius_outside_the_us(sample_catalog):
    proposal = parse_rules(
        "서울 35도 넘는 날이 늘었나요?", "ko", sample_catalog, _at(SEOUL)
    )
    assert proposal.spec.metric.typed == "35 °C"


@pytest.mark.parametrize(
    "text", ["Is PM2.5 getting worse in Seoul?", "서울 미세먼지가 심해지고 있나요?"]
)
def test_pm25_question_is_unavailable_with_the_nearest_variable(sample_catalog, text):
    proposal = parse_rules(text, "en", sample_catalog, _nowhere)
    assert proposal.unavailable == UnavailableRequest(
        requested="PM2.5", nearest_var="PBLTOP"
    )


def test_pm25_question_proposes_the_nearest_variable(sample_catalog):
    proposal = parse_rules("Is fine dust worse?", "en", sample_catalog, _nowhere)
    assert proposal.variables == [
        ProposedVariable(
            var="PBLTOP",
            metric_id="annual_mean",
            reason_code=ReasonCode.NearestAvailable,
        )
    ]


def test_unavailable_metric_is_still_named(sample_catalog):
    # rainy_season_length has is_available false in the catalog, which is its mark.
    proposal = parse_rules("장마가 길어지고 있나요?", "ko", sample_catalog, _nowhere)
    assert _first_pick(proposal) == ("PRECTOTCORR", "rainy_season_length")


def test_text_with_no_keyword_gives_an_empty_rules_proposal(sample_catalog):
    proposal = parse_rules("Tell me a story", "en", sample_catalog, _nowhere)
    assert proposal == ParseProposal(
        spec=InvestigationSpec(
            lang="en",
            intent=None,
            place=None,
            metric=None,
            window=FULL_RECORD,
            compare_to=None,
            board=None,
            clarify=None,
        ),
        variables=[],
        source="rules",
        unavailable=None,
        clarify=None,
    )


@pytest.mark.parametrize(
    ("get", "expected"),
    [
        (lambda proposal: proposal.spec.place.name, "Seoul"),
        (_first_pick, ("T2M_MAX", "threshold_days")),
    ],
)
def test_mixed_text_finds_the_place_and_the_keyword(sample_catalog, get, expected):
    proposal = parse_rules("서울 heat wave 늘었어?", "en", sample_catalog)
    assert get(proposal) == expected


@pytest.mark.parametrize(
    ("get", "expected"),
    [
        (lambda proposal: proposal.spec.intent, "place_first"),
        (lambda proposal: proposal.variables[0].reason_code, ReasonCode.PlaceDefault),
    ],
)
def test_question_that_names_only_a_place_is_place_first(sample_catalog, get, expected):
    proposal = parse_rules("What is changing in Daejeon?", "en", sample_catalog)
    assert get(proposal) == expected


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Is Jeju getting warmer in summer?", "en"),
        ("제주 여름이 더워지고 있나요?", "ko"),
    ],
)
def test_typed_season_turns_an_annual_metric_seasonal(sample_catalog, text, lang):
    metric = parse_rules(text, lang, sample_catalog, _nowhere).spec.metric
    assert (metric.id, metric.months) == ("seasonal_mean", [6, 7, 8])


@pytest.mark.parametrize(
    ("text", "lang", "months"),
    [
        ("서울 폭염 5월부터 9월까지", "ko", [5, 6, 7, 8, 9]),
        ("서울 폭염 7~8월", "ko", [7, 8]),
        ("heat wave days from June to August", "en", [6, 7, 8]),
        ("heat wave days from November to February", "en", [11, 12, 1, 2]),
    ],
)
def test_typed_month_range_gives_its_months(sample_catalog, text, lang, months):
    proposal = parse_rules(text, lang, sample_catalog, _nowhere)
    assert proposal.spec.metric.months == months


def test_keyword_season_word_is_not_read_as_months(sample_catalog):
    proposal = parse_rules("겨울이 짧아지고 있나요?", "ko", sample_catalog, _nowhere)
    assert proposal.spec.metric.months is None


@pytest.mark.parametrize(
    ("text", "lang", "window"),
    [
        (
            "2000년 이후 대전 봄비가 변했나요?",
            "ko",
            RequestWindow(start=2000, end="latest"),
        ),
        ("Rain in Seoul from 1990 to 2010", "en", RequestWindow(start=1990, end=2010)),
    ],
)
def test_typed_years_set_the_window(sample_catalog, text, lang, window):
    proposal = parse_rules(text, lang, sample_catalog, _nowhere)
    assert proposal.spec.window == window


def test_threshold_in_inches_reads_in_millimetres(sample_catalog):
    proposal = parse_rules(
        "days with a 1 inch downpour", "en", sample_catalog, _nowhere
    )
    assert proposal.spec.metric.value == 25.4


def test_typed_threshold_of_another_unit_is_ignored(sample_catalog):
    proposal = parse_rules("heat wave above 20 mm", "en", sample_catalog, _nowhere)
    assert proposal.spec.metric.value == 33.0


def test_normalize_folds_width_case_and_spaces():
    assert normalize("  Ｓｅｏｕｌ   First\tSNOW ") == "seoul first snow"
