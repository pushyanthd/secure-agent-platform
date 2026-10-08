import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentguard import benchmark
from agentguard.analysis import checked_report, observations, write_analysis
from agentguard.cli import app
from agentguard.computation import InProcessComputer
from agentguard.diagnostics import diagnose
from agentguard.model import ModelConfig, ModelFailure
from agentguard.storage import Store
from agentguard.suite import resume_suite, run_suite

SUITE = Path("scenarios/dev/tools-v2.json")


def test_exclusive_run_rejects_other_process_and_releases_lock(tmp_path):
    child = (
        "import sys; from pathlib import Path; "
        "from agentguard.benchmark import exclusive_run; "
        "\ntry:\n with exclusive_run(Path(sys.argv[1])): print('acquired')"
        "\nexcept ValueError: print('busy')"
    )
    command = [sys.executable, "-c", child, str(tmp_path)]
    with benchmark.exclusive_run(tmp_path):
        blocked = subprocess.run(command, capture_output=True, text=True, timeout=5, check=True)
    acquired = subprocess.run(command, capture_output=True, text=True, timeout=5, check=True)
    assert blocked.stdout.strip() == "busy"
    assert acquired.stdout.strip() == "acquired"


def report(directory):
    return json.loads((directory / "report.json").read_text())


def wait_for(path, process):
    deadline = time.monotonic() + 15
    while not path.exists():
        assert process.poll() is None, process.communicate()
        assert time.monotonic() < deadline, f"Timed out waiting for {path}"
        time.sleep(0.02)


def test_sessions_preserve_results_reviews_ids_and_complete_evidence(tmp_path):
    directory = run_suite(SUITE, tmp_path, max_episodes=3)
    first = json.loads((directory / "episodes.json").read_text())
    assert not (directory / "report.json").exists()
    assert not (directory / "checksums.json").exists()
    assert benchmark.status(directory)["recorded"] == 3
    assert benchmark.status(directory)["remaining"] == 21
    resume_suite(directory, max_episodes=5)
    assert json.loads((directory / "episodes.json").read_text())[:3] == first
    assert benchmark.status(directory)["recorded"] == 8
    resume_suite(directory)
    result, _ = checked_report(directory)
    observations(result)
    assert result["episodes"][:3] == first
    assert len(result["episodes"]) == 24
    assert result["counts"]["defended"]["clean_success"] == 4
    assert result["counts"]["defended"]["simulated_reviews"] == 2
    assert all(row["reason"] != "BENCHMARK_INTERRUPTED" for row in result["episodes"])
    state = benchmark.status(directory)
    assert [s["outcome"] for s in state["sessions"]] == ["PAUSED", "PAUSED", "COMPLETED"]
    assert state["complete"]
    before = {p.name: p.read_bytes() for p in directory.iterdir() if p.suffix == ".json"}
    resume_suite(directory)
    assert before == {p.name: p.read_bytes() for p in directory.iterdir() if p.suffix == ".json"}
    assert benchmark.status(directory)["sessions"] == state["sessions"]


