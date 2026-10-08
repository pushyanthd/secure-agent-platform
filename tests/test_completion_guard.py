import json

import pytest
from test_runtime import FINAL, FakeModel, action, reply
from test_worker import IDENTITY, Crash, review

from agentguard.runtime import Budgets, Runtime, model_scope
from agentguard.worker import Worker


def guarded(store, contract, documents, projects, tools=("tickets.create",)):
    return store.create_episode(
        contract.model_copy(update={"completion_tools": tools}), documents, projects
    )


def test_legacy_serialization_and_initial_model_scope_are_unchanged(contract):
    assert "completion_tools" not in contract.model_dump(mode="json")
    changed = contract.model_copy(update={"completion_tools": ("tickets.create",)})
    assert model_scope(changed) == model_scope(contract)
    assert changed.model_dump(mode="json")["completion_tools"] == ["tickets.create"]


def test_final_without_effect_recovers_with_original_budgets(store, contract, documents, projects):
    episode = guarded(store, contract, documents, projects)
    model = FakeModel([reply(FINAL), reply(action()), reply(FINAL)])
    result = Runtime(store, model).run(episode, "Create the requested ticket")
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 3
    assert len(store.tickets(episode)) == 1
    feedback = json.loads(model.requests[1][0][-1]["content"])
    assert feedback["required_tools"] == ["tickets.create"]
    assert "arguments" not in feedback


def test_denial_cannot_satisfy_obligation(store, contract, documents, projects):
    episode = guarded(store, contract, documents, projects)
    model = FakeModel([reply(action("orion")), reply(FINAL), reply(FINAL)])
    result = Runtime(store, model, Budgets(max_steps=3)).run(episode, "Create a ticket")
    assert result["reason"] == "STEP_BUDGET"
    assert result["final_response"] == ""
    assert not store.tickets(episode)


def test_each_tool_required_and_successful_effect_not_repeated(
    store, contract, documents, projects
):
    episode = guarded(store, contract, documents, projects, ("documents.read", "tickets.create"))
    read = json.dumps(
        {
            "kind": "action",
            "action": {"tool": "documents.read", "arguments": {"document_id": "doc"}},
        }
    )
    model = FakeModel([reply(action()), reply(FINAL), reply(read), reply(FINAL)])
    result = Runtime(store, model).run(episode, "Read and create")
    assert result["status"] == "COMPLETED"
    assert json.loads(model.requests[2][0][-1]["content"])["required_tools"] == ["documents.read"]
    assert len(store.tickets(episode)) == 1


def test_guard_feedback_obeys_output_limit(store, contract, documents, projects):
    episode = guarded(store, contract, documents, projects)
    result = Runtime(store, FakeModel([reply(FINAL)]), Budgets(max_tool_result_bytes=50)).run(
        episode, "Create"
    )
    assert result["reason"] == "TOOL_RESULT_LIMIT"


def test_guard_replay_after_committed_effect_never_duplicates(
    store, contract, documents, projects, clock
):
    episode = guarded(store, contract, documents, projects)
    calls = 0

    def crash_after_effect():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise Crash

    first = Worker(
        store,
        FakeModel([reply(FINAL), reply(action())], on_call=crash_after_effect),
        model_identity=IDENTITY,
    )
    first.submit(episode, "Create")
    with pytest.raises(Crash):
        first.run_once()
    assert len(store.tickets(episode)) == 1
    # An in-flight model call is uncertain: recovery must fail closed, not regenerate.
    clock[0] += 31
    recovered = Worker(store, FakeModel([]), model_identity=IDENTITY).run_once()
    assert recovered["status"] == "FAILED"
    assert len(store.tickets(episode)) == 1


def test_saved_guard_reminder_and_effect_replay_to_completion(
    store, contract, documents, projects, clock, monkeypatch
):
    episode = guarded(store, contract, documents, projects)
    execute = store.execute

    def crash_after_commit(*args, **kwargs):
        execute(*args, **kwargs)
        raise Crash

    monkeypatch.setattr(store, "execute", crash_after_commit)
    first = Worker(store, FakeModel([reply(FINAL), reply(action())]), model_identity=IDENTITY)
    first.submit(episode, "Create")
    with pytest.raises(Crash):
        first.run_once()
    monkeypatch.setattr(store, "execute", execute)
    clock[0] += 31
    model = FakeModel([reply(FINAL)])
    result = Worker(store, model, model_identity=IDENTITY).run_once()
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 3
    assert len(model.requests) == 1
    assert len(store.tickets(episode)) == 1
    assert sum(e["kind"] == "EXECUTED" for e in store.events(episode)) == 1


def test_approval_resume_preserves_guard_transcript(store, contract, documents, projects):
    episode = guarded(store, contract, documents, projects)
    read = json.dumps(
        {
            "kind": "action",
            "action": {"tool": "documents.read", "arguments": {"document_id": "doc"}},
        }
    )
    first = Worker(
        store,
        FakeModel([reply(FINAL), reply(read), reply(action("shared"))]),
        model_identity=IDENTITY,
    )
    first.submit(episode, "Create")
    paused = first.run_once()
    assert paused["status"] == "WAITING_APPROVAL"
    assert not store.tickets(episode)
    review(store, paused["trace"][-1]["execution"]["approval_id"])
    resumed = Worker(store, FakeModel([reply(FINAL)]), model_identity=IDENTITY).run_once()
    assert resumed["status"] == "COMPLETED"
    assert len(store.tickets(episode)) == 1


def test_current_requirements_checked_at_final_commit(
    store, contract, documents, projects, monkeypatch
):
    episode = store.create_episode(contract, documents, projects)
    original = store.connection
    checks = 0
    from contextlib import contextmanager

    @contextmanager
    def change_before_commit():
        nonlocal checks
        with original() as db:
            # Change after final-turn inspection, at finish's accounting checkpoint.
            if db.execute(
                "SELECT count(*) FROM model_calls WHERE raw_response IS NOT NULL"
            ).fetchone()[0]:
                checks += 1
                if checks == 3:
                    updated = contract.model_copy(update={"completion_tools": ("tickets.create",)})
                    db.execute(
                        "UPDATE episodes SET contract=? WHERE id=?",
                        (updated.model_dump_json(), episode),
                    )
                    db.commit()
            yield db

    monkeypatch.setattr(store, "connection", change_before_commit)
    result = Runtime(store, FakeModel([reply(FINAL)])).run(episode, "Create")
    assert result["reason"] == "REQUIRED_ACTIONS_MISSING"
    assert result["status"] == "FAILED"
    assert result["final_response"] == ""
