"""The dataset ID and version of a POWER store, from its group attributes."""

import pytest
import zarr

from boramae.power import reader as reader_module
from boramae.power.reader import read_store_identity, store_identity
from tests.power.stores import write_monthly_store

DAILY_ID = "power_merra2_daily_temporal_utc"
MONTHLY_ID = "power_merra2_monthly_temporal_utc"
STORE_VERSION = "POWER Version 10.0.0"
MONTHLY_ATTRIBUTES = {"id": f"{MONTHLY_ID}.zarr", "version": STORE_VERSION}


@pytest.mark.parametrize(
    ("attributes", "identity"),
    [
        ({"id": f"{DAILY_ID}.zarr", "version": STORE_VERSION}, (DAILY_ID, "10.0.0")),
        (MONTHLY_ATTRIBUTES, (MONTHLY_ID, "10.0.0")),
        ({"id": DAILY_ID, "version": "POWER Version 10.1"}, (DAILY_ID, "10.1")),
    ],
)
def test_should_take_the_id_without_zarr_and_the_version_number(attributes, identity):
    assert store_identity(attributes) == identity


@pytest.mark.parametrize("version", ["POWER Version", "POWER Version 10", ""])
def test_should_refuse_a_version_text_with_no_dotted_version_number(version):
    with pytest.raises(ValueError, match="no dotted version number"):
        store_identity({"id": f"{DAILY_ID}.zarr", "version": version})


@pytest.fixture
def monthly_store(tmp_path, monkeypatch):
    """A tiny monthly store at tmp_path whose group holds the attributes."""
    path = tmp_path / "power_monthly.zarr"
    write_monthly_store(path)
    group = zarr.open_group(str(path), mode="r+", zarr_format=2)
    group.attrs.update(MONTHLY_ATTRIBUTES)
    zarr.consolidate_metadata(str(path), zarr_format=2)
    url = tmp_path.as_uri() + "/power_{freq}.zarr"
    monkeypatch.setattr(reader_module, "STORE_URL", url)
    return path


def test_should_read_the_identity_from_the_store_metadata(monthly_store):
    assert read_store_identity("monthly") == (MONTHLY_ID, "10.0.0")
