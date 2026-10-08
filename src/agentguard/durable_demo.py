"""Authored approval/recovery demonstration; no fresh or recorded model inference."""

import json
import time
import uuid
from pathlib import Path
from typing import Any

from agentguard.contracts import canonical_json, digest
from agentguard.live import atomic_json
from agentguard.reviewer import ExactActionReviewer
from agentguard.scenarios import DevelopmentTask, grade_episode
from agentguard.storage import Store
from agentguard.worker import Worker


class ScriptedModel:
    """Select an authored turn from the restored transcript, with no generated tokens."""

    def __init__(self, task: DevelopmentTask):
        self.turns = [
            {"kind": "action", "action": action.model_dump()}
            for action in task.clean_script.actions
        ] + [{"kind": "final", "text": task.clean_script.final_response}]

    def count_tokens(self, messages: list[dict[str, str]], *, timeout: float) -> int:
        return 0  # Explicit fixture metering, never live-model evidence.

    def complete(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        max_tokens: int,
        timeout: float,
    ) -> str:
        index = sum(message["role"] == "assistant" for message in messages)
        return canonical_json(
            {
                "choices": [
                    {
                        "message": {"content": canonical_json(self.turns[index])},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }
        )


class DemoInterruption(Exception):
    pass


def run_durable_demo(task_path: Path, output_root: Path) -> Path:
    task = DevelopmentTask.model_validate_json(task_path.read_bytes())
    directory = output_root / str(uuid.uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    now = [time.time()]
    database = directory / "state.sqlite3"
    store = Store(database, clock=lambda: now[0])
    identity = {"mode": "authored_fixture", "task_sha256": digest(task.model_dump(mode="json"))}
    episode = store.create_episode(
        task.contract, task.documents, task.projects, tickets=task.initial_tickets
    )
    worker = Worker(store, ScriptedModel(task), model_identity=identity)
    worker.submit(episode, task.task)
    waiting = worker.run_once()
    if waiting is None or waiting["status"] != "WAITING_APPROVAL":
        raise ValueError("Demo fixture must reach a reviewable write")
    approval = waiting["trace"][-1]["execution"]["approval_id"]
    reviewer = ExactActionReviewer(task.contract, task.review_contract)
    if not reviewer.review(store, approval):
        raise ValueError("Demo fixture review contract must permit the exact write")

    class InterruptAfterCommit(Store):
        def execute(self, *args: Any, **kwargs: Any) -> Any:
            result = super().execute(*args, **kwargs)
            if "ticket_id" in result.result:
                raise DemoInterruption("Simulated worker interruption after effect commit")
            return result

    interrupted_store = InterruptAfterCommit(database, clock=lambda: now[0])
    try:
        Worker(interrupted_store, ScriptedModel(task), model_identity=identity).run_once()
    except DemoInterruption:
        pass
    else:
        raise AssertionError("Expected an interruption after the reviewed effect")
    committed_before_recovery = len(store.tickets(episode))
    now[0] += 31  # Simulated lease expiry; no sleep or claim of measured outage duration.
    reopened = Store(database, clock=lambda: now[0])
    recovered = Worker(reopened, ScriptedModel(task), model_identity=identity).run_once()
    assert recovered is not None
    grade = grade_episode(
        reopened, episode, recovered["final_response"], task.expectation, attacked=False
    )
    checks = {
        "approval_wait_persisted": waiting["status"] == "WAITING_APPROVAL",
        "effect_committed_before_interruption": committed_before_recovery == 1,
        "no_duplicate_effect_after_restart": len(reopened.tickets(episode)) == 1,
        "approval_consumed_once": reopened.approval(approval)["consumed"] == 1,
        "completed_after_restart": recovered["status"] == "COMPLETED",
        "independent_task_grade_passed": grade["task_success"],
        "one_saved_response_per_authored_turn": recovered["model_calls"]
        == len(task.clean_script.actions) + 1,
    }
    report = {
        "mode": "scripted_recovery_demo",
        "fresh_model_trials": 0,
        "containment": reopened.computer.mode,
        "interruption": "injected exception after commit; simulated 31-second lease expiry",
        "approval_behavior": "exact-action reviewer simulation, not an authenticated human",
        "episode_id": episode,
        "checks": checks,
        "passed": all(checks.values()),
        "result": recovered,
        "grade": grade,
        "events": reopened.events(episode),
        "execution_manifest": json.loads(worker.manifest),
    }
    atomic_json(directory / "report.json", report)
    (directory / "report.md").write_text(
        "# Durable execution demonstration\n\n"
        "Authored replay; **zero model trials**. In-process synthetic tools.\n\n"
        "An exact-action reviewer approves the persisted request. An injected interruption "
        "occurs after the ticket commit. A reopened store recovers the saved response after "
        "simulated lease expiry and completes without duplicating the ticket.\n\n"
        + "\n".join(f"- {'PASS' if passed else 'FAIL'}: {name}" for name, passed in checks.items())
        + "\n"
    )
    return directory
