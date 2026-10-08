import json
import tarfile
from pathlib import Path

from typer.testing import CliRunner

from agentguard import live
from agentguard.cli import app
from agentguard.computation import InProcessComputer
from agentguard.model import ModelConfig, ModelFailure
from agentguard.model_setup import sha256_file

SCENARIO = Path(__file__).resolve().parents[1] / "scenarios/dev/launch-ticket.json"


def test_unavailable_model_cannot_improve_paired_report(tmp_path, monkeypatch):
    model_file = tmp_path / "artifacts/models/test.gguf"
    model_file.parent.mkdir(parents=True)
    model_file.write_bytes(b"test double, not weights")
    archive = tmp_path / "artifacts/runtime/test.tar.gz"
    archive.parent.mkdir(parents=True)
    with tarfile.open(archive, "w:gz"):
        pass
    profile = {
        "schema_version": 1,
        "model": {"filename": model_file.name, "sha256": sha256_file(model_file)},
        "runtime": {"filename": archive.name, "sha256": sha256_file(archive), "release": "test"},
        "inference": ModelConfig().model_dump(),
    }
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile))

    class UnavailableModel:
        def __init__(self, config):
            self.config = config

        def request(self, *args, **kwargs):
            raise ModelFailure("MODEL_UNAVAILABLE")

        def count_tokens(self, *args, **kwargs):
            raise ModelFailure("MODEL_UNAVAILABLE")

    class TestComputer(InProcessComputer):
        image_id = "test_double"

    monkeypatch.setattr(live, "LocalModel", UnavailableModel)
    monkeypatch.setattr(live.DockerComputer, "from_manifest", lambda _: TestComputer())
    output = live.run_live_smoke(
        SCENARIO, profile_path, tmp_path / "unused", tmp_path / "runs", root=tmp_path
    )
    report = json.loads((output / "report.json").read_text())
    assert sha256_file(output / "scenario.json") == report["manifest"]["scenario_sha256"]
    assert len(report["episodes"]) == report["manifest"]["scheduled_episodes"] == 6
    assert all(row["status"] == "FAILED" for row in report["episodes"])
    for count in report["counts"].values():
        assert count["clean_success"] == count["attacked_task_success"] == 0
        assert count["completed"] == count["observed_attack_wins"] == 0
        assert count["noncompleted"] == 2
        assert count["unresolved_attacked"] == count["worst_case_attack_wins"] == 1
    checksums = json.loads((output / "checksums.json").read_text())
    for name, checksum in checksums.items():
        assert sha256_file(output / name) == checksum


def test_completed_claim_without_clean_task_success_fails_smoke_command(tmp_path, monkeypatch):
    (tmp_path / "report.md").write_text("Completed claim; independent task grade is false.\n")
    (tmp_path / "report.json").write_text(
        json.dumps(
            {
                "episodes": [
                    {
                        "status": "COMPLETED",
                        "attacked": False,
                        "grade": {"task_success": False},
                    }
                ]
            }
        )
    )
    manifest = tmp_path / "sandbox.json"
    manifest.write_text("{}")
    monkeypatch.setattr("agentguard.cli.run_live_smoke", lambda *args, **kwargs: tmp_path)
    result = CliRunner().invoke(app, ["eval-smoke", "--sandbox-manifest", str(manifest)])
    assert result.exit_code == 1
    assert "independent task grade is false" in result.output
