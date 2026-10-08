"""Portable, credential-free state regrading for synthetic benchmark evidence."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentguard import benchmark
from agentguard.analysis import checked_report, observations
from agentguard.contracts import Execution, Identifier, Ticket
from agentguard.live import atomic_json
from agentguard.scenarios import GRADER_VERSION, DevelopmentTask, grade_episode
from agentguard.storage import Store

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ExecutionState(StateModel):
    proposal_hash: Sha256
    output: Execution | None


class ShareState(StateModel):
    id: Identifier
    document_id: Identifier
    project_id: Identifier
    document_version: int = Field(ge=1)
    body: str


class EpisodeState(StateModel):
    episode_id: str = Field(min_length=1)
    tickets: tuple[Ticket, ...]
    shares: tuple[ShareState, ...]
    executions: tuple[ExecutionState, ...]


class GradingState(StateModel):
    version: Literal["portable-grading-state-v1"]
    original_checksums_sha256: Sha256
    original_database_sha256: Sha256
    episodes: tuple[EpisodeState, ...]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_grader(root: Path, report: dict[str, Any]) -> None:
    source = json.loads((root / "source.json").read_text())
    if report["manifest"]["grader_version"] != GRADER_VERSION:
        raise ValueError("Regrading requires the original grader version")
    # Do not execute Python from an evidence bundle. Require the installed grader,
    # its contracts, and state reader to match the source captured before inference.
    for name in ("scenarios.py", "contracts.py", "storage.py"):
        if source.get(name) != (Path(__file__).parent / name).read_text():
            raise ValueError(f"Regrading requires the frozen source for {name}")


def _regrade(root: Path, report: dict[str, Any], state: GradingState) -> dict[str, Any]:
    observations(report)  # Reject missing results, duplicate identities, and altered denominators.
    _check_grader(root, report)
    rows = report["episodes"]
    if [episode.episode_id for episode in state.episodes] != [row["episode_id"] for row in rows]:
        raise ValueError("Grading state does not match the complete scheduled results")
    tasks = {
        fixture["id"]: DevelopmentTask.model_validate_json((root / fixture["file"]).read_bytes())
        for fixture in report["manifest"]["fixtures"]
    }
    with tempfile.TemporaryDirectory(prefix="agentguard-regrade-") as temporary:
        store = Store(Path(temporary) / "state.sqlite3")
        with store.connection() as db:
            for row, episode in zip(rows, state.episodes, strict=True):
                task = tasks[row["task_id"]]
                db.execute(
                    "INSERT INTO episodes(id,contract,profile,max_actions) VALUES (?,?,?,?)",
                    (episode.episode_id, task.contract.model_dump_json(), row["profile"], 8),
                )
                for ticket in episode.tickets:
                    db.execute(
                        "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?)",
                        (
                            ticket.id,
                            episode.episode_id,
                            ticket.project_id,
                            ticket.title,
                            ticket.body,
                            ticket.workspace,
                            ticket.version,
                            ticket.classification,
                        ),
                    )
                for share in episode.shares:
                    db.execute(
                        "INSERT INTO simulated_shares VALUES (?,?,?,?,?,?)",
                        (
                            share.id,
                            episode.episode_id,
                            share.document_id,
                            share.project_id,
                            share.document_version,
                            share.body,
                        ),
                    )
                for index, execution in enumerate(episode.executions):
                    if execution.output is not None and execution.output.approval_id is not None:
                        raise ValueError("Portable grading state must omit approval references")
                    db.execute(
                        "INSERT INTO executions VALUES (?,?,?,?)",
                        (
                            episode.episode_id,
                            str(index),
                            execution.proposal_hash,
                            execution.output.model_dump_json() if execution.output else None,
                        ),
                    )
        for row in rows:
            grade = grade_episode(
                store,
                row["episode_id"],
                row["final_response"],
                tasks[row["task_id"]].expectation,
                attacked=row["attacked"],
            )
            expected = grade | {
                "state_task_success": grade["task_success"],
                "task_success": grade["task_success"] and row["status"] == "COMPLETED",
            }
            if expected != row["grade"]:
                raise ValueError(f"Saved grade differs from committed state: {row['episode_id']}")
    return {
        "version": "portable-regrade-v1",
        "verified_episodes": len(rows),
        "mode": report["manifest"]["mode"],
        "grader_version": GRADER_VERSION,
        "all_grades_match": True,
        "release_gate_recomputed": False,
        "limits": [
            "Checksums detect inconsistency, not forgery by the evidence publisher.",
            "Regrades synthetic effects and tool results; does not rerun inference or containment.",
            "This state projection cannot verify approval lifecycle, leases, or the release gate.",
            "Published model requests and tool content remain privileged synthetic data.",
        ],
    }


def export_evidence(root: Path, output: Path) -> Path:
    """Validate the original snapshot and publish only fields consumed by the grader."""
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Export evidence outside the immutable input directory")
    if output.exists():
        raise FileExistsError(output)
    wal = root / "evidence.sqlite3-wal"
    if wal.exists() and wal.stat().st_size:
        raise ValueError("Original database snapshot has pending WAL data")
    report, checksums = checked_report(root)
    if "evidence.sqlite3" not in checksums:
        raise ValueError("Export requires the checksummed original database snapshot")
    observations(report)
    _check_grader(root, report)
    if any(
        Path(name).suffix not in (".json", ".md") and name != "evidence.sqlite3"
        for name in checksums
    ):
        raise ValueError("Unexpected file in benchmark evidence")
    if {"grading-state.json", "original-run-checksums.json"} & checksums.keys():
        raise ValueError("Export requires original evidence, not an existing portable export")
    episodes = []
    with tempfile.TemporaryDirectory(prefix="agentguard-export-") as temporary:
        snapshot = Path(temporary) / "state.sqlite3"
        shutil.copyfile(root / "evidence.sqlite3", snapshot)
        store = Store(snapshot)
        if benchmark.recorded(store, report["manifest"]) != report["episodes"]:
            raise ValueError("Saved results disagree with the original database journal")
        with store.connection() as db:
            if [dict(row) for row in db.execute("SELECT * FROM model_calls")] != json.loads(
                (root / "model-calls.json").read_text()
            ):
                raise ValueError("Saved model calls disagree with the original database journal")
            for row in report["episodes"]:
                episode_id = row["episode_id"]
                executions = []
                for record in db.execute(
                    "SELECT proposal_hash,output FROM executions WHERE episode_id=? ORDER BY rowid",
                    (episode_id,),
                ):
                    execution = (
                        Execution.model_validate_json(record["output"])
                        if record["output"] is not None
                        else None
                    )
                    executions.append(
                        ExecutionState(
                            proposal_hash=record["proposal_hash"],
                            output=execution.model_copy(update={"approval_id": None})
                            if execution
                            else None,
                        )
                    )
                episodes.append(
                    EpisodeState(
                        episode_id=episode_id,
                        tickets=tuple(
                            Ticket.model_validate(
                                {k: v for k, v in ticket.items() if k != "episode_id"}
                            )
                            for ticket in store.tickets(episode_id)
                        ),
                        shares=tuple(
                            ShareState.model_validate(
                                {k: v for k, v in share.items() if k != "episode_id"}
                            )
                            for share in store.shares(episode_id)
                        ),
                        executions=tuple(executions),
                    )
                )
    state = GradingState(
        version="portable-grading-state-v1",
        original_checksums_sha256=_sha(root / "checksums.json"),
        original_database_sha256=checksums["evidence.sqlite3"],
        episodes=tuple(episodes),
    )
    _regrade(root, report, state)  # Verify before creating a publishable directory.
    output.mkdir(parents=True, exist_ok=False)
    for name in checksums:
        if name == "evidence.sqlite3":
            continue
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, destination)
    shutil.copyfile(root / "checksums.json", output / "original-run-checksums.json")
    atomic_json(output / "grading-state.json", state.model_dump(mode="json"))
    atomic_json(
        output / "checksums.json",
        {
            path.relative_to(output).as_posix(): _sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
    )
    return output


def verify_evidence(root: Path) -> dict[str, Any]:
    """Recheck all published grades offline; never connect to a model or run a tool."""
    report, checksums = checked_report(root)
    if not {"grading-state.json", "original-run-checksums.json"} <= checksums.keys():
        raise ValueError("Missing portable grading state or original checksums")
    state = GradingState.model_validate_json((root / "grading-state.json").read_bytes())
    if _sha(root / "original-run-checksums.json") != state.original_checksums_sha256:
        raise ValueError("Original checksum provenance changed")
    original = json.loads((root / "original-run-checksums.json").read_text())
    if original.get("evidence.sqlite3") != state.original_database_sha256 or any(
        checksums.get(name) != expected
        for name, expected in original.items()
        if name != "evidence.sqlite3"
    ):
        raise ValueError("Published evidence differs from the original snapshot")
    return _regrade(root, report, state)
