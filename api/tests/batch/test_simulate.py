"""The false-alarm simulation: its generator, its fixed seed and the saved rate table.

The table tests read content/evidence/false-alarm.json, the output of the one protocol
run (decision D-09). A rate above the gate is a result to report, not a test to change.
"""

import json

import numpy as np
import pytest

from boramae.batch.simulate import EVIDENCE_FILE, ar1_series, count_alarms
from boramae.engine.definitions import (
    ENGINE_VERSION,
    FALSE_ALARM_MAX,
    SIM_LENGTH,
    SIM_R1_VALUES,
    SIM_SEED,
    SIM_SERIES_PER_R1,
)
from boramae.services.content import content_dir

GENERATOR_SEED = 7  # any seed of the generator tests; not the seed of the protocol
SMALL_RUN = 40
R1 = 0.4
# D-09: the one protocol run gave 0.073 at r1 = 0.2, above the 0.07 gate. The rate is
# published as measured, so this case is an expected failure and no case is rerun.
D09_GATE_FAILED = pytest.mark.xfail(
    strict=True,
    reason="D-09: observed false-alarm rate 0.073 at r1 = 0.2 against the 0.07 gate",
)
GATED_R1_VALUES = (0.0, pytest.param(0.2, marks=D09_GATE_FAILED))  # TRD.md:504
PROTOCOL = {
    "seed": SIM_SEED,
    "series_per_r1": SIM_SERIES_PER_R1,
    "length": SIM_LENGTH,
    "engine_version": ENGINE_VERSION,
}


def _innovations():
    rng = np.random.default_rng(GENERATOR_SEED)
    return rng.standard_normal((SMALL_RUN, SIM_LENGTH))


def _series():
    return ar1_series(np.random.default_rng(GENERATOR_SEED), R1, SMALL_RUN)


@pytest.fixture(scope="module")
def saved_table():
    return json.loads((content_dir() / EVIDENCE_FILE).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def saved_rows(saved_table):
    return {row["r1"]: row for row in saved_table["rates"]}


def test_should_draw_the_first_value_from_the_stationary_distribution():
    assert np.allclose(_series()[:, 0], _innovations()[:, 0] / np.sqrt(1 - R1**2))


def test_should_step_each_series_by_r1_and_a_unit_innovation():
    series = _series()
    assert np.allclose(series[:, 1:] - R1 * series[:, :-1], _innovations()[:, 1:])


@pytest.mark.parametrize("r1_index", range(len(SIM_R1_VALUES)))
def test_should_give_the_same_counts_for_the_same_seed(r1_index):
    assert count_alarms(r1_index, SMALL_RUN) == count_alarms(r1_index, SMALL_RUN)


def test_should_save_the_protocol_of_the_current_engine(saved_table):
    assert {name: saved_table[name] for name in PROTOCOL} == PROTOCOL


def test_should_save_one_row_for_each_r1_value(saved_rows):
    assert tuple(saved_rows) == SIM_R1_VALUES


@pytest.mark.parametrize("r1", SIM_R1_VALUES)
def test_should_save_a_rate_inside_its_95_percent_interval(saved_rows, r1):
    low, high = saved_rows[r1]["ci95"]
    assert low <= saved_rows[r1]["rate"] <= high


@pytest.mark.parametrize("r1", GATED_R1_VALUES)
def test_should_save_a_rate_at_or_below_the_gate(saved_rows, r1):
    assert saved_rows[r1]["rate"] <= FALSE_ALARM_MAX
