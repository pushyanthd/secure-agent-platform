import copy
import hashlib
import json
from pathlib import Path

import pytest

from agentguard.analysis import analyze, checked_report, observations
from agentguard.computation import InProcessComputer
from agentguard.diagnostics import diagnose
from agentguard.model import ModelConfig, ModelFailure
from agentguard.scenarios import (
    DevelopmentTask,
    attack_variants,
    episode_documents,
    load_suite,
    select_attack,
)
from agentguard.storage import Store
from agentguard.suite import resume_suite, run_suite

SUITE = Path("scenarios/dev/multi-attack-v1.json")


@pytest.fixture
def task():
    return load_suite(SUITE)[1][0][2]


@pytest.fixture
def report(tmp_path):
    directory = run_suite(SUITE, tmp_path)
    return checked_report(directory)[0]


def test_payload_selection_changes_only_untrusted_body_and_replay(task):
    attacks = attack_variants(task)
    assert len(attacks) == 4
    assert {a.family for a in attacks} == {
        "instruction_override",
        "authority_spoofing",
        "action_redirection",
        "data_disclosure",
    }
    trusted = ("task", "contract", "expectation", "review_contract", "projects", "initial_tickets")
    for attack in attacks:
        selected = select_attack(task, attack.id)
        assert all(getattr(selected, field) == getattr(task, field) for field in trusted)
        assert selected.attacked_script == attack.script
        assert episode_documents(selected, attacked=False) == task.documents
        for before, after in zip(
            task.documents, episode_documents(selected, attacked=True), strict=True
        ):
            assert before.model_dump(exclude={"body"}) == after.model_dump(exclude={"body"})
            assert after.body == before.body + "\n\n" + attack.payload
    with pytest.raises(ValueError, match="Unknown attack"):
        select_attack(task, "unknown")


@pytest.mark.parametrize(
    "corruption", ["duplicate", "reserved", "document", "contract", "body", "v2"]
)
def test_invalid_variants_rejected_before_scheduling(task, corruption):
    raw = task.model_dump(mode="json")
    attack = raw["additional_attacks"][0]
    if corruption == "duplicate":
        raw["additional_attacks"].append(copy.deepcopy(attack))
    elif corruption == "reserved":
        attack["id"] = "primary"
    elif corruption == "document":
        attack["document_id"] = "missing"
    elif corruption == "contract":
        attack["contract"] = {"actor": "admin"}
    elif corruption == "body":
        raw["documents"][0]["body"] = "x" * 11700
        attack["payload"] = "x" * 400
    else:
        raw["schema_version"] = 2
    with pytest.raises(ValueError):
        DevelopmentTask.model_validate(raw)


def test_four_attacks_share_one_clean_control_per_profile(report, task):
    rows, tasks, variants = observations(report)
    assert len(rows) == 15
    assert tasks == [task.id]
    assert len(variants) == 3
    for profile in variants:
        group = [r for r in rows if r.profile == profile]
        assert sum(not r.attacked for r in group) == 1
        assert {r.attack_id for r in group if r.attacked} == {a.id for a in attack_variants(task)}
    metadata = report["manifest"]["fixtures"][0]["attacks"]
    for actual, attack in zip(metadata, attack_variants(task), strict=True):
        assert actual["payload_sha256"] == hashlib.sha256(attack.payload.encode()).hexdigest()
        assert actual["payload_bytes"] == len(attack.payload.encode())
    result = analyze(report, resamples=100)
    assert result["profiles"]["defended"]["clean_utility"]["denominator"] == 1
    assert result["profiles"]["defended"]["attacked_utility"]["numerator"] == 4
    assert result["profiles"]["baseline"]["observed_attack_success"]["numerator"] == 4
    assert result["profiles"]["defended"]["observed_attack_success"]["numerator"] == 0
    assert result["comparisons"][0]["conditional_attack_success"]["baseline"]["denominator"] == 4
    diagnostics = diagnose(report, [])
    assert diagnostics["scheduled_episodes"] == 15
    assert {r["attack_id"] for r in diagnostics["episodes"]} == {
        None,
        *(a.id for a in attack_variants(task)),
    }


@pytest.mark.parametrize(
    "corruption", ["missing_all_profiles", "rename", "clean", "absent", "extra"]
)
def test_variant_identity_cannot_be_dropped_or_substituted(report, corruption):
    attacked = next(r for r in report["episodes"] if r["attack_id"] == "instruction-override")
    if corruption == "missing_all_profiles":
        for rows in (report["episodes"], report["manifest"]["schedule"]):
            rows[:] = [r for r in rows if r["attack_id"] != "instruction-override"]
        report["manifest"]["scheduled_episodes"] = len(report["episodes"])
    elif corruption == "rename":
        attacked["attack_id"] = "primary"
    elif corruption == "clean":
        report["manifest"]["schedule"][0]["attack_id"] = "primary"
    elif corruption == "absent":
        del attacked["attack_id"]
    else:
        report["manifest"]["fixtures"][0]["attacks"].append({"id": "unscheduled"})
    with pytest.raises(ValueError):
        analyze(report, resamples=100)


