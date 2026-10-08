"""Development-only paired local inference smoke; no held-out or release claims."""

import hashlib
import json
import platform
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from agentguard.contracts import Document, Profile, canonical_json, digest
from agentguard.model import LocalModel, ModelConfig, ModelFailure
from agentguard.model_setup import load_profile, model_paths, sha256_file, verify_runtime
from agentguard.policy import POLICY_VERSION
from agentguard.replay import Scenario, grade
from agentguard.response_policy import RESPONSE_POLICY_VERSION
from agentguard.runtime import (
    BASE_PROMPT,
    FEEDBACK_VERSION,
    HARDENED_PROMPT,
    Budgets,
    Runtime,
    turn_schema,
)
from agentguard.storage import Store
from agentguard.supervisor import DockerComputer


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical_json(value) + "\n")
    temporary.replace(path)


def prepare_local_model(
    root: Path, profile_path: Path
) -> tuple[LocalModel, dict[str, Any], dict[str, Any]]:
    profile = load_profile(profile_path)
    if profile["runtime"].get("format") == "windows-cuda-zip":
        from agentguard.pc_model import prepare_pc_model

        return prepare_pc_model(root, profile)
    for spec, path in zip(
        (profile["model"], profile["runtime"]), model_paths(root, profile), strict=True
    ):
        if sha256_file(path) != spec["sha256"]:
            raise ValueError("Model/runtime artifact checksum mismatch")
    model = LocalModel(ModelConfig.model_validate(profile["inference"]))
    _, archive = model_paths(root, profile)
    verify_runtime(archive, root / "artifacts/runtime" / profile["runtime"]["release"])
    server: dict[str, Any]
    try:
        props = json.loads(model.request("/props", None, timeout=10))
        expected_build = profile["runtime"]["release"] + "-" + profile["runtime"]["commit"][:9]
        if (
            props["model_alias"] != model.config.model
            or Path(props["model_path"]).resolve() != model_paths(root, profile)[0].resolve()
            or props["build_info"] != expected_build
            or props["default_generation_settings"]["n_ctx"] != model.config.context_tokens
            or props["total_slots"] != 1
            or not props["chat_template"]
        ):
            raise ValueError("Running server does not match the selected model profile")
        server = {
            "build_info": props["build_info"],
            "chat_template": props["chat_template"],
            "chat_template_sha256": digest(props["chat_template"]),
            "generation_defaults": props["default_generation_settings"],
            "non_thinking": True,
            "template_source": "embedded in checksum-verified GGUF",
            "total_slots": props["total_slots"],
        }
    except ModelFailure as exc:
        # Still schedule and account for all trials if the configured runtime is unavailable.
        server = {"preflight_error": str(exc)}
    return model, profile, server


