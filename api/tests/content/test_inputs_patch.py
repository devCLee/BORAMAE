"""Inputs 4, 8 and 44 and the CB-02 focus give the numbers their questions ask for."""

import statistics
from pathlib import Path

import numpy as np
import pytest

from boramae.batch.build_catalog import build_catalog
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.services.catalog import find_metric, find_variable
from boramae.services.content import CONTENT_FILES, read_content
from boramae.services.parser_rules import parse_rules
from boramae.services.trend import compute_trend
from boramae.spec.canonical import canonicalize, source_freq
from boramae.spec.validate import validate_request
from tests.fakes import FakeReader

CONTENT = Path(__file__).parents[3] / "content"


def _content(name):
    relative, model = CONTENT_FILES[name]
    return read_content(CONTENT / relative, model)


INPUTS = {item.id: item for item in _content("inputs").inputs}
BOARDS = {board.id: board for board in _content("boards")}
# The catalog that build-catalog makes from the seed. The fake stores carry every
# variable in both stores, so only the seed decides which store a metric reads.
SEED_CATALOG = build_catalog(
    FakeReader(), _content("catalog_seed"), lambda freq: ("fake-id", "fake-version")
)[0]
SEOUL = Circle(lat=37.5665, lon=126.978, radius_km=25)
FIRST_YEAR = 1981
# May to September of any year: 31 x 5 + 30 x 6 + 31 x 7 + 31 x 8 + 30 x 9.
MAY_TO_SEP_MONTH_NUMBER_SUM = 1070.0
# A Seoul-like daily T2M: warmest on 28 Jul, and below 5 C from about 25 Nov to
# about 30 Mar, so the winter lasts about 125 days and the spring (5 C to 20 C
# rising) about 63.
WARMEST_DAY = np.datetime64("2000-07-28")
MEAN_C, AMPLITUDE_C, YEAR_DAYS = 11.9, 14.5, 365.2425
WINTER_DAYS = 125


def _request_spec(input_id):
    expected = INPUTS[input_id].expected
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
        area=SEOUL,
        window=RequestWindow(start=expected.window_start or FIRST_YEAR, end="latest"),
    )


def _canonical(input_id, catalog):
    return canonicalize(validate_request(_request_spec(input_id), catalog), catalog)


def _month_number(var, freq, times, cell):
    return times.astype("datetime64[M]").astype(int) % 12 + 1


def _seoul_like_t2m(var, freq, times, cell):
    days = (times - WARMEST_DAY).astype(int)
    return MEAN_C + AMPLITUDE_C * np.cos(2 * np.pi * days / YEAR_DAYS)


def _nowhere(text, lang):
    return None


def _yearly_values(input_id, values_fn):
    canonical = _canonical(input_id, SEED_CATALOG)
    result = compute_trend(canonical, SEED_CATALOG, FakeReader(values_fn=values_fn))
    return result.series.yearly.values


def test_input_8_canonical_spec_validates_against_the_sample_catalog(sample_catalog):
    assert _canonical(8, sample_catalog).metric == SpecMetric(
        id="seasonal_total", months=[5, 6, 7, 8, 9]
    )


def test_cdd18_3_seasonal_total_reads_the_daily_store():
    variable = find_variable(SEED_CATALOG, "CDD18_3")
    metric = find_metric(SEED_CATALOG, "seasonal_total")
    assert source_freq(variable, metric) == "daily"


def test_input_8_sums_the_daily_cooling_degree_days_of_may_to_september():
    # The old degree_days row subtracted the 18.3 base again, and every year read 0.
    assert set(_yearly_values(8, _month_number)) == {MAY_TO_SEP_MONTH_NUMBER_SUM}


def test_input_8_pair_is_a_focus_of_its_board():
    expected = INPUTS[8].expected
    focus = BOARDS[INPUTS[8].board].focus
    assert (expected.var, expected.metric_id) in {(f.var, f.metric_id) for f in focus}


def test_input_4_counts_the_winter_length():
    values = _yearly_values(4, _seoul_like_t2m)
    assert statistics.median(values) == pytest.approx(WINTER_DAYS, abs=2)


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_rules_parse_of_input_4_counts_the_winter(sample_catalog, lang):
    text = getattr(INPUTS[4].text, lang)
    metric = parse_rules(text, lang, sample_catalog, _nowhere).spec.metric
    assert (metric.op, metric.value) == ("<", 5.0)
