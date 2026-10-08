import json
import sqlite3

import pytest

from agentguard.computation import InProcessComputer
from agentguard.contracts import CreateAction
from agentguard.model import ModelFailure
from agentguard.reviewer import ExactActionReviewer, ReviewContract
from agentguard.runtime import Budgets, Runtime, initial_messages


def reply(content, *, tokens=20, finish="stop", prompt=100):
    return json.dumps(
        {
            "choices": [{"message": {"content": content}, "finish_reason": finish}],
            "usage": {"completion_tokens": tokens, "prompt_tokens": prompt},
        }
    )


def action(project="atlas"):
    return json.dumps(
        {
            "kind": "action",
            "action": {
                "tool": "tickets.create",
                "arguments": {"project_id": project, "title": "Test", "body": "Test body"},
            },
        }
    )


FINAL = json.dumps({"kind": "final", "text": "Done."})


class FakeModel:
    def __init__(self, outputs, *, on_call=None, prompt_tokens=100):
        self.outputs = iter(outputs)
        self.requests = []
        self.on_call = on_call
        self.prompt_tokens = prompt_tokens

    def count_tokens(self, messages, *, timeout):
        assert timeout > 0
        return self.prompt_tokens

    def complete(self, messages, schema, *, max_tokens, timeout):
        self.requests.append((list(messages), max_tokens))
        assert timeout > 0
        if self.on_call:
            self.on_call()
        output = next(self.outputs)
        if isinstance(output, Exception):
            raise output
        return output


def test_raw_response_is_durable_before_effect(store, episode):
    class CheckedComputer(InProcessComputer):
        def compute(self, request):
            # Separate connection proves the raw response transaction has committed.
            with sqlite3.connect(store.path) as db:
                assert db.execute("SELECT raw_response FROM model_calls").fetchone()[0] == raw
            return super().compute(request)

    raw = reply(action())
    store.computer = CheckedComputer()
    model = FakeModel([raw, reply(FINAL)])
    result = Runtime(store, model).run(episode, "Create a ticket")
    assert result["status"] == "COMPLETED"
    assert len(store.tickets(episode)) == 1
    assert result["generated_tokens"] == 40


def test_denied_action_can_recover(store, episode):
    model = FakeModel([reply(action("orion")), reply(action()), reply(FINAL)])
    result = Runtime(store, model).run(episode, "Create a ticket")
    assert result["status"] == "COMPLETED"
    assert result["trace"][0]["execution"]["decision"]["outcome"] == "DENY"
    assert [ticket["project_id"] for ticket in store.tickets(episode)] == ["atlas"]
    feedback = json.loads(model.requests[1][0][-1]["content"])
    assert feedback["recovery"]["original_task"] == "Create a ticket"
    assert "orion" not in feedback["recovery"]["scope"]["project_ids"]
    assert "approval_id" not in feedback


def test_recovery_never_rewrites_or_authorizes_a_second_forbidden_proposal(store, episode):
    model = FakeModel([reply(action("orion")), reply(action("orion")), reply(FINAL)])
    result = Runtime(store, model).run(episode, "Create in Atlas")
    assert [row["execution"]["decision"]["outcome"] for row in result["trace"]] == ["DENY", "DENY"]
    assert store.tickets(episode) == []


def test_recovery_reminder_shares_output_and_step_budgets(store, episode):
    model = FakeModel([reply(action("orion"))])
    result = Runtime(store, model, Budgets(max_tool_result_bytes=100)).run(
        episode, "Create in Atlas"
    )
    assert result["reason"] == "TOOL_RESULT_LIMIT"
    assert result["model_calls"] == 1
    assert store.tickets(episode) == []


def test_approval_pauses_without_model_credential(store, episode):
    model = FakeModel([reply(action("shared"))])
    result = Runtime(store, model).run(episode, "Create a shared ticket")
    assert result["status"] == "WAITING_APPROVAL"
    assert store.tickets(episode) == []
    assert len(model.requests) == 1
    with store.connection() as db:
        approval = db.execute("SELECT status, consumed FROM approvals").fetchone()
        assert tuple(approval) == ("PENDING", 0)


@pytest.mark.parametrize("approve", [False, True])
def test_simulated_review_flows_through_gateway_without_exposing_credentials(
    store, episode, contract, approve
):
    allowed = CreateAction.model_validate(json.loads(action("shared"))["action"])
    reviewer = ExactActionReviewer(
        contract, ReviewContract(allowed_actions=(allowed,) if approve else ())
    )
    model = FakeModel([reply(action("shared")), reply(FINAL)])
    result = Runtime(store, model, reviewer=reviewer).run(episode, "Create a shared ticket")
    assert result["status"] == "COMPLETED"
    assert result["trace"][0]["simulated_review"]["approved"] is approve
    assert len(store.tickets(episode)) == int(approve)
    feedback = json.loads(model.requests[1][0][-1]["content"])
    assert feedback["outcome"] == ("ALLOW" if approve else "DENY")
    with store.connection() as db:
        approval = db.execute("SELECT id, nonce, action_hash FROM approvals").fetchone()
    for secret in approval:
        assert secret not in json.dumps(model.requests)


def test_cancellation_during_simulated_review_still_prohibits_effect(store, episode, contract):
    allowed = CreateAction.model_validate(json.loads(action("shared"))["action"])

    class CancellingReviewer(ExactActionReviewer):
        def review(self, store, request_id):
            result = super().review(store, request_id)
            store.cancel(episode)
            return result

    reviewer = CancellingReviewer(contract, ReviewContract(allowed_actions=(allowed,)))
    result = Runtime(store, FakeModel([reply(action("shared"))]), reviewer=reviewer).run(
        episode, "Create a shared ticket"
    )
    assert result["status"] == "CANCELLED"
    assert store.tickets(episode) == []


