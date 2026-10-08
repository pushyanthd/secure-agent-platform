"""Coarse final-output authorization without inspecting text or hidden grader data."""

from typing import Literal

from agentguard.contracts import Contract, Profile, TaskContract, digest

RESPONSE_POLICY_VERSION = "response-clearance-v2"
TICKET_UPDATE_RECEIPT_TEXT = "Ticket update confirmed."


class ResponseDecision(Contract):
    outcome: Literal["ALLOW", "DENY"]
    reason: str
    recipient: str | None
    classification: Literal["internal", "confidential"]
    policy_version: str = RESPONSE_POLICY_VERSION
    binding_hash: str
    # Defaults preserve parsing of historical evidence.
    receipt_evidence_hash: str | None = None


def deliver_response(proposed: str, decision: ResponseDecision) -> str:
    if decision.outcome == "DENY":
        return ""
    if decision.reason == "VERIFIED_EFFECT_RECEIPT":
        return TICKET_UPDATE_RECEIPT_TEXT
    return proposed


def evaluate_response(
    *,
    episode_id: str,
    contract: TaskContract,
    profile: Profile,
    confidential: bool,
    cancelled: bool,
    receipt_evidence_hash: str | None = None,
) -> ResponseDecision:
    scope = contract.response_scope
    outcome: Literal["ALLOW", "DENY"] = "ALLOW"
    reason = "RESPONSE_AUTHORIZED"
    if cancelled:
        outcome, reason = "DENY", "CANCELLED"
    elif profile not in ("baseline", "prompt_only", "defended"):
        outcome, reason = "DENY", "UNKNOWN_PROFILE"
    elif profile != "defended":
        reason = "EXPERIMENTAL_BUSINESS_CONTROLS_DISABLED"
    elif scope is None:
        reason = "LEGACY_RESPONSE_UNRESTRICTED"
    elif scope.effect_receipt is not None:
        # Opting in selects a fixed receipt, even when model text could be released.
        # Failure never falls back to the model's unverified success claim.
        if receipt_evidence_hash is None:
            outcome, reason = "DENY", "EFFECT_RECEIPT_UNVERIFIED"
        else:
            reason = "VERIFIED_EFFECT_RECEIPT"
    elif confidential and scope.max_classification == "internal":
        outcome, reason = "DENY", "CONFIDENTIAL_RESPONSE_BLOCKED"
    return ResponseDecision(
        outcome=outcome,
        reason=reason,
        recipient=scope.recipient if scope else None,
        classification="confidential" if confidential else "internal",
        receipt_evidence_hash=receipt_evidence_hash
        if reason == "VERIFIED_EFFECT_RECEIPT"
        else None,
        binding_hash=digest(
            {
                "episode_id": episode_id,
                "contract": contract.model_dump(mode="json"),
                "profile": profile,
                "confidential": confidential,
                "cancelled": cancelled,
                "policy_version": RESPONSE_POLICY_VERSION,
                "receipt_evidence_hash": receipt_evidence_hash,
            }
        ),
    )
