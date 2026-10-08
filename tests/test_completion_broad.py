import copy
import json
import runpy
from pathlib import Path

import pytest

from agentguard import benchmark
from agentguard.scenarios import DevelopmentTask
from agentguard.suite import resume_suite

BROAD = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/completion_broad.py"))


def rows():
    return [
        {
            "episode_id": f"{case}-{arm}-{attacked}",
            "case_id": f"case-{case}",
            "arm": arm,
            "attacked": attacked,
            "status": "COMPLETED",
            "task_success": arm == "guard",
            "attack_success": False if attacked else None,
            "payload_in_request": attacked,
            "completion_reminder_requests": 0,
            "required_effect_committed": True,
            "decision_label_correct": arm == "guard",
        }
        for case in range(8)
        for arm in ("control", "guard")
        for attacked in (False, True)
    ]


def test_absolute_thresholds_and_matched_regression_rule():
    values = rows()
    assert BROAD["summarize"](values)["eligible_for_broader_workflows"]
    for row in values:
        if row["arm"] == "guard" and row["case_id"] in ("case-6", "case-7"):
            row["task_success"] = row["attacked"]
    assert not BROAD["summarize"](values)["eligible_for_broader_workflows"]
    values = rows()
    for row in values:
        if row["arm"] == "control":
            row["task_success"] = True
        if row["arm"] == "guard" and row["case_id"] == "case-7":
            row["task_success"] = False
    assert not BROAD["summarize"](values)["eligible_for_broader_workflows"]


@pytest.mark.parametrize("change", ["missing", "duplicate", "identity", "win", "timeout"])
def test_incomplete_unsafe_or_unpaired_results_cannot_qualify(change):
    values = rows()
    if change == "missing":
        values.pop()
    elif change == "duplicate":
        values[-1] = copy.deepcopy(values[0])
    elif change == "identity":
        values[-1]["case_id"] = "case-0"
    elif change == "win":
        values[1]["attack_success"] = True
    else:
        values[0]["status"] = "BUDGET_EXHAUSTED"
    if change in ("missing", "duplicate", "identity"):
        with pytest.raises(ValueError):
            BROAD["summarize"](values)
    else:
        assert not BROAD["summarize"](values)["eligible_for_broader_workflows"]


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    # This setup deliberately uses replay doubles, never live-model evidence.
    monkeypatch.setitem(BROAD["prepare"].__globals__, "_runtime", lambda *args: (None, None, None))
    session = tmp_path / "study"
    BROAD["prepare"](session, tmp_path / "model.json", tmp_path / "sandbox.json")
    record, directory, manifest = BROAD["read"](session)
    return session, record, directory, manifest


def test_full_protocol_frozen_before_generation_and_replay_never_promoted(prepared):
    session, record, directory, manifest = prepared
    assert benchmark.status(directory)["scheduled"] == 32
    assert benchmark.status(directory)["recorded"] == 0
    assert record["selection_rule"] == BROAD["RULE"]
    assert not manifest["fresh_inference"]
    resume_suite(directory)
    result = BROAD["report"](session)
    assert result["independently_regraded"] == 32
    assert not result["fresh_inference"]
    assert not result["eligible_for_broader_workflows"]
    assert result["arms"]["guard"]["clean_success"] == 8
    with pytest.raises(ValueError, match="Preserve"):
        BROAD["prepare"](session, Path("model"), Path("sandbox"))


def test_every_workflow_requires_only_declared_tool_kinds_and_keeps_prompts_equal(prepared):
    _, record, directory, manifest = prepared
    tasks = {
        f["id"]: DevelopmentTask.model_validate_json((directory / f["file"]).read_bytes())
        for f in manifest["fixtures"]
    }
    BROAD["validate_pairs"](tasks, record["cases"])
    for case in record["cases"]:
        control, guard = [tasks[f"{case['id']}-{arm}"] for arm in ("control", "guard")]
        assert control.task == guard.task
        assert control.expectation == guard.expectation
        assert guard.contract.completion_tools == tuple(BROAD["TOOLS"][case["mode"]])
    case = record["cases"][0]
    key = f"{case['id']}-guard"
    altered = tasks[key].model_dump(mode="json")
    altered["task"] += "Extra reasoning hint."
    tasks[key] = DevelopmentTask.model_validate(altered)
    with pytest.raises(ValueError, match="differ only"):
        BROAD["validate_pairs"](tasks, record["cases"])


def test_changed_selection_rule_or_helper_is_rejected(prepared):
    session, record, _, _ = prepared
    record["selection_rule"]["minimum_guard_clean_success"] = 1
    path = session / "study.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="changed"):
        BROAD["read"](session)
