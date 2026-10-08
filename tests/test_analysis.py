import copy
import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentguard.analysis import analyze, checked_report, write_analysis
from agentguard.cli import app
from agentguard.suite import run_suite

SUITE = Path(__file__).resolve().parents[1] / "scenarios/dev/suite-v1.json"


@pytest.fixture
def evidence(tmp_path):
    return run_suite(SUITE, tmp_path / "runs")


@pytest.fixture
def report(evidence):
    return json.loads((evidence / "report.json").read_text())


def fresh(report):
    # Synthetic statistical examples, never exported as measured live evidence.
    report["manifest"]["fresh_inference"] = True
    report["manifest"]["mode"] = "fresh_local_inference"
    return report


def test_replay_counts_conditional_denominators_and_no_model_intervals(report):
    result = analyze(report, resamples=100)
    assert result["scheduled_episodes"] == 60
    assert result["task_clusters"] == 10
    assert result["bootstrap"]["resamples"] == 0
    assert result["profiles"]["defended"]["clean_utility"]["numerator"] == 10
    assert result["profiles"]["baseline"]["clean_utility"]["numerator"] == 8
    assert result["profiles"]["baseline"]["clean_utility"]["descriptive_95pct_interval"] is None
    pair = next(
        p
        for p in result["comparisons"]
        if p["reference"] == "baseline" and p["treatment"] == "defended"
    )
    assert len(pair["common_clean_solved_tasks"]) == 8
    assert len(pair["excluded_tasks"]) == 2
    assert pair["conditional_attack_success"]["baseline"] == {
        "numerator": 8,
        "denominator": 8,
        "rate": 1.0,
    }
    assert pair["conditional_attack_success"]["defended"]["numerator"] == 0
    assert pair["paired_deltas"]["observed_attack_success"]["treatment_minus_reference"] == -1


def test_bootstrap_preserves_pairing_and_is_reproducible(report):
    fresh(report)
    # Baseline and prompt-only have identical observations but nonconstant utility.
    result = analyze(report, resamples=300)
    assert result == analyze(copy.deepcopy(report), resamples=300)
    same = result["comparisons"][0]
    assert same["paired_deltas"]["clean_utility"]["descriptive_95pct_interval"] == [0, 0]
    bounds = result["profiles"]["baseline"]["clean_utility"]["descriptive_95pct_interval"]
    assert bounds[0] < 0.8 < bounds[1]
    assert result["profiles"]["defended"]["clean_utility"]["descriptive_95pct_interval"] == [1, 1]
    # Input row order must not affect paired draws or estimates.
    shuffled = copy.deepcopy(report)
    shuffled["episodes"].reverse()
    reordered = analyze(shuffled, resamples=300)
    assert reordered["comparisons"] == result["comparisons"]
    assert reordered["profiles"] == result["profiles"]


def test_no_common_solved_tasks_is_undefined_not_zero_risk(report):
    for row in report["episodes"]:
        if not row["attacked"]:
            row["grade"]["task_success"] = False
    result = analyze(report, resamples=100)
    for pair in result["comparisons"]:
        assert len(pair["excluded_tasks"]) == 10
        for conditional in pair["conditional_attack_success"].values():
            assert conditional == {"numerator": 0, "denominator": 0, "rate": None}


def test_failed_episodes_stay_in_rates_and_observed_wins_are_not_double_counted(report):
    for row in report["episodes"]:
        if row["attacked"]:
            row["status"] = "FAILED"
            row["grade"]["task_success"] = False
    result = analyze(report, resamples=100)
    for profile in result["profiles"].values():
        assert profile["worst_case_attack_success"]["numerator"] == 10
        assert profile["observed_attack_success"]["denominator"] == 10
    assert result["profiles"]["baseline"]["unresolved_attacked"] == 0
    assert result["profiles"]["defended"]["unresolved_attacked"] == 10


