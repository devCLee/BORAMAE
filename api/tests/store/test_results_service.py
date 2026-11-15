import json
import logging
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from boramae.contracts.spec import ContractModel
from boramae.errors import ProblemError
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService
from tests.fakes import DictStore

KIND = "trend"
KEY = "0123456789abcdef0123456789abcdef"
PATH = f"r/{KIND}/{KEY}.json"
WINNER_BODY = b'{"winner":true}'
SHORT_WAIT_S = 0.05
EVENT_WAIT_S = 5.0


class Record(ContractModel):
    value: float
    label: str = "b"


class CountingCompute:
    """A compute callable that counts its calls; it can block until released."""

    def __init__(self, record: ContractModel | None = None) -> None:
        self.record = Record(value=1.5) if record is None else record
        self.calls = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()

    def __call__(self) -> ContractModel:
        self.calls += 1
        self.started.set()
        self.release.wait(EVENT_WAIT_S)
        return self.record


class LookoutStore(DictStore):
    """Signals each lookup, so a test knows that a second request missed."""

    def __init__(self) -> None:
        super().__init__()
        self.lookups = threading.Semaphore(0)

    def get(self, path: str) -> bytes | None:
        body = super().get(path)
        self.lookups.release()
        return body


class LateWinnerStore(DictStore):
    """Another writer stores its file between our lookup and our create."""

    def create_once(self, path: str, body: bytes) -> bool:
        self.files[path] = WINNER_BODY
        return False


class FailingWriteStore(DictStore):
    def __init__(self, error: Exception | None = None) -> None:
        super().__init__()
        self.error = OSError("disk full") if error is None else error

    def create_once(self, path: str, body: bytes) -> bool:
        raise self.error


WRITE_ERRORS = [
    OSError("disk full"),
    ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject"),
    EndpointConnectionError(endpoint_url="https://s3.us-west-2.amazonaws.com"),
]


def make_service(store: DictStore, pool_size: int = 2) -> ResultService:
    return ResultService(store, WorkerPool(pool_size, SHORT_WAIT_S))


def two_concurrent_requests() -> tuple[CountingCompute, list[bytes]]:
    """Request B misses while request A computes, then both finish."""
    store = LookoutStore()
    service = make_service(store)
    compute = CountingCompute()
    compute.release.clear()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.get_or_compute, KIND, KEY, compute)
        compute.started.wait(EVENT_WAIT_S)
        drain(store.lookups)
        second = executor.submit(service.get_or_compute, KIND, KEY, compute)
        store.lookups.acquire(timeout=EVENT_WAIT_S)
        compute.release.set()
        bodies = [first.result()[0], second.result()[0]]
    return compute, bodies


def drain(semaphore: threading.Semaphore) -> None:
    while semaphore.acquire(blocking=False):
        pass


@contextmanager
def pool_full(pool: WorkerPool) -> Iterator[None]:
    release = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        entered = threading.Event()

        def hold() -> None:
            entered.set()
            release.wait(EVENT_WAIT_S)

        executor.submit(pool.submit_leaf, hold)
        entered.wait(EVENT_WAIT_S)
        try:
            yield
        finally:
            release.set()


def overloaded_problem(service: ResultService, compute: Callable) -> ProblemError:
    with pool_full(service.pool), pytest.raises(ProblemError) as caught:
        service.get_or_compute(KIND, KEY, compute)
    return caught.value


def test_miss_returns_the_computed_body():
    body, _ = make_service(DictStore()).get_or_compute(KIND, KEY, CountingCompute())
    assert json.loads(body) == {"label": "b", "value": 1.5}


def test_miss_reports_miss():
    _, cache = make_service(DictStore()).get_or_compute(KIND, KEY, CountingCompute())
    assert cache == "miss"


def test_miss_stores_the_body_at_the_result_path():
    store = DictStore()
    body, _ = make_service(store).get_or_compute(KIND, KEY, CountingCompute())
    assert store.files == {PATH: body}


