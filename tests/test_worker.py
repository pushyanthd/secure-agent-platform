import json
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from test_runtime import FINAL, FakeModel, action, reply

from agentguard.computation import InProcessComputer
from agentguard.contracts import CreateAction
from agentguard.runtime import Budgets, Runtime
from agentguard.storage import LeaseLost, ReviewRejected, Store
from agentguard.worker import Worker

IDENTITY = {"mode": "scripted_fixture", "version": 1}


class Crash(BaseException):
    pass


def worker(store, outputs=(), **kwargs):
    return Worker(store, FakeModel(outputs), model_identity=IDENTITY, **kwargs)


def review(store, request_id, approve=True):
    pending = store.approval(request_id)
    store.review(
        request_id,
        expected_hash=pending["action_hash"],
        nonce=pending["nonce"],
        reviewer="operator",
        approve=approve,
    )


def test_submission_is_idempotent_and_pins_inputs(store, episode):
    w = worker(store)
    w.submit(episode, "Task")
    w.submit(episode, "Task")
    with pytest.raises(ValueError, match="different inputs"):
        w.submit(episode, "Changed")
    with pytest.raises(ValueError, match="different inputs"):
        w.submit(episode, "Task", Budgets(max_steps=2))
    changed = Worker(store, FakeModel([]), model_identity={"model": "different"})
    assert changed.run_once() is None
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1


def test_queue_excludes_baselines_and_used_episodes(store, contract, documents, projects, episode):
    baseline = store.create_episode(contract, documents, projects, experimental_profile="baseline")
    with pytest.raises(ValueError, match="defended"):
        worker(store).submit(baseline, "Task")
    Runtime(store, FakeModel([reply(FINAL)])).run(episode, "Task")
    with pytest.raises(ValueError, match="unused"):
        worker(store).submit(episode, "Task")


def test_atomic_claim_allows_only_one_active_episode(store, episode, contract, documents, projects):
    w = worker(store)
    w.submit(episode, "Task")
    second = store.create_episode(contract, documents, projects)
    w.submit(second, "Task")
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: w.queue.claim(manifest=w.manifest), range(8)))
    assert sum(claim is not None for claim in claims) == 1


def test_expired_and_superseded_tokens_cannot_execute_or_heartbeat(store, episode, clock):
    w = worker(store)
    w.submit(episode, "Task")
    old = w.queue.claim(manifest=w.manifest, lease_seconds=10)
    clock[0] += 10
    with pytest.raises(LeaseLost):
        w.queue.heartbeat(old)
    new = w.queue.claim(manifest=w.manifest)
    assert new.generation == old.generation + 1
    proposal = CreateAction.model_validate(json.loads(action())["action"])
    for invalid in (None, old, replace(new, episode_id="different"), replace(new, token="fake")):
        with pytest.raises(LeaseLost):
            store.execute(episode, "key", proposal, lease=invalid)
    assert store.tickets(episode) == []
    w.queue.heartbeat(new)
    store.execute(episode, "key", proposal, lease=new)
    assert len(store.tickets(episode)) == 1


def test_lease_is_rechecked_after_tool_computation(store, episode, clock):
    w = worker(store)
    w.submit(episode, "Task")
    lease = w.queue.claim(manifest=w.manifest, lease_seconds=10)

    class SlowComputer(InProcessComputer):
        def compute(self, request):
            clock[0] += 10
            return super().compute(request)

    store.computer = SlowComputer()
    proposal = CreateAction.model_validate(json.loads(action())["action"])
    with pytest.raises(LeaseLost):
        store.execute(episode, "key", proposal, lease=lease)
    assert store.tickets(episode) == []
    assert not any(e["kind"] == "EXECUTED" for e in store.events(episode))


def test_stale_worker_cannot_save_model_response_or_final_status(store, episode, clock):
    w = worker(store)
    w.submit(episode, "Task")
    old = w.queue.claim(manifest=w.manifest, lease_seconds=10)

    def supersede():
        clock[0] += 10
        assert w.queue.claim(manifest=w.manifest) is not None

    with pytest.raises(LeaseLost):
        Runtime(store, FakeModel([reply(action())], on_call=supersede)).run(
            episode, "Task", lease=old
        )
    with store.connection() as db:
        assert db.execute("SELECT raw_response FROM model_calls").fetchone()[0] is None
        assert db.execute("SELECT status FROM agent_runs").fetchone()[0] == "RUNNING"
    assert store.tickets(episode) == []


