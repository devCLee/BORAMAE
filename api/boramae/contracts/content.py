"""Models of the content files (DES-014). Frozen from wave 2: report a needed change.

Unknown fields are errors (ContractModel). A nullable field is still required:
write null. services/content.py maps each file to its model.
"""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from boramae.constants import (
    MAX_BOARD_DRIVERS,
    MAX_BOARD_RESPONSES,
    METRIC_IDS,
    VARIABLE_IDS,
)
from boramae.contracts.spec import (
    BoardId,
    Circle,
    ContractModel,
    DecimalStr,
    IntentId,
    Lang,
    Latitude,
    LocalizedText,
    Longitude,
    Months,
    Op,
    RequestSpec,
    RequestWindow,
    ResultKind,
)
from boramae.ports import Freq

Text = Annotated[str, Field(min_length=1)]
Doi = Annotated[str, Field(pattern=r"^10\.\d{4,9}/\S+$")]
Url = Annotated[str, Field(pattern=r"^https?://\S+$")]
VariableId = Literal[*VARIABLE_IDS]
MetricId = Literal[*METRIC_IDS]
# ponytail: the PRD status list is open (TRD Q-16); this closed list is a working value.
LinkStatus = Literal["robust", "contested", "weak", "not_testable_here", "unsourced"]
# ponytail: season names are a working value; no document fixes them.
Season = Literal["spring", "summer", "autumn", "winter"]
DemoAction = Literal[
    "choose_language",
    "type_question",
    "submit_question",
    "confirm_variables",
    "set_pin",
    "set_window",
    "confirm_spec",
    "show_verdict",
    "open_board",
    "open_fallback",
    "closing_card",
]


class LocalizedTerms(ContractModel):
    en: list[Text]
    ko: list[Text]


class SeedVariable(ContractModel):
    id: VariableId
    name: LocalizedText
    definition: LocalizedText
    dataset: Text
    kind: Literal["model"]
    min_record_years: Annotated[int, Field(gt=0)]
    default_metric: MetricId
    scan_set: bool
    share_scale: Literal["fraction", "percent"] | None
    nearest_available: VariableId | None


class SeedMetric(ContractModel):
    id: MetricId
    name: LocalizedText
    definition: LocalizedText
    source_freq: Freq
    value_kind: Literal["mean", "total", "count", "date", "max", "length", "index"]
    default_months: Months | None
    default_threshold: DecimalStr | None
    op: Op | None
    unit_rule: Text


class UnavailableVariable(ContractModel):
    id: Text
    names: LocalizedTerms
    nearest_var: VariableId | None


class CatalogSeed(ContractModel):
    variables: list[SeedVariable]
    metrics: list[SeedMetric]
    unavailable: list[UnavailableVariable]


class LinkMetric(ContractModel):
    id: MetricId
    months: Months | None
    threshold: DecimalStr | None
    op: Op | None


class LinkSide(ContractModel):
    var: VariableId
    metric: LinkMetric


class RegistryLink(ContractModel):
    id: Text
    driver: LinkSide
    response: LinkSide
    expected_sign: Literal["+", "-"]
    mechanism: LocalizedText
    scale: Text
    area: Text  # 'user' or a named area ID
    lag_years: Annotated[int, Field(ge=0)]
    status: LinkStatus
    doi: Doi | None
    url: Url | None
    citation: Text

    @model_validator(mode="after")
    def _has_source(self) -> "RegistryLink":
        if self.doi is None and self.url is None:
            raise ValueError("a registry row needs a doi or a url")
        return self


class BoardFocus(ContractModel):
    var: VariableId
    metric_id: MetricId


class Board(ContractModel):
    id: BoardId
    title: LocalizedText
    focus: Annotated[list[BoardFocus], Field(min_length=1)]
    drivers: Annotated[list[Text], Field(max_length=MAX_BOARD_DRIVERS)]
    responses: Annotated[list[Text], Field(max_length=MAX_BOARD_RESPONSES)]


class KeywordEntry(ContractModel):
    keywords: LocalizedTerms
    var: VariableId
    metric_id: MetricId
    intent: IntentId
    default_months: Months | None
    default_threshold: DecimalStr | None
    op: Op | None


class Chip(ContractModel):
    input_id: int
    country: Text
    seasons: Annotated[list[Season], Field(min_length=1)]
    intent: IntentId


class Place(ContractModel):
    id: Text
    name: LocalizedText
    alt: list[Text]
    lat: Latitude
    lon: Longitude
    country: Text
    kind: Text


class InputPlace(ContractModel):
    name: LocalizedText
    country: Text


class ExpectedSpec(ContractModel):
    var: VariableId
    metric_id: MetricId
    months: Months | None
    threshold: DecimalStr | None
    op: Op | None
    window_start: int | None
    supported: bool


class ExpectedReply(ContractModel):
    reply: Literal["not_in_this_version"]
    nearest_var: VariableId | None


class CatalogInput(ContractModel):
    id: Annotated[int, Field(ge=1)]
    theme: Text
    text: LocalizedText
    intent: IntentId
    place: InputPlace | None
    months: Months | None
    threshold_text: Text | None
    metric_text: Text | None
    data_text: Text | None
    board: BoardId | None
    power_only: bool
    expected: ExpectedSpec | ExpectedReply


class EdgeCase(ContractModel):
    id: Annotated[str, Field(pattern=r"^E\d+$")]
    text: LocalizedText
    reply_class: Text
    reply_text: LocalizedText | None


class CatalogInputs(ContractModel):
    inputs: list[CatalogInput]
    edge_cases: list[EdgeCase]


class DemoSpecs(ContractModel):
    trend: RequestSpec
    caseboard: RequestSpec | None
    scan: RequestSpec | None


class DemoPrompt(ContractModel):
    id: Text
    text: LocalizedText


class DemoCase(ContractModel):
    id: Text
    input_id: int
    lang: Lang
    question: LocalizedText
    area: Circle
    window: RequestWindow
    specs: DemoSpecs
    prompts: list[DemoPrompt]


class DemoStep(ContractModel):
    id: Text
    action: DemoAction
    args: dict[str, JsonValue]
    caption: LocalizedText
    is_verdict_step: bool


class DemoScript(ContractModel):
    id: Text
    case_id: Text
    steps: Annotated[list[DemoStep], Field(min_length=1)]


class DemoAnswer(ContractModel):
    prompt_id: Text
    lang: Lang
    text: Text
    result_keys: list[Text]
    citations: list[Text]


class ManifestFile(ContractModel):
    file: Text
    key: Text
    s: Text


class ManifestAnswers(ContractModel):
    ko: Text | None  # null when no stored answers exist
    en: Text | None


class ManifestCase(ContractModel):
    case_id: Text
    parse: LocalizedText  # parse file of each language
    kinds: dict[ResultKind, ManifestFile]
    # Result files that a file of kinds names by key, such as a board node trend.
    referenced: dict[ResultKind, dict[Text, Text]]  # kind -> result key -> file
    answers: ManifestAnswers


class DemoManifest(ContractModel):
    """web/public/demo/manifest.json, written by export-demo."""

    catalog: Text
    cases: list[ManifestCase]


class LicenseEntry(ContractModel):
    name: Text
    kind: Text
    license: Text
    url: Url
    citation: Text
    is_verified: bool
