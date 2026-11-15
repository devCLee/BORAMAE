"""Replay of the FR-08 proof: saved POWER cell values through area_mean, no network.

tests/live/test_area_series_live.py saves one file per test area. Each holds the
per-cell values that the service read and the series that an independent xarray
computation gave for the same cells.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from boramae.engine.series import area_mean

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "area_series"
SAVED_AREAS = sorted(FIXTURE_DIR.glob("*.json"))
AREA_COUNT = 3  # FR-08: 3 test areas
# The working value of the live test: 0.1% of the larger of the reference and 1 unit.
RELATIVE_TOLERANCE = 0.001
TOLERANCE_FLOOR = 1.0


def test_should_hold_one_file_for_each_test_area():
    assert len(SAVED_AREAS) == AREA_COUNT


@pytest.mark.parametrize("path", SAVED_AREAS, ids=lambda path: path.stem)
def test_should_replay_the_reference_series_within_tolerance(path):
    saved = json.loads(path.read_text(encoding="utf-8"))
    series = area_mean(np.array(saved["cell_values"], dtype=float), saved["latitudes"])
    reference = np.array(saved["reference_series"], dtype=float)
    bound = RELATIVE_TOLERANCE * np.maximum(np.abs(reference), TOLERANCE_FLOOR)
    assert np.all(np.abs(series - reference) <= bound)