@pytest.mark.parametrize("boundary", ["before_effect", "after_effect"])
def test_process_death_recovers_saved_response_and_exactly_one_effect(
    store, episode, clock, boundary
):
    w = worker(store)
    w.submit(episode, "Task")
    # Real process death: no exception unwinding, worker cleanup, or in-memory state survives.
    script = """
import json, os, sys
from pathlib import Path
from agentguard.computation import InProcessComputer
from agentguard.storage import Store
from agentguard.worker import Worker
class Computer(InProcessComputer):
    def compute(self, request):
        if sys.argv[2] == "before_effect": os._exit(73)
        return super().compute(request)
class CrashingStore(Store):
    def execute(self, *args, **kwargs):
        result = super().execute(*args, **kwargs)
        os._exit(73)
class Model:
    def count_tokens(self, *args, **kwargs): return 100
    def complete(self, *args, **kwargs): return sys.argv[3]
store = CrashingStore(Path(sys.argv[1]), clock=lambda: 1000.0, computer=Computer())
Worker(store, Model(), model_identity={"mode":"scripted_fixture","version":1}).run_once()
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(store.path), boundary, reply(action())],
        timeout=10,
        capture_output=True,
        text=True,
    )
    assert child.returncode == 73, child.stderr
    assert len(store.tickets(episode)) == int(boundary == "after_effect")
    clock[0] += 31
    reopened = Store(store.path, clock=lambda: clock[0])
    restarted = worker(reopened, [reply(FINAL)])
    result = restarted.run_once()
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 2
    assert result["generated_tokens"] == 40
    assert len(restarted.model.requests) == 1
    assert len(reopened.tickets(episode)) == 1
    assert len([e for e in store.events(episode) if e["kind"] == "EXECUTED"]) == 1
    assert restarted.run_once() is None


def test_lost_response_is_failed_without_regeneration_or_budget_reset(store, episode, clock):
    def crash():
        raise Crash

    w = Worker(store, FakeModel([], on_call=crash), model_identity=IDENTITY)
    w.submit(episode, "Task", Budgets(max_total_generated_tokens=25))
    with pytest.raises(Crash):
        w.run_once()
    clock[0] += 31
    resumed = worker(store)
    result = resumed.run_once()
    assert result["reason"] == "MODEL_RESPONSE_LOST"
    assert result["model_calls"] == 1
    assert result["generated_tokens"] == 0
    assert result["reserved_generated_tokens"] == 25
    assert result["charged_generated_tokens"] == 25
    assert not resumed.model.requests


@pytest.mark.parametrize("approve", [True, False])
def test_approval_releases_lease_and_resumes_across_reopen(store, episode, clock, approve):
    w = worker(store, [reply(action("shared"))])
    w.submit(episode, "Task")
    waiting = w.run_once()
    assert waiting["status"] == "WAITING_APPROVAL"
    assert w.run_once() is None
    with store.connection() as db:
        assert db.execute("SELECT token,lease_until FROM jobs").fetchone()[:] == (None, None)
    request_id = waiting["trace"][0]["execution"]["approval_id"]
    reopened = Store(store.path, clock=lambda: clock[0])
    review(reopened, request_id, approve)
    resumed = worker(reopened, [reply(FINAL)])
    result = resumed.run_once()
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 2
    assert len(store.tickets(episode)) == int(approve)
    assert store.approval(request_id)["consumed"] == int(approve)
    for credential in (request_id, store.approval(request_id)["nonce"]):
        assert credential not in json.dumps(resumed.model.requests)


def test_review_race_before_wait_checkpoint_does_not_lose_wakeup(store, episode, monkeypatch):
    execute = store.execute

    def early_review(*args, **kwargs):
        result = execute(*args, **kwargs)
        if result.approval_id:
            review(store, result.approval_id)
        return result

    monkeypatch.setattr(store, "execute", early_review)
    w = worker(store, [reply(action("shared")), reply(FINAL)])
    w.submit(episode, "Task")
    assert w.run_once()["status"] == "WAITING_APPROVAL"
    assert w.run_once()["status"] == "COMPLETED"
    assert len(store.tickets(episode)) == 1


def test_review_before_crash_before_wait_checkpoint_is_recovered(
    store, episode, clock, monkeypatch
):
    execute = store.execute

    def crash_after_review(*args, **kwargs):
        result = execute(*args, **kwargs)
        review(store, result.approval_id)
        raise Crash

    monkeypatch.setattr(store, "execute", crash_after_review)
    w = worker(store, [reply(action("shared"))])
    w.submit(episode, "Task")
    with pytest.raises(Crash):
        w.run_once()
    monkeypatch.setattr(store, "execute", execute)
    clock[0] += 31
    assert worker(store, [reply(FINAL)]).run_once()["status"] == "COMPLETED"
    assert len(store.tickets(episode)) == 1


def test_approved_changed_resource_is_denied_on_resume(store, episode):
    w = worker(store, [reply(action("shared"))])
    w.submit(episode, "Task")
    waiting = w.run_once()
    request_id = waiting["trace"][0]["execution"]["approval_id"]
    review(store, request_id)
    with store.connection() as db:
        row = db.execute("SELECT payload FROM resources WHERE id='shared'").fetchone()
        resource = json.loads(row[0])
        resource["version"] += 1
        db.execute("UPDATE resources SET payload=? WHERE id='shared'", (json.dumps(resource),))
    result = worker(store, [reply(FINAL)]).run_once()
    assert result["trace"][0]["execution"]["decision"]["reason"] == "APPROVAL_INVALID"
    assert store.tickets(episode) == []


def test_revoked_task_scope_is_enforced_after_approval(store, episode, contract):
    w = worker(store, [reply(action("shared"))])
    w.submit(episode, "Task")
    waiting = w.run_once()
    review(store, waiting["trace"][0]["execution"]["approval_id"])
    with store.connection() as db:
        db.execute(
            "UPDATE episodes SET contract=? WHERE id=?",
            (contract.model_copy(update={"project_ids": ("atlas",)}).model_dump_json(), episode),
        )
    result = worker(store, [reply(FINAL)]).run_once()
    assert result["status"] == "COMPLETED"
    assert result["trace"][0]["execution"]["decision"]["outcome"] == "DENY"
    assert store.tickets(episode) == []


def test_expired_approval_is_woken_without_approval_or_new_generation(store, episode, clock):
    w = worker(store, [reply(action("shared"))])
    w.submit(episode, "Task", Budgets(max_episode_seconds=600))
    w.run_once()
    clock[0] += 301
    result = worker(store, [reply(FINAL)]).run_once()
    assert result["trace"][0]["execution"]["decision"]["reason"] == "APPROVAL_CLOSED"
    assert store.tickets(episode) == []


def test_deadline_is_not_reset_by_approval_wait_or_restart(store, episode, clock):
    w = worker(store, [reply(action("shared"))])
    w.submit(episode, "Task")
    w.run_once()
    clock[0] += 301
    resumed = worker(store)
    result = resumed.run_once()
    assert result["status"] == "BUDGET_EXHAUSTED"
    assert result["model_calls"] == 1
    assert result["generated_tokens"] == 20
    assert not resumed.model.requests
    assert store.tickets(episode) == []


def test_cancelled_wait_cannot_be_reviewed_or_reclaimed(store, episode):
    w = worker(store, [reply(action("shared"))])
    w.submit(episode, "Task")
    result = w.run_once()
    store.cancel(episode)
    with pytest.raises(ReviewRejected):
        review(store, result["trace"][0]["execution"]["approval_id"])
    assert w.run_once() is None
    with store.connection() as db:
        assert db.execute("SELECT status FROM jobs").fetchone()[0] == "CANCELLED"
        assert db.execute("SELECT status FROM agent_runs").fetchone()[0] == "CANCELLED"


def test_cancellation_during_generation_fences_response_and_effect(store, episode):
    model = FakeModel([reply(action())], on_call=lambda: store.cancel(episode))
    w = Worker(store, model, model_identity=IDENTITY)
    w.submit(episode, "Task")
    with pytest.raises(LeaseLost):
        w.run_once()
    assert store.tickets(episode) == []
    with store.connection() as db:
        assert db.execute("SELECT status FROM agent_runs").fetchone()[0] == "CANCELLED"


def test_heartbeat_keeps_lease_during_long_model_call(store, episode):
    store.clock = time.time
    model = FakeModel([reply(FINAL)], on_call=lambda: time.sleep(0.6))
    w = Worker(store, model, model_identity=IDENTITY, lease_seconds=0.3)
    w.submit(episode, "Task")
    assert w.run_once()["status"] == "COMPLETED"


def test_schema_v2_upgrades_without_losing_evidence(store, episode):
    Runtime(store, FakeModel([reply(FINAL)])).run(episode, "Task")
    with store.connection() as db:
        db.execute("DROP TABLE jobs")
        db.execute("PRAGMA user_version=2")
    reopened = Store(store.path)
    with reopened.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM model_calls").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0


def test_unknown_schema_still_fails_closed(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="Unsupported"):
        Store(path)


@pytest.mark.parametrize("repair", [False, True])
def test_recovery_preserves_tokens_repairs_and_step_numbers(
    store, episode, clock, monkeypatch, repair
):
    execute = store.execute

    def interrupt(*args, **kwargs):
        execute(*args, **kwargs)
        raise Crash

    monkeypatch.setattr(store, "execute", interrupt)
    outputs = ([reply("invalid")] if repair else []) + [reply(action())]
    w = worker(store, outputs)
    w.submit(episode, "Task", Budgets(max_total_generated_tokens=45 if repair else 25))
    with pytest.raises(Crash):
        w.run_once()
    monkeypatch.setattr(store, "execute", execute)
    clock[0] += 31
    resumed = worker(store, [reply(FINAL, tokens=5)])
    result = resumed.run_once()
    assert result["status"] == "COMPLETED"
    assert result["schema_repairs"] == int(repair)
    assert result["generated_tokens"] == (45 if repair else 25)
    assert result["model_calls"] == (3 if repair else 2)
    assert resumed.model.requests[0][1] == 5
    assert len(store.tickets(episode)) == 1


def test_saved_final_response_resumes_without_contacting_model(store, episode, clock, monkeypatch):
    from agentguard import runtime

    adapter = runtime.TURN_ADAPTER

    class CrashOnParse:
        def validate_json(self, content):
            raise Crash

    w = worker(store, [reply(FINAL)])
    w.submit(episode, "Task")
    monkeypatch.setattr(runtime, "TURN_ADAPTER", CrashOnParse())
    # The schema is needed before the response; retain its original schema method.
    CrashOnParse.json_schema = adapter.json_schema
    with pytest.raises(Crash):
        w.run_once()
    monkeypatch.setattr(runtime, "TURN_ADAPTER", adapter)
    clock[0] += 31
    result = worker(store).run_once()
    assert result["status"] == "COMPLETED"
    assert result["model_calls"] == 1


def test_unmanaged_runtime_cannot_bypass_queue_fencing(store, episode):
    worker(store).submit(episode, "Task")
    with pytest.raises(LeaseLost):
        Runtime(store, FakeModel([reply(FINAL)])).run(episode, "Task")


def test_completed_job_rejects_stale_finish(store, episode):
    w = worker(store, [reply(FINAL)])
    w.submit(episode, "Task")
    lease = w.queue.claim(manifest=w.manifest)
    Runtime(store, w.model).run(episode, "Task", lease=lease)
    with pytest.raises(LeaseLost):
        Runtime(store, FakeModel([reply(action())])).run(episode, "Task", lease=lease)
    assert store.tickets(episode) == []


def test_durable_demo_cli_produces_graded_recovery_evidence(tmp_path):
    from typer.testing import CliRunner

    from agentguard.cli import app

    result = CliRunner().invoke(app, ["demo-durable", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output
    reports = list(tmp_path.glob("*/report.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert report["passed"]
    assert report["fresh_model_trials"] == 0
    assert all(report["checks"].values())
