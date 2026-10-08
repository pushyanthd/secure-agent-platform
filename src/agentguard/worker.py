"""Single-active-job SQLite queue. Trusted host API, not an agent tool or control plane."""

import secrets
import sqlite3
import threading
from pathlib import Path
from typing import Any

from agentguard.contracts import canonical_json, digest
from agentguard.runtime import Budgets, Model, Runtime
from agentguard.storage import Lease, LeaseLost, Store


def execution_manifest(store: Store, model_identity: dict[str, Any]) -> str:
    """Bind recovery to caller-verified model provenance, source, and tool backend."""
    if not model_identity:
        raise ValueError("A verified model manifest or explicit fixture identity is required")
    return canonical_json(
        {
            "model": model_identity,
            "source": {
                path.name: digest(path.read_text())
                for path in sorted(Path(__file__).parent.glob("*.py"))
            },
            "tools": {
                "mode": store.computer.mode,
                "image_id": getattr(store.computer, "image_id", None),
                "timeout": getattr(store.computer, "timeout", None),
            },
        }
    )


class Queue:
    def __init__(self, store: Store):
        self.store = store

    def submit(self, episode: str, task: str, budgets: Budgets, *, manifest: str) -> None:
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._submit(db, episode, task, budgets, manifest=manifest)

    def _submit(
        self,
        db: sqlite3.Connection,
        episode: str,
        task: str,
        budgets: Budgets,
        *,
        manifest: str,
    ) -> None:
        """Compose a job and HTTP idempotency record in one transaction."""
        if not task.strip() or len(task) > 16000 or not manifest:
            raise ValueError("A bounded task and execution manifest are required")
        row = db.execute("SELECT * FROM episodes WHERE id=?", (episode,)).fetchone()
        if row is None:
            raise KeyError("Unknown episode")
        if row["profile"] != "defended" or row["cancelled"]:
            raise ValueError("Only active defended episodes can enter the application queue")
        previous = db.execute("SELECT * FROM jobs WHERE episode_id=?", (episode,)).fetchone()
        if previous is not None:
            if (previous["task"], previous["budgets"], previous["manifest"]) != (
                task,
                budgets.model_dump_json(),
                manifest,
            ):
                raise ValueError("Job already binds different inputs")
            return
        if db.execute(
            "SELECT 1 FROM executions WHERE episode_id=? UNION ALL "
            "SELECT 1 FROM agent_runs WHERE episode_id=?",
            (episode, episode),
        ).fetchone():
            raise ValueError("Queue submission requires an unused episode")
        db.execute(
            "INSERT INTO jobs(episode_id,status,task,budgets,manifest) VALUES (?,'QUEUED',?,?,?)",
            (episode, task, budgets.model_dump_json(), manifest),
        )
        self.store._audit(db, episode, None, "JOB_QUEUED", {})

    def claim(self, *, manifest: str, lease_seconds: float = 30) -> Lease | None:
        if not 0 < lease_seconds <= 300:
            raise ValueError("Lease must be between 0 and 300 seconds")
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self.store.clock()
            # Initial topology: exactly one active episode across all worker processes.
            if db.execute(
                "SELECT 1 FROM jobs WHERE status='RUNNING' AND lease_until>?", (now,)
            ).fetchone():
                return None
            row = db.execute(
                "SELECT * FROM jobs WHERE manifest=? AND (status='QUEUED' OR "
                "(status='RUNNING' AND lease_until<=?) OR (status='WAITING_APPROVAL' AND "
                "(deadline<=? OR waiting_approval_id IN "
                "(SELECT id FROM approvals WHERE status!='PENDING' OR expires_at<=?)))) "
                "ORDER BY rowid LIMIT 1",
                (manifest, now, now, now),
            ).fetchone()
            if row is None:
                return None
            budgets = Budgets.model_validate_json(row["budgets"])
            lease = Lease(row["episode_id"], secrets.token_urlsafe(32), row["generation"] + 1)
            db.execute(
                "UPDATE jobs SET status='RUNNING',token=?,generation=?,lease_until=?,"
                "started_at=COALESCE(started_at,?),deadline=COALESCE(deadline,?) "
                "WHERE episode_id=?",
                (
                    lease.token,
                    lease.generation,
                    now + lease_seconds,
                    now,
                    now + budgets.max_episode_seconds,
                    lease.episode_id,
                ),
            )
            self.store._audit(
                db, lease.episode_id, None, "JOB_CLAIMED", {"generation": lease.generation}
            )
            return lease

    def heartbeat(self, lease: Lease, *, lease_seconds: float = 30) -> None:
        if not 0 < lease_seconds <= 300:
            raise ValueError("Lease must be between 0 and 300 seconds")
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self.store.require_lease(db, lease.episode_id, lease)
            db.execute(
                "UPDATE jobs SET lease_until=? WHERE episode_id=?",
                (self.store.clock() + lease_seconds, lease.episode_id),
            )


class Worker:
    def __init__(
        self,
        store: Store,
        model: Model,
        *,
        model_identity: dict[str, Any],
        lease_seconds: float = 30,
    ):
        if not 0 < lease_seconds <= 300:
            raise ValueError("Lease must be between 0 and 300 seconds")
        self.store, self.model = store, model
        self.manifest = execution_manifest(store, model_identity)
        self.queue = Queue(store)
        self.lease_seconds = lease_seconds
        self.last_orphan_cleanup: list[str] = []

    def submit(self, episode: str, task: str, budgets: Budgets | None = None) -> None:
        self.queue.submit(episode, task, budgets or Budgets(), manifest=self.manifest)

    def run_once(self) -> dict[str, Any] | None:
        """Claim one compatible job, heartbeat long calls, and release on completion/wait.

        LeaseLost propagates; stale workers must exit without recording a terminal result.
        Unexpected process/runtime failures retain the job for reclaim after lease expiry.
        """
        reconcile = getattr(self.store.computer, "reconcile_orphans", None)
        if reconcile is not None:
            self.last_orphan_cleanup = reconcile()
        lease = self.queue.claim(manifest=self.manifest, lease_seconds=self.lease_seconds)
        if lease is None:
            return None
        stop = threading.Event()

        def heartbeat() -> None:
            while not stop.wait(self.lease_seconds / 3):
                try:
                    self.queue.heartbeat(lease, lease_seconds=self.lease_seconds)
                except (LeaseLost, OSError, sqlite3.Error):
                    return

        thread = threading.Thread(target=heartbeat, name="agentguard-lease", daemon=True)
        thread.start()
        try:
            with self.store.connection() as db:
                job = self.store.require_lease(db, lease.episode_id, lease)
                assert job is not None
            return Runtime(self.store, self.model, Budgets.model_validate_json(job["budgets"])).run(
                lease.episode_id, job["task"], lease=lease
            )
        finally:
            stop.set()
            thread.join()
