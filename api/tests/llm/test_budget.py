from datetime import date

import pytest

from boramae.llm.budget import LlmBudget

DAY = date(2026, 11, 14)
NEXT_DAY = date(2026, 11, 15)


class FakeClock:
    def __init__(self) -> None:
        self.day = DAY

    def __call__(self) -> date:
        return self.day


@pytest.fixture
def clock():
    return FakeClock()


def test_call_within_the_caps_is_allowed(clock):
    assert LlmBudget(session_cap=2, daily_budget=10, today=clock).allow("tab-a") is True


def test_call_past_the_session_cap_is_refused(clock):
    budget = LlmBudget(session_cap=2, daily_budget=10, today=clock)
    budget.allow("tab-a")
    budget.allow("tab-a")
    assert budget.allow("tab-a") is False


def test_session_cap_does_not_limit_another_session(clock):
    budget = LlmBudget(session_cap=1, daily_budget=10, today=clock)
    budget.allow("tab-a")
    assert budget.allow("tab-b") is True


def test_refused_call_does_not_count_against_the_daily_budget(clock):
    budget = LlmBudget(session_cap=1, daily_budget=2, today=clock)
    budget.allow("tab-a")
    budget.allow("tab-a")
    assert budget.allow("tab-b") is True


def test_llm_is_on_before_the_daily_budget_is_spent(clock):
    budget = LlmBudget(session_cap=5, daily_budget=2, today=clock)
    budget.allow("tab-a")
    assert budget.is_llm_off() is False


def test_spent_daily_budget_switches_the_llm_off(clock):
    budget = LlmBudget(session_cap=5, daily_budget=2, today=clock)
    budget.allow("tab-a")
    budget.allow("tab-b")
    assert budget.is_llm_off() is True


def test_spent_daily_budget_refuses_a_new_session(clock):
    budget = LlmBudget(session_cap=5, daily_budget=1, today=clock)
    budget.allow("tab-a")
    assert budget.allow("tab-c") is False


def test_llm_is_on_again_when_the_date_changes(clock):
    budget = LlmBudget(session_cap=5, daily_budget=1, today=clock)
    budget.allow("tab-a")
    clock.day = NEXT_DAY
    assert budget.is_llm_off() is False


def test_new_day_allows_calls_again(clock):
    budget = LlmBudget(session_cap=1, daily_budget=1, today=clock)
    budget.allow("tab-a")
    clock.day = NEXT_DAY
    assert budget.allow("tab-a") is True
