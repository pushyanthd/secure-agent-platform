"""Offline runtime diagnostics; reconcile saved model usage with scheduled outcomes."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, get_args

from pydantic import BaseModel, ConfigDict, Field

from agentguard.analysis import checked_report, observations, percentile
from agentguard.contracts import Tool
from agentguard.live import atomic_json
from agentguard.model import ModelFailure, parse_reply
from agentguard.runtime import Budgets

DIAGNOSTICS_VERSION = "runtime-diagnostics-v2"


class SavedCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    episode_id: str
    step: int = Field(ge=0)
    request: str
    max_tokens: int = Field(gt=0)
    raw_response: str | None
    elapsed_seconds: float | None = Field(ge=0, allow_inf_nan=False)
    error: str | None


def distribution(values: list[int] | list[float]) -> dict[str, int | float | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "median": percentile(list(values), 0.5) if values else None,
        "p95": percentile(list(values), 0.95) if values else None,
        "max": max(values) if values else None,
    }


def diagnose(report: dict[str, Any], raw_calls: list[dict[str, Any]]) -> dict[str, Any]:
    rows, _, variants = observations(report)
    manifest = report["manifest"]
    fresh = manifest["fresh_inference"]
    if type(fresh) is not bool or manifest["mode"] != (
        "fresh_local_inference" if fresh else "scripted_suite_replay"
    ):
        raise ValueError("Inconsistent inference mode")
    budgets = Budgets.model_validate(manifest["budgets"])
    calls = [SavedCall.model_validate(call) for call in raw_calls]
    if not fresh and calls:
        raise ValueError("Scripted replay cannot contain model calls")
    by_episode: dict[str, list[SavedCall]] = defaultdict(list)
    identities: set[tuple[str, int]] = set()
    scheduled = {row.episode_id for row in rows}
    for call in calls:
        identity = (call.episode_id, call.step)
        if call.episode_id not in scheduled or identity in identities:
            raise ValueError("Unscheduled or duplicate model call")
        identities.add(identity)
        by_episode[call.episode_id].append(call)
    original = {row["episode_id"]: row for row in report["episodes"]}
    episode_details = []
    tool_counts = {
        profile: {
            tool: Counter(
                {
                    "proposals": 0,
                    "ALLOW": 0,
                    "DENY": 0,
                    "REQUIRE_APPROVAL": 0,
                    "simulated_reviews": 0,
                }
            )
            for tool in get_args(Tool)
        }
        for profile in variants
    }
    measured_prompt: list[int] = []
    measured_completion: list[int] = []
    measured_headroom: list[int] = []
    measured_latency: list[float] = []
    totals: Counter[str] = Counter(
        {
            "calls": len(calls),
            "usage_known_calls": 0,
            "usage_unknown_calls": 0,
            "generated_tokens": 0,
            "reserved_tokens": 0,
            "schema_repairs": 0,
        }
    )
    for row in rows:
        group = sorted(by_episode[row.episode_id], key=lambda call: call.step)
        if len(group) != row.model_calls or [c.step for c in group] != list(range(len(group))):
            raise ValueError("Model-call count or step sequence disagrees with the episode")
        known = reserved = unknown = 0
        prompt: list[int] = []
        completion: list[int] = []
        headroom: list[int] = []
        latency: list[float] = []
        for call in group:
            if call.elapsed_seconds is not None:
                latency.append(call.elapsed_seconds)
            try:
                reply = parse_reply(call.raw_response or "")
            except ModelFailure:
                reserved += call.max_tokens
                unknown += 1
                continue
            known += reply.completion_tokens
            prompt.append(reply.prompt_tokens)
            completion.append(reply.completion_tokens)
            # This is server-reported usage, NOT the separately measured admission count.
            headroom.append(budgets.context_tokens - reply.prompt_tokens - reply.completion_tokens)
        evidence = original[row.episode_id]
        if known != row.generated_tokens:
            raise ValueError("Recorded model usage disagrees with generated-token totals")
        for field, value in (
            ("reserved_generated_tokens", reserved),
            ("charged_generated_tokens", known + reserved),
        ):
            if field in evidence and evidence[field] != value:
                raise ValueError("Reserved/charged token accounting disagrees with raw calls")
        # Usage is unknown for a lost or malformed response; do not call reserved tokens measured.
        totals.update(
            usage_known_calls=len(group) - unknown,
            usage_unknown_calls=unknown,
            generated_tokens=known,
            reserved_tokens=reserved,
            schema_repairs=evidence.get("schema_repairs", 0),
        )
        measured_prompt.extend(prompt)
        measured_completion.extend(completion)
        measured_headroom.extend(headroom)
        measured_latency.extend(latency)
        denials = []
        allowed_indices = []
        for index, entry in enumerate(row.trace):
            tool = entry["action"]["tool"]
            if tool not in tool_counts[row.profile]:
                raise ValueError("Unknown tool in execution trace")
            outcome = entry["execution"]["decision"]["outcome"]
            if outcome not in ("ALLOW", "DENY", "REQUIRE_APPROVAL"):
                raise ValueError("Unknown policy outcome")
            tool_counts[row.profile][tool].update(
                {"proposals": 1, outcome: 1, "simulated_reviews": int("simulated_review" in entry)}
            )
            if outcome == "DENY":
                denials.append(
                    {
                        "trace_index": index,
                        "tool": tool,
                        "reason": entry["execution"]["decision"]["reason"],
                    }
                )
            elif outcome == "ALLOW":
                allowed_indices.append(index)
        episode_details.append(
            {
                **{
                    key: getattr(row, key)
                    for key in (
                        "episode_id",
                        "task_id",
                        "profile",
                        "attacked",
                        "attack_id",
                        "status",
                        "reason",
                    )
                },
                "task_success": row.grade.task_success,
                "attack_success": row.grade.attack_success,
                "calls": len(group),
                "generated_tokens": known,
                "reserved_tokens": reserved,
                "usage_unknown_calls": unknown,
                "max_reported_prompt_tokens": max(prompt, default=None),
                "max_reported_completion_tokens": max(completion, default=None),
                "min_reported_context_headroom": min(headroom, default=None),
                "generated_token_budget_remaining": budgets.max_total_generated_tokens
                - known
                - reserved,
                "episode_seconds": row.elapsed_seconds,
                "model_call_seconds_with_measurement": sum(latency),
                "denials": denials,
                "allowed_action_after_denial": bool(
                    denials and any(i > denials[0]["trace_index"] for i in allowed_indices)
                ),
            }
        )
    recovery = {}
    for profile in variants:
        denied_episodes = [
            row for row in episode_details if row["profile"] == profile and row["denials"]
        ]
        recovery[profile] = {
            "episodes_with_denial": len(denied_episodes),
            "task_success_with_denial": sum(row["task_success"] for row in denied_episodes),
            "allowed_action_after_denial": sum(
                row["allowed_action_after_denial"] for row in denied_episodes
            ),
            "task_success_and_later_allowed_action": sum(
                row["task_success"] and row["allowed_action_after_denial"]
                for row in denied_episodes
            ),
        }
    return {
        "version": DIAGNOSTICS_VERSION,
        "mode": manifest["mode"],
        "scheduled_episodes": len(rows),
        "budgets": budgets.model_dump(),
        "model_accounting": dict(totals),
        "reported_prompt_tokens": distribution(measured_prompt),
        "reported_completion_tokens": distribution(measured_completion),
        "reported_context_headroom_tokens": distribution(measured_headroom),
        "model_call_seconds": distribution(measured_latency),
        "episode_seconds": distribution(
            [row.elapsed_seconds for row in rows if row.elapsed_seconds is not None]
        ),
        "unknown_episode_durations": sum(row.elapsed_seconds is None for row in rows),
        "status_counts": dict(Counter(row.status for row in rows)),
        "reason_counts": dict(Counter(row.reason for row in rows)),
        "tool_coverage": tool_counts,
        "denial_outcomes": recovery,
        "episodes": episode_details,
        "limits": [
            "Server-reported token usage is not independent metering "
            "or tokenizer admission evidence.",
            "Missing/malformed responses reserve their allowance; actual token use is unknown.",
            "Call durations include prompt processing and response generation, "
            "not pure decode throughput.",
            "Task success after a denial is a state observation, not a causal recovery estimate.",
            "No-denial denominators are empty observations, not perfect recovery rates.",
            "Small development sets and uncontrolled host load are not release evidence.",
            "Tool coverage counts policy decisions; failed computation may leave no trace.",
        ],
    }


def markdown(result: dict[str, Any]) -> str:
    totals = result["model_accounting"]
    lines = [
        "# Runtime diagnostics",
        "",
        f"Mode: `{result['mode']}`; scheduled episodes: {result['scheduled_episodes']}.",
        "",
        f"Saved model calls: {totals['calls']}; usage known: {totals['usage_known_calls']}; "
        f"usage unknown: {totals['usage_unknown_calls']}.",
        f"Reported generated tokens: {totals['generated_tokens']}; "
        f"reserved allowance for unknown usage: {totals['reserved_tokens']}.",
        f"Episodes with unknown duration: {result['unknown_episode_durations']} "
        "(excluded from timing distributions).",
        "",
        "| Profile | Episodes with denial | Task success among them | "
        "Later allowed action and task success |",
        "|---|---:|---:|---:|",
    ]
    for profile, row in result["denial_outcomes"].items():
        lines.append(
            f"| {profile} | {row['episodes_with_denial']} | {row['task_success_with_denial']} | "
            f"{row['task_success_and_later_allowed_action']} |"
        )
    lines += [
        "",
        "| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for profile, tools in result["tool_coverage"].items():
        for tool, counts in tools.items():
            lines.append(
                f"| {profile} / {tool} | {counts['proposals']} | {counts['ALLOW']} | "
                f"{counts['DENY']} | {counts['REQUIRE_APPROVAL']} | "
                f"{counts['simulated_reviews']} |"
            )
    lines += [
        "",
        "| Observed quantity | N | Min | Median | P95 | Max |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in (
        "reported_prompt_tokens",
        "reported_completion_tokens",
        "reported_context_headroom_tokens",
        "model_call_seconds",
        "episode_seconds",
    ):
        values = result[name]
        cells = [
            str(round(values[k], 3)) if values[k] is not None else "N/A"
            for k in ("count", "min", "median", "p95", "max")
        ]
        lines.append(f"| {name} | {' | '.join(cells)} |")
    lines += ["", "## Limits", "", *[f"- {limit}" for limit in result["limits"]], ""]
    return "\n".join(lines)


def write_diagnostics(root: Path, output: Path) -> Path:
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Write diagnostics outside the immutable input evidence directory")
    report, checksums = checked_report(root)
    result = diagnose(report, json.loads((root / "model-calls.json").read_text()))
    result["input_checksums"] = checksums
    result["diagnostics_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "diagnostics.json", result)
    (output / "diagnostics.md").write_text(markdown(result))
    (output / "diagnostics-source.py").write_bytes(Path(__file__).read_bytes())
    atomic_json(
        output / "checksums.json",
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())},
    )
    return output
