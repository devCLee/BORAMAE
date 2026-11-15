from pathlib import Path

import pytest

from tests.fakes import DictStore, FakeReader, make_client

SAMPLE_CATALOG = Path(__file__).parent / "fixtures" / "catalog.sample.json"


@pytest.fixture
def reader():
    return FakeReader()


@pytest.fixture
def store():
    return DictStore()


@pytest.fixture
def client(reader, store):
    return make_client(reader=reader, store=store)


@pytest.fixture
def sample_catalog():
    from boramae.contracts.results_catalog import Catalog

    return Catalog.model_validate_json(SAMPLE_CATALOG.read_bytes())
