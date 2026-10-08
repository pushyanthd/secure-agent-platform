import json

import pytest
from test_runtime import FINAL, FakeModel, action, reply
from test_worker import IDENTITY, Crash, review

from agentguard.runtime import Budgets, Runtime, turn_schema
from agentguard.worker import Worker

V2 = Budgets(decision_review="structured-v2")


class SchemaModel(FakeModel):
    def __init__(self, outputs):
        super().__init__(outputs)
        self.schemas = []

    def complete(self, messages, schema, **kwargs):
        self.schemas.append(schema)
        return super().complete(messages, schema, **kwargs)


def test_mutation_review_uses_same_tool_grammar_and_executes_replacement_only(store, episode):
    wrong = json.loads(action())
    wrong["action"]["arguments"]["body"] = "Wrong"
    model = SchemaModel([reply(json.dumps(wrong)), reply(action()), reply(FINAL), reply(FINAL)])
    result = Runtime(store, model, V2).run(episode, "Create")
    assert result["status"] == "COMPLETED"
    assert len(result["trace"]) == 1
    assert store.tickets(episode)[0]["body"] == "Test body"
    assert model.schemas[0] == model.schemas[2] == model.schemas[3] == turn_schema()
    schema = model.schemas[1]
    assert schema["properties"]["kind"]["const"] == "action"
    assert schema["properties"]["action"] == {"$ref": "#/$defs/CreateAction"}
    assert schema["$defs"]["CreateAction"]["required"] == ["tool", "arguments"]
    assert list(schema["properties"]) == ["kind", "action"]
    assert list(schema["$defs"]["CreateAction"]["properties"]) == ["tool", "arguments"]


@pytest.mark.parametrize(
    "replacement",
    [
        FINAL,
        json.dumps(
            {
                "kind": "action",
                "action": {"tool": "documents.read", "arguments": {"document_id": "doc"}},
            }
        ),
    ],
)
def test_host_rejects_review_that_violates_grammar_without_effects(store, episode, replacement):
    model = FakeModel([reply(action()), reply(replacement)])
    result = Runtime(store, model, V2).run(episode, "Create")
    assert result["status"] == "FAILED"
    assert result["reason"] == "INVALID_REVIEW_PROPOSAL"
    assert result["generated_tokens"] == 40
    assert result["trace"] == []
    assert result["final_response"] == ""
    assert not store.tickets(episode)


def test_omitted_effect_gets_completion_feedback_before_final_review(
    store, contract, documents, projects
):
    contract = contract.model_copy(update={"completion_tools": ("tickets.create",)})
    episode = store.create_episode(contract, documents, projects)
    model = SchemaModel(
        [reply(FINAL), reply(action()), reply(action()), reply(FINAL), reply(FINAL)]
    )
    result = Runtime(store, model, V2).run(episode, "Create")
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 5
    assert json.loads(model.requests[1][0][-1]["content"])["reason"] == "REQUIRED_ACTIONS_MISSING"
    assert len(store.tickets(episode)) == 1


def test_structured_review_still_requires_gateway_authority(store, episode):
    model = FakeModel([reply(action("orion")), reply(action("orion")), reply(FINAL), reply(FINAL)])
    result = Runtime(store, model, V2).run(episode, "Create")
    assert result["trace"][0]["execution"]["decision"]["outcome"] == "DENY"
    assert not store.tickets(episode)


def test_malformed_review_repair_keeps_action_grammar(store, episode):
    model = SchemaModel([reply(action()), reply("{}"), reply(action()), reply(FINAL), reply(FINAL)])
    result = Runtime(store, model, V2).run(episode, "Create")
    assert result["status"] == "COMPLETED"
    assert result["schema_repairs"] == 1
    assert model.schemas[1] == model.schemas[2]
    assert len(store.tickets(episode)) == 1


def test_pending_review_and_effect_recover_with_original_settings(
    store, episode, clock, monkeypatch
):
    execute = store.execute

    def crash(*args, **kwargs):
        execute(*args, **kwargs)
        raise Crash

    monkeypatch.setattr(store, "execute", crash)
    worker = Worker(store, SchemaModel([reply(action()), reply(action())]), model_identity=IDENTITY)
    worker.submit(episode, "Create", V2)
    with pytest.raises(Crash):
        worker.run_once()
    monkeypatch.setattr(store, "execute", execute)
    clock[0] += 31
    model = SchemaModel([reply(FINAL), reply(FINAL)])
    result = Worker(store, model, model_identity=IDENTITY).run_once()
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 4
    assert len(model.requests) == 2
    assert len(store.tickets(episode)) == 1


def test_operator_approval_binds_reviewed_action(store, episode):
    worker = Worker(
        store, FakeModel([reply(action()), reply(action("shared"))]), model_identity=IDENTITY
    )
    worker.submit(episode, "Create", V2)
    paused = worker.run_once()
    assert paused["status"] == "WAITING_APPROVAL"
    assert paused["trace"][-1]["action"]["arguments"]["project_id"] == "shared"
    review(store, paused["trace"][-1]["execution"]["approval_id"])
    result = Worker(
        store, FakeModel([reply(FINAL), reply(FINAL)]), model_identity=IDENTITY
    ).run_once()
    assert result["status"] == "COMPLETED"
    assert [ticket["project_id"] for ticket in store.tickets(episode)] == ["shared"]


def test_review_cannot_commit_candidate_after_budget_exhaustion(store, episode):
    model = FakeModel([reply(action())])
    result = Runtime(store, model, V2.model_copy(update={"max_steps": 1})).run(episode, "Create")
    assert result["reason"] == "STEP_BUDGET"
    assert not store.tickets(episode)
