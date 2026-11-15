"""Writes reference_series.json, the fixed input of the trend engine tests.

Run from api/: uv run python -m tests.engine.data.make_reference_series

The tags rho1 and has_ties come from scipy, not from the engine under test. The rho1
tag ranks float residuals, so it is exact only where those lose no tie; the tests
use its sign, and its value for ref10 alone. The 6-value series is hand-made;
tests/engine/test_trend.py holds its hand statistics.
"""

import json
from pathlib import Path

import numpy as np
from scipy import stats

from boramae.engine.definitions import lag1_autocorr

SEED = 20261114
MAX_ATTEMPTS = 5000
DECIMALS = 6
OUTPUT = Path(__file__).with_name("reference_series.json")


def float_rho1(values, years):
    """Lag-1 autocorrelation of the ranks of the series minus its scipy Sen line."""
    slope = stats.theilslopes(values, years).slope
    residuals = np.asarray(values, dtype=float) - slope * np.asarray(years, dtype=float)
    return lag1_autocorr(stats.rankdata(residuals, method="average"))


def reverse_differs_in_floats(values, years):
    """With an odd pair count, one pair lies exactly on the Sen line.

    Float residuals can lose that tie. This rule takes a draw where they do and where
    the correction is active, so the series tells an engine that ranks float
    residuals from one that keeps the tie: only the second gives the reverse the
    same p.
    """
    forward = float_rho1(values, years)
    return forward > 0.1 and abs(float_rho1(values[::-1], years) - forward) > 1e-6


WANTED = {
    "any": lambda values, years: True,
    "nonpositive": lambda values, years: float_rho1(values, years) < -0.02,
    "negative": lambda values, years: float_rho1(values, years) < -0.1,
    "small_positive": lambda values, years: 0.045 <= float_rho1(values, years) <= 0.055,
    "positive": lambda values, years: float_rho1(values, years) > 0.3,
    "reverse_differs": reverse_differs_in_floats,
}

# id, first year, length, base, trend per year, noise SD, AR(1) phi, wanted rho1
REFERENCE_SPECS = [
    ("ref01_warming_ar02", 1981, 45, 11.8, 0.03, 0.5, 0.2, "any"),
    ("ref02_white_no_trend", 1981, 45, 12.5, 0.0, 0.6, 0.0, "nonpositive"),
    ("ref03_share_ar04_no_trend", 1986, 40, 0.31, 0.0, 0.04, 0.4, "any"),
    ("ref04_date_falling_ar02", 1996, 30, 325.0, -0.4, 9.0, 0.2, "any"),
    ("ref05_short_total_rising", 2006, 20, 1300.0, 12.0, 220.0, 0.0, "nonpositive"),
    ("ref06_negative_rho1", 2001, 25, 5.0, 0.0, 1.0, -0.4, "negative"),
    ("ref08_strong_trend_ar06", 1991, 35, 20.0, 0.08, 0.4, 0.6, "any"),
    ("ref09_height_falling_ar03", 1981, 45, 850.0, -3.0, 60.0, 0.3, "any"),
    ("ref10_small_positive_rho1", 1998, 28, 3.0, 0.02, 0.3, 0.1, "small_positive"),
]
# id, first year, length, Poisson mean of the first and of the last year
COUNT_SPEC = ("ref07_counts_with_ties", 1982, 44, 2.0, 6.0)
MISSING_YEAR_SPEC = ("missing_year", 1991, 31, 14.0, 0.04, 0.5, 0.0, "any")
MISSING_INDEX = 14
TEN_VALUES_SPEC = ("ten_values", 2011, 10, 8.0, 0.0, 1.0, 0.7, "positive")
ODD_PAIRS_SPEC = ("odd_pair_count", 1995, 31, 12.0, 0.03, 0.5, 0.5, "reverse_differs")
HAND_SIX = {
    "id": "hand_six",
    "years": [2001, 2002, 2003, 2004, 2005, 2006],
    "values": [2.0, 1.0, 6.0, 8.0, 7.0, 5.0],
}


def ar1_values(rng, length, base, trend, sd, phi):
    noise = np.empty(length)
    noise[0] = rng.normal()
    for step in range(1, length):
        noise[step] = phi * noise[step - 1] + np.sqrt(1 - phi**2) * rng.normal()
    return np.round(base + trend * np.arange(length) + sd * noise, DECIMALS)


def tagged(series_id, years, values):
    return {
        "id": series_id,
        "years": years,
        "values": values.tolist(),
        "rho1": float_rho1(values, years),
        "has_ties": len(set(values.tolist())) < len(values),
    }


def ar1_series(index, series_id, first_year, length, base, trend, sd, phi, wanted):
    """The first tie-free draw of the seeded stream that meets the wanted rule."""
    years = list(range(first_year, first_year + length))
    for attempt in range(MAX_ATTEMPTS):
        rng = np.random.default_rng([SEED, index, attempt])
        values = ar1_values(rng, length, base, trend, sd, phi)
        if len(set(values.tolist())) == length and WANTED[wanted](values, years):
            return tagged(series_id, years, values)
    raise RuntimeError(f"no {wanted} draw for {series_id} in {MAX_ATTEMPTS} attempts")


def count_series(index, series_id, first_year, length, mean_first, mean_last):
    rng = np.random.default_rng([SEED, index])
    values = rng.poisson(np.linspace(mean_first, mean_last, length)).astype(float)
    return tagged(series_id, list(range(first_year, first_year + length)), values)


def untagged(series, drop_index=None):
    """Years and values only, for a series whose tags no test reads."""
    keep = [k for k in range(len(series["years"])) if k != drop_index]
    return {
        "id": series["id"],
        "years": [series["years"][k] for k in keep],
        "values": [series["values"][k] for k in keep],
    }


def main():
    count = len(REFERENCE_SPECS)
    reference = [ar1_series(index, *spec) for index, spec in enumerate(REFERENCE_SPECS)]
    reference.append(count_series(count, *COUNT_SPEC))
    reference.sort(key=lambda series: series["id"])
    missing_year = untagged(ar1_series(count + 1, *MISSING_YEAR_SPEC), MISSING_INDEX)
    parts = {
        "seed": json.dumps(SEED),
        "reference": "[\n" + ",\n".join(map(json.dumps, reference)) + "\n]",
        "missing_year": json.dumps(missing_year),
        "ten_values": json.dumps(ar1_series(count + 2, *TEN_VALUES_SPEC)),
        "odd_pair_count": json.dumps(untagged(ar1_series(count + 3, *ODD_PAIRS_SPEC))),
        "hand_six": json.dumps(HAND_SIX),
    }
    body = ",\n".join(f"{json.dumps(name)}: {text}" for name, text in parts.items())
    OUTPUT.write_text("{\n" + body + "\n}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
