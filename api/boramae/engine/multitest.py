"""Benjamini-Hochberg control of every list built by scanning (TR-F-022)."""

from collections.abc import Sequence

from scipy.stats import false_discovery_control

from .definitions import BH_Q


def bh_adjust(p_values: Sequence[float]) -> list[float]:
    """Return the Benjamini-Hochberg q-value of each p-value, in the input order."""
    return false_discovery_control(p_values, method="bh").tolist()


def bh_select(p_values: Sequence[float], q: float = BH_Q) -> list[bool]:
    """Return the mask of the tests that Benjamini-Hochberg selects at level q."""
    return [q_value <= q for q_value in bh_adjust(p_values)]
