"""Result service: one computation per key, each result stored once (DES-010).

A stored file holds only record.to_json_bytes(): no timing, no cache state and no
creation time, so every request for one key gets equal bytes (TR-D-010).
"""

import logging
import threading
from collections.abc import Callable

from botocore.exceptions import BotoCoreError, ClientError

from boramae.contracts.http import CacheStatus
from boramae.contracts.spec import ContractModel
from boramae.errors import Overloaded, ProblemError
from boramae.ports import ObjectStore
from boramae.store.pool import WorkerPool

OVERLOADED_STATUS = 503
HEADER_RETRY_AFTER = "Retry-After"
# ponytail: no document fixes the problem code or the Retry-After seconds of a full
# pool; tune RETRY_AFTER_S from the measured pool waits.
OVERLOADED_CODE = "overloaded"
RETRY_AFTER_S = 5
# What a failed write raises: LocalStore an OSError, S3Store a botocore error.
WRITE_ERRORS = (OSError, BotoCoreError, ClientError)

_log = logging.getLogger(__name__)


def result_path(kind: str, key: str) -> str:
    return f"r/{kind}/{key}.json"


class ResultService:
    def __init__(self, store: ObjectStore, pool: WorkerPool) -> None:
        self.store = store
        self.pool = pool
        self._guard = threading.Lock()
        # ponytail: one lock per key computed in this process, never freed (about
        # 100 bytes each); count waiters and drop idle locks if a task runs for months.
        self._flights: dict[str, threading.Lock] = {}

    def get_or_compute(
        self,
        kind: str,
        key: str,
        compute: Callable[[], ContractModel],
        bounded: bool = True,
    ) -> tuple[bytes, CacheStatus]:
        """The stored body of the key, or compute, store and return it.

        bounded true runs compute in a pool slot (a public request); false runs it
        in the calling thread (a builder's leaf, which already holds a slot). A full
        pool raises ProblemError 503 with Retry-After, and nothing is stored.
        """
        path = result_path(kind, key)
        body = self.store.get(path)
        if body is not None:
            return body, "hit"
        with self._flight(path):
            body = self.store.get(path)
            if body is not None:
                return body, "hit"
            return self._compute_and_store(path, compute, bounded), "miss"

    def _flight(self, path: str) -> threading.Lock:
        with self._guard:
            return self._flights.setdefault(path, threading.Lock())

    def _compute_and_store(
        self, path: str, compute: Callable[[], ContractModel], bounded: bool
    ) -> bytes:
        try:
            record = self.pool.submit_leaf(compute) if bounded else compute()
        except Overloaded as exc:
            raise ProblemError(
                OVERLOADED_STATUS,
                OVERLOADED_CODE,
                headers={HEADER_RETRY_AFTER: str(RETRY_AFTER_S)},
            ) from exc
        body = record.to_json_bytes()
        try:
            created = self.store.create_once(path, body)
        except WRITE_ERRORS:
            # TDD.md Flow B: return the computed result; the next request computes again.
            _log.exception("result write failed: %s", path)
            return body
        if created:
            return body
        return self.store.get(path) or body
