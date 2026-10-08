"""Only authorized, bounded snapshots cross the computation boundary."""

from typing import Annotated, Literal, Protocol

from pydantic import Field, TypeAdapter

from agentguard.contracts import (
    Action,
    Contract,
    CreateAction,
    CreateArguments,
    Identifier,
    ListAction,
    ReadAction,
    SearchAction,
    ShareAction,
    ShareArguments,
    UpdateAction,
    UpdateArguments,
)


class DocumentSnapshot(Contract):
    id: Identifier
    body: str = Field(max_length=12000)


class SearchHit(Contract):
    document_id: Identifier
    snippet: str = Field(max_length=512)
    version: int = Field(ge=1)


class TicketPreview(Contract):
    ticket_id: Identifier
    project_id: Identifier
    title: str = Field(max_length=160)
    body_preview: str = Field(max_length=512)
    version: int = Field(ge=1)


class ToolRequest(Contract):
    action: Action
    document: DocumentSnapshot | None = None
    documents: tuple[SearchHit, ...] = Field(default=(), max_length=5)
    tickets: tuple[TicketPreview, ...] = Field(default=(), max_length=5)


class DocumentResult(Contract):
    kind: Literal["document"] = "document"
    document_id: Identifier
    body: str = Field(max_length=12000)


class SearchResult(Contract):
    kind: Literal["search"] = "search"
    documents: tuple[SearchHit, ...] = Field(max_length=5)


class ListResult(Contract):
    kind: Literal["tickets"] = "tickets"
    tickets: tuple[TicketPreview, ...] = Field(max_length=5)


class TicketEffect(Contract):
    kind: Literal["ticket"] = "ticket"
    arguments: CreateArguments


class UpdateEffect(Contract):
    kind: Literal["update"] = "update"
    arguments: UpdateArguments


class ShareEffect(Contract):
    kind: Literal["share"] = "share"
    arguments: ShareArguments
    body: str = Field(max_length=12000)


ToolResult = Annotated[
    DocumentResult | SearchResult | ListResult | TicketEffect | UpdateEffect | ShareEffect,
    Field(discriminator="kind"),
]
RESULT_ADAPTER: TypeAdapter[ToolResult] = TypeAdapter(ToolResult)


class ToolFailure(RuntimeError):
    """Bounded reason code; raw process stderr must not become model-visible output."""

    def __init__(self, code: str, *, exit_status: int | None = None):
        self.code = code
        self.exit_status = exit_status
        super().__init__(code)


class Computer(Protocol):
    mode: str

    def compute(self, request: ToolRequest) -> ToolResult: ...


def expected_result(request: ToolRequest) -> ToolResult:
    action = request.action
    if isinstance(action, (ReadAction, ShareAction)):
        if (
            request.document is None
            or request.document.id != action.arguments.document_id
            or request.documents
            or request.tickets
        ):
            raise ToolFailure("INVALID_SNAPSHOT")
        if isinstance(action, ReadAction):
            return DocumentResult(document_id=request.document.id, body=request.document.body)
        return ShareEffect(arguments=action.arguments, body=request.document.body)
    if request.document is not None:
        raise ToolFailure("INVALID_SNAPSHOT")
    if isinstance(action, SearchAction):
        if request.tickets or len(request.documents) > action.arguments.limit:
            raise ToolFailure("INVALID_SNAPSHOT")
        return SearchResult(documents=request.documents)
    if isinstance(action, ListAction):
        if (
            request.documents
            or len(request.tickets) > action.arguments.limit
            or any(t.project_id != action.arguments.project_id for t in request.tickets)
        ):
            raise ToolFailure("INVALID_SNAPSHOT")
        return ListResult(tickets=request.tickets)
    if request.documents or request.tickets:
        raise ToolFailure("INVALID_SNAPSHOT")
    if isinstance(action, UpdateAction):
        return UpdateEffect(arguments=action.arguments)
    assert isinstance(action, CreateAction)
    return TicketEffect(arguments=action.arguments)


def validate_result(request: ToolRequest, result: ToolResult) -> None:
    if result != expected_result(request):
        raise ToolFailure("EFFECT_MISMATCH")


class InProcessComputer:
    mode = "trusted_python_simulation_only"

    def compute(self, request: ToolRequest) -> ToolResult:
        return expected_result(request)
