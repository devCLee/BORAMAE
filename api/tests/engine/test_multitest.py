import pytest

from boramae.engine.multitest import bh_adjust, bh_select

# Hand values. With m p-values in ascending order, q(i) is the smallest p(j) x m / j
# over j >= i.
# PLAIN sorted: 0.005, 0.01, 0.03, 0.04, 0.9 give 0.025, 0.025, 0.05, 0.05, 0.9.
PLAIN = [0.01, 0.04, 0.03, 0.005, 0.9]
# STEP_UP sorted: 0.03, 0.035, 0.04, 0.2 give 0.12, 0.07, 0.16 / 3, 0.2 before the
# minimum. 0.03 misses its own bound of 0.025 and is still selected.
STEP_UP = [0.03, 0.2, 0.035, 0.04]
# LONE sorted: 0.04, 0.5, 0.6 give 0.12, 0.75, 0.6 before the minimum.
LONE = [0.04, 0.5, 0.6]


@pytest.mark.parametrize(
    ("p_values", "expected"),
    [
        (PLAIN, [0.025, 0.05, 0.05, 0.025, 0.9]),
        (STEP_UP, [0.16 / 3, 0.2, 0.16 / 3, 0.16 / 3]),
        (LONE, [0.12, 0.6, 0.6]),
        ([0.04], [0.04]),
        ([], []),
    ],
    ids=["plain", "step_up", "lone_small_p", "one_test", "no_test"],
)
def test_bh_adjust_gives_the_hand_q_values_in_the_input_order(p_values, expected):
    assert bh_adjust(p_values) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("p_values", "expected"),
    [
        (PLAIN, [True, True, True, True, False]),
        (STEP_UP, [True, False, True, True]),
        (LONE, [False, False, False]),
        ([], []),
    ],
    ids=["plain", "step_up", "lone_small_p", "no_test"],
)
def test_bh_select_equals_the_benjamini_hochberg_selection_at_q_010(p_values, expected):
    assert bh_select(p_values) == expected


# 0.05 x 2 / 1 is exactly 0.1 in floating point: Benjamini-Hochberg selects at "<=".
def test_bh_select_keeps_a_p_value_exactly_at_its_bound():
    assert bh_select([0.05, 0.5]) == [True, False]


def test_bh_select_takes_another_level():
    assert bh_select(LONE, q=0.2) == [True, False, False]
