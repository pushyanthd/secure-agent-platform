"""Paired development evaluation with explicit replay/live modes and exact-action review."""

import hashlib
import json
import platform
import sqlite3
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentguard import benchmark
from agentguard.completion import CompletionPlan
from agentguard.computation import Computer, ToolFailure
from agentguard.contracts import Profile, digest
from agentguard.decision_review import ReviewVersion
from agentguard.live import atomic_json
from agentguard.model import LocalModel
from agentguard.policy import POLICY_VERSION
from agentguard.response_policy import RESPONSE_POLICY_VERSION, deliver_response
from agentguard.reviewer import REVIEWER_VERSION, ExactActionReviewer
from agentguard.runtime import (
    BASE_PROMPT,
    FEEDBACK_VERSION,
    HARDENED_PROMPT,
    Budgets,
    Runtime,
    turn_schema,
)
from agentguard.scenarios import (
    GRADER_VERSION,
    DevelopmentTask,
    Script,
    attack_manifest,
    attack_variants,
    episode_documents,
    grade_episode,
    load_suite,
    select_attack,
)
from agentguard.storage import ReviewRejected, Store

VARIANTS: tuple[Profile, ...] = ("baseline", "prompt_only", "defended")


def run_script(
    store: Store, episode: str, script: Script, reviewer: ExactActionReviewer | None
) -> dict[str, Any]:
    start = time.monotonic()
    trace: list[dict[str, Any]] = []
    status, reason, final = "COMPLETED", "AUTHORED_SCRIPT", script.final_response
    try:
        for index, action in enumerate(script.actions):
            key = f"step-{index}:call-0"
            result = store.execute(episode, key, action)
            entry: dict[str, Any] = {"action": action.model_dump(mode="json")}
            if result.decision.outcome == "REQUIRE_APPROVAL" and reviewer is not None:
                assert result.approval_id is not None
                approved = reviewer.review(store, result.approval_id)
                entry["simulated_review"] = {
                    "approved": approved,
                    "initial_decision": result.decision.model_dump(),
                }
                result = store.execute(
                    episode, key, action, approval_id=result.approval_id if approved else None
                )
            entry["execution"] = result.model_dump(mode="json")
            trace.append(entry)
            if result.decision.outcome == "REQUIRE_APPROVAL":
                status, reason, final = "WAITING_APPROVAL", "SENSITIVE_WRITE", ""
                break
            if result.decision.reason in ("CANCELLED", "BUDGET_EXHAUSTED"):
                status, reason, final = result.decision.reason, result.decision.reason, ""
                break
    except (ToolFailure, ReviewRejected) as exc:
        status, reason, final = "FAILED", type(exc).__name__, ""
    response = {}
    if status == "COMPLETED":
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            decision = store.authorize_response(db, episode)
            response = {"response_decision": decision.model_dump(mode="json")}
            final = deliver_response(final, decision)
            if decision.outcome == "DENY":
                final, reason = "", decision.reason
                if reason == "CANCELLED":
                    status = "CANCELLED"
    return {
        **response,
        "status": status,
        "reason": reason,
        "final_response": final,
        "trace": trace,
        "model_calls": 0,
        "generated_tokens": 0,
        "elapsed_seconds": round(time.monotonic() - start, 4),
    }


def summarize(rows: list[dict[str, Any]], variants: tuple[Profile, ...]) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    for variant in variants:
        group = [r for r in rows if r["profile"] == variant]
        clean = [r for r in group if not r["attacked"]]
        attacked = [r for r in group if r["attacked"]]
        wins = sum(bool(r["grade"]["attack_success"]) for r in attacked)
        unresolved = sum(
            r["status"] != "COMPLETED" and not r["grade"]["attack_success"] for r in attacked
        )
        counts[variant] = {
            "scheduled_clean": len(clean),
            "scheduled_attacked": len(attacked),
            "clean_success": sum(r["grade"]["task_success"] for r in clean),
            "attacked_task_success": sum(r["grade"]["task_success"] for r in attacked),
            "observed_attack_wins": wins,
            "unresolved_attacked": unresolved,
            "worst_case_attack_wins": wins + unresolved,
            "noncompleted": sum(r["status"] != "COMPLETED" for r in group),
            "response_denials_clean": sum(
                r.get("response_decision", {}).get("outcome") == "DENY" for r in clean
            ),
            "response_denials_attacked": sum(
                r.get("response_decision", {}).get("outcome") == "DENY" for r in attacked
            ),
            "verified_effect_receipts": sum(
                r.get("response_decision", {}).get("reason") == "VERIFIED_EFFECT_RECEIPT"
                for r in group
            ),
            "simulated_reviews": sum("simulated_review" in t for r in group for t in r["trace"]),
        }
    return counts


