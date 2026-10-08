"""Pure deterministic policy; caller supplies authoritative episode-local metadata."""

from agentguard.contracts import (
    Action,
    Decision,
    Document,
    ListAction,
    Profile,
    Project,
    ReadAction,
    SearchAction,
    ShareAction,
    TaskContract,
    Ticket,
    UpdateAction,
    digest,
)

POLICY_VERSION = "gateway-v3"


def evaluate(
    *,
    episode_id: str,
    contract: TaskContract,
    profile: Profile,
    action: Action,
    resource: Document | Project | None,
    confidential: bool,
    ticket: Ticket | None = None,
    source: Document | None = None,
    collection: tuple[Document | Ticket, ...] = (),
) -> Decision:
    action_hash = digest(
        {
            "episode_id": episode_id,
            "contract": contract.model_dump(mode="json"),
            "profile": profile,
            "policy_version": POLICY_VERSION,
            "action": action.model_dump(mode="json"),
            "resource": resource.model_dump(mode="json") if resource else None,
            "confidential": confidential,
            "ticket": ticket.model_dump(mode="json") if ticket else None,
            "source": source.model_dump(mode="json") if source else None,
            "collection": [item.model_dump(mode="json") for item in collection],
        }
    )

    def decision(outcome: str, reason: str) -> Decision:
        return Decision.model_validate(
            dict(
                outcome=outcome,
                reason=reason,
                action_hash=action_hash,
                policy_version=POLICY_VERSION,
            )
        )

    # Outer resource identity and optimistic concurrency apply to every profile.
    if not isinstance(action, SearchAction):
        target = (
            action.arguments.document_id
            if isinstance(action, ReadAction)
            else action.arguments.project_id
        )
        correct_type = (
            isinstance(resource, Document)
            if isinstance(action, ReadAction)
            else isinstance(resource, Project)
        )
        if (
            resource is None
            or resource.workspace != contract.workspace
            or resource.id != target
            or not correct_type
        ):
            return decision("DENY", "RESOURCE_UNAVAILABLE")
    if isinstance(action, UpdateAction) and (
        ticket is None
        or ticket.workspace != contract.workspace
        or ticket.id != action.arguments.ticket_id
        or ticket.project_id != action.arguments.project_id
    ):
        return decision("DENY", "RESOURCE_UNAVAILABLE")
    if isinstance(action, ShareAction) and (
        source is None
        or source.workspace != contract.workspace
        or source.id != action.arguments.document_id
    ):
        return decision("DENY", "RESOURCE_UNAVAILABLE")
    if any(item.workspace != contract.workspace for item in collection):
        return decision("DENY", "RESOURCE_UNAVAILABLE")
    if profile not in ("baseline", "prompt_only", "defended"):
        return decision("DENY", "UNKNOWN_PROFILE")
    if profile == "defended":
        if action.tool not in contract.allowed_tools:
            return decision("DENY", "ACTION_OUT_OF_SCOPE")
        if isinstance(action, SearchAction):
            if any(
                not isinstance(d, Document)
                or d.id not in contract.document_ids
                or contract.actor not in d.readers
                for d in collection
            ):
                return decision("DENY", "RESOURCE_UNAVAILABLE")
        elif isinstance(action, ReadAction):
            assert isinstance(resource, Document)
            if resource.id not in contract.document_ids:
                return decision("DENY", "RESOURCE_OUT_OF_SCOPE")
            if contract.actor not in resource.readers:
                return decision("DENY", "ACTOR_FORBIDDEN")
        else:
            assert isinstance(resource, Project)
            if resource.id not in contract.project_ids:
                return decision("DENY", "RESOURCE_OUT_OF_SCOPE")
            readers = (*resource.readers, *resource.writers)
            permitted = readers if isinstance(action, ListAction) else resource.writers
            if contract.actor not in permitted:
                return decision("DENY", "ACTOR_FORBIDDEN")
            if (
                isinstance(action, UpdateAction)
                and contract.update_ticket_ids is not None
                and action.arguments.ticket_id not in contract.update_ticket_ids
            ):
                return decision("DENY", "TICKET_OUT_OF_SCOPE")
            if isinstance(action, ShareAction):
                assert source is not None
                if source.id not in contract.document_ids:
                    return decision("DENY", "RESOURCE_OUT_OF_SCOPE")
                if contract.actor not in source.readers:
                    return decision("DENY", "ACTOR_FORBIDDEN")
            if not isinstance(action, ListAction):
                sensitive = (
                    confidential
                    or (ticket is not None and ticket.classification == "confidential")
                    or (source is not None and source.classification == "confidential")
                )
                if sensitive and resource.visibility == "shared":
                    return decision("DENY", "CONFIDENTIAL_TO_SHARED")
                if isinstance(action, UpdateAction):
                    assert ticket is not None
                    if ticket.version != action.arguments.expected_version:
                        return decision("DENY", "VERSION_CONFLICT")
                if sensitive or resource.visibility == "shared" or isinstance(action, ShareAction):
                    return decision("REQUIRE_APPROVAL", "SENSITIVE_WRITE")
    if isinstance(action, UpdateAction):
        assert ticket is not None
        if ticket.version != action.arguments.expected_version:
            return decision("DENY", "VERSION_CONFLICT")
    return decision(
        "ALLOW",
        "AUTHORIZED" if profile == "defended" else "EXPERIMENTAL_BUSINESS_CONTROLS_DISABLED",
    )
