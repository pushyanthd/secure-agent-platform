import json
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Annotated, cast

import typer

from agentguard import benchmark
from agentguard.analysis import write_analysis
from agentguard.api import create_app
from agentguard.contracts import Profile
from agentguard.control_setup import (
    ControlSettings,
    initialize_control,
    load_credentials,
    prepare_control,
)
from agentguard.control_smoke import run_control_smoke
from agentguard.diagnostics import write_diagnostics
from agentguard.doctor import inventory
from agentguard.durable_demo import run_durable_demo
from agentguard.evidence import export_evidence, verify_evidence
from agentguard.live import prepare_local_model, run_live_smoke
from agentguard.model import inference_environment
from agentguard.model_setup import fetch_models, serve_command
from agentguard.policy_benchmark import write_policy_benchmark
from agentguard.release_cli import register as register_release_commands
from agentguard.replay import run_replay
from agentguard.sandbox_setup import build_images, smoke
from agentguard.storage import LeaseLost
from agentguard.suite import VARIANTS, resume_suite, run_suite
from agentguard.supervisor import DockerComputer

app = typer.Typer(
    no_args_is_help=True,
    help="Agent authorization laboratory. Replay is not live inference.",
    pretty_exceptions_show_locals=False,
)
register_release_commands(app)


@app.command()
def control_smoke(
    output: Annotated[Path, typer.Option()] = Path("artifacts/control-smoke"),
) -> None:
    """Exercise real authenticated HTTP and worker processes using authored responses."""
    directory = run_control_smoke(Path.cwd(), output)
    report = json.loads((directory / "report.json").read_text())
    typer.echo("AUTHORED FIXTURE — zero model trials; real loopback HTTP.")
    typer.echo(json.dumps(report["checks"], indent=2))
    typer.echo(f"Report: {directory / 'report.json'}")
    if not report["passed"]:
        raise typer.Exit(1)


@app.command()
def control_init(
    directory: Annotated[Path, typer.Option()] = Path("artifacts/control"),
    fixture: Annotated[bool, typer.Option("--fixture")] = False,
    port: Annotated[int, typer.Option(min=1024, max=65535)] = 8000,
    model_profile: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
) -> None:
    """Create private local credentials and settings. Explicit --fixture needs no services."""
    try:
        path = initialize_control(
            Path.cwd(), directory, fixture=fixture, port=port, model_profile=model_profile
        )
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Settings: {path}")
    typer.echo(f"Operator token: {path.parent / 'operator.token'} (keep private)")
    typer.echo("AUTHORED FIXTURE — zero model trials" if fixture else "PINNED LOCAL INFERENCE")


@app.command()
def api_serve(
    settings: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "artifacts/control/settings.json"
    ),
    credentials: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "artifacts/control/credentials.json"
    ),
) -> None:
    """Serve the operator API on 127.0.0.1; never pass credentials to the worker."""
    import uvicorn

    configured = ControlSettings.model_validate_json(settings.read_bytes())
    control, _ = prepare_control(configured)
    application = create_app(
        control, load_credentials(credentials), origin=f"http://127.0.0.1:{configured.port}"
    )
    uvicorn.run(
        application,
        host="127.0.0.1",
        port=configured.port,
        proxy_headers=False,
        access_log=False,
        server_header=False,
    )


@app.command()
def worker(
    settings: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "artifacts/control/settings.json"
    ),
    once: Annotated[bool, typer.Option("--once")] = False,
) -> None:
    """Drain compatible durable jobs in a separate process without operator credentials."""
    configured = ControlSettings.model_validate_json(settings.read_bytes())
    _, runner = prepare_control(configured)
    typer.echo(f"Worker mode: {configured.mode}")
    while True:
        try:
            result = runner.run_once()
        except LeaseLost:
            typer.echo("Worker lease revoked or superseded; stopping.")
            raise typer.Exit(1) from None
        if result is not None:
            typer.echo(f"Run state: {result['status']}")
        if once:
            return
        if result is None:
            time.sleep(1)


@app.command()
def demo_durable(
    output: Annotated[Path, typer.Option()] = Path("artifacts/durable"),
) -> None:
    """Scripted approval and post-commit recovery demo; zero model trials."""
    directory = run_durable_demo(Path("scenarios/dev/suite/authorized-shared-write.json"), output)
    typer.echo((directory / "report.md").read_text())
    typer.echo(f"Report and database: {directory}")
    if not json.loads((directory / "report.json").read_text())["passed"]:
        raise typer.Exit(1)


@app.command()
def eval_export(
    run_directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option()],
) -> None:
    """Export synthetic benchmark state for offline regrading without approval credentials."""
    try:
        result = export_evidence(run_directory, output)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        raise typer.BadParameter(f"Unusable benchmark evidence: {exc}") from exc
    typer.echo(f"Portable evidence: {result}")
    typer.echo("Includes synthetic model/tool content; review before publishing.")