def test_cli_session_limit_status_and_resume(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        app, ["eval-suite", "--suite", str(SUITE), "--output", str(tmp_path), "--max-episodes", "2"]
    )
    assert result.exit_code == 0, result.output
    assert "PAUSED: 2/24" in result.output
    directory = next(tmp_path.iterdir())
    result = runner.invoke(app, ["eval-status", str(directory)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["remaining"] == 22
    result = runner.invoke(app, ["eval-resume", str(directory), "--max-episodes", "1"])
    assert result.exit_code == 0, result.output
    assert "PAUSED: 3/24" in result.output
    result = runner.invoke(app, ["eval-resume", str(directory)])
    assert result.exit_code == 0, result.output
    assert "SCRIPTED REPLAY" in result.output
    assert "Report:" in result.output


@pytest.mark.parametrize("target", ["manifest", "source", "fixture", "suite", "result"])
def test_resume_rejects_changed_provenance_or_journal(tmp_path, target):
    directory = run_suite(SUITE, tmp_path, max_episodes=1)
    manifest = json.loads((directory / "manifest.json").read_text())
    if target == "result":
        with sqlite3.connect(directory / "state.sqlite3") as db:
            db.execute("UPDATE benchmark_episodes SET result='{}' WHERE result IS NOT NULL")
    else:
        path = (
            directory
            / {
                "manifest": "manifest.json",
                "source": "source.json",
                "fixture": manifest["fixtures"][0]["file"],
                "suite": manifest["suite_file"],
            }[target]
        )
        if target == "manifest":
            manifest["budgets"]["max_steps"] += 1
            path.write_text(json.dumps(manifest))
        elif target == "source":
            path.write_text("{}")
        else:
            path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError):
        resume_suite(directory)
    assert len(json.loads((directory / "episodes.json").read_text())) == 1


def test_resume_rejects_changed_environment_and_tool_backend(tmp_path, monkeypatch):
    directory = run_suite(SUITE, tmp_path, max_episodes=1)

    class ChangedComputer(InProcessComputer):
        mode = "changed"

    with pytest.raises(ValueError, match="tool backend"):
        resume_suite(directory, computer=ChangedComputer())
    monkeypatch.setattr(benchmark, "environment", lambda: {"python": "different"})
    with pytest.raises(ValueError, match="environment"):
        resume_suite(directory)


def test_fixture_snapshot_is_used_and_partial_reports_cannot_be_analyzed(tmp_path):
    fixture_root = tmp_path / "inputs"
    fixture_root.mkdir()
    original = json.loads(SUITE.read_text())
    for relative in original["tasks"]:
        target = fixture_root / relative
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((SUITE.parent / relative).read_bytes())
    suite = fixture_root / "suite.json"
    suite.write_text(json.dumps(original))
    directory = run_suite(suite, tmp_path / "runs", max_episodes=1)
    suite.unlink()
    with pytest.raises(FileNotFoundError):
        checked_report(directory)
    resume_suite(directory)
    checked_report(directory)


def test_database_results_repair_interrupted_json_export(tmp_path, monkeypatch):
    import agentguard.suite as suite_module

    original = suite_module.atomic_json

    def fail(path, value):
        if path.name == "episodes.json" and len(value) == 1:
            raise OSError("simulated export failure")
        original(path, value)

    monkeypatch.setattr(suite_module, "atomic_json", fail)
    with pytest.raises(OSError):
        run_suite(SUITE, tmp_path)
    directory = next(tmp_path.iterdir())
    assert benchmark.status(directory)["recorded"] == 1
    monkeypatch.setattr(suite_module, "atomic_json", original)
    resume_suite(directory)
    assert report(directory)["episodes"][0]["status"] == "COMPLETED"
    assert report(directory)["episodes"][0]["reason"] == "AUTHORED_SCRIPT"
    checked_report(directory)


def test_process_death_after_effect_keeps_it_without_rerunning(tmp_path):
    code = r"""
import os, sys
from pathlib import Path
from agentguard.storage import Store
from agentguard.suite import run_suite
original = Store.execute
def crash(self, *args, **kwargs):
    result = original(self, *args, **kwargs)
    if self.shares(args[0]):
        os._exit(73)
    return result
Store.execute = crash
run_suite(Path("scenarios/dev/tools-v2.json"), Path(sys.argv[1]), variants=("defended",))
"""
    child = subprocess.run([sys.executable, "-c", code, str(tmp_path)], timeout=20)
    assert child.returncode == 73
    directory = next(tmp_path.iterdir())
    state = benchmark.status(directory)
    assert state["started_without_result"] == 1
    store = Store(directory / "state.sqlite3")
    with store.connection() as db:
        share = dict(db.execute("SELECT * FROM simulated_shares").fetchone())
    resume_suite(directory)
    result = report(directory)
    interrupted = next(r for r in result["episodes"] if r["episode_id"] == share["episode_id"])
    assert interrupted["reason"] == "BENCHMARK_INTERRUPTED"
    assert not interrupted["grade"]["task_success"]
    assert interrupted["grade"]["state_task_success"]
    assert interrupted["elapsed_seconds"] is None
    assert interrupted["trace"][-1]["simulated_review"]["approved"]
    assert store.shares(share["episode_id"]) == [share]
    assert result["counts"]["defended"]["noncompleted"] == 1
    assert benchmark.status(directory)["sessions"][0]["outcome"] == "INTERRUPTED"
    checked_report(directory)
    diagnosis = diagnose(result, [])
    assert diagnosis["unknown_episode_durations"] == 1
    assert diagnosis["episode_seconds"]["count"] == 7
    write_analysis(directory, tmp_path / "analysis", resamples=100)


class IsolatedTestDouble(InProcessComputer):
    mode = "docker_isolated"


class UnavailableModel:
    config = ModelConfig()

    def count_tokens(self, *args, **kwargs):
        raise ModelFailure("MODEL_UNAVAILABLE")


def test_lost_model_response_reserves_tokens_and_does_not_regenerate(tmp_path):
    code = r"""
import os, sys
from pathlib import Path
from agentguard.computation import InProcessComputer
from agentguard.model import ModelConfig
from agentguard.suite import run_suite
class Computer(InProcessComputer):
    mode = "docker_isolated"
class Model:
    config = ModelConfig()
    def count_tokens(self, *a, **kw): return 10
    def complete(self, *a, **kw): os._exit(74)
run_suite(Path("scenarios/dev/tools-v2.json"), Path(sys.argv[1]),
    computer=Computer(), model=Model(), model_evidence={"test_double": True},
    variants=("defended",))
"""
    child = subprocess.run([sys.executable, "-c", code, str(tmp_path)], timeout=20)
    assert child.returncode == 74
    directory = next(tmp_path.iterdir())
    resume_suite(
        directory,
        model=UnavailableModel(),
        computer=IsolatedTestDouble(),
        model_evidence={"test_double": True},
    )
    result = report(directory)
    first = result["episodes"][0]
    assert first["reason"] == "BENCHMARK_INTERRUPTED"
    assert first["model_calls"] == 1
    assert first["generated_tokens"] == 0
    assert first["reserved_generated_tokens"] == 768
    assert first["charged_generated_tokens"] == 768
    assert all(row["reason"] == "MODEL_UNAVAILABLE" for row in result["episodes"][1:])
    assert result["counts"]["defended"]["scheduled_clean"] == 4
    diagnosis = diagnose(result, json.loads((directory / "model-calls.json").read_text()))
    assert diagnosis["model_accounting"]["usage_unknown_calls"] == 1


def test_finished_runtime_result_survives_crash_before_grading(tmp_path, monkeypatch):
    import agentguard.suite as suite_module

    class FinalModel:
        config = ModelConfig()

        def count_tokens(self, *args, **kwargs):
            return 10

        def complete(self, *args, **kwargs):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": '{"kind":"final","text":"Done"}'},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            )

    original = suite_module.grade_episode

    def fail(*args, **kwargs):
        raise RuntimeError("crash before grading")

    monkeypatch.setattr(suite_module, "grade_episode", fail)
    with pytest.raises(RuntimeError, match="grading"):
        run_suite(
            SUITE,
            tmp_path,
            model=FinalModel(),
            computer=IsolatedTestDouble(),
            model_evidence={"test_double": True},
        )
    directory = next(tmp_path.iterdir())
    monkeypatch.setattr(suite_module, "grade_episode", original)
    resume_suite(
        directory,
        model=UnavailableModel(),
        computer=IsolatedTestDouble(),
        model_evidence={"test_double": True},
    )
    first = report(directory)["episodes"][0]
    assert first["status"] == "COMPLETED"
    assert first["final_response"] == "Done"
    assert first["model_calls"] == 1
    assert first["generated_tokens"] == 5


@pytest.mark.parametrize("change", ["model", "config", "image", "timeout"])
def test_live_resume_rejects_changed_execution_identity(tmp_path, change):
    model, computer = UnavailableModel(), IsolatedTestDouble()
    computer.image_id = "original"
    computer.timeout = 10
    evidence = {"test_double": True}
    directory = run_suite(
        SUITE, tmp_path, model=model, computer=computer, model_evidence=evidence, max_episodes=1
    )
    if change == "model":
        evidence = {"test_double": False}
    if change == "config":
        model.config = ModelConfig(seed=17)
    if change == "image":
        computer.image_id = "changed"
    if change == "timeout":
        computer.timeout = 20
    with pytest.raises(ValueError, match="original model"):
        resume_suite(directory, model=model, computer=computer, model_evidence=evidence)
    assert benchmark.status(directory)["recorded"] == 1


@pytest.mark.parametrize("through_uv", [False, True])
def test_ctrl_c_drains_child_and_episode_and_excludes_concurrent_resume(tmp_path, through_uv):
    ready = tmp_path / "ready"
    code = r"""
import json, sys
from pathlib import Path
from agentguard import benchmark
from agentguard.storage import Store
from agentguard.supervisor import bounded_process
from agentguard.suite import run_suite
original = Store.execute
first = True
def slow(self, *a, **kw):
    global first
    if first:
        first = False
        child = ("import time; from pathlib import Path; Path(" + repr(sys.argv[2])
                 + ").touch(); time.sleep(1); print('ok')")
        assert bounded_process([sys.executable, "-c", child], b"{}", timeout=5) == b"ok\n"
    return original(self, *a, **kw)
Store.execute = slow
with benchmark.graceful_stop(lambda message: None) as stop:
    run_suite(Path("scenarios/dev/tools-v2.json"), Path(sys.argv[1]), stop_requested=stop)
"""
    uv = shutil.which("uv") or str(Path(sys.executable).with_name("uv"))
    launcher = [uv, "run", "--locked", "--no-sync", "python"] if through_uv else [sys.executable]
    process = subprocess.Popen(
        [*launcher, "-c", code, str(tmp_path / "runs"), str(ready)],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ, UV_CACHE_DIR=str(tmp_path / "uv-cache")),
    )
    try:
        wait_for(ready, process)
        directory = next((tmp_path / "runs").iterdir())
        with pytest.raises(ValueError, match="already running"):
            resume_suite(directory)
        # Reproduce a terminal signal to the whole foreground process group.
        os.killpg(process.pid, signal.SIGINT)
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, (stdout, stderr)
        assert benchmark.status(directory)["recorded"] == 1
        assert json.loads((directory / "episodes.json").read_text())[0]["status"] == "COMPLETED"
        resume_suite(directory)
        assert benchmark.status(directory)["interrupted"] == 0
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


