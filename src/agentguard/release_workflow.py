"""Convenient local release handoff; planning never calls model generation."""

import json
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Annotated, Any

import typer

from agentguard import benchmark
from agentguard.analysis import write_analysis
from agentguard.diagnostics import write_diagnostics
from agentguard.live import atomic_json
from agentguard.release import (
    audit_corpus,
    freeze_experiment,
    protocol,
    sha,
    validate_freeze,
    validation_hash,
    verify_checks,
    verify_manifest,
    verify_suite,
)
from agentguard.release_corpus import validate_corpus
from agentguard.suite import resume_suite, run_suite

DEFAULT_FREEZE = Path("artifacts/frozen-release-v1/freeze.json")
DEFAULT_SESSION = Path("artifacts/release-session")


def register(app: typer.Typer) -> None:
    for command in (
        release_validate,
        release_prepare,
        release_launch,
        release_progress,
        release_results,
    ):
        app.command()(command)


def read_freeze(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text())
    validate_freeze(value)
    verify_checks(path.parent / "checks", value["checks"])
    if json.loads((path.parent / "checks/checks.json").read_text()) != value["checks"]:
        raise ValueError("Frozen invariant check manifest changed")
    verify_suite(value, path.parent / "fixtures/suite.json")
    return value


def release_validate(
    suite: Annotated[Path, typer.Option(exists=True)] = Path("scenarios/held-out/suite-v1.json"),
    lineage: Annotated[Path, typer.Option(exists=True)] = Path(
        "scenarios/held-out/lineage-v1.json"
    ),
    output: Annotated[Path, typer.Option()] = Path("artifacts/held-out-validation"),
    sandbox_manifest: Annotated[Path | None, typer.Option(exists=True)] = None,
) -> None:
    """Exercise all 400 authored cases; no model inference and no live release score."""
    from agentguard.supervisor import DockerComputer

    try:
        computer = DockerComputer.from_manifest(sandbox_manifest) if sandbox_manifest else None
        path = validate_corpus(suite, lineage, Path("scenarios/dev"), output, computer=computer)
        report = json.loads((path / "validation.json").read_text())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"400 authored cases; zero model trials. Validation: {path / 'validation.json'}")
    typer.echo(json.dumps({"passed": report["passed"], "counts": report["counts"]}, indent=2))
    if not report["passed"]:
        raise typer.Exit(1)


def release_prepare(
    output: Annotated[Path, typer.Option()] = DEFAULT_FREEZE.parent,
    suite: Annotated[Path, typer.Option(exists=True)] = Path("scenarios/held-out/suite-v1.json"),
    lineage: Annotated[Path, typer.Option(exists=True)] = Path(
        "scenarios/held-out/lineage-v1.json"
    ),
    limitations: Annotated[Path, typer.Option(exists=True)] = Path(
        "evaluations/release-limitations-v1.json"
    ),
    model_profile: Annotated[Path, typer.Option(exists=True)] = Path("config/model-mac-small.json"),
    sandbox_manifest: Annotated[Path, typer.Option(exists=True)] = Path(
        "artifacts/sandbox/manifest.json"
    ),
) -> None:
    """Validate authored cases, run hard checks, and freeze; zero model generation."""
    from agentguard.release_cli import _runtime, release_check

    try:
        model, computer, evidence = _runtime(model_profile, sandbox_manifest)
        live_protocol = protocol(
            evidence, model.config.model_dump(mode="json"), computer.image_id, computer.timeout
        )
        if output.exists():
            frozen = read_freeze(output / "freeze.json")
            verify_suite(frozen, suite)
            if (
                frozen["protocol"] != live_protocol
                or frozen["audit"] != audit_corpus(suite, lineage, Path("scenarios/dev"))
                or frozen["limitations"] != json.loads(limitations.read_text())
            ):
                raise ValueError("Existing freeze differs; preserve it and select a new --output")
            typer.echo(f"Existing freeze verified: {output / 'freeze.json'}")
            return
        work = Path("artifacts/release-preparation") / str(uuid.uuid4())
        typer.echo("Checking all 400 authored cases (zero model trials)...")
        corpus = validate_corpus(suite, lineage, Path("scenarios/dev"), work / "corpus")
        if not json.loads((corpus / "validation.json").read_text())["passed"]:
            raise ValueError(f"Authored corpus failed; inspect {corpus / 'validation.json'}")
        release_check(output=work / "checks", sandbox_manifest=sandbox_manifest)
        # Retain corpus checks with the source-bound invariant evidence in the freeze.
        target = work / "checks/corpus-validation.json"
        shutil.copyfile(corpus / "validation.json", target)
        checks_path = work / "checks/checks.json"
        checks = json.loads(checks_path.read_text())
        checks["files"][target.name] = sha(target)
        atomic_json(checks_path, checks)
        limits = json.loads(limitations.read_text())
        if (
            not isinstance(limits, list)
            or not limits
            or any(not isinstance(s, str) for s in limits)
        ):
            raise ValueError("Limitations must be a nonempty list of strings")
        frozen_path = freeze_experiment(
            suite,
            lineage,
            Path("scenarios/dev"),
            checks_path,
            output,
            live_protocol,
            limitations=limits,
        )
        read_freeze(frozen_path)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Ready: {frozen_path}. Next: make release-plan")


