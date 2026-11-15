"""The typed threshold of a question, in the unit of the data (FR-38).

Split from parser_rules.py, which re-exports every public name here.
"""

import re
from dataclasses import dataclass

from boramae.contracts.content import Place

# FR-38: a bare number takes the unit of the place.
IMPERIAL_COUNTRIES = frozenset({"US"})
# PRD input 44 reads 110 °F as 43.3 °C.
CONVERTED_DIGITS = 1
# ponytail: no document caps a typed threshold. A longer number is no threshold, so
# float() never overflows to infinity (309 digits do, or 308 in inches).
MAX_THRESHOLD_DIGITS = 6

# Typed unit -> (catalog unit, offset, factor): data value = (typed + offset) x factor.
TO_DATA_UNIT = {
    "°C": ("C", 0.0, 1.0),
    "°F": ("C", -32.0, 5 / 9),
    "mm": ("mm/day", 0.0, 1.0),
    "inch": ("mm/day", 0.0, 25.4),
}
IMPERIAL_UNITS = frozenset({"°F", "inch"})
# Catalog unit -> the typed unit of a bare number: (metric place, imperial place).
BARE_UNIT = {"C": ("°C", "°F"), "mm/day": ("mm", "inch")}
# Written unit -> typed unit. A degree with no scale, or 도, is a bare number.
UNIT_WORDS = {"°c": "°C", "°f": "°F", "mm": "mm", "inch": "inch", "inches": "inch"}

THRESHOLD = re.compile(
    rf"(?<![\d.a-z])(\d{{1,{MAX_THRESHOLD_DIGITS}}}(?:\.\d+)?)"
    r"\s*(°c|°f|-?degrees?|도|mm|inch(?:es)?)(?![a-z])"
)


@dataclass(frozen=True)
class Typed:
    value: float
    text: str
    is_imperial: bool


def typed_threshold(
    match: re.Match[str], data_unit: str, place: Place | None
) -> Typed | None:
    """The typed threshold in the unit of the data, or None for another unit."""
    number, word = match.groups()
    unit = UNIT_WORDS.get(word)
    if unit is None:
        is_us = place is not None and place.country in IMPERIAL_COUNTRIES
        unit = BARE_UNIT.get(data_unit, (None, None))[is_us]
    if unit is None or TO_DATA_UNIT[unit][0] != data_unit:
        return None
    _, offset, factor = TO_DATA_UNIT[unit]
    value = (float(number) + offset) * factor
    is_imperial = unit in IMPERIAL_UNITS
    if is_imperial:
        value = round(value, CONVERTED_DIGITS)
    return Typed(value, f"{number} {unit}", is_imperial)
