"""Small, explicitly scoped policy microbenchmark over authoritative fixture snapshots."""

import hashlib
import platform
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from agentguard.analysis import percentile
from agentguard.contracts import Action, TaskContract, digest
from agentguard.live import atomic_json
from agentguard.policy import POLICY_VERSION
from agentguard.scenarios import episode_documents, load_suite
from agentguard.storage import Store
from agentguard.tool_state import ToolState, resolve


def measure_policy(suite_path: Path, *, samples: int = 1000, warmup: int = 100) -> dict[str, Any]:
    if not 100 <= samples <= 100000 or not 0 <= warmup <= 10000:
        raise ValueError("Use 100–100000 samples and 0–10000 warmup calls")
    suite, fixtures = load_suite(suite_path)
    cases: list[tuple[str, TaskContract, Action, ToolState, bool]] = []
    source_hashes = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ("policy.py", "contracts.py", "tool_state.py", "policy_benchmark.py")
    }
    # Resolve snapshots before timing. Never execute tools or mutate ticket/share state.
    with tempfile.TemporaryDirectory(prefix="agentguard-policy-") as directory:
        store = Store(Path(directory) / "state.sqlite3")
        for _, _, task in fixtures:
            for attacked in (False, True):
                episode = store.create_episode(
                    task.contract,
                    episode_documents(task, attacked=attacked),
                    task.projects,
                    tickets=task.initial_tickets,
                )
                script = task.attacked_script if attacked else task.clean_script
                with store.connection() as db:
                    for action in script.actions:
                        state = resolve(db, episode, task.contract, "defended", action)
                        # Both taint states exercise allowed, denied, and reviewed decisions.
                        for confidential in (False, True):
                            cases.append((episode, task.contract, action, state, confidential))
    if not cases:
        raise ValueError("Policy benchmark needs at least one scripted proposal")

    def decide(index: int) -> tuple[str, str]:
        episode, contract, action, state, confidential = cases[index % len(cases)]
        decision = state.decision(
            episode_id=episode,
            contract=contract,
            profile="defended",
            action=action,
            confidential=confidential,
        )
        return action.tool, decision.outcome

    for index in range(warmup):
        decide(index)
    durations: list[float] = []
    tools: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    for index in range(samples):
        started = time.perf_counter_ns()
        tool, outcome = decide(index)
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
        tools[tool] += 1
        outcomes[outcome] += 1
    return {
        "schema_version": 1,
        "mode": "pure_policy_microbenchmark",
        "fresh_model_trials": 0,
        "suite_id": suite.id,
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "fixtures": {task.id: hashlib.sha256(raw).hexdigest() for _, raw, task in fixtures},
        "source_sha256": source_hashes,
        "policy_version": POLICY_VERSION,
        "hardware": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "samples": samples,
        "warmup_calls": warmup,
        "case_count": len(cases),
        "tool_counts": dict(tools),
        "outcome_counts": dict(outcomes),
        "milliseconds": {
            "min": min(durations),
            "median": percentile(durations, 0.5),
            "p95": percentile(durations, 0.95),
            "max": max(durations),
        },
        "raw_milliseconds": durations,
        "initial_p95_objective_ms": 20,
        "within_initial_p95_objective": percentile(durations, 0.95) < 20,
        "limits": [
            "Includes deterministic policy rules and canonical full-snapshot hashing.",
            "Excludes parsing, resource resolution, SQLite, tools, and inference.",
            "Cases reuse fixture snapshots in two sensitivity states; this is not task execution.",
            "Observed on one uncontrolled local host, not a service latency SLA or CI timing gate.",
        ],
    }


def write_policy_benchmark(suite: Path, output: Path, *, samples: int = 1000) -> Path:
    result = measure_policy(suite, samples=samples)
    result["result_sha256"] = digest(result)
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "policy-benchmark.json", result)
    for name in result["source_sha256"]:
        (output / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    atomic_json(
        output / "checksums.json",
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())},
    )
    return output
