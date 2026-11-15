"""Every open statistic definition of the engine, in one place (TDD.md:298).

Frozen from wave 2: a changed definition bumps ENGINE_VERSION so old results keep
their keys. The Q-02 values are Proposed working values, not owner decisions.
"""

from collections.abc import Sequence

import numpy as np

ENGINE_VERSION = "1.0.0"  # TDD.md:298, bumped with each changed definition

ALPHA = 0.05  # TRD.md:470, Mann-Kendall significance level
CI_LEVEL = 0.95  # TRD.md:442, Sen and OLS interval level
MIN_RECORD_YEARS = 20  # TRD.md:490, record guard, counts values
# ponytail: no document fixes this floor; fewer values give null statistics with a
# reason code. Raise it if a test shows a less noisy minimum.
MIN_STAT_VALUES = 3
BH_Q = 0.10  # TRD.md:512, Benjamini-Hochberg level of a scan list
MISSING_SHARE_FLAG = 0.10  # TRD.md:385-387, flag above 10%, not at 10%
CENSORED_SHARE_SWITCH = 0.20  # TRD.md:396-397, switch to event days above 20%
# ponytail: TRD.md:570 (Q-16) states no level and no overlap for the link test;
# these are working values until Q-16 is decided.
LINK_ALPHA = 0.05
LINK_MIN_OVERLAP_YEARS = 10

# Q-02 working values 1 to 9 (TRD.md:1242-1366), one switch each.
Q02_1_ONE_VALUE_PER_YEAR = True  # TRD.md:1245
Q02_2_MK_CONTINUITY_CORRECTION = True  # TRD.md:1261, two-sided normal p
Q02_3_VAR_S_TIE_TERM = False  # TRD.md:1273-1274
Q02_4_SEN_RANK_ROUNDING = "nearest_even"  # TRD.md:1290-1291, numpy.round, then 1..N
Q02_5_SPAN_LAST_MINUS_FIRST = True  # TRD.md:1310
Q02_6_SD_DDOF = 1  # TRD.md:1320-1321, sample SD of the series minus its Sen line
Q02_7_ZERO_SLOPE_DIFFERS_IN_SIGN = False  # TRD.md:1334-1335
Q02_8_YEAR_NEEDS_FULL_SEASON = True  # TRD.md:1346-1347
Q02_9_BOUNDED_MARK_ON_YEARLY_VALUE = True  # TRD.md:1357

# Owner questions answered by the user's defaults of 2026-11-14.
SEN_BOUND_AT_ZERO_INCLUDES_ZERO = True  # TRD.md:1299, decision D-03
PERCENT_PER_DECADE = "points"  # TRD.md:1361-1362, percentage points
# TDD.md:294 (Q-020): sqrt(12) beside sigma when sigma and phi are yearly.
YEARS_NEEDED_YEARLY_SQRT12 = True
# ponytail: no document caps n_eff (TRD.md:1218-1366 names none); None means no cap.
NEFF_CAP = None

# False-alarm protocol, fixed before any run (TRD.md:495-505, decision D-09).
# ponytail: seed and length are this plan's choice; TRD.md:501 leaves both Unknown.
SIM_SEED = 20261114
SIM_SERIES_PER_R1 = 1000  # TRD.md:501
SIM_LENGTH = 45  # 1981 to 2025, as TRD.md:1313
SIM_R1_VALUES = (0.0, 0.2, 0.4)  # TRD.md:501
FALSE_ALARM_MAX = 0.07  # TRD.md:502


# ponytail: the estimator form (lag-1 products over the full sum of squares) is a
# working value; TRD.md:1274 fixes only the rank input and the 0 for equal ranks.
def lag1_autocorr(values: Sequence[float]) -> float:
    """Lag-1 autocorrelation: sum of (x[t]-m)(x[t+1]-m) over the sum of (x[t]-m)^2.

    Returns 0 when the denominator is 0, as for a constant series.
    """
    x = np.asarray(values, dtype=float)
    # Checked before the mean: a float mean can miss a constant value by one ulp.
    if x.size == 0 or np.ptp(x) == 0.0:
        return 0.0
    deviations = x - x.mean()
    denominator = float(np.dot(deviations, deviations))
    if denominator == 0.0:  # tiny deviations whose squares underflow
        return 0.0
    return float(np.dot(deviations[:-1], deviations[1:])) / denominator
