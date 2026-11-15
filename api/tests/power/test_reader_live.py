"""PowerReader against the real POWER stores. Needs the network: run with -m live."""

import numpy as np
import pytest

from boramae.config import load_settings
from boramae.engine.types import CellSeries, GridDef
from boramae.power.reader import PowerReader

pytestmark = pytest.mark.live

SEOUL = (255, 491)
T2M_VALID_MIN_C = -125.0
T2M_VALID_MAX_C = 80.0
SNOW_DAY_MM = 0.1
# Measured on 2026-11-15 from the stored whole numbers of the three chunks, with no
# reader. The same days counted on the float32 decode give 946: 40 days hold 0.10.
SEOUL_SNOW_DAYS = 986


@pytest.fixture(scope="module")
def live_reader() -> PowerReader:
    return PowerReader(load_settings())


@pytest.fixture(scope="module")
def seoul_monthly(live_reader) -> CellSeries:
    return live_reader.read_cells("T2M", "monthly", [SEOUL], "1981-01", "2029-12")


def test_should_read_more_than_500_months_of_seoul_t2m(seoul_monthly):
    assert seoul_monthly.times.size > 500


def test_should_hold_seoul_t2m_inside_its_valid_range(seoul_monthly):
    values = seoul_monthly.values
    assert np.all((values >= T2M_VALID_MIN_C) & (values <= T2M_VALID_MAX_C))


@pytest.mark.parametrize("freq", ["monthly", "daily"])
def test_should_pin_2026_08_or_a_later_month(live_reader, freq):
    month = live_reader.last_valid_month(freq)
    print(f"\npinned {freq} month: {month}")
    assert month >= "2026-08"


def test_should_start_the_daily_axis_on_1980_12_31(live_reader):
    series = live_reader.read_cells("T2M", "daily", [SEOUL], "1980-01", "1981-01")
    assert series.times[0] == np.datetime64("1980-12-31")


def test_should_hold_the_snow_and_rain_variables_in_the_daily_store(live_reader):
    assert {"PRECSNO", "PRECTOTCORR"} <= set(live_reader.variables("daily"))


def test_should_count_each_seoul_snow_day_at_the_stored_precision(live_reader):
    series = live_reader.read_cells("PRECSNO", "daily", [SEOUL], "1981-01", "2026-09")
    snow_days = int((series.values >= SNOW_DAY_MM).sum())
    print(f"\nSeoul days with PRECSNO >= {SNOW_DAY_MM} mm/day: {snow_days}")
    assert snow_days == SEOUL_SNOW_DAYS


def test_should_find_the_power_grid_in_the_store(live_reader):
    assert live_reader.grid() == GridDef(-90.0, 0.5, 361, -180.0, 0.625, 576)
