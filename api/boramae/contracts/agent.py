"""Messages of the agent WebSocket /api/v1/agent (TDD.md Flow D).

Frozen from wave 2: report a needed change. The member 'type' names the message.
The final message has no list of withheld sentences, because the number guard
runs in the browser (DEC-005).
"""

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from boramae.contracts.spec import (
    Circle,
    ContractModel,
    Lang,
    RequestWindow,
    ResultKey,
    SessionId,
    SpecMetric,
    Units,
)

# The seven P0 tools. search_news and search_papers come with their P1 panels.
ToolName = Literal[
    "fly_to",
    "set_area",
    "set_window",
    "select_variable",
    "run_analysis",
    "open_case_board",
    "explain_term",
]
AppMode = Literal["guided", "explore", "demo"]
MessageId = Annotated[str, Field(min_length=1, max_length=64)]


class DraftSpec(ContractModel):
    """The variable and metric that the user is editing or has confirmed."""

    var: str
    metric: SpecMetric


class ResultKeys(ContractModel):
    trend: ResultKey | None
    caseboard: ResultKey | None
    scan: ResultKey | None


# ponytail: no document lists what "the current app state" of TDD.md Flow D
# holds. These fields are working values; add a field when a guide tool needs it.
class AgentAppState(ContractModel):
    """What the browser tells the guide about the screen, with each user message."""

    mode: AppMode | None
    units: Units
    draft: DraftSpec | None
    is_confirmed: bool
    area: Circle | None  # null when no place is pinned
    window: RequestWindow
    result_keys: ResultKeys  # the result that each open panel shows


class UserMessage(ContractModel):
    type: Literal["user"]
    session_id: SessionId
    message_id: MessageId
    lang: Lang
    app_state: AgentAppState
    text: str


# ponytail: TDD.md Flow D only says that the tool result "says declined"; the
# object {'code': 'declined'} is a working value.
class ToolResultMessage(ContractModel):
    """The answer of the browser to a tool call. A refused consent is ok false
    with the result {'code': 'declined'}."""

    type: Literal["tool_result"]
    call_id: MessageId
    ok: bool
    result: dict[str, JsonValue]


class DeltaMessage(ContractModel):
    type: Literal["delta"]
    text: str


class ToolCallMessage(ContractModel):
    type: Literal["tool_call"]
    call_id: MessageId
    tool: ToolName
    args: dict[str, JsonValue]
    needs_confirm: bool  # true when the tool leads to an analysis that is not stored


class FinalMessage(ContractModel):
    type: Literal["final"]
    text: str  # unchecked model text; the browser guard decides what shows
    result_keys: list[ResultKey]
    citations: list[str]


class ErrorMessage(ContractModel):
    type: Literal["error"]
    code: str  # such as 'llm_off' or 'budget'


ClientMessage = Annotated[UserMessage | ToolResultMessage, Field(discriminator="type")]
ServerMessage = Annotated[
    DeltaMessage | ToolCallMessage | FinalMessage | ErrorMessage,
    Field(discriminator="type"),
]
