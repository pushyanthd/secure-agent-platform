import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from agentguard.cli import app
from agentguard.replay import Scenario, grade, run_replay

SCENARIO = Path(__file__).resolve().parents[1] / "scenarios/dev/launch-ticket.json"


def test_replay_grades_state_and_preserves_denominators(tmp_path):
    output = run_replay(SCENARIO, tmp_path)
    report = json.loads((output / "report.json").read_text())
    assert report["manifest"]["scheduled_episodes"] == len(report["episodes"]) == 4
    assert report["manifest"]["fresh_inference"] is False
    assert report["manifest"]["model"] is None
    rows = {(row["profile"], row["attacked"]): row["grade"] for row in report["episodes"]}
    assert rows["baseline", False]["task_success"]
    assert rows["defended", False]["task_success"]
    assert rows["baseline", True]["attack_success"]
    assert not rows["defended", True]["attack_success"]
    assert rows["defended", True]["task_success"]
    checksums = json.loads((output / "checksums.json").read_text())
    for name, checksum in checksums.items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == checksum


def test_denial_alone_is_not_success():
    rules = Scenario.model_validate_json(SCENARIO.read_text()).predicates
    result = grade([], "I completed the task", rules, attacked=True)
    assert result["task_success"] is False
    result = grade([], rules.canary, rules, attacked=True)
    assert result["attack_success"] is True


def test_cli_labels_scripted_results(tmp_path):
    result = CliRunner().invoke(
        app, ["demo-replay", "--scenario", str(SCENARIO), "--output", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "0 model trials" in result.output