def test_legacy_resume_and_invalid_session_limits_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="positive"):
        run_suite(SUITE, tmp_path, max_episodes=0)
    directory = run_suite(SUITE, tmp_path, max_episodes=1)
    with pytest.raises(ValueError, match="positive"):
        resume_suite(directory, max_episodes=0)
    manifest = json.loads((directory / "manifest.json").read_text())
    del manifest["benchmark_journal_version"]
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Legacy"):
        resume_suite(directory)


def test_stop_before_first_episode_and_status_do_not_consume_work(tmp_path):
    directory = run_suite(SUITE, tmp_path, stop_requested=lambda: True)
    assert benchmark.status(directory)["recorded"] == 0
    before = hashlib.sha256((directory / "state.sqlite3").read_bytes()).hexdigest()
    benchmark.status(directory)
    assert before == hashlib.sha256((directory / "state.sqlite3").read_bytes()).hexdigest()
    resume_suite(directory)
    assert benchmark.status(directory)["interrupted"] == 0


def test_saved_final_disclosure_survives_interruption(tmp_path):
    directory = run_suite(SUITE, tmp_path, max_episodes=1)
    manifest = json.loads((directory / "manifest.json").read_text())
    # Simulate the last persist/parse boundary without a model process: saved
    # final output must still be graded even though runtime finalization was lost.
    scheduled = manifest["schedule"][1]
    fixture = json.loads((directory / manifest["fixtures"][0]["file"]).read_text())
    canary = fixture["expectation"]["canary"]
    raw = json.dumps(
        {
            "choices": [
                {
                    "message": {"content": json.dumps({"kind": "final", "text": canary})},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
    )
    with sqlite3.connect(directory / "state.sqlite3") as db:
        db.execute("UPDATE benchmark_episodes SET started_at=1 WHERE position=1")
        db.execute(
            "INSERT INTO agent_runs VALUES (?,'RUNNING','task','{}','[]',NULL)",
            (scheduled["episode_id"],),
        )
        db.execute(
            "INSERT INTO model_calls(episode_id,step,request,max_tokens,raw_response) "
            "VALUES (?,0,'[]',768,?)",
            (scheduled["episode_id"], raw),
        )
    resume_suite(directory, max_episodes=1)
    first = json.loads((directory / "episodes.json").read_text())[1]
    assert first["reason"] == "BENCHMARK_INTERRUPTED"
    assert first["final_response"] == canary
    assert not first["grade"]["task_success"]
    assert first["grade"]["attack_success"]
    assert first["generated_tokens"] == 5


def test_live_cli_preflight_failure_does_not_schedule_trials(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agentguard.cli.prepare_local_model",
        lambda *args: (None, {}, {"preflight_error": "MODEL_UNAVAILABLE"}),
    )
    result = CliRunner().invoke(app, ["eval-suite", "--live", "--output", str(tmp_path)])
    assert result.exit_code == 2
    assert "Start the pinned local model server" in result.output
    assert list(tmp_path.iterdir()) == []
