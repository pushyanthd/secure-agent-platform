import copy
import json
import runpy
from pathlib import Path

import pytest

from agentguard import benchmark
from agentguard.completion import CompletionPlan
from agentguard.computation import InProcessComputer
from agentguard.model import ModelConfig
from agentguard.scenarios import DevelopmentTask
from agentguard.suite import resume_suite, run_suite, valid_treatment

ROOT = Path(__file__).resolve().parents[1]
STUDY = runpy.run_path(str(ROOT / "scripts/resource_completion.py"))
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
    assert len(manifest["runtime_treatments"]) == 20
    for case in record["cases"]:
        setting = manifest["runtime_treatments"][case["id"] + "-guard"]
        assert set(setting) == {"completion_plan"}
        assert "decision_review" not in setting
        assert case["id"] + "-control" not in manifest["runtime_treatments"]
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


@pytest.mark.parametrize(
    "setting",
    [
        {},
        {"max_steps": 64},
        {"completion_plan": None},
        {"completion_plan": {"reads": ["doc"], "expected_answer": "GO"}},
        {"decision_review": None},
    ],
)
def test_runtime_treatment_cannot_override_budgets_or_inject_grader_answers(setting):
    assert not valid_treatment(setting)


def test_live_double_preserves_resource_assignment_on_bounded_resume(tmp_path):
    from test_runtime import FakeModel, reply

    case = next(c for c in CASES if c["id"] == "two-document-synthesis")
    suite = tmp_path / "suite.json"
    tasks = {}
    for arm in ("control", "guard"):
        value = json.loads((ROOT / "scenarios/dev" / case["file"]).read_text())
        value["id"] = value["contract"]["task_id"] = case["id"] + "-" + arm
        value["contract"]["completion_tools"] = case["completion_tools"]
        value["task"] += STUDY["CHECKLIST"]
        task = DevelopmentTask.model_validate(value)
        tasks[task.id] = task
        (tmp_path / (task.id + ".json")).write_text(json.dumps(value))
    suite.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "resource-double",
                "split": "development",
                "tasks": [name + ".json" for name in tasks],
            }
        )
    )

    class IsolatedDouble(InProcessComputer):
        mode = "docker_isolated"  # Explicit double, no real containment or model evidence.

    class ScriptModel(FakeModel):
        config = ModelConfig()

        def complete(self, messages, schema, *, max_tokens, timeout):
            self.requests.append((list(messages), max_tokens))
            task = tasks[json.loads(messages[1]["content"])["scope"]["task_id"]]
            turns = [json.loads(m["content"]) for m in messages if m["role"] == "assistant"]
            if not turns:
                candidate = {
                    "kind": "action",
                    "action": task.clean_script.actions[0].model_dump(mode="json"),
                }
            elif len(turns) == 1:
                candidate = {
                    "kind": "action",
                    "action": task.clean_script.actions[2].model_dump(mode="json"),
                }
            elif json.loads(messages[-1]["content"]).get("required_resources"):
                candidate = {
                    "kind": "action",
                    "action": task.clean_script.actions[1].model_dump(mode="json"),
                }
            else:
                candidate = {"kind": "final", "text": task.clean_script.final_response}
            return reply(json.dumps(candidate))

    model, computer, evidence = ScriptModel([]), IsolatedDouble(), {"test_double": True}
    run = run_suite(
        suite,
        tmp_path / "runs",
        variants=("defended",),
        model=model,
        computer=computer,
        model_evidence=evidence,
        max_episodes=1,
        completion_plans={
            case["id"] + "-guard": CompletionPlan.model_validate(case["completion_plan"])
        },
    )
    assert benchmark.status(run)["recorded"] == 1
    resume_suite(run, model=model, computer=computer, model_evidence=evidence)
    rows = json.loads((run / "episodes.json").read_text())
    assert [r["grade"]["task_success"] for r in rows] == [False, False, True, True]
    assert [r["model_calls"] for r in rows] == [3, 3, 5, 5]
