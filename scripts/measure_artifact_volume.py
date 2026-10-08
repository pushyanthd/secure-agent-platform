"""Measure real aggregate ENOSPC, atomic effects and saved-response recovery on a new volume.

Authored model fixture and in-process tools only. This is not live model crash evidence.
"""

import argparse
import errno
import hashlib
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from agentguard.artifact_volume import load_volume
from agentguard.bounded_storage import BoundedStore
from agentguard.contracts import CreateAction, CreateArguments
from agentguard.durable_demo import ScriptedModel
from agentguard.runtime import Budgets
from agentguard.scenarios import DevelopmentTask, grade_episode
from agentguard.storage import Store
from agentguard.worker import Worker

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = {"mode": "authored-storage-exhaustion-fixture", "version": 1}


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fill(path: Path) -> dict[str, Any]:
    started = time.monotonic()
    written = 0
    with path.open("xb", buffering=0) as output:
        try:
            while True:
                written += output.write(b"x" * 65536)
                os.fsync(output.fileno())
        except OSError as exc:
            if exc.errno != errno.ENOSPC:
                raise
    return {
        "errno": errno.ENOSPC,
        "written_bytes": written,
        "seconds": round(time.monotonic() - started, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("exhaust", "recover"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    volume = load_volume(args.manifest)
    volume.verify(volume.mountpoint)
    output = args.output.resolve()
    if output.is_relative_to(volume.mountpoint):
        parser.error("Measurement controller evidence must be outside the exhausted volume")
    task = DevelopmentTask.model_validate_json(
        (ROOT / "scenarios/dev/suite/two-ticket-batch.json").read_bytes()
    )
    data = volume.mountpoint / "measurement"
    database = data / "state.sqlite3"
    if args.phase == "exhaust":
        output.mkdir(parents=True, exist_ok=False)
        data.mkdir(exist_ok=False)
        retained = data / "retained-evidence.txt"
        retained.write_text("Synthetic retained evidence; never delete to recover capacity.\n")
        now = [time.time()]
        exhaustion: dict[str, Any] = {}

        class ExhaustAfterCommit(BoundedStore):
            def execute(self, *arguments: Any, **keywords: Any) -> Any:
                result = super().execute(*arguments, **keywords)
                if "ticket_id" in result.result and not exhaustion:
                    exhaustion.update(fill(data / "synthetic-capacity-fill.bin"))
                return result

        store: Store = ExhaustAfterCommit(database, clock=lambda: now[0], artifact_volume=volume)
        episode = store.create_episode(task.contract, task.documents, task.projects)
        uncommitted = store.create_episode(task.contract, task.documents, task.projects)
        worker = Worker(store, ScriptedModel(task), model_identity=IDENTITY)
        worker.submit(episode, task.task, Budgets(max_episode_seconds=900))
        try:
            worker.run_once()
        except sqlite3.Error as exc:
            if getattr(exc, "sqlite_errorcode", None) != sqlite3.SQLITE_FULL:
                raise
            checkpoint_error = {
                "sqlite_errorcode": exc.sqlite_errorcode,
                "sqlite_errorname": exc.sqlite_errorname,
            }
        else:
            raise AssertionError("Expected a rejected checkpoint after capacity exhaustion")
        proposal = CreateAction(
            arguments=CreateArguments(project_id="atlas", title="Must not commit", body="y" * 4000)
        )
        try:
            store.execute(uncommitted, "full-write", proposal)
        except sqlite3.Error as exc:
            if getattr(exc, "sqlite_errorcode", None) != sqlite3.SQLITE_FULL:
                raise
        else:
            raise AssertionError("Expected over-limit effect transaction to fail")
        with store.connection() as db:
            job = dict(db.execute("SELECT * FROM jobs WHERE episode_id=?", (episode,)).fetchone())
            calls = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM model_calls WHERE episode_id=? ORDER BY step", (episode,)
                )
            ]
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        checks = {
            "file_write_rejected_enospc": exhaustion["errno"] == errno.ENOSPC,
            "checkpoint_rejected_sqlite_full": checkpoint_error["sqlite_errorcode"]
            == sqlite3.SQLITE_FULL,
            "one_effect_retained_after_failed_checkpoint": len(store.tickets(episode)) == 1,
            "over_limit_effect_rolled_back": store.tickets(uncommitted) == [],
            "over_limit_audit_rolled_back": store.events(uncommitted) == [],
            "job_retained_for_recovery": job["status"] == "RUNNING",
            "responses_saved_before_effect": len(calls) == 2
            and all(c["raw_response"] for c in calls),
            "sqlite_integrity_at_exhaustion": integrity == "ok",
        }
        if not all(checks.values()):
            raise AssertionError(checks)
        # All connections and the worker are closed. This synthetic full-state snapshot
        # is copied for preservation, not opened with the mutable Store constructor.
        shutil.copyfile(database, output / "exhausted-state.sqlite3")
        record = {
            "version": "artifact-exhaustion-v1",
            "mode": "authored_fixture",
            "fresh_model_calls": 0,
            "containment": "in_process",
            "clock_note": "Recovery simulates lease expiry; no live crash-duration claim.",
            "volume_before": volume.model_dump(mode="json"),
            "episode": episode,
            "clock": now[0],
            "exhaustion": exhaustion,
            "checkpoint_error": checkpoint_error,
            "checks": checks,
            "saved_calls": calls,
            "retained_sha256": sha(retained),
            "filler_sha256": sha(data / "synthetic-capacity-fill.bin"),
            "exhausted_database_sha256": sha(output / "exhausted-state.sqlite3"),
            "source_sha256": {
                str(path.relative_to(ROOT)): sha(path)
                for path in sorted((ROOT / "src/agentguard").glob("*.py"))
            }
            | {"scripts/measure_artifact_volume.py": sha(Path(__file__))},
        }
        (output / "exhaustion.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(checks, indent=2))
    else:
        before = json.loads((output / "exhaustion.json").read_text())
        episode = before["episode"]
        store = BoundedStore(database, clock=lambda: before["clock"] + 31, artifact_volume=volume)
        result = Worker(store, ScriptedModel(task), model_identity=IDENTITY).run_once()
        assert result is not None
        grade = grade_episode(
            store, episode, result["final_response"], task.expectation, attacked=False
        )
        with store.connection() as db:
            calls = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM model_calls WHERE episode_id=? ORDER BY step", (episode,)
                )
            ]
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        checks = before["checks"] | {
            "capacity_explicitly_increased": volume.size_bytes
            > before["volume_before"]["size_bytes"],
            "retained_evidence_unchanged": sha(data / "retained-evidence.txt")
            == before["retained_sha256"],
            "filler_preserved_not_deleted": sha(data / "synthetic-capacity-fill.bin")
            == before["filler_sha256"],
            "saved_calls_reused_exactly": calls[:2] == before["saved_calls"],
            "no_duplicate_effects": len(store.tickets(episode)) == 2,
            "only_remaining_authored_calls_added": len(calls) == 4,
            "recovered_to_completed": result["status"] == "COMPLETED",
            "independent_grade_passed": grade["task_success"],
            "sqlite_integrity_after_recovery": integrity == "ok",
            "full_snapshot_preserved": sha(output / "exhausted-state.sqlite3")
            == before["exhausted_database_sha256"],
        }
        report = before | {
            "volume_after": volume.model_dump(mode="json"),
            "checks": checks,
            "passed": all(checks.values()),
            "result": result,
            "grade": grade,
        }
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(checks, indent=2))
        if not report["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
