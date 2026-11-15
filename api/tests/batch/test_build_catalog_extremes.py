"""build-catalog takes the store of a default metric from source_freq (wave 3 close)."""

from pathlib import Path

import pytest

from boramae.batch.build_catalog import build_catalog
from boramae.contracts.content import CatalogSeed
from boramae.services.content import read_content
from tests.fakes import FakeReader

SEED_PATH = Path(__file__).resolve().parents[3] / "content" / "catalog.seed.json"
SEED = read_content(SEED_PATH, CatalogSeed)


class UnitNamesTheStore(FakeReader):
    def variables(self, freq):
        return dict.fromkeys(super().variables(freq), freq)


class DailyLacksT2mMax(FakeReader):
    def variables(self, freq):
        units = dict(super().variables(freq))
        if freq == "daily":
            del units["T2M_MAX"]
        return units


def fake_identity(freq):
    return f"fake-id-{freq}", "0.0.0"


def variable_of(reader, var_id):
    catalog, _ = build_catalog(reader, SEED, fake_identity)
    return next(item for item in catalog.variables if item.id == var_id)


@pytest.mark.parametrize(
    ("var_id", "store"),
    [("T2M_MAX", "daily"), ("T2M_MIN", "daily"), ("T2M", "monthly")],
)
def test_should_take_the_unit_from_the_store_of_the_default_metric(var_id, store):
    assert variable_of(UnitNamesTheStore(), var_id).unit == store


def test_should_leave_the_scan_set_when_the_daily_store_lacks_a_daily_high_mean():
    assert variable_of(DailyLacksT2mMax(), "T2M_MAX").scan_set is False
