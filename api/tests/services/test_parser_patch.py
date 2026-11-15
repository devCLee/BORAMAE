"""Rules parser patch (W4-PATCH-PARSER): a long typed number, and season words."""

import pytest

from boramae.services.parser_rules import parse_rules

# 309 nines overflow float to infinity; 308 digits in inches overflow after x 25.4.
OVERLONG_THRESHOLDS = [
    "heat wave above " + "9" * 309 + " °C",
    "days with a " + "1" * 308 + " inch downpour",
]


def _nowhere(text, lang):
    return None


@pytest.mark.parametrize("text", OVERLONG_THRESHOLDS)
def test_overlong_typed_number_gives_no_threshold(sample_catalog, text):
    proposal = parse_rules(text, "en", sample_catalog, _nowhere)
    assert proposal.spec.metric.typed is None


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Is the first snow of winter coming later in Seoul?", "en"),
        ("서울 겨울 첫눈이 늦어지고 있나요?", "ko"),
    ],
)
def test_season_word_keeps_the_default_months_of_a_date_metric(
    sample_catalog, text, lang
):
    metric = parse_rules(text, lang, sample_catalog, _nowhere).spec.metric
    assert (metric.var, metric.id, metric.months) == ("PRECSNO", "first_date", None)


@pytest.mark.parametrize(
    "text", ["What is changing in Winter Haven?", "Is Palm Springs getting hotter?"]
)
def test_season_word_inside_a_place_name_gives_no_seasonal_metric(sample_catalog, text):
    assert parse_rules(text, "en", sample_catalog).spec.metric.id == "annual_mean"


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Is Winter Haven getting warmer in summer?", "en"),
        ("Winter Haven의 여름이 더워지고 있나요?", "ko"),
    ],
)
def test_season_word_outside_the_place_name_still_sets_the_months(
    sample_catalog, text, lang
):
    metric = parse_rules(text, lang, sample_catalog).spec.metric
    assert (metric.id, metric.months) == ("seasonal_mean", [6, 7, 8])
