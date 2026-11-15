"""Years of data needed to detect a trend at the current rate (FR-15, TR-F-023).

The formula is recalled, not quoted, from Weatherhead et al. 1998, and the yearly
form with its sqrt(12) factor is unchecked against the paper (TDD.md:293-294, Q-020).
"""

import math

from .definitions import YEARS_NEEDED_YEARLY_SQRT12
from .types import YearsNeeded

DETECTION_FACTOR = 3.3  # TDD.md:293
MONTHS_PER_YEAR = 12

WITHIN_RECORD = "within_record"
ZERO_SLOPE = "zero_slope"
NO_SCATTER = "no_scatter"
PHI_OUT_OF_RANGE = "phi_out_of_range"


def years_needed(sigma: float, phi: float, omega: float, n_values: int) -> YearsNeeded:
    """Return n* = (3.3 x sqrt(12) x sigma / |omega| x sqrt((1 + phi)/(1 - phi)))^(2/3).

    sigma and phi are the standard deviation and the lag-1 autocorrelation of the
    yearly Sen residuals, and omega is the Sen slope per year. total is n*, and more
    is the years still needed beyond the n_values of the record. A case with no
    finite n* has an empty total and more, and a reason code.
    """
    if omega == 0:
        return YearsNeeded(total=None, more=None, reason=ZERO_SLOPE)
    if sigma == 0:
        return YearsNeeded(total=None, more=None, reason=NO_SCATTER)
    # ponytail: phi = -1 is refused too, although the formula gives 0 there.
    if not -1 < phi < 1:
        return YearsNeeded(total=None, more=None, reason=PHI_OUT_OF_RANGE)
    yearly_factor = math.sqrt(MONTHS_PER_YEAR) if YEARS_NEEDED_YEARLY_SQRT12 else 1.0
    noise_to_trend = yearly_factor * sigma / abs(omega)
    autocorr_factor = math.sqrt((1 + phi) / (1 - phi))
    total = (DETECTION_FACTOR * noise_to_trend * autocorr_factor) ** (2 / 3)
    if total <= n_values:
        return YearsNeeded(total=total, more=0, reason=WITHIN_RECORD)
    return YearsNeeded(total=total, more=math.ceil(total - n_values), reason=None)
