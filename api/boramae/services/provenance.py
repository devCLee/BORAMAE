"""The provenance record and the method constants of a trend result (FR-26, TR-D-009).

The dataset ID and version come from the catalog entry of the store that the service
read; the bytes that one request moved travel in the headers, never in the record.
"""

from boramae.contracts.results import MethodConstants, Period, Provenance
from boramae.contracts.results_catalog import DatasetVersion
from boramae.contracts.spec import CanonicalSpec
from boramae.engine import definitions
from boramae.ports import Freq
from boramae.power.reader import STORE_URL

# The key of the method text in the provenance message files (W3-VERDICT-UI).
METHOD_TEXT_KEY = "sen_mk_hamed_rao_lag1"
# The daily store names end in "utc", so a daily metric counts UTC days (TRD Q-29).
UTC_DAY_BASIS = "UTC"
MODEL_DATA = "model"


def build_provenance(
    canonical: CanonicalSpec,
    dataset: DatasetVersion,
    freq: Freq,
    compute_location: str,
) -> Provenance:
    """Where the values of a result come from and how the service computed them."""
    start_year, last_month = canonical.window
    return Provenance(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        access_path=STORE_URL.format(freq=freq),
        period=Period(start=f"{start_year:04d}-01", end=last_month),
        cells=canonical.cells,
        method=METHOD_TEXT_KEY,
        compute_location=compute_location,
        day_basis=UTC_DAY_BASIS if freq == "daily" else None,
        data_kind=MODEL_DATA,
    )


def method_constants(min_record_years: int) -> MethodConstants:
    """The constants behind a verdict; the minimum record is the variable's."""
    return MethodConstants(
        alpha=definitions.ALPHA,
        ci_level=definitions.CI_LEVEL,
        min_record_years=min_record_years,
        missing_share_flag=definitions.MISSING_SHARE_FLAG,
        censored_share_switch=definitions.CENSORED_SHARE_SWITCH,
    )
