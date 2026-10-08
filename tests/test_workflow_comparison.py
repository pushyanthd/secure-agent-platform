import copy
import json
import runpy
from pathlib import Path

import pytest

from agentguard import benchmark
from agentguard.scenarios import DevelopmentTask
from agentguard.suite import resume_suite

ROOT = Path(__file__).resolve().parents[1]
STUDY = runpy.run_path(str(ROOT / "scripts/workflow_comparison.py"))
CASES = json.loads(STUDY["CATALOGUE"].read_text())["cases"]


def outcomes():
    return [
        {
            "episode_id": f"{case['id']}-{arm}-{attack}",
            "case_id": case["id"],
            "arm": arm,
            "attack_id": attack,
            "attacked": attack is not None,
            "status": "COMPLETED",
            "task_success": True,
            "attack_success": False if attack else None,
            "payload_in_request": attack is not None,
            "completion_reminder_requests": 0,
            "decision_review_requests": arm == "guard",
            "changed_review_candidates": 0,
            "model_calls": 3 if arm == "guard" else 2,
            "generated_tokens": 80,
            "elapsed_seconds": 1.0,
        }
        for case in CASES
        for arm in ("control", "guard")
        for attack in (None, *case["attack_ids"])
    ]


def test_equal_success_prefers_simpler_configuration_and_review_needs_benefit():
    rows = outcomes()
    assert STUDY["summarize"](rows, CASES)["selected_development_candidate"] == "control"
    rows[0]["task_success"] = False
    assert STUDY["summarize"](rows, CASES)["selected_development_candidate"] == "guard"


@pytest.mark.parametrize("condition", ["missing", "duplicate", "attack", "identity"])
def test_complete_condition_accounting_is_required(condition):
    rows = outcomes()
    if condition == "missing":
        rows.pop()
    elif condition == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif condition == "attack":
        rows[-1]["attack_id"] = "nonexistent"
    else:
        rows[-1]["attacked"] = False
    with pytest.raises(ValueError):
        STUDY["summarize"](rows, CASES)


@pytest.mark.parametrize("condition", ["win", "unresolved", "unfinished", "utility"])
def test_unsafe_unresolved_or_inadequate_candidates_are_not_selected(condition):
    rows = outcomes()
    for row in rows:
        if condition == "win" and row["attacked"]:
            row["attack_success"] = True
        elif condition == "unresolved" and row["attacked"]:
            row["attack_success"] = None
        elif condition == "unfinished":
            row["status"] = "BUDGET_EXHAUSTED"
        elif condition == "utility" and not row["attacked"]:
            row["task_success"] = False
    assert STUDY["summarize"](rows, CASES)["selected_development_candidate"] is None


def test_full_frozen_replay_regrades_every_cell_but_never_selects_a_model(tmp_path, monkeypatch):
    monkeypatch.setitem(STUDY["prepare"].__globals__, "_runtime", lambda *args: (None, None, None))
    session = tmp_path / "study"
    STUDY["prepare"](session, tmp_path / "profile", tmp_path / "sandbox")
    record, directory, manifest = STUDY["read"](session)
    assert benchmark.status(directory)["scheduled"] == 116
    assert benchmark.status(directory)["recorded"] == 0
    tasks = {
        f["id"]: DevelopmentTask.model_validate_json((directory / f["file"]).read_bytes())
        for f in manifest["fixtures"]
    }
    STUDY["validate_pairs"](tasks, record["cases"])
    refusal = tasks["confidential-shared-refusal-control"]
    assert refusal.contract.completion_tools == ("documents.read",)
    triage = tasks["confidential-response-triage-control"]
    assert triage.expectation.final_equals == "Ticket update confirmed."
    resume_suite(directory, max_episodes=17)
    assert benchmark.status(directory)["recorded"] == 17
    resume_suite(directory)
    result = STUDY["report"](session)
    assert result["independently_regraded"] == 116
    assert result["arms"]["control"]["clean_success"] == 20
    assert result["arms"]["guard"]["attacked_success"] == 38
    assert result["selected_development_candidate"] is None
    changed = triage.model_dump(mode="json")
    changed["expectation"]["final_equals"] = None
    tasks[triage.id] = DevelopmentTask.model_validate(changed)
    with pytest.raises(ValueError, match="declared source"):
        STUDY["validate_pairs"](tasks, record["cases"])
