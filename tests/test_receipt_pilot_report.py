"""Reject misleading cross-run comparisons before publishing the live pilot."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agentguard.suite import run_suite

SCRIPT = Path("scripts/compare_receipt_pilot.py").resolve()


@pytest.fixture(scope="module")
def original_runs(tmp_path_factory):
    output = tmp_path_factory.mktemp("receipt-pilot")
    return tuple(
        run_suite(
            Path(f"scenarios/dev/receipt-live-pilot-{mode}-v1.json"), output, variants=("defended",)
        )
        for mode in ("control", "treatment")
    )


@pytest.fixture
def runs(original_runs, tmp_path):
    paths = []
    for mode, source in zip(("control", "treatment"), original_runs, strict=True):
        destination = tmp_path / mode
        shutil.copytree(source, destination)
        paths.append(destination)
    return paths


def call(paths):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, paths)], capture_output=True, text=True, timeout=20
    )


def rewrite(path, edit):
    report = json.loads((path / "report.json").read_text())
    edit(report)
    for name, payload in [
        ("report.json", report),
        ("episodes.json", report["episodes"]),
        ("manifest.json", report["manifest"]),
    ]:
        (path / name).write_text(json.dumps(payload))
    checksums = json.loads((path / "checksums.json").read_text())
    for name in checksums:
        checksums[name] = hashlib.sha256((path / name).read_bytes()).hexdigest()
    (path / "checksums.json").write_text(json.dumps(checksums))


def test_complete_replay_is_labeled_and_success_is_not_a_release_gate(runs):
    result = call(runs)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["usable"] and not report["release_gate"] and not report["fresh_inference"]
    assert report["task_clusters"] == 1 and report["scheduled_episodes"] == 10
    assert report["counts"]["control"]["clean_success"] == 0
    assert report["counts"]["treatment"]["clean_success"] == 1
    assert report["counts"]["treatment"]["attacked_task_success"] == 4
    assert report["counts"]["treatment"]["verified_effect_receipts"] == 5


@pytest.mark.parametrize(
    "field,value",
    [
        ("budgets", {"max_steps": 999}),
        ("model_config", {"seed": 999}),
        ("grader_version", "changed"),
        ("policy_version", "changed"),
        ("response_policy_version", "changed"),
        ("tool_image_id", "different-image"),
        ("prompts_sha256", "changed"),
        ("simulated_approvals", False),
    ],
)
def test_incompatible_execution_or_grading_is_unusable(runs, field, value):
    rewrite(runs[1], lambda r: r["manifest"].__setitem__(field, value))
    result = call(runs)
    assert result.returncode == 2 and field in result.stderr
    assert not result.stdout


def test_dropped_episode_cannot_improve_comparison(runs):
    rewrite(runs[0], lambda r: r["episodes"].pop())
    result = call(runs)
    assert result.returncode == 2 and "Missing or duplicate" in result.stderr


def test_missing_metadata_is_not_an_implicit_match(runs):
    for path in runs:
        rewrite(path, lambda r: r["manifest"].pop("response_policy_version"))
    result = call(runs)
    assert result.returncode == 2 and "Missing comparison field" in result.stderr


def test_model_call_claims_must_reconcile_with_raw_evidence(runs):
    rewrite(runs[1], lambda r: r["episodes"][0].__setitem__("model_calls", 1))
    result = call(runs)
    assert result.returncode == 2 and "Model-call count" in result.stderr


def test_replay_cannot_be_relabelled_as_fresh_without_model_provenance(runs):
    def relabel(report):
        report["manifest"].update(fresh_inference=True, mode="fresh_local_inference")

    for path in runs:
        rewrite(path, relabel)
    result = call(runs)
    assert result.returncode == 2 and "Fresh inference requires" in result.stderr


def test_changed_task_prose_is_not_a_receipt_only_treatment(runs):
    def alter_task(report):
        fixture = report["manifest"]["fixtures"][0]
        path = runs[1] / fixture["file"]
        raw = json.loads(path.read_text())
        raw["task"] += " Skip reading the guide."
        path.write_text(json.dumps(raw))
        fixture["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    rewrite(runs[1], alter_task)
    result = call(runs)
    assert result.returncode == 2 and "Fixtures must differ only" in result.stderr


def test_failed_trial_stays_in_denominators_and_worst_case_bound(runs):
    def fail(report):
        row = report["episodes"][1]
        row.update(status="FAILED", reason="MODEL_UNAVAILABLE")
        row["grade"]["task_success"] = False

    rewrite(runs[1], fail)
    result = call(runs)
    assert result.returncode == 0, result.stderr
    counts = json.loads(result.stdout)["counts"]["treatment"]
    assert counts["scheduled"] == 5 and counts["attacked_denominator"] == 4
    assert counts["attacked_task_success"] == 3
    assert counts["noncompleted"] == counts["unresolved_attacked"] == 1
    assert counts["observed_attack_wins"] == 0 and counts["worst_case_attack_wins"] == 1


def test_broken_checksum_stops_analysis(runs):
    with (runs[0] / "model-calls.json").open("a") as stream:
        stream.write(" ")
    result = call(runs)
    assert result.returncode == 2 and "checksum mismatch" in result.stderr


@pytest.mark.parametrize(
    "role,outcome,expected",
    [
        ("user", "ALLOW", True),
        ("user", "DENY", False),
        ("assistant", "ALLOW", False),
    ],
)
def test_exposure_checks_decoded_document_result_not_a_proposal(role, outcome, expected):
    import runpy

    check = runpy.run_path(str(SCRIPT))["payload_in_requests"]
    payload = 'Quoted "instruction"\nand another line.'
    content = {"outcome": outcome, "result": {"document_id": "guide", "body": "Source. " + payload}}
    calls = [
        {
            "episode_id": "one",
            "request": json.dumps([{"role": role, "content": json.dumps(content)}]),
        }
    ]
    assert check(calls, "one", "guide", payload) is expected
    assert not check(calls, "another", "guide", payload)
    assert not check(calls, "one", "different-source", payload)


def test_replay_exposure_is_unmeasured_not_zero(runs):
    report = json.loads(call(runs).stdout)
    assert report["counts"]["control"]["attacked_payload_in_recorded_request"] is None
    assert report["common_clean_task_success"] is False
    assert all(
        pair["treatment"]["payload_in_recorded_request"] is None for pair in report["paired_inputs"]
    )
