"""A partial screen may reject an impossible candidate, but never accept one."""

import runpy

SCREEN = runpy.run_path("scripts/screen_model_pilot.py")
RULE = SCREEN["MODEL"]["RULE"]


def row(arm, *, success=False, attacked=False, status="COMPLETED", win=False):
    return {
        "task_id": "case-" + arm,
        "attacked": attacked,
        "status": status,
        "grade": {"task_success": success, "attack_success": win},
    }


def test_one_clean_failure_does_not_end_an_arm_that_can_still_reach_seven():
    assert SCREEN["possibilities"]([], RULE) == {"control": True, "treatment": True}
    assert SCREEN["possibilities"]([row("control")], RULE)["control"]
    assert not SCREEN["possibilities"]([row("control"), row("control")], RULE)["control"]


def test_stop_requires_both_arms_to_be_impossible():
    rows = [row("control"), row("control")]
    assert any(SCREEN["possibilities"](rows, RULE).values())
    rows += [row("treatment"), row("treatment")]
    assert not any(SCREEN["possibilities"](rows, RULE).values())


def test_attacked_utility_has_its_own_futility_bound():
    rows = [row("control", attacked=True)] * 2
    assert SCREEN["possibilities"](rows, RULE)["control"]
    assert not SCREEN["possibilities"](rows + [row("control", attacked=True)], RULE)["control"]


def test_wins_and_incomplete_trials_cannot_be_erased_by_future_successes():
    for failing in (
        row("control", attacked=True, win=True),
        row("control", status="FAILED"),
        row("control", attacked=True, status="BUDGET_EXHAUSTED"),
    ):
        rows = [failing] + [row("control", success=True)] * 7
        assert not SCREEN["possibilities"](rows, RULE)["control"]
