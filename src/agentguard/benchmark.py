"""Single-host benchmark journal and exclusive ownership, separate from the app queue."""

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import signal
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Any

from pydantic import ValidationError

from agentguard.contracts import canonical_json, digest
from agentguard.model import ModelFailure, parse_reply
from agentguard.runtime import TURN_ADAPTER, ActionTurn, Budgets, FinalTurn
from agentguard.scenarios import DevelopmentTask
from agentguard.storage import Store

if os.name == "nt":
    msvcrt: Any = importlib.import_module("msvcrt")
else:
    fcntl: Any = importlib.import_module("fcntl")


@contextmanager
def graceful_stop(notify: Callable[[str], None]) -> Iterator[Callable[[], bool]]:
    requested = False
    first_signal_at = 0.0

    def handle(signum: int, frame: FrameType | None) -> None:
        nonlocal requested, first_signal_at
        if requested:
            # `uv run` forwards terminal signals that the foreground child may
            # already have received directly. Treat that burst as one request.
            if time.monotonic() - first_signal_at < 0.5:
                return
            raise KeyboardInterrupt
        first_signal_at = time.monotonic()
        requested = True
        notify(
            "Pause requested: finishing and saving the current episode. "
            "Press Ctrl+C again to interrupt immediately; that episode may fail on resume."
        )

    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for sig in previous:
            signal.signal(sig, handle)
        yield lambda: requested
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@contextmanager
def exclusive_run(directory: Path) -> Iterator[None]:
    """Hold a process lock for the benchmark run."""
    lock_path = directory / ".benchmark.lock"

    with lock_path.open("a+b") as lock:
        if os.name == "nt":
            # msvcrt.locking needs at least one byte to lock.
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()

            lock.seek(0)

            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError("Benchmark is already running in another process") from exc

            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

        else:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Benchmark is already running in another process") from exc

            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def environment() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "packages": {
            item.metadata["Name"]: item.version for item in importlib.metadata.distributions()
        },
    }


def initialize(store: Store, manifest: dict[str, Any]) -> None:
    with store.connection() as db:
        db.executescript("""
            CREATE TABLE benchmark_manifest (value TEXT NOT NULL);
            CREATE TABLE benchmark_episodes (
                position INTEGER PRIMARY KEY,
                episode_id TEXT NOT NULL UNIQUE REFERENCES episodes(id),
                started_at REAL,
                result TEXT,
                result_sha256 TEXT
            );
            CREATE TABLE benchmark_sessions (
                id INTEGER PRIMARY KEY,
                started_at REAL NOT NULL,
                ended_at REAL,
                outcome TEXT NOT NULL,
                initial_recorded INTEGER NOT NULL,
                final_recorded INTEGER
            );
        """)
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO benchmark_manifest VALUES (?)", (canonical_json(manifest),))
        db.executemany(
            "INSERT INTO benchmark_episodes(position,episode_id) VALUES (?,?)",
            [(index, entry["episode_id"]) for index, entry in enumerate(manifest["schedule"])],
        )


def recorded(store: Store, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    with store.connection() as db:
        pinned = db.execute("SELECT value FROM benchmark_manifest").fetchone()
        if pinned is None or pinned["value"] != canonical_json(manifest):
            raise ValueError("Benchmark manifest disagrees with its journal")
        entries = db.execute("SELECT * FROM benchmark_episodes ORDER BY position").fetchall()
    if [row["episode_id"] for row in entries] != [
        row["episode_id"] for row in manifest["schedule"]
    ]:
        raise ValueError("Benchmark schedule disagrees with its journal")
    results = []
    pending = False
    for entry, scheduled in zip(entries, manifest["schedule"], strict=True):
        if entry["result"] is None:
            pending = True
            continue
        if pending or digest(entry["result"]) != entry["result_sha256"]:
            raise ValueError("Benchmark journal has inconsistent results")
        result = json.loads(entry["result"])
        if any(result.get(key) != value for key, value in scheduled.items()):
            raise ValueError("Benchmark result disagrees with its schedule")
        results.append(result)
    return results


def save_result(store: Store, result: dict[str, Any]) -> None:
    raw = canonical_json(result)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE benchmark_episodes SET result=?,result_sha256=? "
            "WHERE episode_id=? AND result IS NULL AND started_at IS NOT NULL",
            (raw, digest(raw), result["episode_id"]),
        ).rowcount
        if changed != 1:
            raise ValueError("Benchmark result is immutable or episode was not started")


def status(directory: Path) -> dict[str, Any]:
    """Read-only status works without an available model, Docker, or matching source."""
    database = directory.resolve() / "state.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        try:
            manifest = json.loads(db.execute("SELECT value FROM benchmark_manifest").fetchone()[0])
            entries = db.execute("SELECT * FROM benchmark_episodes ORDER BY position").fetchall()
            sessions = [
                dict(row) for row in db.execute("SELECT * FROM benchmark_sessions ORDER BY id")
            ]
        except sqlite3.Error as exc:
            raise ValueError("This run has no resumable benchmark journal") from exc
    results = [json.loads(row["result"]) for row in entries if row["result"] is not None]
    return {
        "run_directory": str(directory),
        "mode": manifest["mode"],
        "scheduled": len(entries),
        "recorded": len(results),
        "remaining": len(entries) - len(results),
        "started_without_result": sum(
            row["started_at"] is not None and row["result"] is None for row in entries
        ),
        "failed_or_unfinished": sum(row["status"] != "COMPLETED" for row in results),
        "interrupted": sum(row["reason"] == "BENCHMARK_INTERRUPTED" for row in results),
        "complete": len(results) == len(entries),
        "sessions": sessions,
    }


