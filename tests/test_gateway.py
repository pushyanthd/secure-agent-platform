from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from agentguard.contracts import (
    ACTION_ADAPTER,
    CreateAction,
    CreateArguments,
    ReadAction,
    ReadArguments,
)
from agentguard.storage import ExecutionConflict, ReviewRejected, Store


def write(project="atlas", body="Validate rollback."):
    return CreateAction(arguments=CreateArguments(project_id=project, title="Rollback", body=body))


def read(document="doc"):
    return ReadAction(arguments=ReadArguments(document_id=document))


def grant(store, episode, key="write", action=None):
    result = store.execute(episode, key, action or write("shared"))
    assert result.decision.outcome == "REQUIRE_APPROVAL"
    request = store.approval(result.approval_id)
    store.review(
        request["id"],
        expected_hash=request["action_hash"],
        nonce=request["nonce"],
        reviewer="operator",
        approve=True,
    )
    return request


@pytest.mark.parametrize("field", ["actor", "workspace", "approval", "profile", "permission_grant"])
def test_proposal_cannot_supply_authority(field):
    value = write().model_dump(mode="json") | {field: "admin"}
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(value)


@pytest.mark.parametrize(
    "arguments",
    [
        {"project_id": "../atlas", "title": "x", "body": "x"},
        {"project_id": "atlas", "title": "x", "body": "x", "actor": "admin"},
        {"project_id": "atlas", "title": "x", "body": "x" * 4001},
    ],
)
def test_argument_validation(arguments):
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python({"tool": "tickets.create", "arguments": arguments})


def test_clean_workflow(store, episode):
    result = store.execute(episode, "read", read())
    assert result.result["body"] == "Validate rollback."
    assert store.execute(episode, "write", write()).decision.outcome == "ALLOW"
    assert len(store.tickets(episode)) == 1


def test_unauthorized_write_has_no_effect(store, episode):
    result = store.execute(episode, "write", write("orion"))
    assert result.decision.reason == "RESOURCE_OUT_OF_SCOPE"
    assert store.tickets(episode) == []
    assert store.events(episode)[0]["payload"]["outcome"] == "DENY"


def test_actor_acl_not_overridden_by_task_scope(store, contract, documents, projects):
    contract = contract.model_copy(update={"project_ids": ("orion",), "document_ids": ("private",)})
    episode = store.create_episode(contract, documents, projects)
    assert store.execute(episode, "write", write("orion")).decision.reason == "ACTOR_FORBIDDEN"
    result = store.execute(episode, "read", read("private"))
    assert result.decision.reason == "ACTOR_FORBIDDEN"
    assert "PROTECTED" not in result.model_dump_json()


def test_disallowed_operation(store, contract, documents, projects):
    episode = store.create_episode(
        contract.model_copy(update={"allowed_tools": ("documents.read",)}), documents, projects
    )
    assert store.execute(episode, "write", write()).decision.reason == "ACTION_OUT_OF_SCOPE"


@pytest.mark.parametrize("profile", ["baseline", "prompt_only", "defended"])
def test_every_profile_contains_unknown_resources_and_budgets(
    store, contract, documents, projects, profile
):
    episode = store.create_episode(
        contract, documents, projects, experimental_profile=profile, max_actions=1
    )
    assert store.execute(episode, "one", write("missing")).decision.reason == "RESOURCE_UNAVAILABLE"
    assert store.execute(episode, "two", write()).decision.reason == "BUDGET_EXHAUSTED"
    assert store.tickets(episode) == []


@pytest.mark.parametrize("profile", ["baseline", "prompt_only"])
def test_experimental_business_controls_disabled(store, contract, documents, projects, profile):
    episode = store.create_episode(contract, documents, projects, experimental_profile=profile)
    assert store.execute(episode, "write", write("orion")).decision.outcome == "ALLOW"


def test_episode_isolation(store, episode, contract, documents, projects):
    other = store.create_episode(contract, (), ())
    assert store.execute(other, "read", read()).decision.reason == "RESOURCE_UNAVAILABLE"
    store.execute(episode, "write", write())
    assert store.tickets(other) == []


def test_confidential_read_taints_subsequent_writes(store, episode):
    store.execute(episode, "read", read("secret"))
    assert store.execute(episode, "internal", write()).decision.outcome == "REQUIRE_APPROVAL"
    assert (
        store.execute(episode, "shared", write("shared")).decision.reason
        == "CONFIDENTIAL_TO_SHARED"
    )
    assert store.tickets(episode) == []


def test_approval_is_narrow_and_consumed_with_effect(store, episode):
    request = grant(store, episode)
    assert request["snapshot"]["action"] == write("shared").model_dump(mode="json")
    result = store.execute(episode, "write", write("shared"), approval_id=request["id"])
    assert result.decision.reason == "APPROVED"
    assert store.approval(request["id"])["consumed"] == 1
    assert len(store.tickets(episode)) == 1
    # A delivery retry returns the same committed result without consuming twice.
    assert store.execute(episode, "write", write("shared"), approval_id=request["id"]) == result
    assert len(store.tickets(episode)) == 1
    assert (
        store.execute(
            episode, "other-key", write("shared"), approval_id=request["id"]
        ).decision.reason
        == "APPROVAL_INVALID"
    )


