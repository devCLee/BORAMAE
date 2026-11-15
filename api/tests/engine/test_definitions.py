import pytest

from boramae.engine.definitions import lag1_autocorr


# Hand values: both lists have mean 3.5 and a sum of squares of 17.5. The lag-1
# sums of products are 8.75 and -7.75.
@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1, 2, 3, 4, 5, 6], 0.5),
        ([2, 4, 1, 5, 3, 6], -31 / 70),
        ([3, 3, 3, 3, 3, 3], 0.0),
        ([0.1] * 6, 0.0),
        ([], 0.0),
        # Not constant, but each squared deviation (2.5e-401) underflows to 0.0.
        ([0.0, 1e-200], 0.0),
    ],
    ids=[
        "rising",
        "alternating",
        "constant",
        "constant_inexact_mean",
        "empty",
        "squares_underflow",
    ],
)
def test_lag1_autocorr_equals_the_hand_value(values, expected):
    assert lag1_autocorr(values) == pytest.approx(expected)
