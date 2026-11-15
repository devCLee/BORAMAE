"""Spec records of the API contract: parse, request spec and canonical spec.

Frozen from wave 2: report a needed change. Every name is Proposed and listed in
docs/BUILD_CONTRACT.md (DEC-003 form). A catalog ID stays a plain string here,
because the validator checks it against the catalog file (TDD.md Flow B, step 3).
"""

import base64
import json
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from boramae.constants import (
    INTENT_IDS,
    KEY_HEX_LEN,
    MAX_PROPOSED_VARIABLES,
    RADIUS_DEFAULT_KM,
    RESULT_KINDS,
)

SPEC_VERSION = 1

Lang = Literal["en", "ko"]
Units = Literal["metric", "imperial"]
Op = Literal[">=", ">", "<=", "<"]
ResultKind = Literal[*RESULT_KINDS]
IntentId = Literal[*INTENT_IDS]
ProposalSource = Literal["model", "rules"]

# A threshold travels as a decimal string, so no float format can change a key.
DecimalStr = Annotated[str, Field(pattern=r"^-?(\d+(\.\d*)?|\.\d+)$")]
MonthDay = Annotated[str, Field(pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")]
YearMonth = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
Months = Annotated[
    list[Annotated[int, Field(ge=1, le=12)]], Field(min_length=1, max_length=12)
]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
# [lat_i, lon_i] on the grid of the catalog file.
CellIndex = Annotated[
    list[Annotated[int, Field(ge=0)]], Field(min_length=2, max_length=2)
]
# [start year, last month]: the last month is the pinned month or the December
# of an earlier end year (DEC-006).
CanonicalWindow = tuple[int, YearMonth]
ResultKey = Annotated[str, Field(pattern=rf"^[0-9a-f]{{{KEY_HEX_LEN}}}$")]
BoardId = Annotated[str, Field(pattern=r"^CB-\d{2}$")]
# ponytail: no document fixes the form of the per-tab session ID; a UUID fits.
SessionId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")]


class ContractModel(BaseModel):
    """Base of every contract record. An unknown field or a NaN is an error.

    A record also validates from an object with the same attribute names, such as
    an engine dataclass or a content model.
    """

    # revalidate_instances: by default pydantic takes an engine dataclass instance
    # unchecked, so a NaN inside it would reach model_dump_json and print as null.
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        from_attributes=True,
        revalidate_instances="always",
    )

    def to_json_bytes(self) -> bytes:
        """The stored form: strict JSON, sorted keys, no spaces, UTF-8.

        Raises ValueError for a NaN or an infinity, so none reaches a stored file.
        """
        return _dump_compact(self.model_dump(mode="json")).encode("utf-8")


class LocalizedText(ContractModel):
    en: str = Field(min_length=1)
    ko: str = Field(min_length=1)


class SpecPlace(ContractModel):
    name: str
    lat: Latitude
    lon: Longitude
    radius_km: float = RADIUS_DEFAULT_KM


class InvestigationMetric(ContractModel):
    id: str
    var: str
    op: Op | None = None
    value: float | None = None  # threshold in the unit of the data (FR-38)
    unit: str | None = None
    typed: str | None = None  # threshold as the user typed it, such as '110 °F'
    months: Months | None = None
    season_start: MonthDay | None = None


class RequestWindow(ContractModel):
    start: int
    end: int | Literal["latest"]


class InvestigationSpec(ContractModel):
    """The parsed form of one question, in the PRD shape (FR-03).

    An empty slot is null: the app asks for it or fills the default.
    """

    lang: Lang
    intent: IntentId | None
    place: SpecPlace | None
    metric: InvestigationMetric | None
    display_units: Units | None = None
    window: RequestWindow
    compare_to: None  # FR-34 is P1; the PRD does not define the shape yet
    board: BoardId | None
    clarify: None  # FR-29 is P1; the PRD does not define the type yet


class ParseRequest(ContractModel):
    text: str
    lang: Lang
    session_id: SessionId


# ponytail: no document lists the reason codes (TDD.md:161 only asks for a closed
# list). These five are working values; the frontend holds one template for each.
class ReasonCode(StrEnum):
    DirectMatch = "direct_match"
    ClosestMeasure = "closest_measure"
    RelatedDriver = "related_driver"
    PlaceDefault = "place_default"
    NearestAvailable = "nearest_available"


class ProposedVariable(ContractModel):
    var: str
    metric_id: str
    reason_code: ReasonCode


class UnavailableRequest(ContractModel):
    requested: str
    nearest_var: str | None


# ponytail: FR-03 asks for 1 to 3 variables, and no document says what parse
# answers when no keyword matches. Working value: no variable, and null slots in
# the spec. Add a minimum of 1 if the owner wants an error for that case.
class ParseProposal(ContractModel):
    """The answer of parse. A proposal with no variable is valid: the user then
    picks from the catalog."""

    spec: InvestigationSpec
    variables: Annotated[
        list[ProposedVariable], Field(max_length=MAX_PROPOSED_VARIABLES)
    ]
    source: ProposalSource
    unavailable: UnavailableRequest | None
    clarify: None


class MetricSettings(ContractModel):
    """Threshold, comparison and season of a metric. A null slot takes the default
    of the catalog metric."""

    threshold: DecimalStr | None = None
    op: Op | None = None
    months: Months | None = None
    season_start: MonthDay | None = None


class SpecMetric(MetricSettings):
    id: str


class Circle(ContractModel):
    lat: Latitude
    lon: Longitude
    radius_km: float


class Bbox(ContractModel):
    west: Longitude
    south: Latitude
    east: Longitude
    north: Latitude


class RequestSpec(ContractModel):
    """What the browser sends in the query parameter s (DEC-003)."""

    v: Literal[1]
    kind: ResultKind
    var: str
    metric: SpecMetric
    area: Circle | Bbox
    window: RequestWindow


class CanonicalSpec(ContractModel):
    """The spec that the service hashes into the result key. Its canonical JSON
    holds only integers and strings."""

    v: Literal[1]
    kind: ResultKind
    ds: str  # dataset version, such as 'power-merra2-daily@2026-09'
    eng: str  # engine version
    var: str
    metric: SpecMetric
    cells: Annotated[list[CellIndex], Field(min_length=1)]  # sorted
    window: CanonicalWindow
    content: str | None = None  # mark of the board or scan content; none for a trend


def canonical_json(spec: ContractModel) -> str:
    """The one text form of a spec: sorted keys, no spaces, null members left out,
    numbers as JavaScript prints them."""
    return _dump_compact(
        _to_js_numbers(spec.model_dump(mode="json", exclude_none=True))
    )


def encode_request_spec(spec: RequestSpec) -> str:
    """The value of s: base64url without padding of the canonical JSON."""
    encoded = base64.urlsafe_b64encode(canonical_json(spec).encode("utf-8"))
    return encoded.rstrip(b"=").decode("ascii")


def decode_request_spec(s: str) -> RequestSpec:
    """Raises ValueError for a string that is not base64url or not a request spec."""
    padded = s + "=" * (-len(s) % 4)
    return RequestSpec.model_validate_json(
        base64.b64decode(padded, altchars=b"-_", validate=True)
    )


def _dump_compact(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


# ponytail: covers whole-number floats only (25.0 prints as 25). Python and
# JavaScript also differ below 1e-4 and from 1e16 (1e-05 against 0.00001). No
# latitude, longitude or radius of a bundled case is that small; print such a
# value in plain decimal form if one ever has to match the browser codec.
def _to_js_numbers(value: object) -> object:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _to_js_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_js_numbers(item) for item in value]
    return value