def test_approval_cannot_be_retargeted(store, episode):
    request = grant(store, episode)
    with pytest.raises(ExecutionConflict):
        store.execute(episode, "write", write("atlas"), approval_id=request["id"])
    assert (
        store.execute(
            episode, "new-key", write("shared", body="changed"), approval_id=request["id"]
        ).decision.reason
        == "APPROVAL_INVALID"
    )
    assert store.tickets(episode) == []


def test_cross_episode_approval_rejected(store, episode, contract, documents, projects):
    request = grant(store, episode)
    other = store.create_episode(contract, documents, projects)
    assert (
        store.execute(other, "write", write("shared"), approval_id=request["id"]).decision.reason
        == "APPROVAL_INVALID"
    )
    assert store.tickets(other) == []


def test_expired_grant_rejected(store, episode, clock):
    request = grant(store, episode)
    clock[0] += 300
    assert (
        store.execute(episode, "write", write("shared"), approval_id=request["id"]).decision.reason
        == "APPROVAL_INVALID"
    )
    assert store.tickets(episode) == []


@pytest.mark.parametrize("change", ["version", "acl", "scope", "taint", "policy"])
def test_changed_authority_or_state_invalidates_approval(store, episode, change, monkeypatch):
    request = grant(store, episode)
    with store.connection() as db:
        if change == "version":
            db.execute(
                "UPDATE resources SET payload=json_set(payload, '$.version', 2) "
                "WHERE episode_id=? AND id='shared'",
                (episode,),
            )
        elif change == "acl":
            db.execute(
                "UPDATE resources SET payload=json_set(payload, '$.writers', json('[]')) "
                "WHERE episode_id=? AND id='shared'",
                (episode,),
            )
        elif change == "scope":
            db.execute(
                "UPDATE episodes SET contract=json_set(contract, '$.project_ids', json('[]')) "
                "WHERE id=?",
                (episode,),
            )
        elif change == "taint":
            db.execute("UPDATE episodes SET confidential=1 WHERE id=?", (episode,))
        else:
            monkeypatch.setattr("agentguard.policy.POLICY_VERSION", "test-changed-policy")
    result = store.execute(episode, "write", write("shared"), approval_id=request["id"])
    assert result.decision.outcome == "DENY"
    assert store.tickets(episode) == []
    assert store.approval(request["id"])["consumed"] == 0


@pytest.mark.parametrize("invalid", ["nonce", "hash", "expired", "rejected", "duplicate"])
def test_invalid_operator_reviews(store, episode, clock, invalid):
    pending = store.execute(episode, "write", write("shared"))
    request = store.approval(pending.approval_id)
    args = dict(
        expected_hash=request["action_hash"],
        nonce=request["nonce"],
        reviewer="operator",
        approve=True,
    )
    if invalid in {"rejected", "duplicate"}:
        store.review(request["id"], **(args | {"approve": invalid == "duplicate"}))
    elif invalid == "expired":
        clock[0] += 300
    else:
        args["nonce" if invalid == "nonce" else "expected_hash"] = "wrong"
    with pytest.raises(ReviewRejected):
        store.review(request["id"], **args)
    assert store.tickets(episode) == []


def test_pending_retry_does_not_mint_new_grant(store, episode):
    first = store.execute(episode, "write", write("shared"))
    assert store.execute(episode, "write", write("shared")) == first
    assert len(store.events(episode)) == 1


@pytest.mark.parametrize("close", ["reject", "expire"])
def test_closed_approval_does_not_wait_forever(store, episode, clock, close):
    pending = store.execute(episode, "write", write("shared"))
    request = store.approval(pending.approval_id)
    if close == "expire":
        clock[0] += 300
    else:
        store.review(
            request["id"],
            expected_hash=request["action_hash"],
            nonce=request["nonce"],
            reviewer="operator",
            approve=False,
        )
    result = store.execute(episode, "write", write("shared"))
    assert result.decision.reason == "APPROVAL_CLOSED"
    assert result.approval_id is None
    assert store.tickets(episode) == []


def test_cancellation_prevents_new_effect(store, episode):
    request = grant(store, episode)
    store.cancel(episode)
    assert (
        store.execute(episode, "write", write("shared"), approval_id=request["id"]).decision.reason
        == "CANCELLED"
    )
    assert store.tickets(episode) == []


def test_retry_after_reopening_store_is_idempotent(store, episode):
    original = store.execute(episode, "write", write())
    reopened = Store(store.path)
    assert reopened.execute(episode, "write", write()) == original
    assert len(reopened.tickets(episode)) == 1
    assert len(reopened.events(episode)) == 1


def test_concurrent_delivery_has_one_effect(store, episode):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.execute(episode, "write", write()), range(8)))
    assert all(result == results[0] for result in results)
    assert len(store.tickets(episode)) == 1
    assert len(store.events(episode)) == 1


def test_audit_failure_rolls_back_effect_and_grant(store, episode, monkeypatch):
    request = grant(store, episode)
    original = store._audit

    def crash(*args):
        raise RuntimeError("simulated precommit crash")

    monkeypatch.setattr(store, "_audit", crash)
    with pytest.raises(RuntimeError, match="precommit"):
        store.execute(episode, "write", write("shared"), approval_id=request["id"])
    assert store.tickets(episode) == []
    assert store.approval(request["id"])["consumed"] == 0
    monkeypatch.setattr(store, "_audit", original)
    assert (
        store.execute(episode, "write", write("shared"), approval_id=request["id"]).decision.outcome
        == "ALLOW"
    )
