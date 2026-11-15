"""False-alarm rates of the trend test on trend-free AR(1) series (TR-Q-001).

Run: python -m boramae.batch simulate. The protocol is the SIM_ values of
engine/definitions.py, fixed before any run. Never run it with another seed, length,
series count or estimator to pass the gate: a rate above FALSE_ALARM_MAX is a result
to publish (decision D-09). The table goes to content/evidence/false-alarm.json.
"""

import argparse
import json
import math
import sys

import numpy as np
import numpy.typing as npt
from scipy import stats

from boramae.engine import definitions
from boramae.engine.trend import trend_stats
from boramae.engine.verdict import interval_includes_zero
from boramae.services.content import content_dir

EVIDENCE_FILE = "evidence/false-alarm.json"
FIRST_YEAR = 1981  # the first year of the POWER record, as for SIM_LENGTH
RATE_CI_LEVEL = 0.95


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="simulate", description=__doc__).parse_args(argv)
    table = {
        "seed": definitions.SIM_SEED,
        "series_per_r1": definitions.SIM_SERIES_PER_R1,
        "length": definitions.SIM_LENGTH,
        "engine_version": definitions.ENGINE_VERSION,
        "alpha": definitions.ALPHA,
        "false_alarm_max": definitions.FALSE_ALARM_MAX,
        "rates": [rate_row(index) for index in range(len(definitions.SIM_R1_VALUES))],
    }
    path = content_dir() / EVIDENCE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(table, indent=2, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    for row in table["rates"]:
        print(
            f"r1 = {row['r1']}: false-alarm rate {row['rate']:.3f}"
            f" (95% interval {row['ci95'][0]:.3f} to {row['ci95'][1]:.3f}),"
            f" p < alpha alone {row['p_only_share']:.3f}"
        )
    print(f"simulate: wrote {path.as_posix()}")
    return 0


def rate_row(r1_index: int) -> dict[str, object]:
    """The saved row of one r1 value, from the full series count of the protocol."""
    n_series = definitions.SIM_SERIES_PER_R1
    false_alarms, p_alarms = count_alarms(r1_index, n_series)
    # ponytail: no document names the interval method (TRD R-01 asks for "its sampling
    # interval"). This is Clopper-Pearson, the exact one; use method="wilson" if a
    # narrower interval is wanted.
    interval = stats.binomtest(false_alarms, n_series).proportion_ci(RATE_CI_LEVEL)
    return {
        "r1": definitions.SIM_R1_VALUES[r1_index],
        "false_alarms": false_alarms,
        "rate": false_alarms / n_series,
        "ci95": [float(interval.low), float(interval.high)],
        "p_only_share": p_alarms / n_series,
    }


def count_alarms(r1_index: int, n_series: int) -> tuple[int, int]:
    """Count the false alarms among the first n_series series of one r1 value.

    A false alarm has p < ALPHA and a Sen interval that excludes zero. The second
    count takes p < ALPHA alone. The generator of an r1 value is seeded with
    [SIM_SEED, index of the r1 value], so each r1 value has its own fixed stream.
    """
    r1 = definitions.SIM_R1_VALUES[r1_index]
    rng = np.random.default_rng([definitions.SIM_SEED, r1_index])
    years = range(FIRST_YEAR, FIRST_YEAR + definitions.SIM_LENGTH)
    false_alarms = p_alarms = 0
    for values in ar1_series(rng, r1, n_series):
        tested = trend_stats(values, years)
        is_p_low = tested.mk.p < definitions.ALPHA
        p_alarms += is_p_low
        false_alarms += is_p_low and not interval_includes_zero(
            tested.sen.ci_low, tested.sen.ci_high
        )
    return false_alarms, p_alarms


def ar1_series(
    rng: np.random.Generator, r1: float, n_series: int
) -> npt.NDArray[np.float64]:
    """Trend-free AR(1) series of SIM_LENGTH values, one in each row.

    x[t] = r1 * x[t - 1] + e[t] with standard normal e, drawn row by row. The first
    value is e[0] over sqrt(1 - r1^2), a draw from the stationary distribution
    N(0, 1/(1 - r1^2)), so a series needs no warm-up.
    """
    series = rng.standard_normal((n_series, definitions.SIM_LENGTH))
    series[:, 0] /= math.sqrt(1 - r1**2)
    for step in range(1, definitions.SIM_LENGTH):
        series[:, step] += r1 * series[:, step - 1]
    return series


if __name__ == "__main__":
    sys.exit(main())
