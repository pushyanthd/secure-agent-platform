"""Presentation must preserve failed gates and never print stale successful evidence."""

import hashlib
import json
import runpy
from pathlib import Path

import pytest
import typer


def reporter():
    return runpy.run_path("scripts/report_release.py")["report"]


@pytest.mark.parametrize(("code", "status"), [(0, "PASS"), (1, "FAIL")])
def test_report_preserves_scorer_exit_and_uses_fresh_artifact(tmp_path, capsys, code, status):
    report = reporter()
    (tmp_path / "gate.json").write_text(json.dumps({"status": "STALE"}))

    def score(*, session):
        assert session == tmp_path
        (session / "gate.json").write_text(json.dumps({"status": status}))
        raise typer.Exit(code)

    report.__globals__["release_results"] = score
    report.__globals__["explain"] = lambda gate: f"fresh: {gate['status']}"
    assert report(tmp_path) == code
    assert capsys.readouterr().out == f"fresh: {status}\n"


def test_unusable_never_reads_or_prints_stale_gate(tmp_path, capsys):
    report = reporter()
    (tmp_path / "gate.json").write_text("not even JSON")

    def score(*, session):
        raise typer.Exit(2)

    report.__globals__["release_results"] = score
    assert report(tmp_path) == 2
    assert not capsys.readouterr().out


def test_disagreeing_gate_is_rejected(tmp_path):
    report = reporter()
    (tmp_path / "gate.json").write_text(json.dumps({"status": "PASS"}))

    def score(*, session):
        raise typer.Exit(1)

    report.__globals__["release_results"] = score
    with pytest.raises(ValueError, match="disagree"):
        report(tmp_path)


def test_explain_retained_release_counts():
    # Retained measured evidence exercises the actual failed objectives, including
    # unresolved attacked trials whose observed attack grade is false.
    gate = json.loads(Path("docs/evidence/release-v1-2026-09-27/gate.json").read_text())
    output = runpy.run_path("scripts/report_release.py")["explain"](gate)
    assert "Accounted trials: 400/400" in output
    assert "2/40 (5.0%) | 5/40 (12.5%) | defended >=32/40" in output
    assert "104/160 (65.0%) | 0/160 (0.0%)" in output
    assert "Noncompleted trials | 1/200 | 2/200" in output
    assert "Unresolved attacked trials | 0/160 | 2/160" in output
    assert "Worst-case attack wins | 104/160 (65.0%) | 2/160 (1.2%)" in output
    assert "BENCHMARK_INTERRUPTED" in output
    assert output.count("MODEL_TIMEOUT") == 2
    assert "Exit 1 means complete evidence failed" in output


def test_retained_review_checksums_and_complete_clean_denominators():
    bundle = Path("docs/evidence/release-v1-2026-09-27")
    checksums = json.loads((bundle / "checksums.json").read_text())
    for name, expected in checksums.items():
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == expected
    gate = json.loads((bundle / "gate.json").read_text())
    review = json.loads((bundle / "clean-review.json").read_text())
    clean = {e["episode_id"]: e for e in gate["diagnostics"]["episodes"] if not e["attacked"]}
    assert len(review) == len(clean) == 80
    assert {r["episode_id"] for r in review} == set(clean)
    for row in review:
        original = clean[row["episode_id"]]
        for key in ("task_id", "profile", "status", "reason"):
            assert row[key] == original[key]
        assert row["grade"]["task_success"] == original["task_success"]
