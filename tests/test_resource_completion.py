import json

import pytest
from pydantic import ValidationError
from test_runtime import FINAL, FakeModel, action, reply
from test_worker import IDENTITY, Crash, review

from agentguard.completion import CompletionPlan
from agentguard.contracts import Ticket
from agentguard.runtime import Budgets, Runtime, initial_messages
from agentguard.worker import Worker


def turn(tool, **arguments):
    return reply(json.dumps({"kind": "action", "action": {"tool": tool, "arguments": arguments}}))


def run(store, episode, plan, outputs, **budgets):
    model = FakeModel(outputs)
    result = Runtime(store, model, Budgets(completion_plan=plan, **budgets)).run(episode, "Task")
    return result, model


def test_default_budget_and_prompt_bytes_remain_legacy(contract):
    assert "completion_plan" not in Budgets().model_dump()
    assert "completion_requirements" not in json.loads(
        initial_messages("Task", contract, hardened=True)[1]["content"]
    )


def test_successful_read_is_resource_specific_and_attempt_may_be_denied(store, episode):
    plan = CompletionPlan(reads=("doc",), read_attempts=("private",))
    result, model = run(
        store,
        episode,
        plan,
        [
            turn("documents.read", document_id="doc"),
            reply(FINAL),
            turn("documents.read", document_id="private"),
            reply(FINAL),
        ],
    )
    assert result["status"] == "COMPLETED"
    assert result["trace"][1]["execution"]["decision"]["outcome"] == "DENY"
    feedback = json.loads(model.requests[2][0][-1]["content"])
    assert feedback["required_resources"] == [
        {
            "tool": "documents.read",
            "document_id": "private",
            "observation": "read_attempt",
        }
    ]
    initial = json.loads(model.requests[0][0][1]["content"])
    assert initial["completion_requirements"]["read_attempts"] == ["private"]
    assert "private" not in initial["scope"]["document_ids"]


def test_wrong_successful_resource_and_denial_do_not_satisfy_required_read(store, episode):
    result, _ = run(
        store,
        episode,
        CompletionPlan(reads=("doc",)),
        [
            turn("documents.read", document_id="secret"),
            reply(FINAL),
            reply(FINAL),
        ],
        max_steps=3,
    )
    assert result["reason"] == "STEP_BUDGET"
    assert result["final_response"] == ""


def test_search_requires_phrase_breadth_and_declared_result_coverage(
    store, contract, documents, projects
):
    contract = contract.model_copy(update={"allowed_tools": ("documents.search",), "version": 2})
    episode = store.create_episode(contract, documents, projects)
    plan = CompletionPlan(searches=({"query": "rollback", "document_ids": ["doc"]},))
    result, model = run(
        store,
        episode,
        plan,
        [
            turn("documents.search", query="rollback", limit=1),
            reply(FINAL),
            turn("documents.search", query=" rollback ", limit=5),
            reply(FINAL),
        ],
    )
    assert result["status"] == "COMPLETED"
    assert (
        json.loads(model.requests[2][0][-1]["content"])["required_resources"][0]["minimum_limit"]
        == 5
    )
    # An adequate limit with an unrelated query/result cannot satisfy the request.
    episode2 = store.create_episode(contract, documents, projects)
    result, _ = run(
        store,
        episode2,
        plan,
        [
            turn("documents.search", query="secret", limit=5),
            reply(FINAL),
        ],
        max_steps=2,
    )
    assert result["reason"] == "STEP_BUDGET"


def test_batch_counts_distinct_committed_effects_and_only_remaining_work(store, episode):
    plan = CompletionPlan(creates=({"project_id": "atlas", "count": 2},))
    result, model = run(
        store, episode, plan, [reply(action()), reply(FINAL), reply(action()), reply(FINAL)]
    )
    assert result["status"] == "COMPLETED"
    assert len(store.tickets(episode)) == 2
    feedback = json.loads(model.requests[2][0][-1]["content"])
    assert feedback["required_resources"] == [
        {"tool": "tickets.create", "project_id": "atlas", "remaining_count": 1}
    ]
    # Cached observations of the same effect never count as distinct tickets.
    assert plan.missing([result["trace"][0], result["trace"][0]])[0]["remaining_count"] == 1


def test_plan_does_not_authorize_forbidden_project(store, episode):
    result, _ = run(
        store,
        episode,
        CompletionPlan(creates=({"project_id": "orion", "count": 1},)),
        [reply(action("orion")), reply(FINAL), reply(FINAL)],
        max_steps=3,
    )
    assert result["reason"] == "STEP_BUDGET"
    assert not store.tickets(episode)


def test_listing_and_update_require_declared_ticket_target(store, contract, documents, projects):
    contract = contract.model_copy(
        update={
            "allowed_tools": ("tickets.list", "tickets.update"),
            "version": 2,
        }
    )
    ticket = Ticket(id="one", workspace="lab", project_id="atlas", title="Old", body="Old")
    episode = store.create_episode(contract, documents, projects, tickets=(ticket,))
    plan = CompletionPlan(
        listings=({"project_id": "atlas", "ticket_ids": ["one"]},), updates=("one",)
    )
    result, _ = run(
        store,
        episode,
        plan,
        [
            turn("tickets.list", project_id="atlas", limit=5),
            turn(
                "tickets.update",
                project_id="atlas",
                ticket_id="one",
                expected_version=1,
                title="New",
                body="New",
            ),
            reply(FINAL),
        ],
    )
    assert result["status"] == "COMPLETED"
    assert store.tickets(episode)[0]["version"] == 2
    changed = plan.model_copy(update={"updates": ("two",)})
    assert changed.missing(result["trace"]) == [{"tool": "tickets.update", "ticket_id": "two"}]


