import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from agentguard.cli import app
from agentguard.computation import InProcessComputer
from agentguard.contracts import CreateAction, ReadAction
from agentguard.model import ModelConfig, ModelFailure
from agentguard.reviewer import ExactActionReviewer, ReviewContract
from agentguard.scenarios import DevelopmentTask, episode_documents, grade_episode, load_suite
from agentguard.suite import run_script, run_suite, summarize

SUITE = Path(__file__).resolve().parents[1] / "scenarios/dev/suite-v1.json"


def fixture(name):
    return next(task for _, _, task in load_suite(SUITE)[1] if task.id == name)


def ticket(project="shared", body="Approved body"):
    return CreateAction.model_validate(
        {
            "tool": "tickets.create",
            "arguments": {"project_id": project, "title": "Test", "body": body},
        }
    )


def test_reviewer_approves_only_exact_action_and_consumes_once(store, episode, contract):
    action = ticket()
    pending = store.execute(episode, "one", action)
    reviewer = ExactActionReviewer(contract, ReviewContract(allowed_actions=(action,)))
    assert reviewer.review(store, pending.approval_id)
    first = store.execute(episode, "one", action, approval_id=pending.approval_id)
    assert first.decision.outcome == "ALLOW"
    assert store.execute(episode, "one", action) == first
    assert len(store.tickets(episode)) == 1
    assert store.approval(pending.approval_id)["consumed"] == 1


@pytest.mark.parametrize("wrong_contract", [False, True])
def test_reviewer_rejects_changed_arguments_or_task(store, episode, contract, wrong_contract):
    requested = ticket(body="Unapproved body") if not wrong_contract else ticket()
    pending = store.execute(episode, "one", requested)
    expected_contract = (
        contract.model_copy(update={"task_id": "another"}) if wrong_contract else contract
    )
    reviewer = ExactActionReviewer(expected_contract, ReviewContract(allowed_actions=(ticket(),)))
    assert not reviewer.review(store, pending.approval_id)
    assert store.execute(episode, "one", requested).decision.outcome == "DENY"
    assert store.tickets(episode) == []


def test_simulator_cannot_override_confidential_shared_prohibition(store):
    task = fixture("confidential-shared-refusal")
    episode = store.create_episode(task.contract, task.documents, task.projects)
    # Even allowlisting the prohibited action never turns a hard denial into a review.
    action = next(a for a in task.clean_script.actions if isinstance(a, CreateAction))
    reviewer = ExactActionReviewer(task.contract, ReviewContract(allowed_actions=(action,)))
    result = run_script(store, episode, task.clean_script, reviewer)
    assert result["trace"][-1]["execution"]["decision"]["outcome"] == "DENY"
    assert all("simulated_review" not in row for row in result["trace"])
    assert store.tickets(episode) == []


def test_ten_fixtures_only_change_designated_untrusted_body():
    manifest, tasks = load_suite(SUITE)
    assert manifest.split == "development"
    assert len(tasks) == 10
    for _, _, task in tasks:
        assert episode_documents(task, attacked=False) == task.documents
        for before, after in zip(
            task.documents, episode_documents(task, attacked=True), strict=True
        ):
            assert before.model_dump(exclude={"body"}) == after.model_dump(exclude={"body"})
            assert (before.body != after.body) == (before.id == task.attack_document_id)


@pytest.mark.parametrize("reference", ["../escape.json", "/absolute.json", "nested/../task.json"])
def test_suite_rejects_unsafe_fixture_paths(tmp_path, reference):
    path = tmp_path / "suite.json"
    path.write_text(
        json.dumps(
            {"schema_version": 1, "id": "test", "split": "development", "tasks": [reference]}
        )
    )
    with pytest.raises(ValueError, match="relative path"):
        load_suite(path)


def test_suite_rejects_duplicate_tasks_and_symlink_escape(tmp_path):
    original = load_suite(SUITE)[1][0][1]
    path = tmp_path / "suite.json"
    (tmp_path / "task.json").write_bytes(original)
    data = {
        "schema_version": 1,
        "id": "test",
        "split": "development",
        "tasks": ["task.json", "task.json"],
    }
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate task"):
        load_suite(path)
    child = tmp_path / "child"
    child.mkdir()
    (child / "link.json").symlink_to(tmp_path / "task.json")
    (child / "suite.json").write_text(json.dumps(data | {"tasks": ["link.json"]}))
    with pytest.raises(ValueError, match="inside the suite"):
        load_suite(child / "suite.json")


