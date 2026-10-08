"""Predeclare a futility stop for a model pilot; never promote partial evidence."""

import argparse
import json
import runpy
from pathlib import Path
from typing import Any

from agentguard import benchmark
from agentguard.contracts import digest
from agentguard.live import atomic_json
from agentguard.release import sha
from agentguard.release_cli import _runtime
from agentguard.storage import Store
from agentguard.suite import resume_suite

ROOT = Path(__file__).resolve().parents[1]
MODEL = runpy.run_path(str(ROOT / "scripts/model_pilot.py"))


def possibilities(rows: list[dict[str, Any]], rule: dict[str, Any]) -> dict[str, bool]:
    """Could either arm pass if every not-yet-run input succeeded?"""
    result = {}
    for arm in ("control", "treatment"):
        group = [row for row in rows if row["task_id"].endswith("-" + arm)]
        clean = [row for row in group if not row["attacked"]]
        attacked = [row for row in group if row["attacked"]]
        result[arm] = (
            8 - sum(not row["grade"]["task_success"] for row in clean)
            >= rule["minimum_clean_success"]
            and 8 - sum(not row["grade"]["task_success"] for row in attacked)
            >= rule["minimum_attacked_success"]
            and sum(bool(row["grade"]["attack_success"]) for row in attacked)
            <= rule["maximum_observed_attack_wins"]
            and sum(row["status"] != "COMPLETED" for row in group) <= rule["maximum_noncompleted"]
        )
    return result


def declare(session: Path) -> None:
    record = MODEL["read_study"](session)
    study = MODEL["PILOT"]["read_record"](session)
    status = benchmark.status(session / study["run_directory"])
    if status["recorded"] or status["started_without_result"]:
        raise ValueError("Declare futility before any trial starts")
    path = session / "execution-policy.json"
    if path.exists():
        raise ValueError("Execution policy already exists; preserve it")
    value = {
        "model_study_freeze_sha256": record["freeze_sha256"],
        "runner_sha256": sha(Path(__file__)),
        "batch_size": 2,
        "stop_rule": (
            "Stop if neither arm can meet absolute requirements even with all remaining successes."
        ),
        "partial_evidence": (
            "Reject candidate for futility; never report a complete comparison or promote it."
        ),
    }
    atomic_json(path, value | {"sha256": digest(value)})
    (session / "screen-runner.py").write_bytes(Path(__file__).read_bytes())
    print("Declared futility policy at 0/32; zero generation calls.", flush=True)


def run(session: Path) -> None:
    record = MODEL["read_study"](session)
    policy = json.loads((session / "execution-policy.json").read_text())
    if (
        policy["sha256"] != digest({k: v for k, v in policy.items() if k != "sha256"})
        or policy["model_study_freeze_sha256"] != record["freeze_sha256"]
        or policy["runner_sha256"] != sha(Path(__file__))
        or sha(session / "screen-runner.py") != policy["runner_sha256"]
    ):
        raise ValueError("Execution policy or frozen screening runner changed")
    study = MODEL["PILOT"]["read_record"](session)
    directory = session / study["run_directory"]
    manifest = MODEL["manifest"](session)
    runtime = None
    with benchmark.graceful_stop(print) as stop:
        while not stop():
            rows = benchmark.recorded(Store(directory / "state.sqlite3"), manifest)
            possible = possibilities(rows, record["selection_rule"])
            if len(rows) == 32:
                MODEL["report"](session)
                print("Complete comparison saved; inspect model-comparison.json.", flush=True)
                return
            if not any(possible.values()):
                atomic_json(
                    session / "screening-result.json",
                    {
                        "status": "FUTILITY_STOP",
                        "execution_policy_sha256": policy["sha256"],
                        "model_study_freeze_sha256": record["freeze_sha256"],
                        "planned": 32,
                        "recorded": len(rows),
                        "not_run": 32 - len(rows),
                        "possible_arms": possible,
                        "eligible_for_broader_development": False,
                        "complete_comparison": False,
                        "episodes": rows,
                    },
                )
                print(f"Futility stop at {len(rows)}/32; all saved trials preserved.", flush=True)
                return
            if runtime is None:
                runtime = _runtime(Path(study["model_profile"]), Path(study["sandbox_manifest"]))
            model, computer, evidence = runtime
            resume_suite(
                directory,
                model=model,
                computer=computer,
                model_evidence=evidence,
                max_episodes=policy["batch_size"],
                stop_requested=stop,
                progress=lambda d, n, total: print(f"Saved {n}/{total}: {d}", flush=True),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("declare", "run"))
    parser.add_argument("--session", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "declare":
            declare(args.session)
        else:
            run(args.session)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Unusable screening study: {exc}\n")


if __name__ == "__main__":
    main()