@app.command()
def eval_verify(
    run_directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
) -> None:
    """Independently regrade portable evidence offline, with no inference or tool execution."""
    try:
        result = verify_evidence(run_directory)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        raise typer.BadParameter(f"Unusable portable evidence: {exc}") from exc
    typer.echo(json.dumps(result, indent=2))


@app.command()
def eval_analyze(
    run_directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option()],
    resamples: Annotated[int, typer.Option(min=100, max=100000)] = 5000,
    seed: Annotated[int, typer.Option()] = 42,
) -> None:
    """Verify a completed suite and export paired analysis without changing its evidence."""
    try:
        result = write_analysis(run_directory, output, resamples=resamples, seed=seed)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise typer.BadParameter(f"Unusable suite evidence: {exc}") from exc
    typer.echo(f"Analysis: {result / 'analysis.md'}")
    typer.echo(f"Standalone viewer: {result / 'explorer.html'}")
    typer.echo((result / "analysis.md").read_text())


@app.command()
def eval_diagnostics(
    run_directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option()],
) -> None:
    """Verify evidence and reconcile runtime budgets, tool coverage, and denial outcomes."""
    try:
        result = write_diagnostics(run_directory, output)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise typer.BadParameter(f"Unusable runtime evidence: {exc}") from exc
    typer.echo(f"Diagnostics: {result / 'diagnostics.md'}")
    typer.echo((result / "diagnostics.md").read_text())


@app.command()
def policy_benchmark(
    output: Annotated[Path, typer.Option()],
    suite: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "scenarios/dev/tools-v1.json"
    ),
    samples: Annotated[int, typer.Option(min=100, max=100000)] = 1000,
) -> None:
    """Measure deterministic policy and hashing; exclude persistence, tools, and inference."""
    directory = write_policy_benchmark(suite, output, samples=samples)
    result = json.loads((directory / "policy-benchmark.json").read_text())
    typer.echo(f"Pure-policy milliseconds: {json.dumps(result['milliseconds'])}")
    typer.echo(f"Report: {directory / 'policy-benchmark.json'}")


@app.command()
def doctor() -> None:
    """Inspect this machine without changing services or downloading weights."""
    typer.echo(json.dumps(inventory(Path.cwd()), indent=2))


@app.command()
def demo_replay(
    scenario: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "scenarios/dev/launch-ticket.json"
    ),
    output: Annotated[Path, typer.Option()] = Path("artifacts/replays"),
    sandbox_manifest: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
) -> None:
    """Run four scripted clean/attacked episodes; no inference or container claims."""
    computer = DockerComputer.from_manifest(sandbox_manifest) if sandbox_manifest else None
    result = run_replay(scenario, output, computer=computer)
    mode = computer.mode if computer else "trusted_python_simulation_only"
    typer.echo(f"SCRIPTED REPLAY — 4 episodes; 0 model trials; {mode}.")
    typer.echo(f"Report: {result / 'report.md'}")
    typer.echo((result / "report.md").read_text())


@app.command()
def sandbox_build() -> None:
    """Explicitly download the pinned base image and build fixed tools/probe images."""
    typer.echo(f"Sandbox manifest: {build_images(Path.cwd())}")


@app.command()
def sandbox_smoke(
    manifest: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "artifacts/sandbox/manifest.json"
    ),
    output: Annotated[Path, typer.Option()] = Path("artifacts/sandbox-smoke"),
) -> None:
    """Measure tool computation and containment using a separate diagnostic image."""
    report = smoke(manifest, output)
    typer.echo(f"Container smoke report: {report}")
    result = json.loads(report.read_text())
    typer.echo(json.dumps(result["checks"], indent=2))
    if not result["passed"]:
        raise typer.Exit(1)


@app.command()
def models_fetch(
    profile: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "config/model-mac-small.json"
    ),
) -> None:
    """Explicitly download and verify pinned local weights/runtime and their licenses."""
    fetch_models(Path.cwd(), profile)
    typer.echo("Pinned model and runtime verified. Start with: make model-serve")


@app.command()
def model_serve(
    profile: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "config/model-mac-small.json"
    ),
) -> None:
    """Serve verified project-local weights on loopback in the foreground; no downloads."""
    raise typer.Exit(
        subprocess.call(serve_command(Path.cwd(), profile), env=inference_environment())
    )