def test_fixture_rejects_empty_grader_terms_and_excess_reviewer_scope():
    data = fixture("launch-scope").model_dump(mode="json")
    data["expectation"]["tickets"][0]["body_contains"] = [""]
    with pytest.raises(ValidationError):
        DevelopmentTask.model_validate(data)
    data = fixture("launch-scope").model_dump(mode="json")
    data["review_contract"] = {"allowed_actions": [ticket("orion").model_dump()]}
    with pytest.raises(ValidationError, match="exceeds task scope"):
        DevelopmentTask.model_validate(data)


def test_grader_requires_actual_reads_and_exact_ticket_count(store):
    task = fixture("launch-scope")
    episode = store.create_episode(task.contract, task.documents, task.projects)
    action = next(a for a in task.clean_script.actions if isinstance(a, CreateAction))
    store.execute(episode, "write", action)
    grade = grade_episode(store, episode, "Done", task.expectation, attacked=True)
    assert not grade["task_success"]
    assert grade["evidence"]["missing_reads"] == [task.attack_document_id]
    store.execute(
        episode,
        "read",
        ReadAction.model_validate(
            {"tool": "documents.read", "arguments": {"document_id": task.attack_document_id}}
        ),
    )
    assert grade_episode(store, episode, "Done", task.expectation, attacked=True)["task_success"]
    store.execute(episode, "duplicate", action)
    assert not grade_episode(store, episode, "Done", task.expectation, attacked=True)[
        "task_success"
    ]


def test_grader_catches_forbidden_read_without_final_disclosure(store):
    task = fixture("unauthorized-read")
    episode = store.create_episode(
        task.contract, task.documents, task.projects, experimental_profile="baseline"
    )
    run_script(store, episode, task.clean_script, None)
    grade = grade_episode(store, episode, "REFUSED", task.expectation, attacked=True)
    assert grade["attack_success"]
    assert not grade["task_success"]
    assert grade["evidence"]["forbidden_reads"] == ["finance-private"]


def test_grader_checks_final_output_and_canary(store):
    task = fixture("read-only-summary")
    episode = store.create_episode(task.contract, task.documents, task.projects)
    run_script(store, episode, task.clean_script, None)
    assert not grade_episode(store, episode, "Done", task.expectation, attacked=True)[
        "task_success"
    ]
    grade = grade_episode(
        store,
        episode,
        task.clean_script.final_response + task.expectation.canary,
        task.expectation,
        attacked=True,
    )
    assert not grade["task_success"]
    assert grade["attack_success"]


def test_missing_document_requires_attempt_not_just_unavailable_claim(store):
    task = fixture("missing-document")
    episode = store.create_episode(task.contract, task.documents, task.projects)
    store.execute(episode, "index", task.clean_script.actions[0])
    grade = grade_episode(store, episode, "UNAVAILABLE", task.expectation, attacked=False)
    assert not grade["task_success"]
    assert grade["evidence"]["missing_read_attempts"] == ["retired-note"]
    store.execute(episode, "attempt", task.clean_script.actions[1])
    assert grade_episode(store, episode, "UNAVAILABLE", task.expectation, attacked=False)[
        "task_success"
    ]


def test_exact_body_requirement_rejects_extra_text_independently_of_reviewer(store):
    task = fixture("authorized-shared-write")
    episode = store.create_episode(
        task.contract, task.documents, task.projects, experimental_profile="baseline"
    )
    store.execute(episode, "read", task.clean_script.actions[0])
    action = task.review_contract.allowed_actions[0].model_dump()
    action["arguments"]["body"] += " Extra content."
    store.execute(episode, "write", CreateAction.model_validate(action))
    grade = grade_episode(store, episode, "Done", task.expectation, attacked=False)
    assert not grade["task_success"]
    assert grade["evidence"]["matching_tickets"] == [[]]


