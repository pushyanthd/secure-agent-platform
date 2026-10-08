import json

import pytest
from test_runtime import FINAL, FakeModel, action, reply
from test_worker import IDENTITY, Crash, review

from agentguard.runtime import Budgets, Runtime
from agentguard.worker import Worker


def reviewing(store, contract, documents, projects):
    return store.create_episode(contract, documents, projects)


def test_legacy_budget_bytes_are_preserved():
    assert "decision_review" not in Budgets().model_dump(mode="json")
    assert (
        Budgets(decision_review="independent-v1").model_dump()["decision_review"]
        == "independent-v1"
    )


def test_wrong_candidate_is_not_committed_and_only_reviewed_replacement_executes(
    store, contract, documents, projects
):
    episode = reviewing(store, contract, documents, projects)
    wrong = json.loads(action())
    wrong["action"]["arguments"]["body"] = "Wrong decision"

    def before_call():
        if len(model.requests) <= 2:
            assert not store.tickets(episode)

    model = FakeModel(
        [reply(json.dumps(wrong)), reply(action()), reply(FINAL), reply(FINAL)],
        on_call=before_call,
    )
    result = Runtime(store, model, Budgets(decision_review="independent-v1")).run(
        episode, "Create a ticket"
    )
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 4
    assert result["generated_tokens"] == 80
    assert len(result["trace"]) == 1
    assert store.tickets(episode)[0]["body"] == "Test body"
    feedback = json.loads(model.requests[1][0][-1]["content"])
    assert feedback["reason"] == "DECISION_REVIEW"
    assert feedback["original_task"] == "Create a ticket"
    assert "scope" not in feedback and "expectation" not in feedback
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM model_calls").fetchone()[0] == 4
        assert db.execute("SELECT count(*) FROM executions").fetchone()[0] == 1


def test_final_decision_can_be_corrected_without_any_effect(store, contract, documents, projects):
    episode = reviewing(store, contract, documents, projects)
    correct = json.dumps({"kind": "final", "text": "Result: GO."})
    model = FakeModel([reply(FINAL), reply(correct)])
    result = Runtime(store, model, Budgets(decision_review="independent-v1")).run(
        episode, "Return the decision"
    )
    assert result["final_response"] == "Result: GO."
    assert not result["trace"]
    assert not store.tickets(episode)


def test_review_cannot_authorize_a_forbidden_write(store, contract, documents, projects):
    episode = reviewing(store, contract, documents, projects)
    model = FakeModel([reply(action("orion")), reply(action("orion")), reply(FINAL), reply(FINAL)])
    result = Runtime(store, model, Budgets(decision_review="independent-v1")).run(episode, "Create")
    assert result["trace"][0]["execution"]["decision"]["outcome"] == "DENY"
    assert not store.tickets(episode)


@pytest.mark.parametrize(
    "budget,reason",
    [
        (Budgets(max_steps=1), "STEP_BUDGET"),
        (Budgets(max_total_generated_tokens=20), "TOKEN_BUDGET"),
        (Budgets(max_tool_result_bytes=100), "TOOL_RESULT_LIMIT"),
    ],
)
def test_review_uses_original_budgets_and_exhaustion_leaves_candidate_uncommitted(
    store, contract, documents, projects, budget, reason
):
    episode = reviewing(store, contract, documents, projects)
    result = Runtime(
        store,
        FakeModel([reply(action())]),
        budget.model_copy(update={"decision_review": "independent-v1"}),
    ).run(episode, "Create")
    assert result["reason"] == reason
    assert result["final_response"] == ""
    assert not store.tickets(episode)


def test_reads_need_no_review_and_schema_repair_does_not_approve_candidate(
    store, contract, documents, projects
):
    episode = reviewing(store, contract, documents, projects)
    read = json.dumps(
        {
            "kind": "action",
            "action": {"tool": "documents.read", "arguments": {"document_id": "doc"}},
        }
    )
    model = FakeModel(
        [reply(read), reply(action()), reply("{}"), reply(action()), reply(FINAL), reply(FINAL)]
    )
    result = Runtime(store, model, Budgets(decision_review="independent-v1")).run(
        episode, "Read then create"
    )
    assert result["status"] == "COMPLETED"
    assert result["schema_repairs"] == 1
    assert [entry["action"]["tool"] for entry in result["trace"]] == [
        "documents.read",
        "tickets.create",
    ]
    assert len(store.tickets(episode)) == 1


def test_switch_from_write_to_final_requires_its_own_review(store, contract, documents, projects):
    episode = reviewing(store, contract, documents, projects)
    model = FakeModel([reply(action()), reply(FINAL), reply(FINAL)])
    result = Runtime(store, model, Budgets(decision_review="independent-v1")).run(episode, "Create")
    assert result["model_calls"] == 3
    assert not store.tickets(episode)
    assert json.loads(model.requests[2][0][-1]["content"])["candidate_kind"] == "final"


def test_crash_after_effect_reconstructs_review_without_generation_or_duplicate(
    store, contract, documents, projects, clock, monkeypatch
):
    episode = reviewing(store, contract, documents, projects)
    execute = store.execute

    def crash_after_commit(*args, **kwargs):
        execute(*args, **kwargs)
        raise Crash

    monkeypatch.setattr(store, "execute", crash_after_commit)
    worker = Worker(store, FakeModel([reply(action()), reply(action())]), model_identity=IDENTITY)
    worker.submit(episode, "Create", Budgets(decision_review="independent-v1"))
    with pytest.raises(Crash):
        worker.run_once()
    monkeypatch.setattr(store, "execute", execute)
    clock[0] += 31
    model = FakeModel([reply(FINAL), reply(FINAL)])
    result = Worker(store, model, model_identity=IDENTITY).run_once()
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 4
    assert len(model.requests) == 2
    assert len(store.tickets(episode)) == 1


def test_operator_reviews_the_replacement_and_recovery_preserves_transcript(
    store, contract, documents, projects
):
    episode = reviewing(store, contract, documents, projects)
    worker = Worker(
        store, FakeModel([reply(action()), reply(action("shared"))]), model_identity=IDENTITY
    )
    worker.submit(episode, "Create", Budgets(decision_review="independent-v1"))
    paused = worker.run_once()
    assert paused["status"] == "WAITING_APPROVAL"
    assert not store.tickets(episode)
    review(store, paused["trace"][-1]["execution"]["approval_id"])
    resumed = Worker(
        store, FakeModel([reply(FINAL), reply(FINAL)]), model_identity=IDENTITY
    ).run_once()
    assert resumed["status"] == "COMPLETED"
    assert [ticket["project_id"] for ticket in store.tickets(episode)] == ["shared"]


def test_completion_guard_still_requires_an_effect_after_review(
    store, contract, documents, projects
):
    contract = contract.model_copy(update={"completion_tools": ("tickets.create",)})
    episode = reviewing(store, contract, documents, projects)
    model = FakeModel(
        [reply(FINAL), reply(FINAL), reply(action()), reply(action()), reply(FINAL), reply(FINAL)]
    )
    result = Runtime(store, model, Budgets(decision_review="independent-v1")).run(episode, "Create")
    assert result["status"] == "COMPLETED"
    assert len(store.tickets(episode)) == 1
    assert json.loads(model.requests[2][0][-1]["content"])["reason"] == "REQUIRED_ACTIONS_MISSING"
