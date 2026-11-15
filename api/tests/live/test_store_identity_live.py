"""The dataset ID and version of the real POWER stores. Needs the network: -m live."""

import re

import pytest

from boramae.power.reader import read_store_identity

pytestmark = pytest.mark.live

DOTTED_VERSION = r"\d+(\.\d+)+"


@pytest.fixture(scope="module", params=["daily", "monthly"])
def identity(request) -> tuple[str, str]:
    found = read_store_identity(request.param)
    print(f"\n{request.param} store: dataset_id {found[0]}, dataset_version {found[1]}")
    return found


def test_should_give_an_id_that_ends_in_temporal_utc(identity):
    assert identity[0].endswith("_temporal_utc")


def test_should_give_a_dotted_version_number(identity):
    assert re.fullmatch(DOTTED_VERSION, identity[1]) is not None
