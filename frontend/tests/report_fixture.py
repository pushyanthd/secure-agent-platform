"""Generate authored offline viewer fixtures for real-browser regression checks."""

import json
import shutil
import sys
from pathlib import Path

from agentguard.analysis import write_analysis
from agentguard.suite import run_suite

root, output = map(Path, sys.argv[1:])
fixtures = output / "fixtures"
fixtures.mkdir()
for name, source in (
    ("multi.json", "scenarios/dev/multi-attack/review.json"),
    ("single.json", "scenarios/dev/suite/launch-scope.json"),
):
    shutil.copyfile(root / source, fixtures / name)
suite = fixtures / "suite.json"
suite.write_text(
    json.dumps(
        {
            "schema_version": 1,
            "id": "browser-multi-attack",
            "split": "development",
            "tasks": ["multi.json", "single.json"],
        }
    )
)
run = run_suite(suite, output / "runs")
write_analysis(run, output / "multi", resamples=100)
response_run = run_suite(root / "scenarios/dev/response-scope-v1.json", output / "runs")
write_analysis(response_run, output / "response", resamples=100)
receipt_run = run_suite(root / "scenarios/dev/effect-receipt-treatment-v1.json", output / "runs")
write_analysis(receipt_run, output / "receipt", resamples=100)
write_analysis(
    root / "docs/evidence/fourteen-task-live-2026-09-24/run",
    output / "legacy",
    resamples=100,
)
print(json.dumps({"run": str(run), "output": str(output)}))
