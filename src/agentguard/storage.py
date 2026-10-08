"""Single-node effect kernel. Policy, approval consumption, effect and audit commit together.

This is a trusted library boundary. The model must only receive the Action schema;
HTTP callers must go through the authenticated control plane before review().
"""

import json
import secrets
import sqlite3
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from agentguard.computation import (
    Computer,
    DocumentResult,
    InProcessComputer,
    ListResult,
    SearchResult,
    ShareEffect,
    TicketEffect,
    ToolRequest,
    ToolResult,
    UpdateEffect,
    validate_result,
)
from agentguard.contracts import (
    ACTION_ADAPTER,
    Action,
    CreateAction,
    Document,
    Execution,
    ListAction,
    Profile,
    Project,
    ReadAction,
    SearchAction,
    ShareAction,
    TaskContract,
    Ticket,
    UpdateAction,
    canonical_json,
    digest,
)
from agentguard.response_policy import ResponseDecision, evaluate_response
from agentguard.response_receipts import verified_receipt_hash
from agentguard.tool_state import resolve

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    contract TEXT NOT NULL,
    profile TEXT NOT NULL CHECK(profile IN ('baseline','prompt_only','defended')),
    confidential INTEGER NOT NULL DEFAULT 0,
    cancelled INTEGER NOT NULL DEFAULT 0,
    max_actions INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS resources (
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    kind TEXT NOT NULL,
    id TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (episode_id, kind, id)
);
CREATE TABLE IF NOT EXISTS executions (
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    execution_key TEXT NOT NULL,
    proposal_hash TEXT NOT NULL,
    output TEXT,
    PRIMARY KEY (episode_id, execution_key)
);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    execution_key TEXT NOT NULL,
    action_hash TEXT NOT NULL,
    nonce TEXT NOT NULL,
    snapshot TEXT NOT NULL,
    expires_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    reviewer TEXT,
    consumed INTEGER NOT NULL DEFAULT 0,
    UNIQUE (episode_id, execution_key, action_hash)
);
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT NOT NULL,
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    workspace TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    classification TEXT NOT NULL DEFAULT 'internal',
    PRIMARY KEY (episode_id, id)
);
CREATE TABLE IF NOT EXISTS simulated_shares (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    document_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    document_version INTEGER NOT NULL,
    body TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    episode_id UNINDEXED, document_id UNINDEXED, body
);
CREATE TRIGGER IF NOT EXISTS document_insert AFTER INSERT ON resources
WHEN new.kind='document' BEGIN
    INSERT INTO documents_fts(rowid,episode_id,document_id,body)
    VALUES(new.rowid,new.episode_id,new.id,json_extract(new.payload,'$.body'));
END;
CREATE TRIGGER IF NOT EXISTS document_delete AFTER DELETE ON resources
WHEN old.kind='document' BEGIN
    DELETE FROM documents_fts WHERE rowid=old.rowid;
END;
CREATE TRIGGER IF NOT EXISTS document_update AFTER UPDATE ON resources
WHEN old.kind='document' OR new.kind='document' BEGIN
    DELETE FROM documents_fts WHERE rowid=old.rowid;
    INSERT INTO documents_fts(rowid,episode_id,document_id,body)
    SELECT new.rowid,new.episode_id,new.id,json_extract(new.payload,'$.body')
    WHERE new.kind='document';
