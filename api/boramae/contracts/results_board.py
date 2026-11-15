"""Case board record of the API contract (docs/BUILD_CONTRACT.md).

Frozen from wave 2: report a needed change. RegistryRow mirrors RegistryLink of
contracts/content.py field by field, so a board file holds the row as content
wrote it and this module needs no content file to load.
"""

from typing import Annotated, Literal

from pydantic import Field

from boramae.constants import MAX_BOARD_DRIVERS, MAX_BOARD_RESPONSES
from boramae.contracts.results import Sign
from boramae.contracts.spec import (
    BoardId,
    CanonicalSpec,
    ContractModel,
    LocalizedText,
    ResultKey,
    SpecMetric,
)

NodeRole = Literal["driver", "response"]
# ponytail: the PRD status list is open (TRD Q-16); the closed list of content.py.
RegistryStatus = Literal[
    "robust", "contested", "weak", "not_testable_here", "unsourced"
]
# ponytail: the PRD gives the labels as words and no codes; these codes are
# working values. Null stands for an opposite sign that is not significant, for
# which the PRD names no label (TRD Q-16).
ArrowLabel = Literal["consistent", "weak", "contradicts", "not_testable_here"]


class RowSide(ContractModel):
    var: str
    metric: SpecMetric


class RegistryRow(ContractModel):
    id: str
    driver: RowSide
    response: RowSide
    expected_sign: Literal["+", "-"]
    mechanism: LocalizedText
    scale: str
    area: str  # 'user' or a named area ID
    lag_years: int
    status: RegistryStatus
    doi: str | None
    url: str | None
    citation: str


class BoardLink(ContractModel):
    """engine LinkResult with a closed label. A node with no test keeps null
    numbers, the label 'not_testable_here' and a reason code."""

    r: float | None
    p: float | None
    n_eff: float | None
    lag_years: int
    n_overlap: int
    sign: Sign | None
    label: ArrowLabel | None
    reason: str | None


class BoardNode(ContractModel):
    role: NodeRole
    row: RegistryRow
    trend_key: ResultKey | None  # null when no trend was requested for the node
    link: BoardLink


class CaseBoard(ContractModel):
    spec: CanonicalSpec
    board_id: BoardId | None  # null: the registry holds no board for the focus
    focus_key: ResultKey
    nodes: Annotated[
        list[BoardNode], Field(max_length=MAX_BOARD_DRIVERS + MAX_BOARD_RESPONSES)
    ]
