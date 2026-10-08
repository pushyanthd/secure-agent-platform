"""Validate held-out authoring without querying a model or tuning defenses."""

import hashlib
import uuid
from pathlib import Path

from agentguard.computation import Computer
from agentguard.contracts import Profile
from agentguard.live import atomic_json
from agentguard.release import audit_corpus, sha, source_hash
from agentguard.reviewer import ExactActionReviewer
from agentguard.runtime import Budgets
from agentguard.scenarios import (
    attack_variants,
    episode_documents,
    grade_episode,
    load_suite,
    select_attack,
)
from agentguard.storage import Store
from agentguard.suite import run_script, summarize


def validate_corpus(
    suite: Path, lineage: Path, development: Path, output: Path, *, computer: Computer | None = None
) -> Path:
    audit = audit_corpus(suite, lineage, development)
    _, fixtures = load_suite(suite, allow_held_out=True)
    directory = output / str(uuid.uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    store = Store(directory / "state.sqlite3", computer=computer)
    rows = []
    failures = []
    variants: tuple[Profile, ...] = ("baseline", "defended")
    for _, _, task in fixtures:
        for profile in variants:
            for attack_id in (None, *(a.id for a in attack_variants(task))):
                selected = select_attack(task, attack_id)
                attacked = attack_id is not None
                script = selected.attacked_script if attacked else selected.clean_script
                if len(script.actions) + 1 > Budgets().max_steps:
                    raise ValueError(f"Authored path leaves no final-response step: {task.id}")
                episode = store.create_episode(
                    task.contract,
                    episode_documents(selected, attacked=attacked),
                    task.projects,
                    tickets=task.initial_tickets,
                    experimental_profile=profile,
                )
                reviewer = ExactActionReviewer(task.contract, task.review_contract)
                result = run_script(store, episode, script, reviewer)
                grade = grade_episode(
                    store, episode, result["final_response"], task.expectation, attacked=attacked
                )
                row = {
                    "episode_id": episode,
                    "task_id": task.id,
                    "profile": profile,
                    "attacked": attacked,
                    "attack_id": attack_id,
                    **result,
                    "grade": grade,
                }
                passed = result["status"] == "COMPLETED" and (
                    grade["attack_success"] is True
                    if attacked and profile == "baseline"
                    else grade["task_success"] is True and not grade["attack_success"]
                )
                if not passed:
                    failures.append(
                        {
                            "task_id": task.id,
                            "profile": profile,
                            "attack_id": attack_id,
                            "grade": grade,
                            "reason": result["reason"],
                        }
                    )
                rows.append(row)
    report = {
        "mode": "authored_held_out_validation",
        "fresh_inference": False,
        "model_trials": 0,
        "release_evidence": False,
        "containment": store.computer.mode,
        "source_sha256": source_hash(),
        "suite_sha256": sha(suite),
        "fixture_sha256": {str(n): hashlib.sha256(b).hexdigest() for n, b, _ in fixtures},
        "audit": audit,
        "scheduled_episodes": 400,
        "recorded_episodes": len(rows),
        "passed": len(rows) == 400 and not failures,
        "failures": failures,
        "counts": summarize(rows, variants),
        "episodes": rows,
        "limitation": (
            "Authored actions test boundaries/graders, not model utility or attack susceptibility."
        ),
    }
    atomic_json(directory / "validation.json", report)
    atomic_json(
        directory / "checksums.json", {"validation.json": sha(directory / "validation.json")}
    )
    return directory
