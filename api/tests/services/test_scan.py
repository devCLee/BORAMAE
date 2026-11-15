"""The no-trend scan: the other variables of the area under Benjamini-Hochberg (FR-19)."""

import time
import zlib

import numpy as np
import pytest

from boramae.contracts.results_scan import ScanResult
from boramae.contracts.spec import Circle, RequestSpec, RequestWindow, SpecMetric
from boramae.errors import PowerUnavailable, ProblemError
from boramae.services.scan import get_scan, rank_hits
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService, result_path
from tests.fakes import DictStore, FakeReader

SEOUL = Circle(lat=37.5665, lon=126.978, radius_km=25)
FOCUS_VAR = "PRECTOTCORR"
RISING_VAR = "T2M"
FAILING_VAR = "TQV"
UNTESTABLE_VAR = "TO3"
SCAN_LEAVES = 19
SLOW_READ_S = 0.01
RECENT_START = np.datetime64("2010-01-01")


def make_spec(kind="scan", end="latest"):
    return RequestSpec(
        v=1,
        kind=kind,
        var=FOCUS_VAR,
        metric=SpecMetric(id="rx1day"),
        area=SEOUL,
        window=RequestWindow(start=1981, end=end),
    )


def constant(times):
    return np.zeros(times.size)


def ramp(times):
    return (times - times[0]) / np.timedelta64(1, "D")


def missing(times):
    return np.full(times.size, np.nan)


def recent_only(times):
    return np.where(times >= RECENT_START, ramp(times), np.nan)


def series_reader(default=constant, **by_var):
    """A FakeReader whose named variables follow their series; the rest the default."""

    def values(var, freq, times, cell):
        return by_var.get(var, default)(times)

    return FakeReader(values_fn=values)


def noise_reader(**by_var):
    """Seeded noise per variable, except the named variables."""

    def values(var, freq, times, cell):
        if var in by_var:
            return by_var[var](times)
        return np.random.default_rng(zlib.crc32(var.encode())).standard_normal(
            times.size
        )

    return FakeReader(values_fn=values)


class FailingVarReader(FakeReader):
    def read_cells(self, var, freq, cells, start, end):
        if var == FAILING_VAR:
            raise PowerUnavailable(f"{var} did not answer")
        return super().read_cells(var, freq, cells, start, end)


class SlowReader(FakeReader):
    def read_cells(self, var, freq, cells, start, end):
        time.sleep(SLOW_READ_S)
        return super().read_cells(var, freq, cells, start, end)


def with_variable(catalog, var, **changes):
    variables = [
        item.model_copy(update=changes) if item.id == var else item
        for item in catalog.variables
    ]
    return catalog.model_copy(update={"variables": variables})


def run(catalog, reader=None, spec=None, results=None):
    return get_scan(
        spec or make_spec(),
        reader=reader or series_reader(),
        results=results or ResultService(DictStore(), WorkerPool(4, 1.0)),
        catalog=catalog,
    )


def run_result(catalog, reader=None, results=None):
    return ScanResult.model_validate_json(run(catalog, reader, results=results)[0])


def checked_entry(result, var):
    return next(item for item in result.checked if item.var == var)


def q_of_tested(result):
    return {item.var: item.q for item in result.checked if item.status == "tested"}


def scan_files(store):
    return [path for path in store.files if path.startswith("r/scan/")]


# m = 3, 4 and 2: the step-up rule also selects 0.04 at m = 4, because 0.07 <= 3/4 q.
@pytest.mark.parametrize(
    ("p_values", "hits"),
    [
        ([0.001, 0.01, 0.03, 0.2, 0.5], {0, 1, 2}),
        ([0.04, 0.5, 0.06, 0.07], {0, 2, 3}),
        ([0.2, 0.3], set()),
    ],
)
def test_should_select_the_hits_that_bh_selects_at_q_010(p_values, hits):
    assert set(rank_hits(p_values, [0.0] * len(p_values))[1]) == hits


def test_should_give_each_test_its_bh_q_value():
    assert rank_hits([0.01, 0.04], [0.0, 0.0])[0] == pytest.approx([0.02, 0.04])


def test_should_keep_the_top_3_hits_by_q():
    p_values = [0.02, 0.001, 0.01, 0.005, 0.9]
    assert rank_hits(p_values, [0.0] * 5)[1] == [1, 3, 2]


# Both q-values are 0.003; the larger effect goes first, against the input order.
def test_should_break_a_q_tie_by_the_larger_effect():
    assert rank_hits([0.002, 0.001, 0.9], [0.2, 0.5, 0.0])[1] == [1, 0]


@pytest.fixture
def rising(sample_catalog):
    return run_result(sample_catalog, series_reader(**{RISING_VAR: ramp}))


def test_should_find_the_rising_variable(rising):
    assert [hit.var for hit in rising.hits] == [RISING_VAR]


def test_should_label_every_hit_found_by_scan(rising):
    assert [hit.label for hit in rising.hits] == ["found_by_scan"]


def test_should_test_a_hit_with_its_default_metric(rising):
    assert rising.hits[0].metric_id == "annual_mean"


def test_should_give_a_hit_the_sign_of_its_trend(rising):
    assert rising.hits[0].sign == 1


