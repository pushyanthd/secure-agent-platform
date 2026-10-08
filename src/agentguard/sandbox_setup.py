"""Explicit image setup and standalone measured smoke evidence."""

import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from agentguard.computation import DocumentSnapshot, ToolFailure, ToolRequest, validate_result
from agentguard.contracts import (
    ACTION_ADAPTER,
    CreateAction,
    CreateArguments,
    ReadAction,
    ReadArguments,
)
from agentguard.supervisor import DockerComputer


def build_images(root: Path) -> Path:
    config = json.loads((root / "config/sandbox.json").read_text())
    base = config["base_image"]
    if not base.startswith("python:3.12-slim-bookworm@sha256:"):
        raise ValueError("Unexpected sandbox base image")
    output = root / "artifacts/sandbox"
    output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"schema_version": 1, "base_image": base}
    source_hashes = {
        name: hashlib.sha256((root / "sandbox" / name).read_bytes()).hexdigest()
        for name in ("Dockerfile", "runner.py", "probe.py")
    }
    for target, key in (("tools", "tool_image_id"), ("probe", "probe_image_id")):
        iidfile = output / f"{target}-{uuid.uuid4().hex}.iid"
        subprocess.run(
            [
                "docker",
                "build",
                "--network=none",
                "--build-arg",
                f"BASE_IMAGE={base}",
                "--target",
                target,
                "--iidfile",
                str(iidfile),
                str(root / "sandbox"),
            ],
            check=True,
            timeout=300,
        )
        manifest[key] = iidfile.read_text().strip()
    current_hashes = {
        name: hashlib.sha256((root / "sandbox" / name).read_bytes()).hexdigest()
        for name in ("Dockerfile", "runner.py", "probe.py")
    }
    if source_hashes != current_hashes:
        raise ValueError("Sandbox sources changed during build; rebuild before using the images")
    manifest["source_sha256"] = source_hashes
    path = output / "manifest.json"
    temporary = output / f"manifest-{uuid.uuid4().hex}.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(path)
    return path


def smoke(manifest_path: Path, output_root: Path) -> Path:
    manifest = json.loads(manifest_path.read_text())
    computer = DockerComputer.from_manifest(manifest_path)
    probe = DockerComputer(manifest["probe_image_id"])
    requests: tuple[ToolRequest, ...] = (
        ToolRequest(
            action=ReadAction(arguments=ReadArguments(document_id="launch")),
            document=DocumentSnapshot(id="launch", body="Validate rollback."),
        ),
        ToolRequest(
            action=CreateAction(
                arguments=CreateArguments(
                    project_id="atlas", title="Rollback", body="Validate rollback."
                )
            )
        ),
    )
    requests += tuple(
        ToolRequest(
            action=ACTION_ADAPTER.validate_python({"tool": tool, "arguments": args}),
            document=DocumentSnapshot(id="launch", body="Validate rollback.")
            if tool == "shares.request"
            else None,
        )
        for tool, args in (
            ("documents.search", {"query": "rollback", "limit": 5}),
            ("tickets.list", {"project_id": "atlas", "limit": 5}),
            (
                "tickets.update",
                {
                    "project_id": "atlas",
                    "ticket_id": "ticket-1",
                    "expected_version": 1,
                    "title": "Rollback",
                    "body": "Updated.",
                },
            ),
            ("shares.request", {"document_id": "launch", "project_id": "shared"}),
        )
    )
    results: list[dict[str, Any]] = []
    for request in requests:
        started = time.monotonic()
        try:
            validate_result(request, computer.compute(request))
            results.append(
                {
                    "check": request.action.tool,
                    "passed": True,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
        except ToolFailure as exc:
            results.append({"check": request.action.tool, "passed": False, "error": exc.code})
    try:
        boundary = probe.diagnostic("boundary")
        results.extend({"check": key, "passed": value is True} for key, value in boundary.items())
    except ToolFailure as exc:
        results.append({"check": "boundary", "passed": False, "error": exc.code})
    for operation, expected in (
        ("timeout", "TOOL_TIMEOUT"),
        ("oversized", "OUTPUT_TOO_LARGE"),
        ("memory", "TOOL_PROCESS_FAILED"),
    ):
        selected = DockerComputer(probe.image_id, timeout=3 if operation == "timeout" else 10)
        try:
            selected.diagnostic(operation)
            results.append({"check": operation, "passed": False, "error": "PROBE_SURVIVED"})
        except ToolFailure as exc:
            results.append(
                {
                    "check": operation,
                    "passed": exc.code == expected
                    and (operation != "memory" or exc.exit_status == 137),
                    "observed": exc.code,
                    "exit_status": exc.exit_status,
                }
            )
    directory = output_root / str(uuid.uuid4())
    directory.mkdir(parents=True)
    report = {
        "mode": "live_container_smoke",
        "model_trials": 0,
        "manifest": manifest,
        "passed": all(item["passed"] for item in results),
        "checks": results,
        "limitations": "Local container boundary checks; no kernel-escape or AI evaluation claims.",
    }
    payload = (json.dumps(report, indent=2) + "\n").encode()
    (directory / "report.json").write_bytes(payload)
    (directory / "checksums.json").write_text(
        json.dumps({"report.json": hashlib.sha256(payload).hexdigest()}) + "\n"
    )
    return directory / "report.json"
