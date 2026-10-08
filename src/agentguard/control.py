"""Owner-scoped control-plane operations; no model-supplied authority or raw traces."""

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Literal, cast

from pydantic import Field, StrictBool

from agentguard.contracts import Contract, Identifier, TaskContract, digest
from agentguard.model import ModelFailure, parse_reply
from agentguard.runtime import TURN_ADAPTER, ActionTurn, Budgets
from agentguard.scenarios import DevelopmentTask
from agentguard.storage import Store
from agentguard.worker import Queue

PUBLIC_REASONS = frozenset(
    {
        "FINAL_RESPONSE",
        "SENSITIVE_WRITE",
        "CANCELLED",
        "EPISODE_TIMEOUT",
        "TOKEN_BUDGET",
        "CONTEXT_BUDGET",
        "STEP_BUDGET",
        "TOOL_BUDGET",
        "TOOL_RESULT_LIMIT",
        "OUTPUT_TOKEN_LIMIT",
        "MODEL_UNAVAILABLE",
        "MODEL_TIMEOUT",
        "MODEL_TRANSPORT_FAILED",
        "INVALID_MODEL_RESPONSE",
        "MODEL_RESPONSE_LOST",
        "RECOVERY_INPUT_MISMATCH",
        "MODEL_BUDGET_VIOLATION",
        "MODEL_FINISH_REASON",
        "INVALID_PROPOSAL",
        "REVIEW_INVALID",
        "TOOL_TIMEOUT",
        "EFFECT_MISMATCH",
    }
)


class Principal(Contract):
    subject: Identifier
    actor: Identifier
    workspace: Identifier
    role: Literal["operator", "observer"] = "operator"


class SubmitRun(Contract):
    scenario_id: Identifier


class ReviewAction(Contract):
    expected_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{20,128}$")
    approve: StrictBool


@dataclass
class ControlError(Exception):
    status: int
    code: str