def test_stored_body_has_sorted_keys_and_no_spaces():
    body, _ = make_service(DictStore()).get_or_compute(KIND, KEY, CountingCompute())
    assert body == b'{"label":"b","value":1.5}'


def test_hit_returns_the_stored_body():
    store = DictStore()
    store.files[PATH] = WINNER_BODY
    assert make_service(store).get_or_compute(KIND, KEY, CountingCompute()) == (
        WINNER_BODY,
        "hit",
    )


def test_hit_runs_no_computation():
    store = DictStore()
    store.files[PATH] = WINNER_BODY
    compute = CountingCompute()
    make_service(store).get_or_compute(KIND, KEY, compute)
    assert compute.calls == 0


def test_second_call_is_a_hit_with_equal_bytes():
    service = make_service(DictStore())
    first, _ = service.get_or_compute(KIND, KEY, CountingCompute())
    assert service.get_or_compute(KIND, KEY, CountingCompute()) == (first, "hit")


def test_new_service_reads_what_an_old_one_stored():
    store = DictStore()
    first, _ = make_service(store).get_or_compute(KIND, KEY, CountingCompute())
    assert make_service(store).get_or_compute(KIND, KEY, CountingCompute()) == (
        first,
        "hit",
    )


def test_two_concurrent_identical_requests_run_one_computation():
    compute, _ = two_concurrent_requests()
    assert compute.calls == 1


def test_two_concurrent_identical_requests_return_equal_bodies():
    _, (first, second) = two_concurrent_requests()
    assert first == second


def test_loser_of_create_once_returns_the_stored_file():
    service = make_service(LateWinnerStore())
    assert service.get_or_compute(KIND, KEY, CountingCompute())[0] == WINNER_BODY


@pytest.mark.parametrize("error", WRITE_ERRORS)
def test_write_failure_returns_the_computed_body(error):
    body, _ = make_service(FailingWriteStore(error)).get_or_compute(
        KIND, KEY, CountingCompute()
    )
    assert body == b'{"label":"b","value":1.5}'


def test_write_failure_is_logged(caplog):
    with caplog.at_level(logging.ERROR, logger="boramae.store.results"):
        make_service(FailingWriteStore()).get_or_compute(KIND, KEY, CountingCompute())
    assert [record.levelname for record in caplog.records] == ["ERROR"]


def test_next_call_after_a_write_failure_computes_again():
    service = make_service(FailingWriteStore())
    compute = CountingCompute()
    service.get_or_compute(KIND, KEY, compute)
    service.get_or_compute(KIND, KEY, compute)
    assert compute.calls == 2


def test_body_with_a_nan_raises_value_error():
    compute = CountingCompute(Record.model_construct(value=float("nan"), label="b"))
    with pytest.raises(ValueError):
        make_service(DictStore()).get_or_compute(KIND, KEY, compute)


def test_body_with_a_nan_is_never_written():
    store = DictStore()
    compute = CountingCompute(Record.model_construct(value=float("nan"), label="b"))
    with suppress(ValueError):
        make_service(store).get_or_compute(KIND, KEY, compute)
    assert store.files == {}


def test_bounded_miss_with_a_full_pool_answers_503():
    service = make_service(DictStore(), pool_size=1)
    assert overloaded_problem(service, CountingCompute()).status == 503


def test_bounded_miss_with_a_full_pool_sends_retry_after():
    service = make_service(DictStore(), pool_size=1)
    problem = overloaded_problem(service, CountingCompute())
    assert int(problem.headers["Retry-After"]) > 0


def test_bounded_miss_with_a_full_pool_stores_nothing():
    store = DictStore()
    overloaded_problem(make_service(store, pool_size=1), CountingCompute())
    assert store.files == {}


def test_unbounded_miss_runs_in_the_calling_thread_with_a_full_pool():
    service = make_service(DictStore(), pool_size=1)
    with pool_full(service.pool):
        _, cache = service.get_or_compute(KIND, KEY, CountingCompute(), bounded=False)
    assert cache == "miss"
