"""Verdicts of the four demo candidates, straight from POWER. Run with -m live -s.

Each candidate is the one grid cell nearest to its place, an approximation of the
25 km area, so the result of the trend service is the authoritative verdict. The test
stores no result: it calls the engine directly and writes only the evidence file
content/evidence/demo-candidates.json. No threshold and no window is tuned here.
"""

import json
import time
from dataclasses import asdict

import pytest

from boramae.config import load_settings
from boramae.engine.definitions import ENGINE_VERSION, MIN_RECORD_YEARS
from boramae.engine.metrics import reduce_yearly
from boramae.engine.series import METRIC_USED_DATE
from boramae.engine.trend import trend_stats
from boramae.engine.types import GridDef, MetricParams, Verdict, YearlySeries
from boramae.engine.verdict import decide_verdict, residual_phi, residual_sd
from boramae.power.reader import PowerReader
from boramae.services.content import content_dir

pytestmark = pytest.mark.live

EVIDENCE_FILE = "evidence/demo-candidates.json"
NOTE = (
    "Each candidate is the one POWER grid cell nearest to its place, an approximation"
    " of the 25 km area. The result of the trend service is the authoritative verdict."
    " Slopes and intervals are per year. No threshold and no window was tuned."
)
FIRST_MONTH = "1981-01"
SEOUL = (37.5665, 126.978)  # PRD.md:249
PHOENIX = (33.4484, -112.074)  # PRD.md:273-274
# ponytail: the PRD gives no coordinates for Daegu. These are the row kr-daegu of
# content/gazetteer.json; use the confirmed demo area if input 5 becomes a demo.
DAEGU = (35.868735, 128.605026)
JUN_TO_SEP = (6, 7, 8, 9)
MAY_TO_OCT = (5, 6, 7, 8, 9, 10)
# Input, place, coordinates, variable and metric, as the PRD rows and specs give them.
CANDIDATES = [
    (
        1,
        "Seoul",
        SEOUL,
        "PRECSNO",
        MetricParams("first_date", threshold=0.1, op=">=", season_start="08-01"),
    ),
    (
        5,
        "Daegu",
        DAEGU,
        "T2M_MAX",
        MetricParams("threshold_days", threshold=33.0, op=">=", months=JUN_TO_SEP),
    ),
    (10, "Seoul", SEOUL, "PRECTOTCORR", MetricParams("rx1day", months=JUN_TO_SEP)),
    (
        44,
        "Phoenix",
        PHOENIX,
        "T2M_MAX",
        MetricParams("threshold_days", threshold=43.3, op=">=", months=MAY_TO_OCT),
    ),
]
INPUT_IDS = (1, 5, 10, 44)
FULL_RECORD_VERDICTS = (
    Verdict.SignificantRise,
    Verdict.SignificantFall,
    Verdict.NotYet,
    Verdict.NoTrend,
)


@pytest.fixture(scope="module")
def saved() -> dict[int, dict]:
    reader = PowerReader(load_settings())
    grid, last_month = reader.grid(), reader.last_valid_month("daily")
    evidence = {
        "engine_version": ENGINE_VERSION,
        "window": [FIRST_MONTH, last_month],
        "note": NOTE,
        "candidates": [
            _run_candidate(reader, grid, last_month, *candidate)
            for candidate in CANDIDATES
        ],
    }
    path = content_dir() / EVIDENCE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(evidence, indent=2, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    records = json.loads(path.read_text(encoding="utf-8"))["candidates"]
    print("\n" + "\n".join(_summary(record) for record in records))
    return {record["input_id"]: record for record in records}


def test_should_save_the_four_candidates_in_order(saved):
    assert tuple(saved) == INPUT_IDS


@pytest.mark.parametrize("input_id", INPUT_IDS)
def test_should_give_the_candidate_a_verdict_on_its_full_record(saved, input_id):
    assert saved[input_id]["verdict"] in FULL_RECORD_VERDICTS


def test_should_save_the_censored_share_of_input_1(saved):
    assert 0 <= saved[1]["censored_share"] <= 1


def _run_candidate(
    reader: PowerReader,
    grid: GridDef,
    last_month: str,
    input_id: int,
    place: str,
    point: tuple[float, float],
    var: str,
    params: MetricParams,
) -> dict:
    lat_i = round((point[0] - grid.lat0) / grid.dlat)
    lon_i = round((point[1] - grid.lon0) / grid.dlon)
    started = time.perf_counter()
    read = reader.read_cells(var, "daily", [(lat_i, lon_i)], FIRST_MONTH, last_month)
    read_seconds = time.perf_counter() - started
    yearly = reduce_yearly(read.times, read.values[:, 0], params)
    stats = trend_stats(yearly.values, yearly.years)
    slope = stats.sen.slope
    verdict = decide_verdict(
        stats,
        residual_sd(yearly.values, yearly.years, slope),
        len(yearly.values),
        MIN_RECORD_YEARS,
        False,
        phi=residual_phi(yearly.values, yearly.years, slope),
    )
    return {
        "input_id": input_id,
        "place": place,
        "lat": point[0],
        "lon": point[1],
        "cell": [lat_i, lon_i],
        "cell_lat": grid.lat0 + grid.dlat * lat_i,
        "cell_lon": grid.lon0 + grid.dlon * lon_i,
        "var": var,
        "metric": asdict(params),
        "metric_used": yearly.metric_used or None,
        "censored_share": _censored_share(yearly),
        **asdict(verdict),
        "stats": asdict(stats),
        "series": {"years": yearly.years, "values": yearly.values},
        "read_seconds": round(read_seconds, 1),
        "fetched_bytes": read.fetched_bytes,
    }


def _censored_share(yearly: YearlySeries) -> float | None:
    """Share of the season years with no event day; None for a metric with no date."""
    if not yearly.metric_used:
        return None
    if yearly.metric_used == METRIC_USED_DATE:
        return sum(yearly.is_censored) / len(yearly.years)
    # Above the switch share the series holds event-day counts and no censored flag,
    # and a year with no event counts 0 days.
    return sum(value == 0 for value in yearly.values) / len(yearly.years)


def _summary(record: dict) -> str:
    mk, sen = record["stats"]["mk"], record["stats"]["sen"]
    return (
        f"input {record['input_id']} ({record['place']}, {record['var']}"
        f" {record['metric']['metric_id']}, metric used {record['metric_used']}):"
        f" {record['verdict']}; Sen slope {sen['slope']:.4g} per year,"
        f" 95% interval {sen['ci_low']:.4g} to {sen['ci_high']:.4g};"
        f" MK p {mk['p']:.4g}; n {record['stats']['n']};"
        f" years needed {record['years_needed']};"
        f" censored share {record['censored_share']};"
        f" read {record['read_seconds']} s, {record['fetched_bytes']} bytes"
    )