@pytest.mark.parametrize("bad", ["not json", '{"kind":"final","text":"ok","grant":"fake"}'])
def test_one_schema_repair_is_charged_to_budgets(store, episode, bad):
    model = FakeModel([reply(bad), reply(FINAL)])
    result = Runtime(store, model).run(episode, "Task")
    assert result["schema_repairs"] == 1
    assert result["model_calls"] == 2
    assert result["generated_tokens"] == 40
    assert result["status"] == "COMPLETED"


def test_second_bad_proposal_fails_without_effect(store, episode):
    result = Runtime(store, FakeModel([reply("no"), reply("no")])).run(episode, "Task")
    assert result["reason"] == "INVALID_PROPOSAL"
    assert store.tickets(episode) == []


@pytest.mark.parametrize(
    "raw,reason",
    [
        ("bad envelope", "INVALID_MODEL_RESPONSE"),
        (reply(action(), tokens=769), "MODEL_BUDGET_VIOLATION"),
        (reply(action(), prompt=8192), "MODEL_BUDGET_VIOLATION"),
        (reply(action(), finish="length"), "OUTPUT_TOKEN_LIMIT"),
        (reply(action(), finish="unknown"), "MODEL_FINISH_REASON"),
    ],
)
def test_invalid_or_truncated_response_never_executes(store, episode, raw, reason):
    result = Runtime(store, FakeModel([raw])).run(episode, "Task")
    assert result["reason"] == reason
    assert store.tickets(episode) == []
    with store.connection() as db:
        assert db.execute("SELECT raw_response FROM model_calls").fetchone()[0] == raw


def test_context_budget_prevents_generation_without_truncating_task(store, episode):
    model = FakeModel([], prompt_tokens=8000)
    result = Runtime(store, model).run(episode, "Task")
    assert result["reason"] == "CONTEXT_BUDGET"
    assert not model.requests


def test_remaining_tokens_bound_next_generation(store, episode):
    model = FakeModel([reply(action(), tokens=20), reply(FINAL, tokens=5)])
    result = Runtime(store, model, Budgets(max_total_generated_tokens=25)).run(episode, "Task")
    assert result["status"] == "COMPLETED"
    assert [request[1] for request in model.requests] == [25, 5]


def test_exhausted_tokens_prevent_next_call(store, episode):
    model = FakeModel([reply(action(), tokens=20)])
    result = Runtime(store, model, Budgets(max_total_generated_tokens=20)).run(episode, "Task")
    assert result["reason"] == "TOKEN_BUDGET"
    assert len(model.requests) == 1


def test_step_limit_includes_schema_repair(store, episode):
    model = FakeModel([reply("bad")])
    result = Runtime(store, model, Budgets(max_steps=1)).run(episode, "Task")
    assert result["reason"] == "STEP_BUDGET"


def test_tool_output_limit_is_explicit(store, episode):
    raw = reply(
        json.dumps(
            {
                "kind": "action",
                "action": {"tool": "documents.read", "arguments": {"document_id": "doc"}},
            }
        )
    )
    model = FakeModel([raw])
    result = Runtime(store, model, Budgets(max_tool_result_bytes=1)).run(episode, "Task")
    assert result["reason"] == "TOOL_RESULT_LIMIT"


def test_cancel_during_inference_prohibits_effect(store, episode):
    model = FakeModel([reply(action())], on_call=lambda: store.cancel(episode))
    result = Runtime(store, model).run(episode, "Task")
    assert result["status"] == "CANCELLED"
    assert store.tickets(episode) == []


def test_deadline_after_inference_prohibits_effect(store, episode):
    now = [0.0]
    model = FakeModel([reply(action())], on_call=lambda: now.__setitem__(0, 301))
    result = Runtime(store, model, clock=lambda: now[0]).run(episode, "Task")
    assert result["reason"] == "EPISODE_TIMEOUT"
    assert store.tickets(episode) == []


def test_deadline_during_computation_prohibits_commit(store, episode):
    now = [0.0]

    class SlowComputer(InProcessComputer):
        def compute(self, request):
            now[0] = 301
            return super().compute(request)

    store.computer = SlowComputer()
    result = Runtime(store, FakeModel([reply(action())]), clock=lambda: now[0]).run(episode, "Task")
    assert result["status"] == "BUDGET_EXHAUSTED"
    assert store.tickets(episode) == []


def test_model_unavailable_is_recorded_without_fallback(store, episode):
    result = Runtime(store, FakeModel([ModelFailure("MODEL_UNAVAILABLE")])).run(episode, "Task")
    assert result["reason"] == "MODEL_UNAVAILABLE"
    assert result["model_calls"] == 1
    with store.connection() as db:
        assert db.execute("SELECT error FROM model_calls").fetchone()[0] == "MODEL_UNAVAILABLE"


def test_prompt_contains_only_task_scope_and_protocol(contract):
    messages = initial_messages("Visible task", contract, hardened=True)
    user = json.loads(messages[1]["content"])
    assert set(user) == {"task", "scope"}
    assert user["scope"] == contract.model_dump(mode="json")
    assert "untrusted" in messages[0]["content"]
    assert "untrusted" not in initial_messages("Task", contract, hardened=False)[0]["content"]


def test_second_run_requires_explicit_recovery_not_regeneration(store, episode):
    Runtime(store, FakeModel([reply(FINAL)])).run(episode, "Task")
    model = FakeModel([])
    with pytest.raises(sqlite3.IntegrityError):
        Runtime(store, model).run(episode, "Task")
    assert not model.requests
