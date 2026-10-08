"""Reject confounded model comparisons and ineligible utility candidates."""

import copy
import json
import runpy
from pathlib import Path

import pytest

STUDY = runpy.run_path("scripts/model_pilot.py")


@pytest.fixture
def pair():
    old = {
        "fresh_inference": True,
        "containment": "docker_isolated",
        "source_sha256": "same-source",
        "fixtures": [{"id": "case", "sha256": "same-fixture"}],
        "budgets": {"max_steps": 8},
        "schedule": [{"episode_id": "old", "task_id": "case", "attacked": False}],
        "model_config": {"model": "old", "temperature": 0.7, "seed": 42},
        "model": {
            "profile": {
                "runtime": {"commit": "same"},
                "platform": "Darwin-arm64",
                "model": {"sha256": "old"},
            },
            "server": {
                "build_info": "same",
                "total_slots": 1,
                "non_thinking": True,
                "template_source": "embedded",
                "chat_template": "old-template",
            },
        },
    }
    new = copy.deepcopy(old)
    new["schedule"][0]["episode_id"] = "new"
    new["model_config"]["model"] = "new"
    new["model"]["profile"]["model"]["sha256"] = "new"
    new["model"]["server"]["chat_template"] = "new-template"
    return old, new


def test_model_and_template_can_change_but_not_task_identity(pair):
    old, new = pair
    STUDY["compatible"](old, new)
    new["schedule"][0]["task_id"] = "easier-case"
    with pytest.raises(ValueError, match="scheduled inputs"):
        STUDY["compatible"](old, new)


@pytest.mark.parametrize(
    "path,value",
    [
        (("source_sha256",), "changed"),
        (("fixtures",), [{"id": "case", "sha256": "relaxed-grader"}]),
        (("budgets", "max_steps"), 16),
        (("model_config", "seed"), 43),
        (("model_config", "temperature"), 0.2),
        (("model", "profile", "runtime", "commit"), "changed"),
        (("model", "server", "non_thinking"), False),
        (("model", "profile", "model", "sha256"), "old"),
        (("fresh_inference",), False),
    ],
)
def test_rejects_undeclared_treatments(pair, path, value):
    old, new = pair
    target = new
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        STUDY["compatible"](old, new)


@pytest.mark.parametrize(
    "change",
    [
        {"clean_success": 6},
        {"attacked_success": 5},
        {"observed_attack_wins": 1},
        {"unresolved_attacked": 1},
        {"noncompleted": 1},
    ],
)
def test_security_counts_cannot_compensate_for_failed_utility_or_completion(change):
    old = {"clean_success": 4, "attacked_success": 3}
    new = {
        "clean_success": 7,
        "attacked_success": 6,
        "observed_attack_wins": 0,
        "unresolved_attacked": 0,
        "noncompleted": 0,
    }
    assert STUDY["eligible"](old, new, STUDY["RULE"])
    assert not STUDY["eligible"](old, new | change, STUDY["RULE"])
    assert not STUDY["eligible"](old | {"clean_success": 8}, new, STUDY["RULE"])


@pytest.mark.parametrize("profile", ["mac-instruct", "mac-medium"])
def test_candidate_preserves_runtime_sampling_and_default_profile(profile):
    old = json.loads(Path("config/model-mac-small.json").read_text())
    new = json.loads(Path(f"config/model-{profile}.json").read_text())
    assert old["runtime"] == new["runtime"]
    assert old["inference"] | {"model": new["inference"]["model"]} == new["inference"]
    assert old["model"]["filename"] == "Qwen3-4B-Q4_K_M.gguf"
    assert new["model"]["upstream_repository"] in (
        "Qwen/Qwen3-4B-Instruct-2507",
        "Qwen/Qwen3.5-9B",
    )
    assert new["model"]["revision"] in new["model"]["url"]
    assert new["model"]["upstream_revision"] in new["model"]["license_url"]
