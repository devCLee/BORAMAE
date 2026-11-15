"""The rule-based parser: a question to a proposal bound to catalog IDs (TR-F-005).

Keywords and boards come from content files, the place from the gazetteer, units,
defaults and unavailable variables from the catalog. Both languages count (mixed text).
"""

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from boramae.constants import MAX_PROPOSED_VARIABLES
from boramae.contracts.content import Board, KeywordEntry, Place
from boramae.contracts.results_catalog import (
    Catalog,
    CatalogMetric,
    CatalogUnavailable,
    CatalogVariable,
)
from boramae.contracts.spec import (
    InvestigationMetric,
    InvestigationSpec,
    Lang,
    ParseProposal,
    ProposedVariable,
    ReasonCode,
    RequestWindow,
    SpecPlace,
    UnavailableRequest,
)
from boramae.services import places
from boramae.services.catalog import find_metric, find_variable
from boramae.services.content import load_content

# The unit tables were public here before the split, so they stay importable.
from boramae.services.parser_terms import (  # noqa: F401
    BARE_UNIT,
    CONVERTED_DIGITS,
    IMPERIAL_COUNTRIES,
    IMPERIAL_UNITS,
    THRESHOLD,
    TO_DATA_UNIT,
    UNIT_WORDS,
    Typed,
    typed_threshold,
)
from boramae.spec.canonical import metric_defaults

PlaceFinder = Callable[[str, Lang], Place | None]
Pick = tuple[KeywordEntry | None, CatalogVariable, CatalogMetric]

OTHER_LANG: dict[Lang, Lang] = {"en": "ko", "ko": "en"}
# PRD "User flows": the default window is the full record, from 1981.
FULL_RECORD_START = 1981
# ponytail: no document names the variable of a question that names only a place.
# The Explore default, T2M with its default metric, is a working value.
PLACE_DEFAULT_VAR = "T2M"
PLACE_FIRST = "place_first"
# A typed season turns a yearly metric into the seasonal one.
SEASONAL_OF = {"annual_mean": "seasonal_mean", "annual_total": "seasonal_total"}
# A date metric counts over its whole season year (value_kind of the catalog metric),
# so a typed season or month does not cut that year short.
DATE_KIND = "date"
_YEAR = re.compile(r"(?<![\d.])((?:19|20)\d{2})(?![\d.])")
SEASON_MONTHS = ((3, 4, 5), (6, 7, 8), (9, 10, 11), (12, 1, 2))
# ponytail: "may" also reads as the month May; no question in the catalog uses the verb.
MONTH_NAMES = [
    *("january", "february", "march", "april", "may", "june", "july", "august"),
    *("september", "october", "november", "december"),
]
MONTH_WORDS = {
    **{name: (number,) for number, name in enumerate(MONTH_NAMES, start=1)},
    **dict(zip(("spring", "summer", "autumn", "winter"), SEASON_MONTHS)),
    **dict(zip(("봄", "여름", "가을", "겨울"), SEASON_MONTHS)),
}
_MONTH_WORD = re.compile(
    rf"(?<![a-z])({'|'.join(MONTH_WORDS)})s?(?![a-z])|(\d{{1,2}})월"
)
_KO_SHORT_RANGE = re.compile(r"(\d{1,2})\s*[~\-–]\s*(\d{1,2})월")
_RANGE_JOIN = re.compile(r"\s*(?:to|through|until|-|~|–|부터)\s*")


@dataclass(frozen=True)
class _Hit:
    span: tuple[int, int]
    item: object


def normalize(text: str) -> str:
    """NFKC, lower case and single spaces: the form the rules and the cache key read."""
    return " ".join(unicodedata.normalize("NFKC", text).lower().split())


def parse_rules(
    text: str,
    lang: Lang,
    catalog: Catalog,
    find_place: PlaceFinder = places.find_place,
) -> ParseProposal:
    """The rules proposal of a question. A text with no keyword and no place gets an
    empty proposal, so the user picks from the catalog."""
    normal = normalize(text)
    place = find_place(text, lang) or find_place(text, OTHER_LANG[lang])
    asked = _ranked(normal, catalog.unavailable, lambda item: item.names)
    hits = _ranked(normal, load_content("keywords"), lambda item: item.keywords)
    threshold = THRESHOLD.search(normal)
    spans = [hit.span for hit in (*asked, *hits)] + _place_spans(normal, place)
    rest = _blank(normal, spans + ([threshold.span()] if threshold else []))
    years = [int(year) for year in _YEAR.findall(rest)]
    months = _read_months(rest)
    spec = InvestigationSpec(
        lang=lang,
        intent=None,
        place=place
        and SpecPlace(name=getattr(place.name, lang), lat=place.lat, lon=place.lon),
        metric=None,
        window=RequestWindow(
            start=years[0] if years else FULL_RECORD_START,
            end=years[1] if len(years) > 1 else "latest",
        ),
        compare_to=None,
        board=None,
        clarify=None,
    )
    missing, proposed = None, []
    if asked:
        missing, proposed = _unavailable(asked[0].item, catalog)
    elif picks := _picks(hits, catalog, months, place):
        entry, variable, metric = picks[0]
        typed = threshold and typed_threshold(threshold, variable.unit, place)
        spec = spec.model_copy(
            update={
                "intent": entry.intent if entry else PLACE_FIRST,
                "metric": _spec_metric(variable, metric, entry, months, typed),
                "display_units": "imperial" if typed and typed.is_imperial else None,
                "board": _board_of(variable.id, metric.id),
            }
        )
        reason = ReasonCode.DirectMatch if entry else ReasonCode.PlaceDefault
        proposed = [
            ProposedVariable(var=item.id, metric_id=item_metric.id, reason_code=reason)
            for _, item, item_metric in picks
        ]
    return ParseProposal(
        spec=spec, variables=proposed, source="rules", unavailable=missing, clarify=None
    )