def release_launch(
    freeze: Annotated[Path, typer.Option(exists=True)] = DEFAULT_FREEZE,
    session: Annotated[Path, typer.Option()] = DEFAULT_SESSION,
    output: Annotated[Path, typer.Option()] = Path("artifacts/release-runs"),
    plan_only: Annotated[bool, typer.Option("--plan-only")] = False,
    max_episodes: Annotated[int | None, typer.Option(min=1)] = None,
    model_profile: Annotated[Path, typer.Option(exists=True)] = Path("config/model-mac-small.json"),
    sandbox_manifest: Annotated[Path, typer.Option(exists=True)] = Path(
        "artifacts/sandbox/manifest.json"
    ),
) -> None:
    """Start or resume one named session; --plan-only schedules without generation."""
    from agentguard.release_cli import _runtime

    try:
        frozen = read_freeze(freeze)
        session.mkdir(parents=True, exist_ok=True)
        with benchmark.exclusive_run(session):
            record_path = session / "session.json"
            record = json.loads(record_path.read_text()) if record_path.exists() else None
            if record is not None:
                if record["freeze_sha256"] != frozen["freeze_sha256"]:
                    raise ValueError("Session belongs to another freeze; use a new --session")
                directory = Path(record["run_directory"])
                manifest = json.loads((directory / "manifest.json").read_text())
                if manifest.get("release_freeze") != frozen:
                    raise ValueError("Session run differs from its frozen experiment")
                verify_manifest(frozen, manifest)
                benchmark.verify_files(directory, manifest)
                if frozen["protocol"]["validation_sha256"] != validation_hash():
                    raise ValueError("Release validation assets changed")
                if plan_only or benchmark.status(directory)["complete"]:
                    typer.echo(json.dumps(benchmark.status(directory), indent=2))
                    return
            model, computer, evidence = _runtime(model_profile, sandbox_manifest)

            def progress(directory: Path, recorded: int, total: int) -> None:
                atomic_json(
                    record_path,
                    {
                        "freeze": str(freeze.resolve()),
                        "freeze_sha256": frozen["freeze_sha256"],
                        "run_directory": str(directory.resolve()),
                        "scheduled": total,
                    },
                )
                typer.echo(f"Episodes saved: {recorded}/{total} | {directory}")

            with benchmark.graceful_stop(typer.echo) as stop:
                if record is None:
                    directory = run_suite(
                        freeze.parent / "fixtures/suite.json",
                        output,
                        computer=computer,
                        model=model,
                        model_evidence=evidence,
                        variants=("baseline", "defended"),
                        release_freeze=frozen,
                        progress=progress,
                        max_episodes=max_episodes,
                        stop_requested=(lambda: True) if plan_only else stop,
                    )
                else:
                    directory = resume_suite(
                        directory,
                        computer=computer,
                        model=model,
                        model_evidence=evidence,
                        progress=progress,
                        max_episodes=max_episodes,
                        stop_requested=stop,
                    )
            status = benchmark.status(directory)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"{'COMPLETE' if status['complete'] else 'PAUSED'}: {status['recorded']}/400")
    typer.echo(
        "Next: make release-report" if status["complete"] else "Continue: make release-start"
    )


def release_progress(
    session: Annotated[Path, typer.Option(exists=True)] = DEFAULT_SESSION,
) -> None:
    """Inspect the named session; no model server, inference, or writes."""
    try:
        record = json.loads((session / "session.json").read_text())
        typer.echo(json.dumps(benchmark.status(Path(record["run_directory"])), indent=2))
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        raise typer.BadParameter(str(exc)) from exc


def release_results(
    session: Annotated[Path, typer.Option(exists=True)] = DEFAULT_SESSION,
) -> None:
    """Score a complete session and export the offline viewer, diagnostics, and failures."""
    from agentguard.release_cli import release_gate

    record = json.loads((session / "session.json").read_text())
    directory = Path(record["run_directory"])
    code = 2
    try:
        release_gate(
            directory=directory, freeze=Path(record["freeze"]), output=session / "gate.json"
        )
    except typer.Exit as exc:
        code = exc.exit_code
    if code != 2:
        analysis = session / "analysis"
        diagnostics = session / "diagnostics"
        if not analysis.exists():
            write_analysis(directory, analysis)
        if not diagnostics.exists():
            write_diagnostics(directory, diagnostics)
        typer.echo(f"Viewer: {analysis / 'explorer.html'}")
        typer.echo(f"Diagnostics: {diagnostics / 'diagnostics.md'}")
    raise typer.Exit(code)