def test_infeasible_plan_fails_before_generation_and_effects(store, episode):
    plan = CompletionPlan(creates=({"project_id": "atlas", "count": 2},))
    result, model = run(store, episode, plan, [], max_steps=2)
    assert result["reason"] == "COMPLETION_PLAN_EXCEEDS_STEP_BUDGET"
    assert result["model_calls"] == 0 and not model.requests
    assert not store.tickets(episode)
    handoff = CompletionPlan(
        reads=("doc",),
        listings=({"project_id": "atlas"},),
        updates=("one",),
        creates=({"project_id": "atlas", "count": 1},),
        shares=({"document_id": "doc", "project_id": "shared"},),
    )
    assert handoff.minimum_calls() == 6
    assert handoff.minimum_calls(reviewed=True) == 10


def test_resource_feedback_remains_bounded(store, episode):
    result, _ = run(
        store, episode, CompletionPlan(reads=("doc",)), [reply(FINAL)], max_tool_result_bytes=60
    )
    assert result["reason"] == "TOOL_RESULT_LIMIT"


def test_denied_required_success_is_not_a_successful_read(store, episode):
    result, _ = run(
        store,
        episode,
        CompletionPlan(reads=("private",)),
        [
            turn("documents.read", document_id="private"),
            reply(FINAL),
        ],
        max_steps=2,
    )
    assert result["reason"] == "STEP_BUDGET"


def test_pending_share_not_complete_then_exact_approval_replays_once(
    store, contract, documents, projects
):
    contract = contract.model_copy(update={"allowed_tools": ("shares.request",), "version": 2})
    episode = store.create_episode(contract, documents, projects)
    plan = CompletionPlan(shares=({"document_id": "doc", "project_id": "shared"},))
    first = Worker(
        store,
        FakeModel([turn("shares.request", document_id="doc", project_id="shared")]),
        model_identity=IDENTITY,
    )
    first.submit(episode, "Share", Budgets(completion_plan=plan))
    paused = first.run_once()
    assert paused["status"] == "WAITING_APPROVAL"
    assert plan.missing(paused["trace"])
    assert not store.shares(episode)
    review(store, paused["trace"][-1]["execution"]["approval_id"])
    result = Worker(store, FakeModel([reply(FINAL)]), model_identity=IDENTITY).run_once()
    assert result["status"] == "COMPLETED"
    assert len(store.shares(episode)) == 1
    assert not plan.missing(result["trace"])


def test_malformed_observations_and_wrong_scope_do_not_fulfill_plan():
    plan = CompletionPlan(searches=({"query": "term"},))
    entry = {
        "action": {"tool": "documents.search", "arguments": {"query": "term", "limit": 5}},
        "execution": {"decision": {"outcome": "ALLOW"}, "result": {"documents": "invalid"}},
    }
    assert plan.missing([entry])
    entry["execution"]["result"]["documents"] = "[]"
    assert not plan.missing([entry])  # An empty authorized search can be legitimate.
    entry["execution"]["decision"]["outcome"] = "DENY"
    assert plan.missing([entry])


def test_crash_after_commit_replays_original_plan_without_duplicate(
    store, episode, clock, monkeypatch
):
    plan = CompletionPlan(reads=("doc",), creates=({"project_id": "atlas", "count": 1},))
    execute = store.execute

    def crash(*args, **kwargs):
        result = execute(*args, **kwargs)
        if result.result.get("ticket_id"):
            raise Crash
        return result

    monkeypatch.setattr(store, "execute", crash)
    first = Worker(
        store,
        FakeModel([turn("documents.read", document_id="doc"), reply(action())]),
        model_identity=IDENTITY,
    )
    first.submit(episode, "Task", Budgets(completion_plan=plan))
    with pytest.raises(Crash):
        first.run_once()
    monkeypatch.setattr(store, "execute", execute)
    clock[0] += 31
    model = FakeModel([reply(FINAL)])
    result = Worker(store, model, model_identity=IDENTITY).run_once()
    assert result["status"] == "COMPLETED"
    assert len(store.tickets(episode)) == 1
    assert len(model.requests) == 1
    assert json.loads(model.requests[0][0][1]["content"])["completion_requirements"]["reads"] == [
        "doc"
    ]


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"reads": ["doc", "doc"]},
        {"searches": [{"query": "same"}, {"query": " SAME "}]},
        {"reads": ["doc"], "expected_label": "GO"},
        {"searches": [{"query": "term", "minimum_limit": 6}]},
    ],
)
def test_invalid_empty_duplicate_or_answer_bearing_config_rejected(value):
    with pytest.raises(ValidationError):
        CompletionPlan.model_validate(value)