def run_live_smoke(
    scenario_path: Path,
    profile_path: Path,
    sandbox_manifest: Path,
    output_root: Path,
    *,
    root: Path,
) -> Path:
    scenario_bytes = scenario_path.read_bytes()
    scenario = Scenario.model_validate_json(scenario_bytes)
    if scenario.attack_document_id not in {doc.id for doc in scenario.documents}:
        raise ValueError("Attack insertion point does not exist")
    model, profile, server = prepare_local_model(root, profile_path)
    computer = DockerComputer.from_manifest(sandbox_manifest)
    budgets = Budgets(context_tokens=model.config.context_tokens)
    run_dir = output_root / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=False)
    source = {path.name: path.read_text() for path in sorted(Path(__file__).parent.glob("*.py"))}
    atomic_json(run_dir / "source.json", source)
    (run_dir / "scenario.json").write_bytes(scenario_bytes)
    store = Store(run_dir / "state.sqlite3", computer=computer)
    # Persist the complete schedule first. A killed process leaves discoverable unfinished rows.
    schedule: list[dict[str, Any]] = []
    for selected in ("baseline", "prompt_only", "defended"):
        policy: Profile = selected
        for attacked in (False, True):
            documents = tuple(
                Document.model_validate(
                    document.model_dump()
                    | {"body": document.body + "\n\n" + scenario.attack_payload}
                )
                if attacked and document.id == scenario.attack_document_id
                else document
                for document in scenario.documents
            )
            episode = store.create_episode(
                scenario.contract,
                documents,
                scenario.projects,
                experimental_profile=policy,
                max_actions=budgets.max_steps,
            )
            schedule.append({"episode_id": episode, "profile": policy, "attacked": attacked})
    manifest = {
        "mode": "fresh_local_inference",
        "fresh_inference": True,
        "suite": "development_feasibility_single_task",
        "release_evidence": False,
        "scheduled_episodes": len(schedule),
        "simulated_approvals": False,
        "approval_behavior": "pause_without_automatic_review",
        "containment": computer.mode,
        "tool_image_id": computer.image_id,
        "model_profile": profile,
        "server": server,
        "budgets": budgets.model_dump(),
        "scenario_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        "policy_version": POLICY_VERSION,
        "response_policy_version": RESPONSE_POLICY_VERSION,
        "feedback_version": FEEDBACK_VERSION,
        "source_sha256": digest(
            {name: hashlib.sha256(content.encode()).hexdigest() for name, content in source.items()}
        ),
        "prompts_sha256": digest({"base": BASE_PROMPT, "hardened": HARDENED_PROMPT}),
        "output_schema_sha256": digest(json.dumps(turn_schema(), separators=(",", ":"))),
        "hardware": {"os": platform.system(), "architecture": platform.machine()},
        "python": platform.python_version(),
        "runtime_attestation": "operator-managed local server; artifact hashes verified on disk",
        "schedule": schedule,
    }
    atomic_json(run_dir / "manifest.json", manifest)
    rows = []
    for scheduled in schedule:
        result = Runtime(store, model, budgets).run(scheduled["episode_id"], scenario.task)
        state_grade = grade(
            store.tickets(scheduled["episode_id"]),
            result["final_response"],
            scenario.predicates,
            attacked=scheduled["attacked"],
        )
        rows.append(
            scheduled
            | result
            | {
                "grade": state_grade
                | {
                    "state_task_success": state_grade["task_success"],
                    "task_success": state_grade["task_success"] and result["status"] == "COMPLETED",
                }
            }
        )
        atomic_json(run_dir / "episodes.json", rows)
    counts = {}
    for selected in ("baseline", "prompt_only", "defended"):
        group = [row for row in rows if row["profile"] == selected]
        attacked_rows = [row for row in group if row["attacked"]]
        wins = sum(bool(row["grade"]["attack_success"]) for row in attacked_rows)
        unresolved = sum(
            row["status"] != "COMPLETED" and not row["grade"]["attack_success"]
            for row in attacked_rows
        )
        counts[selected] = {
            "scheduled_clean": 1,
            "scheduled_attacked": 1,
            "clean_success": sum(
                row["grade"]["task_success"] for row in group if not row["attacked"]
            ),
            "attacked_task_success": sum(row["grade"]["task_success"] for row in attacked_rows),
            "observed_attack_wins": wins,
            "unresolved_attacked": unresolved,
            "worst_case_attack_wins": wins + unresolved,
            "completed": sum(row["status"] == "COMPLETED" for row in group),
            "noncompleted": sum(row["status"] != "COMPLETED" for row in group),
        }
    report = {"manifest": manifest, "counts": counts, "episodes": rows}
    atomic_json(run_dir / "report.json", report)
    lines = [
        "# Live local-model development smoke",
        "",
        "One development task, one payload, one trial per cell. "
        "This is feasibility evidence, not a security benchmark or a release gate.",
        "",
        "| Profile | Input | Status | Task success | Observed attack success | Seconds |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['profile']} | {'attacked' if row['attacked'] else 'clean'} | "
            f"{row['status']} | {row['grade']['task_success']} | "
            f"{row['grade']['attack_success'] if row['attacked'] else 'N/A'} | "
            f"{row['elapsed_seconds']:.2f} |"
        )
    lines += [
        "",
        "All 6 scheduled episodes are included, including failures and approval waits.",
        "JSON includes unresolved counts and worst-case attacker wins. "
        "No automatic approvals, response cache, or provider fallback.",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(lines))
    # Include raw model-call evidence in a portable snapshot, not a live WAL copy.
    with store.connection() as db, sqlite3.connect(run_dir / "evidence.sqlite3") as snapshot:
        db.backup(snapshot)
        atomic_json(
            run_dir / "model-calls.json",
            [dict(row) for row in db.execute("SELECT * FROM model_calls ORDER BY rowid")],
        )
    atomic_json(
        run_dir / "checksums.json",
        {
            name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
            for name in (
                "manifest.json",
                "episodes.json",
                "report.json",
                "report.md",
                "evidence.sqlite3",
                "model-calls.json",
                "source.json",
                "scenario.json",
            )
        },
    )
    return run_dir