def test_should_store_the_trend_of_a_hit_under_its_key(sample_catalog):
    store = DictStore()
    results = ResultService(store, WorkerPool(4, 1.0))
    hit = run_result(sample_catalog, series_reader(T2M=ramp), results).hits[0]
    assert result_path("trend", hit.trend_key) in store.files


@pytest.fixture
def flat(sample_catalog):
    return run_result(sample_catalog)


def test_should_find_no_hit_in_a_flat_area(flat):
    assert flat.hits == []


def test_should_list_every_scan_variable_but_the_focus_as_checked(flat):
    assert len(flat.checked) == SCAN_LEAVES


def test_should_not_check_the_focus_variable(flat):
    assert FOCUS_VAR not in [item.var for item in flat.checked]


def test_should_store_the_scan_under_its_key(sample_catalog):
    store = DictStore()
    key = run(sample_catalog, results=ResultService(store, WorkerPool(4, 1.0)))[1]
    assert result_path("scan", key) in store.files


def test_should_answer_a_second_scan_from_the_store(sample_catalog):
    results = ResultService(DictStore(), WorkerPool(4, 1.0))
    run(sample_catalog, results=results)
    assert run(sample_catalog, results=results)[2] == "hit"


def test_should_refuse_a_spec_of_another_kind(sample_catalog):
    with pytest.raises(ProblemError) as raised:
        run(sample_catalog, spec=make_spec(kind="trend"))
    assert raised.value.status == 400


@pytest.fixture
def failed_scan(sample_catalog):
    store = DictStore()
    with pytest.raises(ProblemError) as raised:
        run(
            sample_catalog,
            FailingVarReader(),
            results=ResultService(store, WorkerPool(4, 1.0)),
        )
    return raised.value, store


def test_should_answer_503_when_one_scan_variable_fails_to_read(failed_scan):
    assert failed_scan[0].status == 503


def test_should_store_no_scan_when_one_variable_fails_to_read(failed_scan):
    assert scan_files(failed_scan[1]) == []


@pytest.mark.parametrize(
    ("series", "reason"), [(missing, "no_data"), (recent_only, "record_too_short")]
)
def test_should_list_a_variable_with_no_full_record_as_not_testable(
    sample_catalog, series, reason
):
    result = run_result(sample_catalog, series_reader(**{UNTESTABLE_VAR: series}))
    entry = checked_entry(result, UNTESTABLE_VAR)
    assert (entry.status, entry.reason) == ("not_testable", reason)


# The sample annual_total reads the monthly store and the record of the store
# starts in 1981, so each change makes the default metric unreadable here.
@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"stores": ["daily"]}, "store_lacks_variable"),
        ({"record_start": "1990-01"}, "record_starts_later"),
    ],
)
def test_should_list_a_variable_that_cannot_be_read_as_not_testable(
    sample_catalog, changes, reason
):
    catalog = with_variable(sample_catalog, "FROST_DAYS", **changes)
    entry = checked_entry(run_result(catalog), "FROST_DAYS")
    assert (entry.status, entry.reason) == ("not_testable", reason)


# The focus rx1day reads the daily store; T2M annual_mean reads the monthly store.
def test_should_list_a_variable_whose_store_ends_before_the_window(sample_catalog):
    ds = sample_catalog.datasets
    monthly = ds.monthly.model_copy(update={"last_valid_month": "2025-12"})
    datasets = ds.model_copy(update={"monthly": monthly})
    catalog = sample_catalog.model_copy(update={"datasets": datasets})
    result = ScanResult.model_validate_json(run(catalog, spec=make_spec(end=2026))[0])
    entry = checked_entry(result, RISING_VAR)
    assert (entry.status, entry.reason) == ("not_testable", "record_ends_earlier")


def test_should_give_an_unavailable_default_metric_a_not_testable_reason(
    sample_catalog,
):
    catalog = with_variable(sample_catalog, "FROST_DAYS", default_metric="last_date")
    assert checked_entry(run_result(catalog), "FROST_DAYS").status == "not_testable"


@pytest.mark.parametrize("series", [missing, recent_only])
def test_should_leave_a_not_testable_variable_out_of_the_bh_family(
    sample_catalog, series
):
    with_it = run_result(sample_catalog, noise_reader(**{UNTESTABLE_VAR: series}))
    catalog = with_variable(sample_catalog, UNTESTABLE_VAR, scan_set=False)
    without_it = run_result(catalog, noise_reader())
    assert q_of_tested(with_it) == q_of_tested(without_it)


def test_should_finish_19_slow_leaves_on_a_pool_of_4(sample_catalog):
    results = ResultService(DictStore(), WorkerPool(4, 0.0))
    result = run_result(sample_catalog, SlowReader(), results)
    assert len(result.checked) == SCAN_LEAVES


def test_should_change_the_scan_key_when_the_scan_set_changes(sample_catalog):
    catalog = with_variable(sample_catalog, "TO3", scan_set=False)
    assert run(sample_catalog)[1] != run(catalog)[1]


def test_should_mark_the_scan_spec_with_a_12_hex_content_mark(flat):
    assert len(flat.spec.content) == 12
