"""Worker pool: a fixed number of slots for leaf computations (TDD.md Flow B).

A leaf is one series with its tests, and it holds one slot while it runs. A public
request waits at most max_wait_s for a slot (submit_leaf). A board or scan builder
holds no slot: run_leaves runs its leaves at most `size` at a time and waits for
slots with no limit but the request timeout, so a fan-out cannot starve itself.
"""

import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

from boramae.config import Settings
from boramae.errors import Overloaded

LEAF_THREAD_PREFIX = "leaf"


class WorkerPool:
    def __init__(
        self,
        size: int,
        max_wait_s: float,
        request_timeout_s: float = Settings.request_timeout_s,
    ) -> None:
        self.size = size
        self.max_wait_s = max_wait_s
        self.request_timeout_s = request_timeout_s
        self._slots = threading.BoundedSemaphore(size)

    def submit_leaf[T](self, fn: Callable[[], T]) -> T:
        """Run one public leaf in the calling thread once a slot is free.

        Raises Overloaded when no slot frees within max_wait_s.
        """
        return self._run_in_slot(fn, time.monotonic() + self.max_wait_s)

    def run_leaves[T](self, fns: Sequence[Callable[[], T]]) -> list[T]:
        """Run a builder's leaves, each in a slot, and return their values in order.

        The first failed leaf fails the whole call, and the leaves not yet started
        are dropped. Raises Overloaded when the request timeout passes.
        """
        deadline = time.monotonic() + self.request_timeout_s
        executor = ThreadPoolExecutor(self.size, thread_name_prefix=LEAF_THREAD_PREFIX)
        try:
            futures = [executor.submit(self._run_in_slot, fn, deadline) for fn in fns]
            return [future.result(timeout=_left(deadline)) for future in futures]
        except TimeoutError as exc:
            raise Overloaded(
                f"leaves unfinished after {self.request_timeout_s} s"
            ) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _run_in_slot[T](self, fn: Callable[[], T], deadline: float) -> T:
        if not self._slots.acquire(timeout=_left(deadline)):
            raise Overloaded(f"no free slot of {self.size}")
        try:
            return fn()
        finally:
            self._slots.release()


def _left(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())