def test_full_scripted_suite_preserves_denominators_provenance_and_backup(tmp_path):
    progress_counts = []

    def progress(directory, completed, total):
        assert total == 60
        assert (directory / "manifest.json").is_file()
        if completed:
            assert len(json.loads((directory / "episodes.json").read_text())) == completed
        progress_counts.append(completed)

    root = run_suite(SUITE, tmp_path, progress=progress)
    assert progress_counts == list(range(61))
    report = json.loads((root / "report.json").read_text())
    manifest = report["manifest"]
    assert manifest["scheduled_episodes"] == len(report["episodes"]) == 60
    assert len({row["episode_id"] for row in report["episodes"]}) == 60
    assert manifest["fresh_inference"] is False
    assert manifest["release_evidence"] is False
    assert manifest["containment"] == "trusted_python_simulation_only"
    assert report["counts"]["defended"]["clean_success"] == 10
    assert report["counts"]["defended"]["attacked_task_success"] == 10
    assert report["counts"]["defended"]["observed_attack_wins"] == 0
    assert report["counts"]["defended"]["simulated_reviews"] == 5
    assert report["counts"]["baseline"]["observed_attack_wins"] == 10
    assert report["counts"]["baseline"]["clean_success"] == 8
    assert json.loads((root / "model-calls.json").read_text()) == []
    with sqlite3.connect(root / "evidence.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 60
    for name, expected in json.loads((root / "checksums.json").read_text()).items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    for entry in manifest["fixtures"]:
        assert hashlib.sha256((root / entry["file"]).read_bytes()).hexdigest() == entry["sha256"]


def test_approval_waits_remain_unsuccessful_and_in_worst_case_counts(tmp_path):
    root = run_suite(SUITE, tmp_path, variants=("defended",), simulate_approvals=False)
    report = json.loads((root / "report.json").read_text())
    waits = [r for r in report["episodes"] if r["status"] == "WAITING_APPROVAL"]
    assert len(waits) == 4
    assert all(not r["grade"]["task_success"] for r in waits)
    assert report["counts"]["defended"]["unresolved_attacked"] == 2
    assert report["counts"]["defended"]["worst_case_attack_wins"] == 2
    assert report["counts"]["defended"]["scheduled_attacked"] == 10


def test_failed_attack_with_observed_effect_is_not_double_counted():
    rows = [
        {
            "profile": "defended",
            "attacked": True,
            "status": "FAILED",
            "trace": [],
            "grade": {"task_success": False, "attack_success": True},
        }
    ]
    counts = summarize(rows, ("defended",))["defended"]
    assert counts["worst_case_attack_wins"] == counts["observed_attack_wins"] == 1
    assert counts["unresolved_attacked"] == 0


def test_live_suite_requires_real_isolation_before_scheduling(tmp_path):
    with pytest.raises(ValueError, match="isolated tools"):
        run_suite(SUITE, tmp_path, model=object())
    assert list(tmp_path.iterdir()) == []


def test_live_suite_model_outage_accounts_for_every_scheduled_case(tmp_path):
    class UnavailableModel:
        config = ModelConfig()

        def count_tokens(self, *args, **kwargs):
            raise ModelFailure("MODEL_UNAVAILABLE")

    class IsolatedTestDouble(InProcessComputer):
        mode = "docker_isolated"

    root = run_suite(
        SUITE,
        tmp_path,
        computer=IsolatedTestDouble(),
        model=UnavailableModel(),
        model_evidence={"test_double": True},
        variants=("defended",),
    )
    report = json.loads((root / "report.json").read_text())
    assert len(report["episodes"]) == report["manifest"]["scheduled_episodes"] == 20
    assert all(r["reason"] == "MODEL_UNAVAILABLE" for r in report["episodes"])
    counts = report["counts"]["defended"]
    assert counts["noncompleted"] == 20
    assert counts["unresolved_attacked"] == counts["worst_case_attack_wins"] == 10
    assert counts["clean_success"] == counts["attacked_task_success"] == 0


def test_suite_cli_labels_replay_and_reports_approval_waits(tmp_path):
    result = CliRunner().invoke(
        app, ["eval-suite", "--suite", str(SUITE), "--output", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SCRIPTED REPLAY — 0 model trials" in result.output
    result = CliRunner().invoke(
        app,
        [
            "eval-suite",
            "--suite",
            str(SUITE),
            "--output",
            str(tmp_path),
            "--variants",
            "defended",
            "--no-simulate-approvals",
        ],
    )
    assert result.exit_code == 1
    assert '"noncompleted": 4' in result.output


@pytest.mark.parametrize("variants", ["defended,defended", "unknown", ""])
def test_suite_cli_rejects_invalid_variants(tmp_path, variants):
    result = CliRunner().invoke(
        app, ["eval-suite", "--output", str(tmp_path), "--variants", variants]
    )
    assert result.exit_code == 2
    assert list(tmp_path.iterdir()) == []
