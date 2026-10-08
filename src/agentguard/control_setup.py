"""Project-local setup and separate API/worker processes; no downloads on startup."""

import json
import os
import secrets
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from agentguard.api import Credential, Credentials, token_hash
from agentguard.artifact_volume import load_volume
from agentguard.bounded_storage import BoundedStore
from agentguard.contracts import Contract, canonical_json, digest
from agentguard.control import ControlPlane, Principal
from agentguard.durable_demo import ScriptedModel
from agentguard.live import prepare_local_model
from agentguard.runtime import Budgets, Model
from agentguard.scenarios import DevelopmentTask, load_suite
from agentguard.storage import Store
from agentguard.supervisor import DockerComputer
from agentguard.worker import Worker


class ControlSettings(Contract):
    mode: Literal["authored_fixture", "fresh_local_inference"]
    root: Path
    database: Path
    suite: Path
    model_profile: Path
    sandbox_manifest: Path
    port: int = Field(default=8000, ge=1024, le=65535)
    budgets: Budgets = Budgets(max_episode_seconds=900)
    artifact_volume_manifest: Path | None = None


class FixtureCatalogModel:
    def __init__(self, tasks: dict[str, DevelopmentTask]):
        self.scripts = {task.task: ScriptedModel(task) for task in tasks.values()}
        if len(self.scripts) != len(tasks):
            raise ValueError("Fixture tasks must have distinct user instructions")

    def count_tokens(self, messages: list[dict[str, str]], *, timeout: float) -> int:
        return 0

    def complete(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        max_tokens: int,
        timeout: float,
    ) -> str:
        task = json.loads(messages[1]["content"])["task"]
        return self.scripts[task].complete(messages, schema, max_tokens=max_tokens, timeout=timeout)


def prepare_control(settings: ControlSettings) -> tuple[ControlPlane, Worker]:
    volume = (
        load_volume(settings.artifact_volume_manifest)
        if settings.artifact_volume_manifest is not None
        else None
    )
    if volume is not None:
        volume.verify(settings.database)
    _, rows = load_suite(settings.suite)
    tasks = {task.id: task for _, _, task in rows}
    computer = None
    model: Model
    if settings.mode == "authored_fixture":
        model = FixtureCatalogModel(tasks)
        identity: dict[str, Any] = {
            "mode": "authored_fixture",
            "tasks": {key: digest(task.model_dump(mode="json")) for key, task in tasks.items()},
        }
    else:
        model, profile, server = prepare_local_model(settings.root, settings.model_profile)
        if "preflight_error" in server:
            raise ValueError("Start the pinned local model before the live control plane/worker")
        if settings.budgets.context_tokens != model.config.context_tokens:
            raise ValueError("Application context budget must match the verified server")
        identity = {"mode": "fresh_local_inference", "profile": profile, "server": server}
        computer = DockerComputer.from_manifest(settings.sandbox_manifest)
    store = (
        BoundedStore(settings.database, computer=computer, artifact_volume=volume)
        if volume is not None
        else Store(settings.database, computer=computer)
    )
    worker = Worker(store, model, model_identity=identity)
    control = ControlPlane(
        store, tasks, manifest=worker.manifest, budgets=settings.budgets, mode=settings.mode
    )
    return control, worker


def private_file(path: Path, value: str) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
        output.write(value + "\n")


def initialize_control(
    root: Path,
    directory: Path,
    *,
    fixture: bool,
    port: int = 8000,
    model_profile: Path | None = None,
    artifact_volume_manifest: Path | None = None,
) -> Path:
    root, directory = root.resolve(), directory.resolve()
    if artifact_volume_manifest is not None:
        artifact_volume_manifest = artifact_volume_manifest.resolve()
        load_volume(artifact_volume_manifest).verify(directory)
    settings = ControlSettings(
        mode="authored_fixture" if fixture else "fresh_local_inference",
        root=root,
        database=directory / "state.sqlite3",
        suite=root / "scenarios/dev/suite-v5.json",
        model_profile=(root / model_profile).resolve()
        if model_profile is not None
        else root / "config/model-mac-small.json",
        sandbox_manifest=root / "artifacts/sandbox/manifest.json",
        port=port,
        artifact_volume_manifest=artifact_volume_manifest,
    )
    _, rows = load_suite(settings.suite)
    actor, workspace = rows[0][2].contract.actor, rows[0][2].contract.workspace
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    entries = []
    for role in ("operator", "observer"):
        token = secrets.token_urlsafe(32)
        principal = Principal.model_validate(
            {"subject": "local-operator", "actor": actor, "workspace": workspace, "role": role}
        )
        entries.append(Credential(token_sha256=token_hash(token), principal=principal))
        private_file(directory / f"{role}.token", token)
    private_file(
        directory / "credentials.json", Credentials(entries=tuple(entries)).model_dump_json()
    )
    private_file(directory / "settings.json", canonical_json(settings.model_dump(mode="json")))
    return directory / "settings.json"


def load_credentials(path: Path) -> Credentials:
    if path.stat().st_mode & 0o077:
        raise ValueError("Credential file must be private (chmod 600)")
    return Credentials.model_validate_json(path.read_bytes())