class ControlPlane:
    def __init__(
        self,
        store: Store,
        tasks: dict[str, DevelopmentTask],
        *,
        manifest: str,
        budgets: Budgets,
        mode: str,
    ):
        self.store, self.tasks = store, tasks
        self.manifest, self.budgets, self.mode = manifest, budgets, mode

    @staticmethod
    def operator(principal: Principal) -> None:
        if principal.role != "operator":
            raise ControlError(403, "OPERATOR_REQUIRED")

    def _owned(self, db: sqlite3.Connection, principal: Principal, episode: str) -> sqlite3.Row:
        row = db.execute(
            "SELECT s.*,j.status,j.task,j.started_at,j.deadline,j.generation,j.manifest "
            "FROM api_submissions s JOIN jobs j ON j.episode_id=s.episode_id "
            "WHERE s.episode_id=? AND s.owner=? AND s.actor=? AND s.workspace=?",
            (episode, principal.subject, principal.actor, principal.workspace),
        ).fetchone()
        if row is None:
            raise ControlError(404, "RUN_NOT_FOUND")
        return cast(sqlite3.Row, row)

    def scenarios(self, principal: Principal) -> list[dict[str, Any]]:
        return [
            {"id": task.id, "task": task.task, "scope": task.contract.model_dump()}
            for task in self.tasks.values()
            if (task.contract.actor, task.contract.workspace)
            == (principal.actor, principal.workspace)
        ]

    def submit(self, principal: Principal, request: SubmitRun, key: str) -> str:
        self.operator(principal)
        task = self.tasks.get(request.scenario_id)
        if task is None or (task.contract.actor, task.contract.workspace) != (
            principal.actor,
            principal.workspace,
        ):
            raise ControlError(404, "SCENARIO_NOT_FOUND")
        request_hash = digest(
            {
                "scenario": task.model_dump(mode="json"),
                "manifest": self.manifest,
                "budgets": self.budgets.model_dump(mode="json"),
                "actor": principal.actor,
                "workspace": principal.workspace,
            }
        )
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT * FROM api_submissions WHERE owner=? AND idempotency_key=?",
                (principal.subject, key),
            ).fetchone()
            if previous is not None:
                if previous["request_hash"] != request_hash:
                    raise ControlError(409, "IDEMPOTENCY_CONFLICT")
                return str(previous["episode_id"])
            pending = db.execute(
                "SELECT count(*) FROM api_submissions s JOIN jobs j ON j.episode_id=s.episode_id "
                "WHERE s.owner=? AND j.status IN ('QUEUED','RUNNING','WAITING_APPROVAL')",
                (principal.subject,),
            ).fetchone()[0]
            if pending >= 32:
                raise ControlError(429, "PENDING_RUN_LIMIT")
            episode = self.store._create_episode(
                db,
                task.contract,
                task.documents,
                task.projects,
                tickets=task.initial_tickets,
                max_actions=self.budgets.max_steps,
            )
            Queue(self.store)._submit(db, episode, task.task, self.budgets, manifest=self.manifest)
            db.execute(
                "INSERT INTO api_submissions VALUES (?,?,?,?,?,?,?,?)",
                (
                    episode,
                    principal.subject,
                    principal.actor,
                    principal.workspace,
                    key,
                    request_hash,
                    task.id,
                    self.store.clock(),
                ),
            )
            self.store._audit(db, episode, None, "RUN_SUBMITTED", {"operator": principal.subject})
            return episode

    def runs(self, principal: Principal, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.store.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT s.episode_id,s.scenario_id,s.created_at,j.status "
                    "FROM api_submissions s "
                    "JOIN jobs j ON j.episode_id=s.episode_id "
                    "WHERE s.owner=? AND s.actor=? AND s.workspace=? ORDER BY s.rowid DESC LIMIT ?",
                    (principal.subject, principal.actor, principal.workspace, limit),
                )
            ]

    def detail(self, principal: Principal, episode: str) -> dict[str, Any]:
        with self.store.connection() as db:
            row = self._owned(db, principal, episode)
            run = db.execute(
                "SELECT result FROM agent_runs WHERE episode_id=?", (episode,)
            ).fetchone()
            result = json.loads(run["result"]) if run and run["result"] else {}
            if "reason" in result and result["reason"] not in PUBLIC_REASONS:
                result["reason"] = "FAILURE_REDACTED"
            return {
                "episode_id": episode,
                "scenario_id": row["scenario_id"],
                "task": row["task"],
                "status": row["status"],
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "deadline": row["deadline"],
                "claims": row["generation"],
                "mode": json.loads(row["manifest"])["model"].get("mode", "unknown"),
                "profile": "defended",
                "content_redacted": True,
                "result": {
                    key: result[key]
                    for key in (
                        "reason",
                        "model_calls",
                        "generated_tokens",
                        "reserved_generated_tokens",
                        "charged_generated_tokens",
                        "schema_repairs",
                        "elapsed_seconds",
                    )
                    if key in result
                },
            }

    def timeline(self, principal: Principal, episode: str) -> list[dict[str, Any]]:
        with self.store.connection() as db:
            self._owned(db, principal, episode)
            records = db.execute(
                "SELECT step,raw_response,error,elapsed_seconds FROM model_calls "
                "WHERE episode_id=? ORDER BY step LIMIT 64",
                (episode,),
            ).fetchall()
            contract = TaskContract.model_validate_json(
                db.execute("SELECT contract FROM episodes WHERE id=?", (episode,)).fetchone()[0]
            )
            entries = []
            for record in records:
                entry: dict[str, Any] = {
                    "step": record["step"],
                    "elapsed_seconds": record["elapsed_seconds"],
                    "state": "RESPONSE_SAVED" if record["raw_response"] else "RESPONSE_PENDING",
                    "content_redacted": True,
                }
                if record["error"]:
                    entry["state"] = "MODEL_FAILED"  # Do not reflect arbitrary server errors.
                if record["raw_response"]:
                    try:
                        turn = TURN_ADAPTER.validate_json(
                            parse_reply(record["raw_response"]).content
                        )
                        entry["kind"] = turn.kind
                        if isinstance(turn, ActionTurn):
                            entry["tool"] = turn.action.tool
                            arguments = turn.action.arguments.model_dump()
                            target = arguments.get("document_id", arguments.get("project_id"))
                            entry["target"] = (
                                "permitted documents"
                                if turn.action.tool == "documents.search"
                                else target
                                if target in (*contract.document_ids, *contract.project_ids)
                                else "[outside task scope]"
                            )
                    except (ValueError, ModelFailure):
                        entry["state"] = "INVALID_RESPONSE"
                execution = db.execute(
                    "SELECT output FROM executions WHERE episode_id=? AND execution_key=?",
                    (episode, f"step-{record['step']}:call-0"),
                ).fetchone()
                if execution and execution["output"]:
                    output = json.loads(execution["output"])
                    entry["decision"] = {
                        key: output["decision"][key] for key in ("outcome", "reason")
                    }
                elif execution:
                    approval = db.execute(
                        "SELECT status FROM approvals WHERE episode_id=? AND execution_key=? "
                        "ORDER BY rowid DESC LIMIT 1",
                        (episode, f"step-{record['step']}:call-0"),
                    ).fetchone()
                    if approval is not None:
                        entry["decision"] = {
                            "outcome": "REQUIRE_APPROVAL",
                            "reason": "SENSITIVE_WRITE",
                        }
                        entry["approval_status"] = approval["status"]
                if entry.get("kind") == "final":
                    response = db.execute(
                        "SELECT result FROM agent_runs WHERE episode_id=?", (episode,)
                    ).fetchone()
                    result = (
                        json.loads(response["result"]) if response and response["result"] else {}
                    )
                    decision = result.get("response_decision")
                    if decision is not None:
                        entry["decision"] = {key: decision[key] for key in ("outcome", "reason")}
                entries.append(entry)
            return entries

    def approvals(self, principal: Principal, episode: str) -> list[dict[str, Any]]:
        with self.store.connection() as db:
            self._owned(db, principal, episode)
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id,status,expires_at,consumed FROM approvals WHERE episode_id=? "
                    "ORDER BY rowid LIMIT 64",
                    (episode,),
                )
            ]

    def approval(self, principal: Principal, episode: str, request_id: str) -> dict[str, Any]:
        self.operator(principal)
        with self.store.connection() as db:
            run = self._owned(db, principal, episode)
            row = db.execute(
                "SELECT * FROM approvals WHERE episode_id=? AND id=?", (episode, request_id)
            ).fetchone()
            if row is None:
                raise ControlError(404, "APPROVAL_NOT_FOUND")
            snapshot = json.loads(row["snapshot"])
            return {
                "id": row["id"],
                "episode_id": episode,
                "task": run["task"],
                "execution_key": row["execution_key"],
                "action_hash": row["action_hash"],
                "nonce": row["nonce"],
                "expires_at": row["expires_at"],
                "status": row["status"],
                "consumed": bool(row["consumed"]),
                "snapshot": snapshot,
            }

    def review(
        self, principal: Principal, episode: str, request_id: str, request: ReviewAction
    ) -> None:
        self.approval(
            principal, episode, request_id
        )  # Ownership cannot be changed by any endpoint.
        self.store.review(
            request_id,
            expected_hash=request.expected_hash,
            nonce=request.nonce,
            reviewer=principal.subject,
            approve=request.approve,
        )

    def cancel(self, principal: Principal, episode: str) -> str:
        self.operator(principal)
        with self.store.connection() as db:
            self._owned(db, principal, episode)
        self.store.cancel(episode)
        return str(self.detail(principal, episode)["status"])