def run_suite(
    suite_path: Path,
    output_root: Path,
    *,
    computer: Computer | None = None,
    variants: tuple[Profile, ...] = VARIANTS,
    simulate_approvals: bool = True,
    model: LocalModel | None = None,
    model_evidence: dict[str, Any] | None = None,
    progress: Callable[[Path, int, int], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
    max_episodes: int | None = None,
    release_freeze: dict[str, Any] | None = None,
    decision_review_tasks: tuple[str, ...] = (),
    decision_review_version: ReviewVersion = "independent-v1",
    completion_plans: dict[str, CompletionPlan] | None = None,
) -> Path:
    if max_episodes is not None and max_episodes < 1:
        raise ValueError("Session episode limit must be positive")
    if not variants or len(set(variants)) != len(variants) or not set(variants) <= set(VARIANTS):
        raise ValueError("Select unique known benchmark variants")
    if model is not None and (computer is None or computer.mode != "docker_isolated"):
        raise ValueError("Live suite evaluation requires isolated tools")
    if model is not None and model_evidence is None:
        raise ValueError("Live evaluation requires pinned model evidence")
    suite, fixtures = load_suite(suite_path, allow_held_out=release_freeze is not None)
    if len(set(decision_review_tasks)) != len(decision_review_tasks) or not set(
        decision_review_tasks
    ) <= {task.id for _, _, task in fixtures}:
        raise ValueError("Decision review requires distinct known task IDs")
    if decision_review_version not in ("independent-v1", "structured-v2"):
        raise ValueError("Unknown decision review version")
    if completion_plans is not None and (
        not completion_plans
        or not set(completion_plans) <= {task.id for _, _, task in fixtures}
        or not all(isinstance(plan, CompletionPlan) for plan in completion_plans.values())
    ):
        raise ValueError("Completion plans require known task IDs and typed requirements")
    if release_freeze is not None and (decision_review_tasks or completion_plans):
        raise ValueError("Development review cannot alter a frozen release protocol")
    if release_freeze is not None:
        from agentguard.release import protocol, verify_suite

        verify_suite(release_freeze, suite_path)
        if model is None or computer is None or model_evidence is None:
            raise ValueError("Frozen releases require fresh inference and isolated tools")
        if variants != ("baseline", "defended") or not simulate_approvals:
            raise ValueError("Frozen release requires baseline/defended and simulated review")
        if release_freeze["protocol"] != protocol(
            model_evidence,
            model.config.model_dump(mode="json"),
            getattr(computer, "image_id", ""),
            getattr(computer, "timeout", 0),
        ):
            raise ValueError("Current execution protocol differs from frozen experiment")
    run_dir = output_root / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=False)
    store = Store(run_dir / "state.sqlite3", computer=computer)
    budgets = Budgets(context_tokens=model.config.context_tokens) if model else Budgets()
    source = {p.name: p.read_text() for p in sorted(Path(__file__).parent.glob("*.py"))}
    atomic_json(run_dir / "source.json", source)
    fixture_root = run_dir / "fixtures"
    fixture_root.mkdir()
    (fixture_root / suite_path.name).write_bytes(suite_path.read_bytes())
    fixture_manifest = []
    tasks = {task.id: task for _, _, task in fixtures}
    schedule: list[dict[str, Any]] = []
    for relative, raw, task in fixtures:
        snapshot = fixture_root / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(raw)
        fixture_manifest.append(
            {
                "id": task.id,
                "family": task.family,
                "file": str(snapshot.relative_to(run_dir)),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "attack_family": task.attack_family,
                "attack_document_id": task.attack_document_id,
                "attack_payload_sha256": hashlib.sha256(task.attack_payload.encode()).hexdigest(),
                "attacks": attack_manifest(task),
            }
        )
        for variant in variants:
            for attack_id in (None, *(a.id for a in attack_variants(task))):
                attacked = attack_id is not None
                selected = select_attack(task, attack_id)
                episode = store.create_episode(
                    task.contract,
                    episode_documents(selected, attacked=attacked),
                    task.projects,
                    tickets=task.initial_tickets,
                    experimental_profile=variant,
                    max_actions=budgets.max_steps,
                )
                schedule.append(
                    {
                        "episode_id": episode,
                        "task_id": task.id,
                        "profile": variant,
                        "attacked": attacked,
                        "attack_id": attack_id,
                    }
                )
    manifest = {
        "schema_version": 2,
        "benchmark_journal_version": 1,
        "suite_file": str((fixture_root / suite_path.name).relative_to(run_dir)),
        "environment": benchmark.environment(),
        "suite_id": suite.id,
        "split": suite.split,
        "hardware": {"os": platform.system(), "architecture": platform.machine()},
        "python": platform.python_version(),
        "mode": "fresh_local_inference" if model else "scripted_suite_replay",
        "fresh_inference": model is not None,
        "release_evidence": release_freeze is not None,
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "source_sha256": digest(
            {name: hashlib.sha256(text.encode()).hexdigest() for name, text in source.items()}
        ),
        "fixtures": fixture_manifest,
        "schedule": schedule,
        "scheduled_episodes": len(schedule),
        "variants": variants,
        "containment": store.computer.mode,
        "tool_image_id": getattr(store.computer, "image_id", None),
        "tool_timeout": getattr(store.computer, "timeout", None),
        "model": model_evidence,
        "model_config": model.config.model_dump(mode="json") if model else None,
        "budgets": budgets.model_dump(),
        "policy_version": POLICY_VERSION,
        "response_policy_version": RESPONSE_POLICY_VERSION,
        "grader_version": GRADER_VERSION,
        "feedback_version": FEEDBACK_VERSION,
        "prompts_sha256": digest({"base": BASE_PROMPT, "hardened": HARDENED_PROMPT}),
        "output_schema_sha256": digest(json.dumps(turn_schema(), separators=(",", ":"))),
        "simulated_approvals": simulate_approvals,
        "reviewer_version": REVIEWER_VERSION if simulate_approvals else None,
    }
    if release_freeze is not None:
        from agentguard.release import verify_manifest

        manifest["release_freeze"] = release_freeze
        manifest["validation_sha256"] = release_freeze["protocol"]["validation_sha256"]
        verify_manifest(release_freeze, manifest)
        atomic_json(run_dir / "suite_freeze.json", release_freeze)
    if decision_review_tasks or completion_plans:
        treatments: dict[str, dict[str, Any]] = {
            task_id: {"decision_review": decision_review_version}
            for task_id in decision_review_tasks
        }
        for task_id, plan in (completion_plans or {}).items():
            treatments.setdefault(task_id, {})["completion_plan"] = plan.model_dump(mode="json")
        manifest["runtime_treatments"] = treatments
    atomic_json(run_dir / "manifest.json", manifest)
    with benchmark.exclusive_run(run_dir):
        benchmark.initialize(store, manifest)
        _continue_suite(
            run_dir,
            store,
            manifest,
            tasks,
            model=model,
            progress=progress,
            stop_requested=stop_requested,
            max_episodes=max_episodes,
        )
    return run_dir


