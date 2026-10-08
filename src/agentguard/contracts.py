"""Untrusted proposals contain arguments only; authority lives in trusted contracts."""

import hashlib
import json
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    model_serializer,
)

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")]
Profile = Literal["baseline", "prompt_only", "defended"]
Tool = Literal[
    "documents.read",
    "documents.search",
    "tickets.create",
    "tickets.list",
    "tickets.update",
    "shares.request",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Document(Contract):
    id: Identifier
    workspace: Identifier
    body: str = Field(max_length=12000)
    readers: tuple[Identifier, ...]
    classification: Literal["internal", "confidential"] = "internal"
    version: int = Field(default=1, ge=1)


class Project(Contract):
    id: Identifier
    workspace: Identifier
    writers: tuple[Identifier, ...]
    readers: tuple[Identifier, ...] = ()
    visibility: Literal["internal", "shared"] = "internal"
    version: int = Field(default=1, ge=1)


class ReadArguments(Contract):
    document_id: Identifier


class CreateArguments(Contract):
    project_id: Identifier
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=4000)


class Ticket(CreateArguments):
    id: Identifier
    workspace: Identifier
    version: int = Field(default=1, ge=1)
    classification: Literal["internal", "confidential"] = "internal"


class SearchArguments(Contract):
    query: str = Field(min_length=1, max_length=200, pattern=r"\S")
    limit: int = Field(default=5, ge=1, le=5)


class ListArguments(Contract):
    project_id: Identifier
    limit: int = Field(default=5, ge=1, le=5)


class UpdateArguments(CreateArguments):
    ticket_id: Identifier
    expected_version: int = Field(ge=1)


class ShareArguments(Contract):
    document_id: Identifier
    project_id: Identifier


class ReadAction(Contract):
    tool: Literal["documents.read"] = "documents.read"
    arguments: ReadArguments


class CreateAction(Contract):
    tool: Literal["tickets.create"] = "tickets.create"
    arguments: CreateArguments


class SearchAction(Contract):
    tool: Literal["documents.search"] = "documents.search"
    arguments: SearchArguments


class ListAction(Contract):
    tool: Literal["tickets.list"] = "tickets.list"
    arguments: ListArguments


class UpdateAction(Contract):
    tool: Literal["tickets.update"] = "tickets.update"
    arguments: UpdateArguments


class ShareAction(Contract):
    tool: Literal["shares.request"] = "shares.request"
    arguments: ShareArguments


Action = Annotated[
    ReadAction | CreateAction | SearchAction | ListAction | UpdateAction | ShareAction,
    Field(discriminator="tool"),
]
ACTION_ADAPTER: TypeAdapter[Action] = TypeAdapter(Action)


class TicketUpdateReceipt(Contract):
    # Explicit permission to disclose ONE completion bit, never source or model text.
    template: Literal["ticket_update_v1"] = "ticket_update_v1"
    action: UpdateAction
    # Presentation only; the full action remains mandatory trusted authority.
    model_disclosure: Literal["full_action", "template_only"] = "full_action"


class ResponseScope(Contract):
    # A synthetic response destination, selected by the trusted task author.
    recipient: Identifier
    max_classification: Literal["internal", "confidential"]
    effect_receipt: TicketUpdateReceipt | None = None


class TaskContract(Contract):
    task_id: Identifier
    version: int = Field(default=1, ge=1)
    actor: Identifier
    workspace: Identifier
    document_ids: tuple[Identifier, ...]
    project_ids: tuple[Identifier, ...]
    allowed_tools: tuple[Tool, ...] = ("documents.read", "tickets.create")
    # None preserves explicitly project-wide legacy tasks; () permits no updates.
    # This narrows write authority only, independently of inventory read access.
    update_ticket_ids: tuple[Identifier, ...] | None = Field(default=None, max_length=100)
    response_scope: ResponseScope | None = None  # Legacy tasks retain unrestricted output.
    # Trusted task intent, never additional authority or a statement of correctness.
    completion_tools: tuple[Tool, ...] | None = Field(default=None, max_length=6)

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        value: dict[str, Any] = handler(self)
        if self.completion_tools is None:
            value.pop("completion_tools", None)
        return value


class Decision(Contract):
    outcome: Literal["ALLOW", "DENY", "REQUIRE_APPROVAL"]
    reason: str
    action_hash: str
    policy_version: str


class Execution(Contract):
    decision: Decision
    result: dict[str, str] = Field(default_factory=dict)
    approval_id: str | None = None


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
