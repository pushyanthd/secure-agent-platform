"""Explicit commands for freeze, resumable execution, and offline release scoring."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from agentguard import benchmark
from agentguard.live import atomic_json, prepare_local_model
from agentguard.model import LocalModel
from agentguard.release import (
    freeze_experiment,
    protocol,
    score_release,
    sha,
    source_hash,
    validation_hash,
)
from agentguard.suite import run_suite
from agentguard.supervisor import DockerComputer


def register(app: typer.Typer) -> None:
    from agentguard.release_workflow import register as register_workflow

    register_workflow(app)
    app.command()(release_check)
    app.command()(release_freeze)
    app.command()(release_run)
    app.command()(release_gate)


def release_check(
    output: Annotated[Path, typer.Option()] = Path("artifacts/release-checks"),
    sandbox_manifest: Annotated[Path, typer.Option(exists=True)] = Path(
        "artifacts/sandbox/manifest.json"
    ),
) -> None:
    """Retain Python invariant checks and real container probes for this exact source."""
    if output.exists():
        raise typer.BadParameter("Use a new check directory to preserve previous evidence")
    output.mkdir(parents=True)
    before = source_hash()
    validation_before = validation_hash()
    computer = DockerComputer.from_manifest(sandbox_manifest)
    commands = {
        "python": ["make", "check"],
        "sandbox": [
            sys.executable,
            "-m",
            "agentguard.cli",
            "sandbox-smoke",
            "--manifest",
            str(sandbox_manifest),
            "--output",
            str(output / "sandbox"),
        ],
    }
    outcomes = {}
    for name, command in commands.items():
        typer.echo(f"Checking {name}; log: {output / (name + '.log')}")
        with (output / (name + ".log")).open("w") as log:
            code = subprocess.call(command, stdout=log, stderr=subprocess.STDOUT)
        outcomes[name] = {"argv": command, "exit_code": code}
    checks = {
        "version": "release-checks-v1",
        "source_sha256": before,
        "validation_sha256": validation_before,
        "environment": benchmark.environment(),
        "tool_image_id": computer.image_id,
        "commands": outcomes,
        "passed": before == source_hash()
        and validation_before == validation_hash()
        and all(c["exit_code"] == 0 for c in outcomes.values()),
        "files": {
            str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
        },
    }
    atomic_json(output / "checks.json", checks)
    typer.echo(f"Checks: {output / 'checks.json'}")
    if not checks["passed"]:
        raise typer.Exit(1)


def _runtime(
    model_profile: Path, sandbox_manifest: Path
) -> tuple[LocalModel, DockerComputer, dict[str, Any]]:
    model, profile, server = prepare_local_model(Path.cwd(), model_profile)
    if "preflight_error" in server:
        raise ValueError("Start the pinned model server with make model-serve")
    computer = DockerComputer.from_manifest(sandbox_manifest)
    evidence = {"profile": profile, "server": server}
    return model, computer, evidence


def release_freeze(
    suite: Annotated[Path, typer.Option(exists=True)],
    lineage: Annotated[Path, typer.Option(exists=True)],
    checks: Annotated[Path, typer.Option(exists=True)],
    output: Annotated[Path, typer.Option()],
    limitations: Annotated[Path, typer.Option(exists=True)],
    development: Annotated[Path, typer.Option(exists=True)] = Path("scenarios/dev"),
    model_profile: Annotated[Path, typer.Option(exists=True)] = Path("config/model-mac-small.json"),
    sandbox_manifest: Annotated[Path, typer.Option(exists=True)] = Path(
        "artifacts/sandbox/manifest.json"
    ),
) -> None:
    """Snapshot forty untouched tasks and the verified live protocol before inference."""
    try:
        model, computer, evidence = _runtime(model_profile, sandbox_manifest)
        limits = json.loads(limitations.read_text())
        if (
            not isinstance(limits, list)
            or not limits
            or any(not isinstance(s, str) for s in limits)
        ):
            raise ValueError("Limitations must be a nonempty JSON list of strings")
        path = freeze_experiment(
            suite,
            lineage,
            development,
            checks,
            output,
            protocol(
                evidence, model.config.model_dump(mode="json"), computer.image_id, computer.timeout
            ),
            limitations=limits,
        )
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Frozen: {path}")
    typer.echo("Preserve this file before running; checksums detect changes, not owner forgery.")


def release_run(
    freeze: Annotated[Path, typer.Argument(exists=True)],
    output: Annotated[Path, typer.Option()] = Path("artifacts/release-runs"),
    max_episodes: Annotated[int | None, typer.Option(min=1)] = None,
    model_profile: Annotated[Path, typer.Option(exists=True)] = Path("config/model-mac-small.json"),
    sandbox_manifest: Annotated[Path, typer.Option(exists=True)] = Path(
        "artifacts/sandbox/manifest.json"
    ),
) -> None:
    """Run exactly 400 baseline/defended trials; Ctrl+C saves after the current episode."""
    try:
        value = json.loads(freeze.read_text())
        model, computer, evidence = _runtime(model_profile, sandbox_manifest)
        with benchmark.graceful_stop(typer.echo) as stop:
            directory = run_suite(
                freeze.parent / "fixtures/suite.json",
                output,
                computer=computer,
                model=model,
                model_evidence=evidence,
                variants=("baseline", "defended"),
                release_freeze=value,
                max_episodes=max_episodes,
                stop_requested=stop,
                progress=lambda d, n, total: typer.echo(f"Artifacts: {d} | Episodes: {n}/{total}"),
            )
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    state = benchmark.status(directory)
    if not state["complete"]:
        typer.echo(f"PAUSED: {state['recorded']}/400. Resume: agentguard eval-resume {directory}")
    else:
        typer.echo(
            f"Execution complete. Score: agentguard release-gate {directory} --freeze {freeze}"
        )


def release_gate(
    directory: Annotated[Path, typer.Argument(exists=True)],
    freeze: Annotated[Path, typer.Option(exists=True)],
    output: Annotated[Path, typer.Option()] = Path("artifacts/release-gate.json"),
) -> None:
    """Return PASS (0), FAIL (1), or UNUSABLE (2); failures stay in every denominator."""
    if output.resolve().is_relative_to(directory.resolve()) or output.resolve().is_relative_to(
        freeze.parent.resolve()
    ):
        raise typer.BadParameter("Gate output must be outside the run and frozen evidence")
    try:
        result = score_release(directory, freeze)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        result = {"status": "UNUSABLE", "reason": str(exc), "release_label": "experimental"}
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(output, result)
    typer.echo(
        json.dumps(
            {k: result[k] for k in ("status", "objectives", "reason") if k in result}, indent=2
        )
    )
    typer.echo(f"Gate evidence: {output}")
    raise typer.Exit({"PASS": 0, "FAIL": 1, "UNUSABLE": 2}[result["status"]])
