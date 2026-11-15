"""Flow C fallback: the scan of the other variables and the nearby areas (DES-012).

A scan tests every other scan-set variable of the catalog with its default metric on
the same area and window, under Benjamini-Hochberg at q = 0.10 (TR-F-022). A variable
that cannot be tested here leaves the family and is listed as not testable; only a
read failure fails the scan, and then no scan is stored (TDD.md:228).
"""

import hashlib
import json
import math
import time
from collections.abc import Sequence
from functools import partial

import numpy as np

from boramae.constants import MAX_SCAN_HITS
from boramae.contracts.http import CacheStatus
from boramae.contracts.results import TrendResult
from boramae.contracts.results_catalog import Catalog, CatalogVariable
from boramae.contracts.results_scan import ScanChecked, ScanHit, ScanResult, TrendGrid
from boramae.contracts.spec import RequestSpec, SpecMetric
from boramae.engine.definitions import BH_Q
from boramae.engine.multitest import bh_adjust
from boramae.errors import ProblemError
from boramae.ports import SeriesReader
from boramae.services.catalog import find_metric, list_scan_set
from boramae.services.content import load_content
from boramae.services.nearby import select_nearby
from boramae.services.trend import TREND_KIND, TrendFacts, get_trend
from boramae.spec.canonical import canonicalize, grid_path, result_key, source_freq
from boramae.spec.validate import (
    BAD_REQUEST,
    INVALID_SPEC,
    YEAR_DIGITS,
    validate_request,
)
from boramae.store.results import ResultService

SCAN_KIND = "scan"
HIT_LABEL = "found_by_scan"
LEAVES_STEP = "leaves"
CONTENT_MARK_HEX_LEN = 12
NO_GRID_MARK = "none"
# ponytail: no document names these reason codes of ScanChecked (an open string).
# Any other refusal of the trend endpoint gives its problem code, 'invalid_spec'.
STORE_LACKS_VARIABLE = "store_lacks_variable"
RECORD_STARTS_LATER = "record_starts_later"
RECORD_ENDS_EARLIER = "record_ends_earlier"

Trends = dict[str, tuple[str, TrendResult]]  # variable -> (trend key, result)


def get_scan(
    request_spec: RequestSpec,
    *,
    reader: SeriesReader,
    results: ResultService,
    catalog: Catalog,
) -> tuple[bytes, str, CacheStatus, TrendFacts]:
    """The stored body of a scan, its key, the cache status and the request facts.

    The scan holds no pool slot itself: the focus trend and each leaf run in
    pool.run_leaves, unbounded. A bad spec raises ProblemError 400, a POWER failure
    503 with Retry-After.
    """
    if request_spec.kind != SCAN_KIND:
        raise ProblemError(BAD_REQUEST, INVALID_SPEC, "the spec kind is not scan")
    validated = validate_request(request_spec, catalog)
    focus = canonicalize(validated, catalog)
    path = grid_path(focus.ds, focus.var, focus.metric)
    grid_body = results.store.get(path)
    scan_set = list_scan_set(catalog)
    grid_key = None if grid_body is None else path
    mark = _content_mark([item.id for item in scan_set], grid_key)
    canonical = canonicalize(validated, catalog, mark)
    key = result_key(canonical)
    timings: dict[str, float] = {}
    fetched: list[int] = []

    def compute() -> ScanResult:
        started = time.perf_counter()
        others = [item for item in scan_set if item.id != request_spec.var]
        leaf_specs = {item.id: _leaf_spec(request_spec, item) for item in others}
        reasons = {
            item.id: _untestable_reason(leaf_specs[item.id], item, catalog)
            for item in others
        }
        specs = [request_spec.model_copy(update={"kind": TREND_KIND})]
        specs += [spec for var, spec in leaf_specs.items() if reasons[var] is None]
        answers = results.pool.run_leaves(
            [
                partial(
                    get_trend,
                    spec,
                    reader=reader,
                    results=results,
                    catalog=catalog,
                    bounded=False,
                )
                for spec in specs
            ]
        )
        timings[LEAVES_STEP] = round((time.perf_counter() - started) * 1000, 1)
        fetched.extend(facts.bytes_fetched for _, _, _, facts in answers)
        # The focus is not one of the others, so its variable keys it here too.
        trends = {
            spec.var: (leaf_key, TrendResult.model_validate_json(body))
            for spec, (body, leaf_key, _, _) in zip(specs, answers, strict=True)
        }
        grid = None if grid_body is None else TrendGrid.model_validate_json(grid_body)
        nearby, note = select_nearby(
            grid, trends[request_spec.var][1], catalog.grid, load_content("registry")
        )
        hits, checked = _lists([item.id for item in others], reasons, trends)
        return ScanResult(
            spec=canonical, hits=hits, checked=checked, nearby=nearby, nearby_note=note
        )

    body, cache = results.get_or_compute(SCAN_KIND, key, compute, bounded=False)
    facts = TrendFacts(sum(fetched), validated.used_containing_cell, timings)
    return body, key, cache, facts