END;
CREATE TABLE IF NOT EXISTS audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    execution_key TEXT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_runs (
    episode_id TEXT PRIMARY KEY REFERENCES episodes(id),
    status TEXT NOT NULL,
    task TEXT NOT NULL,
    budgets TEXT NOT NULL,
    initial_messages TEXT NOT NULL,
    result TEXT
);
CREATE TABLE IF NOT EXISTS model_calls (
    episode_id TEXT NOT NULL REFERENCES agent_runs(episode_id),
    step INTEGER NOT NULL,
    request TEXT NOT NULL,
    max_tokens INTEGER NOT NULL,
    raw_response TEXT,
    elapsed_seconds REAL,
    error TEXT,
    PRIMARY KEY (episode_id, step)
);
CREATE TABLE IF NOT EXISTS jobs (
    episode_id TEXT PRIMARY KEY REFERENCES episodes(id),
    status TEXT NOT NULL CHECK(status IN
        ('QUEUED','RUNNING','WAITING_APPROVAL','COMPLETED','FAILED','CANCELLED','BUDGET_EXHAUSTED')),
    task TEXT NOT NULL,
    budgets TEXT NOT NULL,
    manifest TEXT NOT NULL,
    token TEXT,
    generation INTEGER NOT NULL DEFAULT 0,
    lease_until REAL,
    started_at REAL,
    deadline REAL,
    waiting_approval_id TEXT REFERENCES approvals(id)
);
CREATE TABLE IF NOT EXISTS api_submissions (
    episode_id TEXT PRIMARY KEY REFERENCES jobs(episode_id),
    owner TEXT NOT NULL,
    actor TEXT NOT NULL,
    workspace TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    scenario_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE(owner, idempotency_key)
);
PRAGMA user_version = 5;
"""


class ExecutionConflict(ValueError):
    """An execution key was reused for a different proposal."""


class ReviewRejected(ValueError):
    """An operator decision no longer matches the pending request."""


class LeaseLost(RuntimeError):
    """A missing, expired, or superseded worker cannot checkpoint or execute."""


@dataclass(frozen=True)
class Lease:
    episode_id: str
    token: str
    generation: int


@dataclass(frozen=True)
class Prepared:
    request: ToolRequest
    action_hash: str


@dataclass(frozen=True)
class Computed:
    prepared: Prepared
    result: ToolResult


class Store:
    def __init__(
        self,
        path: Path,
        clock: Callable[[], float] = time.time,
        *,
        computer: Computer | None = None,
    ):
        self.path = path
        self.clock = clock
        self.computer = computer if computer is not None else InProcessComputer()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3, 4, 5):
                raise ValueError(f"Unsupported database schema: {version}")
            # Migrate the old global ticket primary key to episode-local resource IDs.
            columns = {r["name"] for r in db.execute("PRAGMA table_info(tickets)")}
            migration = ""
            if columns and "version" not in columns:
                migration = "ALTER TABLE tickets RENAME TO legacy_tickets;\n"
            # executescript implicitly commits an existing transaction. Execute complete
            # statements ourselves so discovery, migration, and backfill hold one lock.
            statement = ""
            for line in (migration + SCHEMA).splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    db.execute(statement)
                    statement = ""
            if migration:
                db.execute(
                    "INSERT INTO tickets(id,episode_id,project_id,title,body,workspace,"
                    "classification) "
                    "SELECT t.id,t.episode_id,t.project_id,t.title,t.body,"
                    "json_extract(e.contract,'$.workspace'),CASE WHEN e.confidential=1 "
                    "THEN 'confidential' ELSE 'internal' END FROM legacy_tickets t "
                    "JOIN episodes e ON e.id=t.episode_id"
                )
                db.execute("DROP TABLE legacy_tickets")
            if version < 5:
                db.execute("DELETE FROM documents_fts")
                db.execute(
                    "INSERT INTO documents_fts(rowid,episode_id,document_id,body) "
                    "SELECT rowid,episode_id,id,json_extract(payload,'$.body') "
                    "FROM resources WHERE kind='document'"
                )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_episode(
        self,
        contract: TaskContract,
        documents: tuple[Document, ...],
        projects: tuple[Project, ...],
        *,
        tickets: tuple[Ticket, ...] = (),
        experimental_profile: Profile = "defended",
        max_actions: int = 8,
    ) -> str:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._create_episode(
                db,
                contract,
                documents,
                projects,
                tickets=tickets,
                experimental_profile=experimental_profile,
                max_actions=max_actions,
            )

    def _create_episode(
        self,
        db: sqlite3.Connection,
        contract: TaskContract,
        documents: tuple[Document, ...],
        projects: tuple[Project, ...],
        *,
        tickets: tuple[Ticket, ...] = (),
        experimental_profile: Profile = "defended",
        max_actions: int = 8,
    ) -> str:
        """Compose fixture creation with trusted control-plane submission atomically."""
        if experimental_profile not in ("baseline", "prompt_only", "defended"):
            raise ValueError("Unknown policy profile")
        if not 1 <= max_actions <= 64:
            raise ValueError("max_actions must be between 1 and 64")
        episode_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO episodes(id,contract,profile,max_actions) VALUES (?,?,?,?)",
            (episode_id, contract.model_dump_json(), experimental_profile, max_actions),
        )
        resources: tuple[Document | Project, ...] = (*documents, *projects)
        for resource in resources:
            if resource.workspace != contract.workspace:
                raise ValueError("Fixtures must belong to the episode workspace")
            db.execute(
                "INSERT INTO resources VALUES (?,?,?,?)",
                (
                    episode_id,
                    "document" if isinstance(resource, Document) else "project",
                    resource.id,
                    resource.model_dump_json(),
                ),
            )
        for ticket in tickets:
            if ticket.workspace != contract.workspace or ticket.project_id not in {
                p.id for p in projects
            }:
                raise ValueError("Ticket fixture exceeds episode resources")
            db.execute(
                "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?)",
                (
                    ticket.id,
                    episode_id,
                    ticket.project_id,
                    ticket.title,
                    ticket.body,
                    ticket.workspace,
                    ticket.version,
                    ticket.classification,
                ),
            )
        return episode_id

    @staticmethod
    def _audit(
        db: sqlite3.Connection, episode_id: str, key: str | None, kind: str, payload: object
    ) -> None:
        db.execute(
            "INSERT INTO audit_events(episode_id,execution_key,kind,payload) VALUES (?,?,?,?)",
            (episode_id, key, kind, canonical_json(payload)),
        )

    def authorize_response(
        self, db: sqlite3.Connection, episode_id: str, *, lease: Lease | None = None
    ) -> ResponseDecision:
        """Caller holds its fenced write transaction through final-result persistence."""
        if not db.in_transaction:
            raise ValueError("Response authorization requires a write transaction")
        self.require_lease(db, episode_id, lease)
        row = db.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown episode")
        contract = TaskContract.model_validate_json(row["contract"])
        receipt_hash = (
            verified_receipt_hash(db, episode_id, contract, confidential=bool(row["confidential"]))
            if row["profile"] == "defended" and not row["cancelled"]
            else None
        )
        decision = evaluate_response(
            episode_id=episode_id,
            contract=contract,
            profile=row["profile"],
            confidential=bool(row["confidential"]),
            cancelled=bool(row["cancelled"]),
            receipt_evidence_hash=receipt_hash,
        )
        self._audit(db, episode_id, None, "RESPONSE_DECISION", decision.model_dump(mode="json"))
        return decision

    def execute(
        self,
        episode_id: str,
        key: str,
        action: Action,
        *,
        approval_id: str | None = None,
        deadline: float | None = None,
        deadline_clock: Callable[[], float] = time.monotonic,
        lease: Lease | None = None,
    ) -> Execution:
        """Authorize, compute outside the DB lock, then recheck before applying effects.

        An approval ID is supplied by the trusted caller after review, never inside
        an untrusted Action. A committed key always returns its original result.
        """
        prepared = self._execute(
            episode_id,
            key,
            action,
            approval_id=approval_id,
            deadline=deadline,
            deadline_clock=deadline_clock,
            lease=lease,
        )
        if isinstance(prepared, Execution):
            return prepared
        result = self.computer.compute(prepared.request)
        validate_result(prepared.request, result)
        output = self._execute(
            episode_id,
            key,
            action,
            approval_id=approval_id,
            computed=Computed(prepared=prepared, result=result),
            deadline=deadline,
            deadline_clock=deadline_clock,
            lease=lease,
        )
        assert isinstance(output, Execution)
        return output

    def _execute(
        self,
        episode_id: str,
        key: str,
        action: Action,
        *,
        approval_id: str | None = None,
        computed: Computed | None = None,
        deadline: float | None = None,
        deadline_clock: Callable[[], float] = time.monotonic,
        lease: Lease | None = None,
    ) -> Execution | Prepared:
        if not key or len(key) > 160:
            raise ValueError("Invalid execution key")
        proposal_hash = digest(action.model_dump(mode="json"))
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            job = self.require_lease(db, episode_id, lease)
            episode = db.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
            if episode is None:
                raise KeyError("Unknown episode")
            previous = db.execute(
                "SELECT * FROM executions WHERE episode_id=? AND execution_key=?", (episode_id, key)
            ).fetchone()
            if previous:
                if previous["proposal_hash"] != proposal_hash:
                    raise ExecutionConflict("Execution key already binds a different action")
                if previous["output"] is not None:
                    return Execution.model_validate_json(previous["output"])

            contract = TaskContract.model_validate_json(episode["contract"])
            state = resolve(db, episode_id, contract, episode["profile"], action)
            resource = state.resource
            decision = state.decision(
                episode_id=episode_id,
                contract=contract,
                profile=episode["profile"],
                action=action,
                confidential=bool(episode["confidential"]),
            )
            count = db.execute(
                "SELECT count(*) FROM executions WHERE episode_id=?", (episode_id,)
            ).fetchone()[0]
            if (
                episode["cancelled"]
                or (previous is None and count >= episode["max_actions"])
                or (deadline is not None and deadline_clock() >= deadline)
                or (job is not None and self.clock() >= job["deadline"])
            ):
                reason = "CANCELLED" if episode["cancelled"] else "BUDGET_EXHAUSTED"
                return Execution(
                    decision=decision.model_copy(update={"outcome": "DENY", "reason": reason})
                )
            if previous is None:
                db.execute(
                    "INSERT INTO executions VALUES (?,?,?,NULL)", (episode_id, key, proposal_hash)
                )

            grant = None
            if approval_id is not None:
                grant = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
                valid = (
                    grant is not None
                    and grant["episode_id"] == episode_id
                    and grant["execution_key"] == key
                    and grant["action_hash"] == decision.action_hash
                    and grant["status"] == "APPROVED"
                    and not grant["consumed"]
                    and grant["expires_at"] > self.clock()
                )
                if not valid:
                    decision = decision.model_copy(
                        update={"outcome": "DENY", "reason": "APPROVAL_INVALID"}
                    )

            if computed is not None and computed.prepared.action_hash != decision.action_hash:
                decision = decision.model_copy(
                    update={"outcome": "DENY", "reason": "STATE_CHANGED"}
                )

            if decision.outcome == "REQUIRE_APPROVAL":
                if grant is not None and approval_id is not None:
                    decision = decision.model_copy(
                        update={"outcome": "ALLOW", "reason": "APPROVED"}
                    )
                else:
                    request = db.execute(
                        "SELECT * FROM approvals WHERE episode_id=? "
                        "AND execution_key=? AND action_hash=?",
                        (episode_id, key, decision.action_hash),
                    ).fetchone()
                    if request is None:
                        request_id = secrets.token_urlsafe(24)
                        db.execute(
                            "INSERT INTO approvals(id,episode_id,execution_key,action_hash,"
                            "nonce,snapshot,expires_at) "
                            "VALUES (?,?,?,?,?,?,?)",
                            (
                                request_id,
                                episode_id,
                                key,
                                decision.action_hash,
                                secrets.token_urlsafe(24),
                                canonical_json(
                                    {
                                        "action": action.model_dump(mode="json"),
                                        "contract": contract.model_dump(mode="json"),
                                        "resource": resource.model_dump(mode="json")
                                        if resource
                                        else None,
                                        "ticket": state.ticket.model_dump(mode="json")
                                        if state.ticket
                                        else None,
                                        "source": state.source.model_dump(mode="json")
                                        if state.source
                                        else None,
                                        "policy_version": decision.policy_version,
                                        "confidential": bool(episode["confidential"]),
                                    }
                                ),
                                self.clock() + 300,
                            ),
                        )
                        self._audit(
                            db, episode_id, key, "APPROVAL_REQUESTED", decision.model_dump()
                        )
                    else:
                        request_id = request["id"]
                    if request is not None and (
                        request["status"] == "REJECTED" or request["expires_at"] <= self.clock()
                    ):
                        decision = decision.model_copy(
                            update={"outcome": "DENY", "reason": "APPROVAL_CLOSED"}
                        )
                    else:
                        return Execution(decision=decision, approval_id=request_id)

            result: dict[str, str] = {}
            if decision.outcome == "ALLOW":
                if computed is None:
                    return Prepared(
                        request=state.request(action),
                        action_hash=decision.action_hash,
                    )
                validate_result(computed.prepared.request, computed.result)
                if isinstance(action, ReadAction):
                    assert isinstance(resource, Document)
                    assert isinstance(computed.result, DocumentResult)
                    result = {
                        "document_id": computed.result.document_id,
                        "body": computed.result.body,
                    }
                    if resource.classification == "confidential":
                        db.execute("UPDATE episodes SET confidential=1 WHERE id=?", (episode_id,))
                elif isinstance(action, CreateAction):
                    assert isinstance(computed.result, TicketEffect)
                    ticket_id = str(uuid.uuid4())
                    db.execute(
                        "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?)",
                        (
                            ticket_id,
                            episode_id,
                            computed.result.arguments.project_id,
                            computed.result.arguments.title,
                            computed.result.arguments.body,
                            contract.workspace,
                            1,
                            "confidential" if episode["confidential"] else "internal",
                        ),
                    )
                    result = {"ticket_id": ticket_id}
                elif isinstance(action, SearchAction):
                    assert isinstance(computed.result, SearchResult)
                    result = {
                        "documents": canonical_json(
                            [hit.model_dump() for hit in computed.result.documents]
                        )
                    }
                elif isinstance(action, ListAction):
                    assert isinstance(computed.result, ListResult)
                    result = {
                        "tickets": canonical_json(
                            [ticket.model_dump() for ticket in computed.result.tickets]
                        )
                    }
                elif isinstance(action, UpdateAction):
                    assert isinstance(computed.result, UpdateEffect)
                    assert state.ticket is not None
                    args = computed.result.arguments
                    version = state.ticket.version + 1
                    db.execute(
                        "UPDATE tickets SET title=?,body=?,version=?,classification=? "
                        "WHERE episode_id=? AND id=?",
                        (
                            args.title,
                            args.body,
                            version,
                            "confidential"
                            if state.sensitive or episode["confidential"]
                            else "internal",
                            episode_id,
                            args.ticket_id,
                        ),
                    )
                    result = {"ticket_id": args.ticket_id, "version": str(version)}
                elif isinstance(action, ShareAction):
                    assert isinstance(computed.result, ShareEffect)
                    assert state.source is not None
                    share_id = str(uuid.uuid4())
                    db.execute(
                        "INSERT INTO simulated_shares VALUES (?,?,?,?,?,?)",
                        (
                            share_id,
                            episode_id,
                            action.arguments.document_id,
                            action.arguments.project_id,
                            state.source.version,
                            computed.result.body,
                        ),
                    )
                    result = {"share_id": share_id}
                if isinstance(action, (ReadAction, SearchAction, ListAction)) and state.sensitive:
                    db.execute("UPDATE episodes SET confidential=1 WHERE id=?", (episode_id,))
                if grant is not None:
                    db.execute("UPDATE approvals SET consumed=1 WHERE id=?", (approval_id,))

            output = Execution(decision=decision, result=result)
            db.execute(
                "UPDATE executions SET output=? WHERE episode_id=? AND execution_key=?",
                (output.model_dump_json(), episode_id, key),
            )
            self._audit(db, episode_id, key, "EXECUTED", output.decision.model_dump())
            return output

    def approval(self, approval_id: str) -> dict[str, Any]:
        """Operator-only detail, including one-use nonce; never expose as a model tool."""
        with self.connection() as db:
            row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None:
                raise KeyError("Unknown approval")
            return {**dict(row), "snapshot": json.loads(row["snapshot"])}

    def review(
        self, approval_id: str, *, expected_hash: str, nonce: str, reviewer: str, approve: bool
    ) -> None:
        """Trusted operator entry point; HTTP authentication lives in agentguard.api."""
        if not reviewer.strip():
            raise ReviewRejected("Reviewer is required")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if (
                row is None
                or row["status"] != "PENDING"
                or row["expires_at"] <= self.clock()
                or row["action_hash"] != expected_hash
                or not secrets.compare_digest(row["nonce"], nonce)
                or db.execute(
                    "SELECT cancelled FROM episodes WHERE id=?", (row["episode_id"],)
                ).fetchone()[0]
            ):
                raise ReviewRejected("Approval is stale, already reviewed, or does not match")
            episode = db.execute(
                "SELECT * FROM episodes WHERE id=?", (row["episode_id"],)
            ).fetchone()
            job = db.execute(
                "SELECT status,deadline FROM jobs WHERE episode_id=?", (row["episode_id"],)
            ).fetchone()
            if job is not None and (
                job["status"] not in ("RUNNING", "WAITING_APPROVAL", "QUEUED")
                or (job["deadline"] is not None and job["deadline"] <= self.clock())
            ):
                raise ReviewRejected("Run is terminal or expired")
            action = ACTION_ADAPTER.validate_python(json.loads(row["snapshot"])["action"])
            contract = TaskContract.model_validate_json(episode["contract"])
            state = resolve(db, row["episode_id"], contract, episode["profile"], action)
            current = state.decision(
                episode_id=row["episode_id"],
                contract=contract,
                profile=episode["profile"],
                action=action,
                confidential=bool(episode["confidential"]),
            )
            if current.action_hash != expected_hash or current.outcome != "REQUIRE_APPROVAL":
                raise ReviewRejected("Approval scope or resource state changed")
            status = "APPROVED" if approve else "REJECTED"
            db.execute(
                "UPDATE approvals SET status=?,reviewer=? WHERE id=?",
                (status, reviewer, approval_id),
            )
            self._audit(
                db,
                row["episode_id"],
                row["execution_key"],
                "REVIEWED",
                {"status": status, "reviewer": reviewer},
            )
            db.execute(
                "UPDATE jobs SET status='QUEUED' WHERE episode_id=? "
                "AND status='WAITING_APPROVAL' AND waiting_approval_id=?",
                (row["episode_id"], approval_id),
            )

    def require_lease(
        self, db: sqlite3.Connection, episode_id: str, lease: Lease | None
    ) -> sqlite3.Row | None:
        """Call inside the SAME write transaction as every managed-run mutation."""
        job = db.execute("SELECT * FROM jobs WHERE episode_id=?", (episode_id,)).fetchone()
        if job is None and lease is None:
            return None  # Legacy, explicitly synchronous evaluation episodes.
        if (
            job is None
            or lease is None
            or lease.episode_id != episode_id
            or job["status"] != "RUNNING"
            or job["token"] != lease.token
            or job["generation"] != lease.generation
            or job["lease_until"] <= self.clock()
        ):
            raise LeaseLost("Worker lease is missing, expired, or superseded")
        return cast(sqlite3.Row, job)

    def is_cancelled(self, episode_id: str) -> bool:
        with self.connection() as db:
            row = db.execute("SELECT cancelled FROM episodes WHERE id=?", (episode_id,)).fetchone()
            if row is None:
                raise KeyError("Unknown episode")
            return bool(row["cancelled"])

    def cancel(self, episode_id: str) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute("UPDATE episodes SET cancelled=1 WHERE id=?", (episode_id,))
            if cursor.rowcount != 1:
                raise KeyError("Unknown episode")
            job = db.execute("SELECT status FROM jobs WHERE episode_id=?", (episode_id,)).fetchone()
            if job is not None and job["status"] in ("QUEUED", "RUNNING", "WAITING_APPROVAL"):
                db.execute(
                    "UPDATE jobs SET status='CANCELLED',token=NULL,lease_until=NULL "
                    "WHERE episode_id=?",
                    (episode_id,),
                )
                db.execute(
                    "UPDATE agent_runs SET status='CANCELLED',result=? WHERE episode_id=?",
                    (canonical_json({"status": "CANCELLED", "reason": "CANCELLED"}), episode_id),
                )
            self._audit(db, episode_id, None, "CANCELLED", {})

    def tickets(self, episode_id: str) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM tickets WHERE episode_id=? ORDER BY id", (episode_id,)
                )
            ]

    def shares(self, episode_id: str) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM simulated_shares WHERE episode_id=? ORDER BY id", (episode_id,)
                )
            ]

    def events(self, episode_id: str) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [
                {**dict(row), "payload": json.loads(row["payload"])}
                for row in db.execute(
                    "SELECT * FROM audit_events WHERE episode_id=? ORDER BY sequence", (episode_id,)
                )
            ]
