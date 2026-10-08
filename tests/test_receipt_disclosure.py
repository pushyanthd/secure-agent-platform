"""Receipt presentation cannot supply a workflow shortcut or weaken authority."""

import json
import runpy
import shutil
from pathlib import Path

import pytest
from test_receipt_pilot_report import rewrite
from test_runtime import FakeModel, action, reply
from test_worker import review, worker

from agentguard.contracts import TaskContract, canonical_json
from agentguard.runtime import Runtime, initial_messages, model_scope
from agentguard.scenarios import load_suite
from agentguard.suite import run_suite

CONTROL = Path("scenarios/dev/receipt-disclosure-control-v1.json")
TREATMENT = Path("scenarios/dev/receipt-disclosure-treatment-v1.json")
TASK = load_suite(TREATMENT)[1][0][2]


def episode_for(store):
    return store.create_episode(
        TASK.contract, TASK.documents, TASK.projects, tickets=TASK.initial_tickets
    )


def test_projection_retains_permissions_but_omits_action_and_selector():
    scope = model_scope(TASK.contract)
    assert scope["response_scope"]["effect_receipt"] == {"template": "ticket_update_v1"}
    assert scope["update_ticket_ids"] == ["triage-1"]
    assert scope["document_ids"] == ["guide"]
    assert "expected_version" not in canonical_json(scope)
    assert TASK.contract.response_scope.effect_receipt.action.arguments.expected_version == 1
    # A model-visible summary can never be parsed as trusted receipt authority.
    with pytest.raises(ValueError):
        TaskContract.model_validate(scope)


def test_legacy_full_scope_prompt_is_byte_compatible():
    raw = json.loads(
        Path("scenarios/dev/effect-receipt/confidential-response-triage-treatment.json").read_text()
    )
    contract = TaskContract.model_validate(raw["contract"])
    assert initial_messages(raw["task"], contract, hardened=True)[1]["content"] == canonical_json(
        {"task": raw["task"], "scope": raw["contract"]}
    )


def test_denial_feedback_keeps_receipt_action_private(store):
    model = FakeModel([reply(action("shared")), reply('{"kind":"final","text":"Done."}')])
    Runtime(store, model).run(episode_for(store), TASK.task)
    messages = model.requests[1][0]
    initial = json.loads(messages[1]["content"])["scope"]
    recovery = json.loads(messages[-1]["content"])["recovery"]["scope"]
    assert initial == recovery == model_scope(TASK.contract)
    assert "expected_version" not in canonical_json(recovery)


def test_recovery_keeps_original_projection_but_enforces_revoked_authority(store):
    episode = episode_for(store)
    responses = [
        reply(json.dumps({"kind": "action", "action": a.model_dump(mode="json")}))
        for a in TASK.clean_script.actions
    ]
    w = worker(store, responses)
    w.submit(episode, TASK.task)
    pending = w.run_once()
    review(store, pending["trace"][-1]["execution"]["approval_id"])
    with store.connection() as db:
        db.execute(
            "UPDATE episodes SET contract=json_set(contract,'$.update_ticket_ids',json('[]'),"
            "'$.response_scope.effect_receipt.model_disclosure','full_action') WHERE id=?",
            (episode,),
        )
    resumed = worker(store, [reply('{"kind":"final","text":"Done."}')])
    result = resumed.run_once()
    assert result["trace"][-1]["execution"]["decision"]["outcome"] == "DENY"
    assert result["response_decision"]["reason"] != "VERIFIED_EFFECT_RECEIPT"
    assert store.tickets(episode)[0]["version"] == 1
    messages = resumed.model.requests[0][0]
    assert json.loads(messages[1]["content"])["scope"] == model_scope(TASK.contract)
    assert json.loads(messages[-1]["content"])["recovery"]["scope"] == model_scope(TASK.contract)


@pytest.fixture(scope="module")
def disclosure_runs(tmp_path_factory):
    output = tmp_path_factory.mktemp("disclosure")
    return tuple(run_suite(s, output, variants=("defended",)) for s in (CONTROL, TREATMENT))


def test_disclosure_comparison_preserves_grading_and_trusted_receipt(disclosure_runs):
    compare = runpy.run_path("scripts/compare_receipt_pilot.py")["compare"]
    report = compare(*disclosure_runs, experiment="receipt_disclosure")
    assert report["experiment"] == "receipt_disclosure"
    assert not report["fresh_inference"] and not report["release_gate"]
    for arm in report["counts"].values():
        assert arm["clean_success"] == 1 and arm["attacked_task_success"] == 4
        assert arm["verified_effect_receipts"] == 5
    with pytest.raises(ValueError, match="Fixtures must differ only"):
        compare(*disclosure_runs)


def test_disclosure_comparison_rejects_reversed_treatment(disclosure_runs):
    compare = runpy.run_path("scripts/compare_receipt_pilot.py")["compare"]
    with pytest.raises(ValueError, match="Disclosure fixtures"):
        compare(*reversed(disclosure_runs), experiment="receipt_disclosure")


@pytest.mark.parametrize("change", ["action", "grader", "prose", "version"])
def test_disclosure_comparison_rejects_additional_treatment_changes(
    disclosure_runs, tmp_path, change
):
    import hashlib

    control, original = disclosure_runs
    treatment = tmp_path / "treatment"
    shutil.copytree(original, treatment)

    def alter(report):
        fixture = report["manifest"]["fixtures"][0]
        path = treatment / fixture["file"]
        raw = json.loads(path.read_text())
        if change == "action":
            raw["contract"]["response_scope"]["effect_receipt"]["action"]["arguments"]["body"] = (
                "Different update"
            )
        elif change == "grader":
            raw["expectation"]["required_reads"] = []
        elif change == "prose":
            raw["task"] += " Skip the document read."
        else:
            raw["contract"]["version"] += 1
        path.write_text(json.dumps(raw))
        fixture["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    rewrite(treatment, alter)
    compare = runpy.run_path("scripts/compare_receipt_pilot.py")["compare"]
    with pytest.raises(ValueError, match="Disclosure fixtures|Fixtures must differ only"):
        compare(control, treatment, experiment="receipt_disclosure")
