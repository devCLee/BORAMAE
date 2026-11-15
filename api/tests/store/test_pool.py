import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager, suppress

import pytest

from boramae.errors import Overloaded
from boramae.store.pool import WorkerPool

SHORT_WAIT_S = 0.05
EVENT_WAIT_S = 5.0
SLOW_LEAF_S = 0.02
BUILDER_LEAVES = 19
POOL_SIZE = 4


class LeafError(Exception):
    pass


@contextmanager
def slots_held(
    pool: WorkerPool, count: int, holder: Callable[..., object] | None = None
) -> Iterator[None]:
    """Keep `count` slots of the pool busy until the block ends."""
    release = threading.Event()
    entered = threading.Semaphore(0)

    def leaf() -> None:
        entered.release()
        release.wait(EVENT_WAIT_S)

    with ThreadPoolExecutor(max_workers=count) as executor:
        if holder is None:
            futures = [executor.submit(pool.submit_leaf, leaf) for _ in range(count)]
        else:
            futures = [executor.submit(holder, [leaf] * count)]
        for _ in range(count):
            entered.acquire(timeout=EVENT_WAIT_S)
        try:
            yield
        finally:
            release.set()
            _wait_all(futures)


def _wait_all(futures: list[Future]) -> None:
    for future in futures:
        future.result(timeout=EVENT_WAIT_S)


def slow_leaves(count: int) -> list[Callable[[], int]]:
    def make(index: int) -> Callable[[], int]:
        def leaf() -> int:
            time.sleep(SLOW_LEAF_S)
            return index

        return leaf

    return [make(index) for index in range(count)]


def peak_concurrency(pool: WorkerPool, count: int) -> int:
    lock = threading.Lock()
    running = [0]
    peak = [0]

    def leaf() -> None:
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        time.sleep(SLOW_LEAF_S)
        with lock:
            running[0] -= 1

    pool.run_leaves([leaf] * count)
    return peak[0]


def failing_leaf() -> int:
    raise LeafError("read failed")


def test_submit_leaf_returns_the_leaf_value():
    assert WorkerPool(1, SHORT_WAIT_S).submit_leaf(lambda: 7) == 7


def test_public_leaf_raises_overloaded_when_the_wait_passes_the_limit():
    pool = WorkerPool(1, SHORT_WAIT_S)
    with slots_held(pool, 1), pytest.raises(Overloaded):
        pool.submit_leaf(lambda: 1)


def test_submit_leaf_frees_the_slot_after_a_failure():
    pool = WorkerPool(1, SHORT_WAIT_S)
    with suppress(LeafError):
        pool.submit_leaf(failing_leaf)
    assert pool.submit_leaf(lambda: 3) == 3


def test_builder_with_19_slow_leaves_completes_on_a_pool_of_4():
    pool = WorkerPool(POOL_SIZE, SHORT_WAIT_S / 10)
    results = pool.run_leaves(slow_leaves(BUILDER_LEAVES))
    assert results == list(range(BUILDER_LEAVES))


def test_builder_runs_at_most_the_pool_size_at_once():
    pool = WorkerPool(POOL_SIZE, SHORT_WAIT_S)
    assert peak_concurrency(pool, BUILDER_LEAVES) <= POOL_SIZE


def test_builder_leaves_take_the_slots_of_public_leaves():
    pool = WorkerPool(2, SHORT_WAIT_S)
    with slots_held(pool, 2, holder=pool.run_leaves), pytest.raises(Overloaded):
        pool.submit_leaf(lambda: 1)


def test_one_failed_leaf_fails_the_builder():
    pool = WorkerPool(POOL_SIZE, SHORT_WAIT_S)
    with pytest.raises(LeafError):
        pool.run_leaves([*slow_leaves(3), failing_leaf])


def test_builder_raises_overloaded_after_the_request_timeout():
    pool = WorkerPool(1, EVENT_WAIT_S, request_timeout_s=SHORT_WAIT_S)
    blocked = threading.Event()
    with pytest.raises(Overloaded):
        pool.run_leaves([lambda: blocked.wait(EVENT_WAIT_S)])
    blocked.set()


def test_builder_of_no_leaves_returns_an_empty_list():
    assert WorkerPool(1, SHORT_WAIT_S).run_leaves([]) == []