def rank_hits(
    p_values: Sequence[float], effects: Sequence[float]
) -> tuple[list[float], list[int]]:
    """The BH q-value of each test, and the indexes of the hits, best first.

    A hit is a test that BH selects at BH_Q. Hits rank by q, then by the larger
    effect, and the list keeps MAX_SCAN_HITS.
    """
    q_values = bh_adjust(p_values)
    selected = [index for index, q in enumerate(q_values) if q <= BH_Q]
    selected.sort(key=lambda index: (q_values[index], -effects[index]))
    return q_values, selected[:MAX_SCAN_HITS]


# ponytail: the mark text is this plan's choice. A change of the scan set or of the
# grid presence gives a new mark, so a scan stored before its grid is never reused.
def _content_mark(scan_ids: list[str], grid_key: str | None) -> str:
    text = json.dumps([sorted(scan_ids), grid_key or NO_GRID_MARK])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:CONTENT_MARK_HEX_LEN]


def _leaf_spec(request_spec: RequestSpec, variable: CatalogVariable) -> RequestSpec:
    return request_spec.model_copy(
        update={
            "kind": TREND_KIND,
            "var": variable.id,
            "metric": SpecMetric(id=variable.default_metric),
        }
    )


def _untestable_reason(
    spec: RequestSpec, variable: CatalogVariable, catalog: Catalog
) -> str | None:
    """Why the trend endpoint would refuse this leaf, found before any read."""
    metric = find_metric(catalog, spec.metric.id)
    if metric is not None:
        freq = source_freq(variable, metric)
        if freq not in variable.stores:
            return STORE_LACKS_VARIABLE
        last_month = getattr(catalog.datasets, freq).last_valid_month
        if spec.window.end != "latest" and spec.window.end > int(
            last_month[:YEAR_DIGITS]
        ):
            return RECORD_ENDS_EARLIER
    if int(variable.record_start[:YEAR_DIGITS]) > spec.window.start:
        return RECORD_STARTS_LATER
    try:
        validate_request(spec, catalog)
    except ProblemError as exc:
        return exc.code
    return None


def _lists(
    variables: list[str], reasons: dict[str, str | None], trends: Trends
) -> tuple[list[ScanHit], list[ScanChecked]]:
    # A result with no verdict (no_data or the record guard) is not testable here.
    why = {var: reasons[var] or trends[var][1].reason for var in variables}
    tested = [var for var in variables if why[var] is None]
    q_values, hit_indexes = rank_hits(
        [trends[var][1].stats.mk.p for var in tested],
        [_effect(trends[var][1]) for var in tested],
    )
    q_by_var = dict(zip(tested, q_values, strict=True))
    checked = [
        ScanChecked(
            var=var,
            status="not_testable" if why[var] else "tested",
            reason=why[var],
            p=None if why[var] else trends[var][1].stats.mk.p,
            q=q_by_var.get(var),
        )
        for var in variables
    ]
    hits = [
        _hit(tested[index], *trends[tested[index]], q_values[index])
        for index in hit_indexes
    ]
    return hits, checked


def _hit(var: str, trend_key: str, trend: TrendResult, q: float) -> ScanHit:
    return ScanHit(
        var=var,
        metric_id=trend.spec.metric.id,
        trend_key=trend_key,
        p=trend.stats.mk.p,
        q=q,
        rate_per_decade=trend.stats.rates.sen,
        rate_unit=trend.rate_unit,
        sign=int(np.sign(trend.stats.sen.slope or 0.0)),
        label=HIT_LABEL,
    )


# ponytail: no document defines the effect size of the q tie-break. Working value:
# the change over the record against the scatter about the Sen line, the unit-free
# ratio of the verdict rule; a series with no scatter ranks first.
def _effect(trend: TrendResult) -> float:
    change = abs(trend.change_over_record or 0.0)
    return change / trend.sd if trend.sd else math.inf