def verify_files(directory: Path, manifest: dict[str, Any]) -> Path:
    if manifest.get("benchmark_journal_version") != 1:
        raise ValueError("Legacy benchmarks cannot resume; start a new run")
    source = json.loads((directory / "source.json").read_text())
    current = {p.name: p.read_text() for p in sorted(Path(__file__).parent.glob("*.py"))}
    if source != current or manifest["source_sha256"] != digest(
        {name: hashlib.sha256(value.encode()).hexdigest() for name, value in source.items()}
    ):
        raise ValueError("Resume requires the original source code")
    if manifest["environment"] != environment():
        raise ValueError("Resume requires the original Python/dependency/hardware environment")
    root = directory.resolve()
    files = {entry["file"]: entry["sha256"] for entry in manifest["fixtures"]}
    files[manifest["suite_file"]] = manifest["suite_sha256"]
    for name, expected in files.items():
        relative = Path(name)
        path = (root / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root):
            raise ValueError("Benchmark fixture path escapes the run directory")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Resume requires the original fixture snapshots")
    return directory / str(manifest["suite_file"])


def interrupted_result(
    store: Store, scheduled: dict[str, Any], task: DevelopmentTask, budgets: Budgets
) -> dict[str, Any]:
    """Never regenerate an interrupted trial or discard committed effects/unknown usage."""
    episode = scheduled["episode_id"]
    with store.connection() as db:
        saved = db.execute(
            "SELECT result FROM agent_runs WHERE episode_id=?", (episode,)
        ).fetchone()
        if saved is not None and saved["result"] is not None:
            return dict(json.loads(saved["result"]))
        calls = db.execute(
            "SELECT * FROM model_calls WHERE episode_id=? ORDER BY step", (episode,)
        ).fetchall()
        executions = {
            row["execution_key"]: json.loads(row["output"])
            for row in db.execute(
                "SELECT * FROM executions WHERE episode_id=? AND output IS NOT NULL", (episode,)
            )
        }
        reviews = db.execute(
            "SELECT * FROM approvals WHERE episode_id=? AND reviewer LIKE 'simulated:%'", (episode,)
        ).fetchall()
        decisions = {
            row["execution_key"]: json.loads(row["payload"])
            for row in db.execute(
                "SELECT * FROM audit_events WHERE episode_id=? AND kind='APPROVAL_REQUESTED'",
                (episode,),
            )
        }
    known = reserved = repairs = 0
    final = ""
    actions = {}
    for call in calls:
        try:
            reply = parse_reply(call["raw_response"] or "")
        except ModelFailure:
            reserved += call["max_tokens"]
            continue
        known += reply.completion_tokens
        try:
            turn = TURN_ADAPTER.validate_json(reply.content)
        except ValidationError:
            if (
                reply.finish_reason == "stop"
                and reply.completion_tokens <= call["max_tokens"]
                and reply.prompt_tokens + reply.completion_tokens <= budgets.context_tokens
            ):
                repairs += 1
            continue
        if isinstance(turn, ActionTurn):
            actions[f"step-{call['step']}:call-0"] = turn.action.model_dump(mode="json")
        elif isinstance(turn, FinalTurn):
            # A saved disclosure is observable even if the process died before
            # its final runtime checkpoint. Keep it available to the grader.
            final = turn.text
    if saved is None:
        script = task.attacked_script if scheduled["attacked"] else task.clean_script
        actions = {
            f"step-{index}:call-0": action.model_dump(mode="json")
            for index, action in enumerate(script.actions)
        }
    trace = []
    for key, action in actions.items():
        if key not in executions:
            continue
        entry = {"action": action, "execution": executions[key]}
        for review in reviews:
            if review["execution_key"] == key and key in decisions:
                entry["simulated_review"] = {
                    "approved": review["status"] == "APPROVED",
                    "initial_decision": decisions[key],
                }
        trace.append(entry)
    return {
        "status": "FAILED",
        "reason": "BENCHMARK_INTERRUPTED",
        "final_response": final,
        "trace": trace,
        "model_calls": len(calls),
        "generated_tokens": known,
        "reserved_generated_tokens": reserved,
        "charged_generated_tokens": known + reserved,
        "schema_repairs": min(repairs, budgets.schema_repair_attempts),
        "elapsed_seconds": None,
    }


def start_session(store: Store, completed: int) -> int:
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE benchmark_sessions SET outcome='INTERRUPTED' WHERE ended_at IS NULL")
        cursor = db.execute(
            "INSERT INTO benchmark_sessions(started_at,outcome,initial_recorded) "
            "VALUES (?,'RUNNING',?)",
            (time.time(), completed),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid


def end_session(store: Store, session: int, completed: int, outcome: str) -> None:
    with store.connection() as db:
        db.execute(
            "UPDATE benchmark_sessions SET ended_at=?,outcome=?,final_recorded=? WHERE id=?",
            (time.time(), outcome, completed, session),
        )
