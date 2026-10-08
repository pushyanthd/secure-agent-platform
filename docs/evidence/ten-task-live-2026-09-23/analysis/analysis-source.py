"""Offline, schedule-checked analysis of one paired development-suite run."""

import hashlib
import json
import random
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from agentguard.contracts import Profile, digest
from agentguard.live import atomic_json
from agentguard.report_viewer import render_viewer

ANALYSIS_VERSION = "paired-development-v1"
METRICS = ("clean_utility", "attacked_utility", "observed_attack_success")


class Scheduled(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    episode_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    profile: Profile
    attacked: StrictBool


class Grade(BaseModel):
    task_success: StrictBool
    attack_success: StrictBool | None
    evidence: dict[str, Any]


class Observation(Scheduled):
    model_config = ConfigDict(extra="ignore", strict=True)
    status: Literal["COMPLETED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED", "WAITING_APPROVAL"]
    reason: str
    grade: Grade
    trace: list[dict[str, Any]]
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    model_calls: int = Field(ge=0)
    generated_tokens: int = Field(ge=0)


def checked_report(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Checksums detect inconsistency, not forgery by the machine owner."""
    root = root.resolve()
    checksums = json.loads((root / "checksums.json").read_text())
    if not isinstance(checksums, dict):
        raise ValueError("Invalid checksum manifest")
    for name, expected in checksums.items():
        relative = Path(name)
        path = (root / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root):
            raise ValueError("Evidence path escapes the run directory")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Evidence checksum mismatch: {name}")
    required = {"report.json", "manifest.json", "episodes.json", "source.json", "model-calls.json"}
    if not required <= checksums.keys():
        raise ValueError("Missing checksums for required suite evidence")
    report = json.loads((root / "report.json").read_text())
    if report["manifest"] != json.loads((root / "manifest.json").read_text()):
        raise ValueError("Report and manifest disagree")
    if report["episodes"] != json.loads((root / "episodes.json").read_text()):
        raise ValueError("Report and incremental episodes disagree")
    source = json.loads((root / "source.json").read_text())
    if report["manifest"]["source_sha256"] != digest(
        {name: hashlib.sha256(text.encode()).hexdigest() for name, text in source.items()}
    ):
        raise ValueError("Source provenance does not match the manifest")
    for fixture in report["manifest"]["fixtures"]:
        if checksums.get(fixture["file"]) != fixture["sha256"]:
            raise ValueError("Fixture provenance does not match checksums")
    return report, checksums


def observations(report: dict[str, Any]) -> tuple[list[Observation], list[str], list[Profile]]:
    manifest = report["manifest"]
    schedule = [Scheduled.model_validate(row) for row in manifest["schedule"]]
    rows = [Observation.model_validate(row) for row in report["episodes"]]
    expected = {s.episode_id: s.model_dump() for s in schedule}
    if len(expected) != len(schedule) or manifest["scheduled_episodes"] != len(schedule):
        raise ValueError("Schedule has duplicate IDs or an inconsistent denominator")
    if len({r.episode_id for r in rows}) != len(rows) or len(rows) != len(schedule):
        raise ValueError("Missing or duplicate scheduled episode results")
    cells = {(s.task_id, s.profile, s.attacked) for s in schedule}
    variants = list(dict.fromkeys(s.profile for s in schedule))
    tasks = sorted({s.task_id for s in schedule})
    if (
        not tasks
        or manifest["variants"] != variants
        or len(cells) != len(schedule)
        or cells
        != {
            (task, profile, attacked)
            for task in tasks
            for profile in variants
            for attacked in (False, True)
        }
    ):
        raise ValueError("Expected exactly one clean/attacked pair per task and profile")
    for row in rows:
        identity = {key: getattr(row, key) for key in Scheduled.model_fields}
        if expected.get(row.episode_id) != identity:
            raise ValueError("Result does not match its scheduled identity")
        if (row.grade.attack_success is None) == row.attacked:
            raise ValueError("Attack grade must be boolean for attacked inputs and null for clean")
        if row.status != "COMPLETED" and row.grade.task_success:
            raise ValueError("An unfinished episode cannot count as task success")
    return rows, tasks, variants


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def interval(values: list[float]) -> list[float]:
    return [round(percentile(values, q), 6) for q in (0.025, 0.975)]


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def analyze(report: dict[str, Any], *, resamples: int = 5000, seed: int = 42) -> dict[str, Any]:
    if not 100 <= resamples <= 100_000:
        raise ValueError("Use between 100 and 100000 bootstrap resamples")
    rows, tasks, variants = observations(report)
    manifest = report["manifest"]
    fresh = manifest["fresh_inference"]
    if type(fresh) is not bool or manifest["mode"] != (
        "fresh_local_inference" if fresh else "scripted_suite_replay"
    ):
        raise ValueError("Inconsistent inference mode")
    by_cell = {(r.task_id, r.profile, r.attacked): r for r in rows}
    vectors: dict[str, dict[str, list[float]]] = {}
    profiles: dict[str, Any] = {}
    for profile in variants:
        clean = [by_cell[t, profile, False] for t in tasks]
        attacked = [by_cell[t, profile, True] for t in tasks]
        group = clean + attacked
        vectors[profile] = {
            "clean_utility": [float(r.grade.task_success) for r in clean],
            "attacked_utility": [float(r.grade.task_success) for r in attacked],
            "observed_attack_success": [float(bool(r.grade.attack_success)) for r in attacked],
        }
        wins = sum(bool(r.grade.attack_success) for r in attacked)
        unresolved = sum(r.status != "COMPLETED" and not r.grade.attack_success for r in attacked)
        reviews = [t["simulated_review"] for r in group for t in r.trace if "simulated_review" in t]
        profiles[profile] = {
            **{
                metric: rate(int(sum(values)), len(tasks))
                for metric, values in vectors[profile].items()
            },
            "worst_case_attack_success": rate(wins + unresolved, len(tasks)),
            "unresolved_attacked": unresolved,
            "statuses": dict(sorted(Counter(r.status for r in group).items())),
            "simulated_reviews": {
                "requested": len(reviews),
                "approved": sum(r["approved"] is True for r in reviews),
            },
            "elapsed_seconds": {
                "min": min(r.elapsed_seconds for r in group),
                "median": percentile([r.elapsed_seconds for r in group], 0.5),
                "p95": percentile([r.elapsed_seconds for r in group], 0.95),
                "max": max(r.elapsed_seconds for r in group),
            },
            "model_calls": sum(r.model_calls for r in group),
            "generated_tokens": sum(r.generated_tokens for r in group),
        }
    rng = random.Random(seed)
    # Draw each task cluster once per replicate, shared by every treatment/metric.
    # The current suite has one clean and one attacked episode per cluster/profile.
    draws = [[rng.randrange(len(tasks)) for _ in tasks] for _ in range(resamples)] if fresh else []
    boot: dict[str, dict[str, list[float]]] = {}
    for profile in variants:
        boot[profile] = {}
        for metric, values in vectors[profile].items():
            samples = [sum(values[i] for i in draw) / len(tasks) for draw in draws]
            boot[profile][metric] = samples
            profiles[profile][metric]["descriptive_95pct_interval"] = (
                interval(samples) if fresh else None
            )
    comparisons = []
    for reference, treatment in combinations(variants, 2):
        common = [
            t
            for t in tasks
            if by_cell[t, reference, False].grade.task_success
            and by_cell[t, treatment, False].grade.task_success
        ]
        deltas = {}
        for metric in METRICS:
            point = profiles[treatment][metric]["rate"] - profiles[reference][metric]["rate"]
            samples = [
                b - a for a, b in zip(boot[reference][metric], boot[treatment][metric], strict=True)
            ]
            deltas[metric] = {
                "treatment_minus_reference": point,
                "descriptive_95pct_interval": interval(samples) if fresh else None,
            }
        comparisons.append(
            {
                "reference": reference,
                "treatment": treatment,
                "paired_deltas": deltas,
                "common_clean_solved_tasks": common,
                "excluded_tasks": [t for t in tasks if t not in common],
                "conditional_attack_success": {
                    p: rate(
                        sum(bool(by_cell[t, p, True].grade.attack_success) for t in common),
                        len(common),
                    )
                    for p in (reference, treatment)
                },
            }
        )
    failures = []
    for row in rows:
        if row.grade.task_success:
            continue
        evidence = row.grade.evidence
        labels = []
        if row.status != "COMPLETED":
            labels.append("unfinished_episode")
        for key in (
            "missing_reads",
            "missing_read_attempts",
            "missing_final_terms",
            "forbidden_reads",
            "forbidden_tickets",
            "exact_canary_leak",
        ):
            if evidence.get(key):
                labels.append(key)
        if evidence.get("ticket_count") != evidence.get("expected_ticket_count"):
            labels.append("ticket_count_mismatch")
        if any(not matches for matches in evidence.get("matching_tickets", [])):
            labels.append("missing_required_ticket_content")
        if any(
            t.get("execution", {}).get("decision", {}).get("outcome") == "DENY" for t in row.trace
        ):
            labels.append("task_failure_with_denial")
        failures.append(
            {
                "episode_id": row.episode_id,
                "task_id": row.task_id,
                "profile": row.profile,
                "attacked": row.attacked,
                "status": row.status,
                "reason": row.reason,
                "labels": labels or ["other_state_grade_failure"],
            }
        )
    return {
        "analysis_version": ANALYSIS_VERSION,
        "suite_id": manifest["suite_id"],
        "mode": manifest["mode"],
        "provenance": {
            key: manifest[key]
            for key in (
                "split",
                "suite_sha256",
                "source_sha256",
                "policy_version",
                "grader_version",
                "feedback_version",
                "prompts_sha256",
                "output_schema_sha256",
                "containment",
                "tool_image_id",
                "model",
                "budgets",
                "simulated_approvals",
                "reviewer_version",
            )
        },
        "release_evidence": False,
        "scheduled_episodes": len(rows),
        "task_clusters": len(tasks),
        "bootstrap": {
            "unit": "task_id",
            "method": "paired percentile",
            "seed": seed,
            "resamples": resamples if fresh else 0,
        },
        "profiles": profiles,
        "comparisons": comparisons,
        "failures": failures,
        "limits": [
            "Development tasks, one attack and one trial per task/profile; not a release gate.",
            "Intervals resample these authored tasks, not unseen attacks or model randomness.",
            "A degenerate interval (including zero wins) is not evidence of zero population risk.",
            "Failure labels overlap and describe state observations, not causal attribution.",
            "Timing is observed under uncontrolled host load, not a performance benchmark.",
            "Scripted replay does not measure model behavior and receives no bootstrap intervals.",
        ],
    }


def markdown(analysis: dict[str, Any]) -> str:
    def cell(value: dict[str, Any]) -> str:
        return f"{value['numerator']}/{value['denominator']}"

    lines = [
        "# Paired development analysis",
        "",
        f"Mode: `{analysis['mode']}`.",
        "",
        f"Scheduled/accounted: {analysis['scheduled_episodes']}; "
        f"task clusters: {analysis['task_clusters']}.",
        "",
        "| Profile | Clean utility | Attacked utility | Observed attack wins | Worst-case wins |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, p in analysis["profiles"].items():
        lines.append(
            f"| {name} | {cell(p['clean_utility'])} | {cell(p['attacked_utility'])} | "
            f"{cell(p['observed_attack_success'])} | {cell(p['worst_case_attack_success'])} |"
        )
    lines += [
        "",
        "## Paired comparisons",
        "",
        "Differences are treatment minus reference, in percentage points. "
        "Negative attack-success differences favor the treatment.",
        "",
    ]
    for pair in analysis["comparisons"]:
        lines += [f"### {pair['treatment']} versus {pair['reference']}", ""]
        for metric, value in pair["paired_deltas"].items():
            bounds = value["descriptive_95pct_interval"]
            suffix = (
                f"; descriptive 95% interval [{100 * bounds[0]:.1f}, {100 * bounds[1]:.1f}]"
                if bounds
                else "; scripted replay, no interval"
            )
            lines.append(f"- {metric}: {100 * value['treatment_minus_reference']:+.1f} pp{suffix}.")
        lines += [
            "",
            f"Common clean-solved tasks: {len(pair['common_clean_solved_tasks'])}; "
            f"excluded: {len(pair['excluded_tasks'])}.",
        ]
        for name, value in pair["conditional_attack_success"].items():
            lines.append(
                f"Conditional observed attack wins, {name}: {cell(value)}"
                + (" (undefined)." if value["rate"] is None else ".")
            )
        lines.append("")
    lines += ["## Limits", "", *[f"- {limit}" for limit in analysis["limits"]], ""]
    return "\n".join(lines)


def write_analysis(root: Path, output: Path, *, resamples: int = 5000, seed: int = 42) -> Path:
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Write analysis outside the immutable input evidence directory")
    report, checksums = checked_report(root)
    result = analyze(report, resamples=resamples, seed=seed)
    result["input_checksums"] = checksums
    result["analysis_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    tasks = {
        f["id"]: json.loads((root / f["file"]).read_text())["task"]
        for f in report["manifest"]["fixtures"]
    }
    viewer = render_viewer(report, result, tasks)
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "analysis.json", result)
    (output / "analysis.md").write_text(markdown(result))
    (output / "analysis-source.py").write_bytes(Path(__file__).read_bytes())
    (output / "viewer-source.py").write_bytes(
        Path(__file__).with_name("report_viewer.py").read_bytes()
    )
    (output / "explorer.html").write_text(viewer)
    atomic_json(
        output / "checksums.json",
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())},
    )
    return output
