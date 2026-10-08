import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentguard.cli import app
from agentguard.evidence import export_evidence, verify_evidence
from agentguard.suite import run_suite

ROOT = Path(__file__).resolve().parents[1]


def rehash(directory, name):
    manifest = json.loads((directory / "checksums.json").read_text())
    manifest[name] = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    (directory / "checksums.json").write_text(json.dumps(manifest))


def mutate_snapshot(directory, statement):
    db = sqlite3.connect(directory / "evidence.sqlite3")
    try:
        db.execute(statement)
        db.commit()
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        db.close()
    rehash(directory, "evidence.sqlite3")


@pytest.fixture
def evidence(tmp_path):
    return run_suite(ROOT / "scenarios/dev/suite-v1.json", tmp_path / "runs")


@pytest.fixture
def portable(evidence, tmp_path):
    return export_evidence(evidence, tmp_path / "published")


@pytest.mark.parametrize(
    "suite",
    [
        "suite-v1.json",
        "tools-v1.json",
        "expansion-v1.json",
        "response-scope-v1.json",
        "effect-receipt-treatment-v1.json",
    ],
)
def test_all_grades_round_trip_without_database_or_services(tmp_path, suite):
    original = run_suite(ROOT / "scenarios/dev" / suite, tmp_path / "runs")
    before = {p: p.read_bytes() for p in original.rglob("*") if p.is_file()}
    output = export_evidence(original, tmp_path / "published")
    verified = verify_evidence(output)
    assert verified["all_grades_match"]
    assert verified["verified_episodes"] == len(
        json.loads((original / "episodes.json").read_text())
    )
    assert verified["mode"] == "scripted_suite_replay"
    assert not verified["release_gate_recomputed"]
    assert not list(output.rglob("*.sqlite3"))
    assert before == {p: p.read_bytes() for p in original.rglob("*") if p.is_file()}
    state = json.loads((output / "grading-state.json").read_text())
    for episode in state["episodes"]:
        assert set(episode) == {"episode_id", "tickets", "shares", "executions"}
        for execution in episode["executions"]:
            assert set(execution) == {"proposal_hash", "output"}
            assert execution["output"] is None or execution["output"]["approval_id"] is None


def test_committed_state_corruption_rejected_even_with_new_checksum(portable):
    path = portable / "grading-state.json"
    state = json.loads(path.read_text())
    episode = next(e for e in state["episodes"] if e["tickets"])
    episode["tickets"][0]["body"] = "Forged success claim"
    path.write_text(json.dumps(state))
    rehash(portable, path.name)
    with pytest.raises(ValueError, match="differs from committed state"):
        verify_evidence(portable)


def test_required_failed_read_attempt_is_preserved(portable):
    report = json.loads((portable / "report.json").read_text())
    row = next(r for r in report["episodes"] if r["task_id"] == "missing-document")
    path = portable / "grading-state.json"
    state = json.loads(path.read_text())
    episode = next(e for e in state["episodes"] if e["episode_id"] == row["episode_id"])
    assert episode["executions"]
    episode["executions"] = []
    path.write_text(json.dumps(state))
    rehash(portable, path.name)
    with pytest.raises(ValueError, match="differs from committed state"):
        verify_evidence(portable)


@pytest.mark.parametrize("change", ["missing", "duplicate", "reordered", "extra_authority"])
def test_state_identity_and_schema_cannot_change(portable, change):
    path = portable / "grading-state.json"
    state = json.loads(path.read_text())
    if change == "missing":
        state["episodes"].pop()
    elif change == "duplicate":
        state["episodes"][-1] = state["episodes"][0]
    elif change == "reordered":
        state["episodes"].reverse()
    else:
        state["episodes"][0]["approvals"] = [{"nonce": "must-never-be-imported"}]
    path.write_text(json.dumps(state))
    rehash(portable, path.name)
    with pytest.raises(ValueError):
        verify_evidence(portable)


def test_corrupted_original_database_cannot_be_published(evidence, tmp_path):
    mutate_snapshot(evidence, "UPDATE tickets SET body='Corrupted state'")
    output = tmp_path / "published"
    with pytest.raises(ValueError, match="differs from committed state"):
        export_evidence(evidence, output)
    assert not output.exists()


def test_corrupted_journal_cannot_be_published(evidence, tmp_path):
    mutate_snapshot(evidence, "UPDATE benchmark_episodes SET result_sha256='bad'")
    with pytest.raises(ValueError, match="inconsistent results"):
        export_evidence(evidence, tmp_path / "published")


def test_pending_wal_data_cannot_be_silently_ignored(evidence, tmp_path):
    db = sqlite3.connect(evidence / "evidence.sqlite3")
    try:
        db.execute("UPDATE tickets SET body='Uncheckpointed state'")
        db.commit()
        with pytest.raises(ValueError, match="pending WAL"):
            export_evidence(evidence, tmp_path / "published")
    finally:
        db.close()


def test_original_provenance_and_unrehashed_state_are_checked(portable):
    state = portable / "grading-state.json"
    state.write_text(state.read_text() + " ")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_evidence(portable)
    rehash(portable, state.name)
    path = portable / "original-run-checksums.json"
    path.write_text(path.read_text() + " ")
    rehash(portable, path.name)
    with pytest.raises(ValueError, match="provenance changed"):
        verify_evidence(portable)


def test_export_refuses_overwrite_nested_destination_and_reexport(evidence, portable, tmp_path):
    with pytest.raises(FileExistsError):
        export_evidence(evidence, portable)
    with pytest.raises(ValueError, match="outside"):
        export_evidence(evidence, evidence / "published")
    with pytest.raises(ValueError, match="original database"):
        export_evidence(portable, tmp_path / "reexport")


def test_cli_regrades_offline_and_rejects_invalid_bundle(evidence, tmp_path):
    output = tmp_path / "published"
    runner = CliRunner()
    assert (
        runner.invoke(app, ["eval-export", str(evidence), "--output", str(output)]).exit_code == 0
    )
    result = runner.invoke(app, ["eval-verify", str(output)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["verified_episodes"] == 60
    (output / "grading-state.json").unlink()
    assert runner.invoke(app, ["eval-verify", str(output)]).exit_code == 2
