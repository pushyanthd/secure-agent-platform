import copy
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentguard.cli import app
from agentguard.diagnostics import diagnose, write_diagnostics
from agentguard.suite import run_suite

SUITE = Path(__file__).resolve().parents[1] / "scenarios/dev/tools-v1.json"


@pytest.fixture
def evidence(tmp_path):
    return run_suite(SUITE, tmp_path / "runs")


@pytest.fixture
def report(evidence):
    return json.loads((evidence / "report.json").read_text())


def fresh_call(report, *, raw=True):
    report["manifest"]["fresh_inference"] = True
    report["manifest"]["mode"] = "fresh_local_inference"
    row = report["episodes"][0]
    row.update(
        model_calls=1,
        generated_tokens=12 if raw else 0,
        reserved_generated_tokens=0 if raw else 768,
        charged_generated_tokens=12 if raw else 768,
    )
    return {
        "episode_id": row["episode_id"],
        "step": 0,
        "request": "[]",
        "max_tokens": 768,
        "raw_response": json.dumps(
            {
                "choices": [
                    {
                        "message": {"content": '{"kind":"final","text":"Done"}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1500, "completion_tokens": 12},
            }
        )
        if raw
        else None,
        "elapsed_seconds": 1.5 if raw else None,
        "error": None if raw else "MODEL_TIMEOUT",
    }


def test_replay_has_no_model_measurements_and_retains_denial_denominators(report):
    result = diagnose(report, [])
    assert result["scheduled_episodes"] == 24
    assert result["reported_prompt_tokens"]["count"] == 0
    assert result["reported_prompt_tokens"]["max"] is None
    assert result["model_accounting"]["generated_tokens"] == 0
    assert result["denial_outcomes"]["baseline"]["episodes_with_denial"] == 0
    defended = result["denial_outcomes"]["defended"]
    assert defended["episodes_with_denial"] == 3
    assert defended["task_success_with_denial"] == 3
    assert defended["task_success_and_later_allowed_action"] == 2
    coverage = result["tool_coverage"]["defended"]["shares.request"]
    assert coverage["ALLOW"] == 2 and coverage["DENY"] == 1
    assert coverage["simulated_reviews"] == 2


def test_known_and_unknown_usage_stay_separate(report):
    call = fresh_call(report)
    result = diagnose(report, [call])
    assert result["model_accounting"]["generated_tokens"] == 12
    assert result["reported_context_headroom_tokens"]["min"] == 8192 - 1500 - 12
    assert result["model_call_seconds"]["median"] == 1.5
    unknown_report = copy.deepcopy(report)
    unknown = fresh_call(unknown_report, raw=False)
    result = diagnose(unknown_report, [unknown])
    assert result["model_accounting"]["usage_unknown_calls"] == 1
    assert result["model_accounting"]["generated_tokens"] == 0
    assert result["model_accounting"]["reserved_tokens"] == 768
    assert result["reported_completion_tokens"]["count"] == 0
    assert result["model_call_seconds"]["count"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign",
        "duplicate",
        "missing",
        "steps",
        "tokens",
        "reserved",
        "charged",
        "replay",
        "nan",
        "bool",
    ],
)
def test_inconsistent_evidence_is_rejected(report, mutation):
    call = fresh_call(report)
    calls = [call]
    row = report["episodes"][0]
    if mutation == "foreign":
        call["episode_id"] = "foreign"
    elif mutation == "duplicate":
        calls.append(copy.deepcopy(call))
    elif mutation == "missing":
        calls.clear()
    elif mutation == "steps":
        call["step"] = 1
    elif mutation == "tokens":
        row["generated_tokens"] = 0
    elif mutation == "reserved":
        row["reserved_generated_tokens"] = 768
    elif mutation == "charged":
        row["charged_generated_tokens"] = 0
    elif mutation == "replay":
        report["manifest"].update(fresh_inference=False, mode="scripted_suite_replay")
    elif mutation == "nan":
        call["elapsed_seconds"] = float("nan")
    else:
        call["step"] = True
    with pytest.raises(ValueError):
        diagnose(report, calls)


def test_malformed_envelope_is_unknown_usage_not_zero_tokens(report):
    call = fresh_call(report, raw=False)
    call["raw_response"] = "invalid-json"
    result = diagnose(report, [call])
    assert result["model_accounting"]["reserved_tokens"] == 768
    assert result["model_accounting"]["usage_unknown_calls"] == 1


def test_failed_task_after_denial_is_not_counted_as_recovery(report):
    row = next(
        row
        for row in report["episodes"]
        if row["profile"] == "defended"
        and row["attacked"]
        and row["task_id"] == "ticket-maintenance"
    )
    row["grade"]["task_success"] = False
    result = diagnose(report, [])
    assert result["denial_outcomes"]["defended"]["episodes_with_denial"] == 3
    assert result["denial_outcomes"]["defended"]["task_success_with_denial"] == 2
    assert result["denial_outcomes"]["defended"]["task_success_and_later_allowed_action"] == 1


def test_export_is_outside_evidence_and_refuses_tampering(evidence, tmp_path):
    with pytest.raises(ValueError, match="outside"):
        write_diagnostics(evidence, evidence / "diagnostics")
    output = tmp_path / "diagnostics"
    result = CliRunner().invoke(app, ["eval-diagnostics", str(evidence), "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert "scripted_suite_replay" in (output / "diagnostics.md").read_text()
    assert (output / "checksums.json").exists()
    (evidence / "model-calls.json").write_text("[{}]")
    with pytest.raises(ValueError, match="checksum"):
        write_diagnostics(evidence, tmp_path / "tampered")


@pytest.mark.parametrize(
    "task_id,manifest",
    [
        ("ticket-maintenance", "ticket-wording-v2.json"),
        ("confidential-search-refusal", "reply-wording-v2.json"),
    ],
)
def test_wording_treatment_preserves_original_task_state_and_grader(task_id, manifest):
    from agentguard.scenarios import load_suite

    root = SUITE.parent
    original = next(task for _, _, task in load_suite(SUITE)[1] if task.id == task_id)
    clarified = load_suite(root / manifest)[1][0][2]
    before, after = original.model_dump(), clarified.model_dump()
    assert before.pop("task") != after.pop("task")
    assert before["contract"].pop("version") == 1
    assert after["contract"].pop("version") == 2
    assert before == after