@pytest.mark.parametrize(
    "corruption",
    [
        "missing",
        "duplicate",
        "identity",
        "grade",
        "unfinished_success",
        "count",
        "unpaired",
        "mode",
    ],
)
def test_invalid_evidence_cannot_improve_a_comparison(report, corruption):
    row = report["episodes"][0]
    if corruption == "missing":
        report["episodes"].pop()
    elif corruption == "duplicate":
        report["episodes"][-1] = copy.deepcopy(row)
    elif corruption == "identity":
        row["task_id"] = "wrong-task"
    elif corruption == "grade":
        row["grade"]["attack_success"] = False
    elif corruption == "unfinished_success":
        row["status"] = "FAILED"
    elif corruption == "count":
        report["manifest"]["scheduled_episodes"] = 59
    elif corruption == "unpaired":
        report["episodes"].pop()
        report["manifest"]["schedule"].pop()
        report["manifest"]["scheduled_episodes"] = 59
    elif corruption == "mode":
        report["manifest"]["fresh_inference"] = True
    with pytest.raises(ValueError):
        analyze(report, resamples=100)


def test_checksum_validation_and_analysis_export_preserve_original(evidence, tmp_path):
    before = (evidence / "checksums.json").read_bytes()
    report, _ = checked_report(evidence)
    output = write_analysis(evidence, tmp_path / "analysis", resamples=100)
    assert (evidence / "checksums.json").read_bytes() == before
    assert json.loads((output / "analysis.json").read_text())["scheduled_episodes"] == 60
    assert "scripted_suite_replay" in (output / "analysis.md").read_text()
    assert "AgentGuard" in (output / "explorer.html").read_text()
    assert (output / "viewer-source.py").is_file()
    for name, expected in json.loads((output / "checksums.json").read_text()).items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    with pytest.raises(FileExistsError):
        write_analysis(evidence, output, resamples=100)
    with pytest.raises(ValueError, match="outside"):
        write_analysis(evidence, evidence / "analysis", resamples=100)
    report["episodes"].pop()
    (evidence / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="checksum mismatch"):
        checked_report(evidence)


@pytest.mark.parametrize("name", ["../escape", "/tmp/escape"])
def test_checksum_paths_cannot_escape_evidence(evidence, name):
    (evidence / "checksums.json").write_text(json.dumps({name: "0" * 64}))
    with pytest.raises(ValueError, match="escapes"):
        checked_report(evidence)


def test_checksum_symlink_escape_and_missing_required_files(evidence, tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("test")
    (evidence / "escape").symlink_to(outside)
    (evidence / "checksums.json").write_text(json.dumps({"escape": "0" * 64}))
    with pytest.raises(ValueError, match="escapes"):
        checked_report(evidence)
    (evidence / "checksums.json").write_text("{}")
    with pytest.raises(ValueError, match="required suite evidence"):
        checked_report(evidence)


@pytest.mark.parametrize("filename", ["manifest.json", "episodes.json", "source.json"])
def test_internally_inconsistent_rechecksummed_bundle_rejected(evidence, filename):
    path = evidence / filename
    data = json.loads(path.read_text())
    if filename == "manifest.json":
        data["scheduled_episodes"] = 59
    elif filename == "episodes.json":
        data.pop()
    else:
        data["runtime.py"] += "\n# altered\n"
    path.write_text(json.dumps(data))
    checksums = json.loads((evidence / "checksums.json").read_text())
    checksums[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    (evidence / "checksums.json").write_text(json.dumps(checksums))
    with pytest.raises(ValueError):
        checked_report(evidence)


def test_analysis_cli_writes_report_and_rejects_corruption(evidence, tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "eval-analyze",
            str(evidence),
            "--output",
            str(tmp_path / "analysis"),
            "--resamples",
            "100",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "scripted_suite_replay" in result.output
    (evidence / "report.json").write_text("{}")
    result = CliRunner().invoke(
        app, ["eval-analyze", str(evidence), "--output", str(tmp_path / "invalid")]
    )
    assert result.exit_code == 2
    assert "Unusable suite evidence" in result.output
    assert not (tmp_path / "invalid").exists()
