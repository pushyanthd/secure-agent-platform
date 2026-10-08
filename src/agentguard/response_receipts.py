"""Verify a reviewed effect from trusted storage; never inspect grader or model text."""

import json
import sqlite3

from agentguard.contracts import Execution, Project, TaskContract, digest
from agentguard.policy import POLICY_VERSION
from agentguard.tool_state import resolve


def verified_receipt_hash(
    db: sqlite3.Connection, episode_id: str, contract: TaskContract, *, confidential: bool
) -> str | None:
    """Called inside finalization's fenced write transaction, without performing tools.

    V1 receipts cover one exact, reviewed ticket update. A matching state alone is
    insufficient: require this episode's committed execution and consumed approval.
    Approval expiry after consumption does not undo a successfully committed effect.
    """
    scope = contract.response_scope
    if scope is None or scope.effect_receipt is None:
        return None
    action = scope.effect_receipt.action
    args = action.arguments
    state = resolve(db, episode_id, contract, "defended", action)
    ticket = state.ticket
    if (
        ticket is None
        or not isinstance(state.resource, Project)
        or ticket.version != args.expected_version + 1
        or ticket.title != args.title
        or ticket.body != args.body
    ):
        return None
    # Recheck current hard prohibitions using the post-effect version. This check
    # neither executes an update nor creates/reuses an approval grant.
    current_action = action.model_copy(
        update={"arguments": args.model_copy(update={"expected_version": ticket.version})}
    )
    if (
        state.decision(
            episode_id=episode_id,
            contract=contract,
            profile="defended",
            action=current_action,
            confidential=confidential,
        ).outcome
        == "DENY"
    ):
        return None
    rows = db.execute(
        "SELECT e.execution_key,e.output,a.action_hash,a.snapshot FROM executions e "
        "JOIN approvals a ON a.episode_id=e.episode_id AND a.execution_key=e.execution_key "
        "WHERE e.episode_id=? AND e.proposal_hash=? AND e.output IS NOT NULL "
        "AND a.status='APPROVED' AND a.consumed=1 ORDER BY e.execution_key",
        (episode_id, digest(action.model_dump(mode="json"))),
    )
    for row in rows:
        execution = Execution.model_validate_json(row["output"])
        snapshot = json.loads(row["snapshot"])
        if (
            execution.decision.outcome != "ALLOW"
            or execution.decision.reason != "APPROVED"
            or execution.decision.policy_version != POLICY_VERSION
            or snapshot["policy_version"] != POLICY_VERSION
            or execution.decision.action_hash != row["action_hash"]
            or execution.result != {"ticket_id": args.ticket_id, "version": str(ticket.version)}
            or snapshot["action"] != action.model_dump(mode="json")
            or TaskContract.model_validate(snapshot["contract"]) != contract
            or snapshot["resource"] != state.resource.model_dump(mode="json")
        ):
            continue
        return digest(
            {
                "episode_id": episode_id,
                "execution_key": row["execution_key"],
                "execution": execution.model_dump(mode="json"),
                "ticket": ticket.model_dump(mode="json"),
                "approval_snapshot": snapshot,
            }
        )
    return None