def _unavailable(
    asked: CatalogUnavailable, catalog: Catalog
) -> tuple[UnavailableRequest, list[ProposedVariable]]:
    nearest = find_variable(catalog, asked.nearest_var or "")
    code = ReasonCode.NearestAvailable
    variables = [
        ProposedVariable(var=item.id, metric_id=item.default_metric, reason_code=code)
        for item in [nearest]
        if item
    ]
    request = UnavailableRequest(requested=asked.id, nearest_var=asked.nearest_var)
    return request, variables


def _ranked(text: str, items: Iterable[object], words: Callable) -> list[_Hit]:
    """Every match of the ko and en lists of words(item), longest first, then earliest."""
    hits = [
        _Hit(match.span(), item)
        for item in items
        for word in (*words(item).ko, *words(item).en)
        for match in re.finditer(_term_pattern(normalize(word)), text)
    ]
    return sorted(hits, key=lambda hit: (hit.span[0] - hit.span[1], hit.span[0]))


def _term_pattern(word: str) -> str:
    # A Latin word starts at a word boundary and may take a plural s. A Korean word
    # has no end boundary, because a particle follows it directly, as in 폭염이.
    left = r"(?<![a-z0-9])" if re.match(r"[a-z0-9]", word) else ""
    right = r"(?:e?s)?(?![a-z0-9])" if re.search(r"[a-z0-9]$", word) else ""
    return left + re.escape(word) + right


def _blank(text: str, spans: Iterable[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def _place_spans(text: str, place: Place | None) -> list[tuple[int, int]]:
    """Where the names of the place stand, so that a season word inside a name, as in
    Winter Haven, gives no months."""
    names = (place.name.en, place.name.ko, *place.alt) if place else ()
    return [
        match.span()
        for name in names
        for match in re.finditer(_term_pattern(normalize(name)), text)
    ]


def _picks(
    hits: list[_Hit], catalog: Catalog, months: list[int] | None, place: Place | None
) -> list[Pick]:
    """Up to 3 catalog picks from the keywords, else the place default."""
    picks: dict[tuple[str, str], Pick] = {}
    for hit in hits:
        entry: KeywordEntry = hit.item
        variable = find_variable(catalog, entry.var)
        metric = find_metric(catalog, _seasonal(entry.metric_id, months))
        if variable and metric:
            picks.setdefault((variable.id, metric.id), (entry, variable, metric))
    if picks or place is None:
        return list(picks.values())[:MAX_PROPOSED_VARIABLES]
    default = find_variable(catalog, PLACE_DEFAULT_VAR)
    metric = default and find_metric(catalog, _seasonal(default.default_metric, months))
    return [(None, default, metric)] if metric else []


def _seasonal(metric_id: str, months: list[int] | None) -> str:
    return SEASONAL_OF.get(metric_id, metric_id) if months else metric_id


def _spec_metric(
    variable: CatalogVariable,
    metric: CatalogMetric,
    entry: KeywordEntry | None,
    months: list[int] | None,
    typed: Typed | None,
) -> InvestigationMetric:
    """Typed values first, then the keyword defaults, then the catalog defaults."""
    defaults = metric_defaults(variable, metric)
    typed_months = None if metric.value_kind == DATE_KIND else months
    op = (entry and entry.op) or defaults.op
    threshold = (entry and entry.default_threshold) or defaults.threshold
    value = typed.value if typed and op else (float(threshold) if threshold else None)
    return InvestigationMetric(
        id=metric.id,
        var=variable.id,
        op=op,
        value=value,
        unit=variable.unit,
        typed=typed.text if typed and op else None,
        months=typed_months or (entry and entry.default_months) or defaults.months,
        season_start=defaults.season_start,
    )


def _read_months(text: str) -> list[int] | None:
    """Months and seasons in the order typed; 'May to October' and 5~10월 are ranges."""
    text = _KO_SHORT_RANGE.sub(r"\1월~\2월", text)
    found: list[list[int]] = []
    last_end = 0
    for match in _MONTH_WORD.finditer(text):
        months = _month_value(match)
        is_range = (
            found
            and len(found[-1]) == len(months) == 1
            and _RANGE_JOIN.fullmatch(text[last_end : match.start()])
        )
        if is_range:
            first, last = found[-1][0], months[0]
            span = range((last - first) % 12 + 1)
            found[-1] = [(first - 1 + step) % 12 + 1 for step in span]
        elif months:
            found.append(months)
        last_end = match.end()
    return list(dict.fromkeys(month for months in found for month in months)) or None


def _month_value(match: re.Match[str]) -> list[int]:
    word, number = match.groups()
    if number:
        return [int(number)] if 1 <= int(number) <= 12 else []
    return list(MONTH_WORDS[word])


def _board_of(var: str, metric_id: str) -> str | None:
    """The first board whose focus holds the variable and the metric."""
    boards: list[Board] = load_content("boards")
    focus = {"var": var, "metric_id": metric_id}
    matches = (b.id for b in boards if any(f.model_dump() == focus for f in b.focus))
    return next(matches, None)