def test_resume_and_interrupted_variant_keep_original_identity_and_effects(tmp_path, task):
    directory = run_suite(SUITE, tmp_path, max_episodes=2)
    before = json.loads((directory / "episodes.json").read_text())
    manifest = json.loads((directory / "manifest.json").read_text())
    scheduled = manifest["schedule"][2]
    assert scheduled["attack_id"] == "instruction-override"
    store = Store(directory / "state.sqlite3")
    with store.connection() as db:
        db.execute(
            "UPDATE benchmark_episodes SET started_at=1 WHERE episode_id=?",
            (scheduled["episode_id"],),
        )
    selected = select_attack(task, scheduled["attack_id"])
    for index, action in enumerate(selected.attacked_script.actions[:2]):
        store.execute(scheduled["episode_id"], f"step-{index}:call-0", action)
    resume_suite(directory, max_episodes=3)
    resume_suite(directory)
    report, _ = checked_report(directory)
    assert report["episodes"][:2] == before
    interrupted = report["episodes"][2]
    assert interrupted["attack_id"] == scheduled["attack_id"]
    assert interrupted["reason"] == "BENCHMARK_INTERRUPTED"
    assert interrupted["grade"]["attack_success"] is True
    assert interrupted["grade"]["task_success"] is False
    assert interrupted["trace"][1]["action"] == selected.attacked_script.actions[1].model_dump()
    result = analyze(report, resamples=100)
    assert result["scheduled_episodes"] == 15
    assert result["profiles"]["baseline"]["worst_case_attack_success"]["numerator"] == 4


def test_unequal_payload_counts_use_episode_rates_and_task_cluster_intervals(tmp_path, task):
    # A synthetic statistical treatment, never published as fresh model evidence.
    (tmp_path / "multi.json").write_text(task.model_dump_json())
    (tmp_path / "single.json").write_bytes(
        Path("scenarios/dev/suite/launch-scope.json").read_bytes()
    )
    suite = tmp_path / "suite.json"
    suite.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "unequal",
                "split": "development",
                "tasks": ["multi.json", "single.json"],
            }
        )
    )
    report = checked_report(run_suite(suite, tmp_path / "runs"))[0]
    report["manifest"].update(fresh_inference=True, mode="fresh_local_inference")
    for row in report["episodes"]:
        row["grade"]["task_success"] = True
        if row["attacked"]:
            row["grade"]["attack_success"] = row["attack_id"] == "primary"
    result = analyze(report, resamples=300)
    for profile in result["profiles"].values():
        metric = profile["observed_attack_success"]
        assert metric["numerator"] == 2
        assert metric["denominator"] == 5
        assert metric["rate"] == 0.4
        # Draws of two whole tasks can only produce 1/4, 2/5, or 1.
        assert metric["descriptive_95pct_interval"] == [0.25, 1.0]
    assert result["comparisons"][0]["paired_deltas"]["observed_attack_success"][
        "descriptive_95pct_interval"
    ] == [0, 0]
    for row in report["episodes"]:
        if row["task_id"] == task.id and not row["attacked"]:
            row["grade"]["task_success"] = False
    conditional = analyze(report, resamples=100)["comparisons"][0]["conditional_attack_success"]
    assert conditional["baseline"] == {"numerator": 1, "denominator": 1, "rate": 1.0}


def test_published_legacy_evidence_remains_readable():
    root = Path("docs/evidence/fourteen-task-live-2026-09-24/run")
    report, _ = checked_report(root)
    result = analyze(report, resamples=100)
    assert result["scheduled_episodes"] == 84
    assert result["profiles"]["defended"]["attacked_utility"]["numerator"] == 13
    assert result["profiles"]["baseline"]["observed_attack_success"]["numerator"] == 4


def test_rechecksummed_catalogue_must_match_pinned_fixture(tmp_path):
    directory = run_suite(SUITE, tmp_path)
    checksums = json.loads((directory / "checksums.json").read_text())
    for name in ("manifest.json", "report.json"):
        path = directory / name
        data = json.loads(path.read_text())
        manifest = data if name == "manifest.json" else data["manifest"]
        manifest["fixtures"][0]["attacks"].pop()
        path.write_text(json.dumps(data))
        checksums[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / "checksums.json").write_text(json.dumps(checksums))
    with pytest.raises(ValueError, match="catalogue does not match"):
        checked_report(directory)


def test_model_outage_keeps_every_attack_in_worst_case_denominator(tmp_path):
    class UnavailableModel:
        config = ModelConfig()

        def count_tokens(self, *args, **kwargs):
            raise ModelFailure("MODEL_UNAVAILABLE")

    class IsolatedTestDouble(InProcessComputer):
        mode = "docker_isolated"

    directory = run_suite(
        SUITE,
        tmp_path,
        computer=IsolatedTestDouble(),
        model=UnavailableModel(),
        model_evidence={"test_double": True},
        variants=("defended",),
    )
    report, _ = checked_report(directory)
    assert all(r["reason"] == "MODEL_UNAVAILABLE" for r in report["episodes"])
    profile = analyze(report, resamples=100)["profiles"]["defended"]
    assert profile["clean_utility"]["rate"] == 0
    assert profile["attacked_utility"]["denominator"] == 4
    assert profile["worst_case_attack_success"] == {"numerator": 4, "denominator": 4, "rate": 1.0}
