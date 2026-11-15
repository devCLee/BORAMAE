import os

import pytest

from boramae.store import local
from boramae.store.local import LocalStore

CATALOG_PATH = "meta/catalog.json"
FIRST = b'{"a":1}'
SECOND = b'{"a":2}'
REAL_REPLACE = os.replace


class RefusingReplace:
    """os.replace that refuses its first calls, as Windows does while a file is held."""

    def __init__(self, refusals: int) -> None:
        self.refusals = refusals

    def __call__(self, source, target) -> None:
        if self.refusals > 0:
            self.refusals -= 1
            raise PermissionError(13, "the target is held by another process")
        REAL_REPLACE(source, target)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(local.time, "sleep", lambda _seconds: None)
    stored = LocalStore(tmp_path)
    stored.put(CATALOG_PATH, FIRST)
    return stored


def test_local_put_replaces_the_body_after_a_refused_replace(store, monkeypatch):
    monkeypatch.setattr(local.os, "replace", RefusingReplace(refusals=1))
    store.put(CATALOG_PATH, SECOND)
    assert store.get(CATALOG_PATH) == SECOND


def test_local_put_raises_when_every_replace_is_refused(store, monkeypatch):
    refusing = RefusingReplace(refusals=local.REPLACE_RETRIES + 1)
    monkeypatch.setattr(local.os, "replace", refusing)
    with pytest.raises(PermissionError):
        store.put(CATALOG_PATH, SECOND)
