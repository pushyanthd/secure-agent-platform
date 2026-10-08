import copy
import json
import runpy
from pathlib import Path

import pytest

from agentguard import benchmark
from agentguard.computation import InProcessComputer
from agentguard.model import ModelConfig
from agentguard.scenarios import DevelopmentTask
from agentguard.suite import resume_suite, run_suite

REVIEW = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/decision_review.py"))


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
            "decision_review_requests": 2 if arm == "guard" else 0,
            "changed_review_candidates": 1 if arm == "guard" else 0,
            "model_calls": 4,
            "generated_tokens": 80,
            "elapsed_seconds": 1.0,
            "required_effect_committed": True,
            "decision_label_correct": arm == "guard",
        }
        for case in range(8)
        for arm in ("control", "guard")
        for attacked in (False, True)
    ]


def test_absolute_thresholds_and_matched_regression_rule():
    values = rows()
    assert REVIEW["summarize"](values)["eligible_for_broader_workflows"]
    for row in values:
        if row["arm"] == "guard" and row["case_id"] in ("case-6", "case-7"):
            row["task_success"] = row["attacked"]
    assert not REVIEW["summarize"](values)["eligible_for_broader_workflows"]
    values = rows()
    for row in values:
        if row["arm"] == "control":
            row["task_success"] = True
        if row["arm"] == "guard" and row["case_id"] == "case-7":
            row["task_success"] = False
    assert not REVIEW["summarize"](values)["eligible_for_broader_workflows"]


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
            REVIEW["summarize"](values)
    else:
        assert not REVIEW["summarize"](values)["eligible_for_broader_workflows"]


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    # This setup deliberately uses replay doubles, never live-model evidence.
    monkeypatch.setitem(REVIEW["prepare"].__globals__, "_runtime", lambda *args: (None, None, None))
    session = tmp_path / "study"
    REVIEW["prepare"](session, tmp_path / "model.json", tmp_path / "sandbox.json")
    record, directory, manifest = REVIEW["read"](session)
    return session, record, directory, manifest


def test_full_protocol_frozen_before_generation_and_replay_never_promoted(prepared):
    session, record, directory, manifest = prepared
    assert benchmark.status(directory)["scheduled"] == 32
    assert benchmark.status(directory)["recorded"] == 0
    assert record["selection_rule"] == REVIEW["RULE"]
    assert not manifest["fresh_inference"]
    resume_suite(directory)
    result = REVIEW["report"](session)
    assert result["independently_regraded"] == 32
    assert not result["fresh_inference"]
    assert not result["eligible_for_broader_workflows"]
    assert result["arms"]["guard"]["clean_success"] == 8
    with pytest.raises(ValueError, match="Preserve"):
        REVIEW["prepare"](session, Path("model"), Path("sandbox"))


def test_every_workflow_keeps_obligations_and_changes_only_review(prepared):
    _, record, directory, manifest = prepared
    tasks = {
        f["id"]: DevelopmentTask.model_validate_json((directory / f["file"]).read_bytes())
        for f in manifest["fixtures"]
    }
    REVIEW["validate_pairs"](tasks, record["cases"])
    for case in record["cases"]:
        control, guard = [tasks[f"{case['id']}-{arm}"] for arm in ("control", "guard")]
        assert control.task == guard.task
        assert control.contract.completion_tools == guard.contract.completion_tools
        assert "decision_review" not in control.contract.model_dump()
        assert "decision_review" not in guard.contract.model_dump()
        assert manifest["runtime_treatments"][guard.id] == {"decision_review": "independent-v1"}
        assert control.id not in manifest["runtime_treatments"]
        assert control.expectation == guard.expectation
        assert guard.contract.completion_tools == tuple(REVIEW["TOOLS"][case["mode"]])
    case = record["cases"][0]
    key = f"{case['id']}-guard"
    altered = tasks[key].model_dump(mode="json")
    altered["task"] += "Extra reasoning hint."
    tasks[key] = DevelopmentTask.model_validate(altered)
    with pytest.raises(ValueError, match="differ only"):
        REVIEW["validate_pairs"](tasks, record["cases"])


def test_changed_selection_rule_or_helper_is_rejected(prepared):
    session, record, _, _ = prepared
    record["selection_rule"]["minimum_guard_clean_success"] = 1
    path = session / "study.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="changed"):
        REVIEW["read"](session)


def test_live_runtime_assignment_survives_bounded_resume(prepared, tmp_path):
    from test_runtime import FakeModel, reply

    _, record, directory, manifest = prepared
    case_id = record["cases"][0]["id"]
    fixtures = [f for f in manifest["fixtures"] if f["id"].startswith(case_id + "-")]
    suite = directory / "fixtures/live-test.json"
    suite.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "review-test-double",
                "split": "development",
                "tasks": [Path(f["file"]).name for f in fixtures],
            }
        )
    )
    tasks = {
        f["id"]: DevelopmentTask.model_validate_json((directory / f["file"]).read_bytes())
        for f in fixtures
    }

    class IsolatedDouble(InProcessComputer):
        mode = "docker_isolated"  # Explicit test double; no containment measurement.

    class ScriptModel(FakeModel):
        config = ModelConfig()

        def complete(self, messages, schema, *, max_tokens, timeout):
            self.requests.append((list(messages), max_tokens))
            if json.loads(messages[-1]["content"]).get("reason") == "DECISION_REVIEW":
                return reply(messages[-2]["content"])
            task = tasks[json.loads(messages[1]["content"])["scope"]["task_id"]]
            if len(messages) == 2:
                return reply(
                    json.dumps(
                        {
                            "kind": "action",
                            "action": task.clean_script.actions[0].model_dump(mode="json"),
                        }
                    )
                )
            return reply(json.dumps({"kind": "final", "text": task.clean_script.final_response}))

    model, computer, evidence = ScriptModel([]), IsolatedDouble(), {"test_double": True}
    live = run_suite(
        suite,
        tmp_path / "live",
        model=model,
        computer=computer,
        model_evidence=evidence,
        variants=("defended",),
        max_episodes=2,
        decision_review_tasks=(case_id + "-guard",),
    )
    assert benchmark.status(live)["recorded"] == 2
    resume_suite(live, model=model, computer=computer, model_evidence=evidence)
    rows = json.loads((live / "episodes.json").read_text())
    assert len(rows) == 4 and all(row["grade"]["task_success"] for row in rows)
    assert [row["model_calls"] for row in rows] == [2, 2, 3, 3]


@pytest.mark.parametrize("selected", [("unknown",), ("launch-scope", "launch-scope")])
def test_invalid_treatment_ids_rejected_before_scheduling(tmp_path, selected):
    with pytest.raises(ValueError, match="distinct known"):
        run_suite(
            Path(__file__).resolve().parents[1] / "scenarios/dev/suite-v1.json",
            tmp_path / "runs",
            decision_review_tasks=selected,
        )
    assert not (tmp_path / "runs").exists()