def resume_suite(
    run_dir: Path,
    *,
    computer: Computer | None = None,
    model: LocalModel | None = None,
    model_evidence: dict[str, Any] | None = None,
    progress: Callable[[Path, int, int], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
    max_episodes: int | None = None,
) -> Path:
    if max_episodes is not None and max_episodes < 1:
        raise ValueError("Session episode limit must be positive")
    with benchmark.exclusive_run(run_dir):
        manifest = json.loads((run_dir / "manifest.json").read_text())
        suite_path = benchmark.verify_files(run_dir, manifest)
        frozen = manifest.get("release_freeze")
        if manifest.get("release_evidence") or frozen is not None:
            from agentguard.release import validation_hash, verify_manifest, verify_suite

            if frozen is None:
                raise ValueError("Release resume requires its frozen experiment")
            verify_manifest(frozen, manifest)
            verify_suite(frozen, suite_path)
            if frozen["protocol"]["validation_sha256"] != validation_hash():
                raise ValueError("Release validation assets changed")
            if json.loads((run_dir / "suite_freeze.json").read_text()) != frozen:
                raise ValueError("Release freeze snapshot changed")
        _, fixtures = load_suite(suite_path, allow_held_out=frozen is not None)
        if not (run_dir / "state.sqlite3").is_file():
            raise ValueError("Benchmark state database is missing")
        store = Store(run_dir / "state.sqlite3", computer=computer)
        expected = (
            manifest["fresh_inference"],
            manifest["model"],
            manifest["model_config"],
            manifest["containment"],
            manifest["tool_image_id"],
            manifest["tool_timeout"],
        )
        actual = (
            model is not None,
            model_evidence,
            model.config.model_dump(mode="json") if model else None,
            store.computer.mode,
            getattr(store.computer, "image_id", None),
            getattr(store.computer, "timeout", None),
        )
        if expected != actual:
            raise ValueError("Resume requires the original model, settings, and tool backend")
        _continue_suite(
            run_dir,
            store,
            manifest,
            {task.id: task for _, _, task in fixtures},
            model=model,
            progress=progress,
            stop_requested=stop_requested,
            max_episodes=max_episodes,
        )
    return run_dir


def valid_treatment(setting: Any) -> bool:
    if (
        not isinstance(setting, dict)
        or not setting
        or not set(setting) <= {"decision_review", "completion_plan"}
    ):
        return False
    if "decision_review" in setting and setting["decision_review"] not in (
        "independent-v1",
        "structured-v2",
    ):
        return False
    if "completion_plan" in setting:
        try:
            CompletionPlan.model_validate(setting["completion_plan"])
        except ValidationError:
            return False
    return True


def _continue_suite(
    run_dir: Path,
    store: Store,
    manifest: dict[str, Any],
    tasks: dict[str, DevelopmentTask],
    *,
    model: LocalModel | None,
    progress: Callable[[Path, int, int], None] | None,
    stop_requested: Callable[[], bool] | None,
    max_episodes: int | None,
) -> None:
    schedule = manifest["schedule"]
    budgets = Budgets.model_validate(manifest["budgets"])
    treatments = manifest.get("runtime_treatments", {})
    if (
        not isinstance(treatments, dict)
        or not set(treatments) <= set(tasks)
        or any(not valid_treatment(setting) for setting in treatments.values())
    ):
        raise ValueError("Invalid frozen runtime treatment")
    rows = benchmark.recorded(store, manifest)
    # Completed evidence is immutable; a redundant resume is a no-op.
    if len(rows) == len(schedule) and (run_dir / "checksums.json").is_file():
        from agentguard.analysis import checked_report

        checked_report(run_dir)
        if progress is not None:
            progress(run_dir, len(rows), len(schedule))
        return
    atomic_json(run_dir / "episodes.json", rows)
    session = benchmark.start_session(store, len(rows))
    initial_count = len(rows)
    if progress is not None:
        progress(run_dir, len(rows), len(schedule))
    for scheduled in schedule[len(rows) :]:
        if (stop_requested is not None and stop_requested()) or (
            max_episodes is not None and len(rows) - initial_count >= max_episodes
        ):
            break
        task = select_attack(
            tasks[scheduled["task_id"]],
            scheduled.get("attack_id", "primary" if scheduled["attacked"] else None),
        )
        task_budgets = Budgets.model_validate(budgets.model_dump() | treatments.get(task.id, {}))
        reviewer = (
            ExactActionReviewer(task.contract, task.review_contract)
            if manifest["simulated_approvals"]
            else None
        )
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            entry = db.execute(
                "SELECT started_at FROM benchmark_episodes WHERE episode_id=?",
                (scheduled["episode_id"],),
            ).fetchone()
            interrupted = entry["started_at"] is not None
            if not interrupted:
                db.execute(
                    "UPDATE benchmark_episodes SET started_at=? WHERE episode_id=?",
                    (time.time(), scheduled["episode_id"]),
                )
        if interrupted:
            result = benchmark.interrupted_result(store, scheduled, task, task_budgets)
        elif model is not None:
            result = Runtime(store, model, task_budgets, reviewer=reviewer).run(
                scheduled["episode_id"], task.task
            )
        else:
            result = run_script(
                store,
                scheduled["episode_id"],
                task.attacked_script if scheduled["attacked"] else task.clean_script,
                reviewer,
            )
        state_grade = grade_episode(
            store,
            scheduled["episode_id"],
            result["final_response"],
            task.expectation,
            attacked=scheduled["attacked"],
        )
        row = (
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
        benchmark.save_result(store, row)
        rows.append(row)
        atomic_json(run_dir / "episodes.json", rows)
        if progress is not None:
            progress(run_dir, len(rows), len(schedule))
    complete = len(rows) == len(schedule)
    benchmark.end_session(store, session, len(rows), "COMPLETED" if complete else "PAUSED")
    state = benchmark.status(run_dir)
    atomic_json(run_dir / "progress.json", state)
    if not complete:
        return
    _export_suite(run_dir, store, manifest, rows)


def _export_suite(
    run_dir: Path, store: Store, manifest: dict[str, Any], rows: list[dict[str, Any]]
) -> None:
    report = {
        "manifest": manifest,
        "counts": summarize(rows, tuple(manifest["variants"])),
        "episodes": rows,
    }
    atomic_json(run_dir / "report.json", report)
    label = (
        "Live frozen release suite"
        if manifest.get("release_evidence")
        else "Live development suite"
        if manifest["fresh_inference"]
        else "Scripted suite replay — no model inference"
    )
    lines = [
        f"# {label}",
        "",
        "Frozen held-out comparison. Use release-gate for the product objectives."
        if manifest.get("release_evidence")
        else "Development fixtures; not a held-out release benchmark.",
        "",
        "| Task | Profile | Input | Status | Task success | Attack success |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task_id']} | {row['profile']} | "
            f"{row.get('attack_id') or ('attacked' if row['attacked'] else 'clean')} | "
            f"{row['status']} | "
            f"{row['grade']['task_success']} | {row['grade']['attack_success']} |"
        )
    lines += [
        "",
        f"Scheduled: {len(manifest['schedule'])}. Accounted for: {len(rows)}.",
        f"Simulated approvals enabled: {manifest['simulated_approvals']}.",
        "Session and interruption history: progress.json. Interrupted episodes retain their "
        "effects and token reservations; unknown elapsed time is null.",
        "Authored replay is contract/grader evidence, not measured model utility or security."
        if not manifest["fresh_inference"]
        else "Fresh local inference; all failures remain in denominators.",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(lines))
    with store.connection() as db, sqlite3.connect(run_dir / "evidence.sqlite3") as snapshot_db:
        db.backup(snapshot_db)
        atomic_json(
            run_dir / "model-calls.json", [dict(r) for r in db.execute("SELECT * FROM model_calls")]
        )
    atomic_json(
        run_dir / "checksums.json",
        {
            str(p.relative_to(run_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(run_dir.rglob("*"))
            if p.is_file() and (p.suffix in (".json", ".md") or p.name == "evidence.sqlite3")
        },
    )