@app.command()
def eval_smoke(
    scenario: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "scenarios/dev/launch-ticket.json"
    ),
    profile: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "config/model-mac-small.json"
    ),
    sandbox_manifest: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "artifacts/sandbox/manifest.json"
    ),
    output: Annotated[Path, typer.Option()] = Path("artifacts/live"),
) -> None:
    """Explicit synthetic benchmark: 6 fresh local-model trials, including unsafe baselines."""
    result = run_live_smoke(scenario, profile, sandbox_manifest, output, root=Path.cwd())
    typer.echo(f"Report: {result / 'report.md'}")
    typer.echo((result / "report.md").read_text())
    report = json.loads((result / "report.json").read_text())
    if any(
        row["status"] != "COMPLETED" or (not row["attacked"] and not row["grade"]["task_success"])
        for row in report["episodes"]
    ):
        raise typer.Exit(1)


@app.command()
def eval_suite(
    suite: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "scenarios/dev/suite-v1.json"
    ),
    live: Annotated[bool, typer.Option("--live")] = False,
    variants: Annotated[str, typer.Option()] = "baseline,prompt_only,defended",
    simulate_approvals: Annotated[bool, typer.Option()] = True,
    model_profile: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "config/model-mac-small.json"
    ),
    sandbox_manifest: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    output: Annotated[Path, typer.Option()] = Path("artifacts/suites"),
    max_episodes: Annotated[int | None, typer.Option(min=1)] = None,
) -> None:
    """Run a synthetic development suite; default is authored replay, not model inference."""
    selected = tuple(v.strip() for v in variants.split(","))
    if len(set(selected)) != len(selected) or not set(selected) <= set(VARIANTS):
        raise typer.BadParameter("Select unique variants from baseline,prompt_only,defended")
    model, evidence = None, None
    if live:
        model, profile, server = prepare_local_model(Path.cwd(), model_profile)
        if "preflight_error" in server:
            raise typer.BadParameter("Start the pinned local model server before starting a suite")
        evidence = {"profile": profile, "server": server}
        sandbox_manifest = sandbox_manifest or Path("artifacts/sandbox/manifest.json")
    computer = DockerComputer.from_manifest(sandbox_manifest) if sandbox_manifest else None

    with benchmark.graceful_stop(typer.echo) as stop:
        result = run_suite(
            suite,
            output,
            computer=computer,
            variants=cast(tuple[Profile, ...], selected),
            simulate_approvals=simulate_approvals,
            model=model,
            model_evidence=evidence,
            progress=_suite_progress,
            stop_requested=stop,
            max_episodes=max_episodes,
        )
    _suite_output(result)


def _suite_progress(directory: Path, completed: int, total: int) -> None:
    typer.echo(f"Artifacts: {directory} | Episodes recorded: {completed}/{total}")


@app.command()
def eval_status(directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    """Inspect saved benchmark progress without starting inference or changing state."""
    try:
        typer.echo(json.dumps(benchmark.status(directory), indent=2))
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def eval_resume(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    model_profile: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "config/model-mac-small.json"
    ),
    sandbox_manifest: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    max_episodes: Annotated[int | None, typer.Option(min=1)] = None,
) -> None:
    """Continue an existing benchmark with its original schedule and settings."""
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        benchmark.verify_files(directory, manifest)
        model, evidence = None, None
        if manifest["fresh_inference"]:
            model, profile, server = prepare_local_model(Path.cwd(), model_profile)
            if "preflight_error" in server:
                raise ValueError("Start the pinned local model server before resuming")
            evidence = {"profile": profile, "server": server}
        if manifest["containment"] == "docker_isolated":
            sandbox_manifest = sandbox_manifest or Path("artifacts/sandbox/manifest.json")
        computer = DockerComputer.from_manifest(sandbox_manifest) if sandbox_manifest else None
        with benchmark.graceful_stop(typer.echo) as stop:
            result = resume_suite(
                directory,
                computer=computer,
                model=model,
                model_evidence=evidence,
                progress=_suite_progress,
                stop_requested=stop,
                max_episodes=max_episodes,
            )
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _suite_output(result)


def _suite_output(result: Path) -> None:
    state = benchmark.status(result)
    live = state["mode"] == "fresh_local_inference"
    typer.echo("FRESH LOCAL INFERENCE" if live else "SCRIPTED REPLAY — 0 model trials")
    if not state["complete"]:
        typer.echo(f"PAUSED: {state['recorded']}/{state['scheduled']} episodes recorded.")
        typer.echo(f"Resume: agentguard eval-resume {result}")
        return
    typer.echo(f"Report: {result / 'report.md'}")
    report = json.loads((result / "report.json").read_text())
    typer.echo(json.dumps(report["counts"], indent=2))
    if report["manifest"].get("release_evidence"):
        typer.echo("Frozen release execution complete. Run release-gate with the original freeze.")
        return
    if any(
        r["status"] != "COMPLETED"
        or (
            r["profile"] == "defended"
            and (
                (not r["attacked"] and not r["grade"]["task_success"])
                or r["grade"]["attack_success"]
            )
        )
        for r in report["episodes"]
    ):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
