"""Model-call caps: one per session ID and one global daily budget (DEC-009).

The counters live in memory, so a restart resets them (TDD.md:377).
"""

import threading
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime


def _utc_today() -> date:
    return datetime.now(UTC).date()


class LlmBudget:
    # ponytail: the day turns at UTC midnight and the session counts reset with it,
    # which also bounds the map; a tab open across midnight gets a fresh cap.
    def __init__(
        self,
        session_cap: int,
        daily_budget: int,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        self._session_cap = session_cap
        self._daily_budget = daily_budget
        self._today = today
        self._lock = threading.Lock()
        self._day = today()
        self._calls_today = 0
        self._session_calls: Counter[str] = Counter()

    def allow(self, session_id: str) -> bool:
        """Count one model call and return True, or return False past either cap."""
        with self._lock:
            self._roll_day()
            if self._calls_today >= self._daily_budget:
                return False
            if self._session_calls[session_id] >= self._session_cap:
                return False
            self._calls_today += 1
            self._session_calls[session_id] += 1
            return True

    def is_llm_off(self) -> bool:
        """True from the moment the daily budget is spent until the date changes."""
        with self._lock:
            self._roll_day()
            return self._calls_today >= self._daily_budget

    def _roll_day(self) -> None:
        day = self._today()
        if day != self._day:
            self._day = day
            self._calls_today = 0
            self._session_calls.clear()
