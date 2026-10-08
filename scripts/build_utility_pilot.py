"""Render exposed-family development examples; --check detects fixture drift."""

import argparse
import copy
import json
from pathlib import Path

from build_held_out import render

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "scenarios/dev/utility-pilot"


def build():
    catalogue = json.loads((CORPUS / "catalogue.json").read_text())
    files, task_paths = {}, []
    for index, case in enumerate(catalogue["cases"]):
        # Deliberately reuse the known resource/attack plumbing, not a holdout claim.
        original = render(case, 0)
        original["schema_version"] = 2
        original.pop("additional_attacks")
        # Alternate which arm runs first across cases; clean then primary attack.
        arms = ("control", "treatment") if index % 2 == 0 else ("treatment", "control")
        for arm in arms:
            task = copy.deepcopy(original)
            task["id"] = f"{case['id']}-{arm}"
            task["contract"]["task_id"] = task["id"]
            if arm == "treatment":
                task["task"] += catalogue["treatment_suffix"]
            path = f"tasks/{task['id']}.json"
            task_paths.append(path)
            files[CORPUS / path] = task
    files[CORPUS / "suite.json"] = {
        "schema_version": 1,
        "id": catalogue["study_id"],
        "split": "development",
        "tasks": task_paths,
    }
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, value in build().items():
        rendered = json.dumps(value, indent=2) + "\n"
        if args.check:
            if not path.is_file() or path.read_text() != rendered:
                raise SystemExit(f"Fixture drift: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered)
