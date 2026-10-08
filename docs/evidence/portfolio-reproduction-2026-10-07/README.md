# Fresh source and environment reproduction

Completed October 7, 2026 on the same PC under Ubuntu/WSL2. A new source snapshot,
Python environment, and dependency cache reproduced the reviewer commands
without model weights, inference, Docker, credentials, or original operational
databases. Dependency installation required network access.

| Check | Result |
|---|---|
| Locked dependency installation | PASS |
| Python tests | 735/735 passed |
| Ruff lint and formatting | PASS; 321 Python files checked |
| Strict mypy | PASS; 48 source files |
| Forty-template release corpus validation | PASS |
| Scripted replay and durable recovery demonstrations | PASS; zero model calls |
| Five published PC studies | All 124 saved state/output grades match, including failures |

- [Exact source file hashes and command results](result.json)
- [Complete test, lint, formatting, and typing log](logs/contracts.log)
- [Release corpus validation](logs/release-corpus.log)
- [Replay](logs/replay.log) and [durable demonstration](logs/durable.log)
- [Decision review regrading](logs/verify-pc-decision-review-2026-10-07.log)

The first attempt passed 734 tests but failed the subprocess interruption test
because the repository-local bootstrap `uv` executable was absent from child
`PATH`. The reproduction helper now adds its selected uv directory to that
environment. A new snapshot then passed every test; the first attempt's
[result](initial-attempt.json) and [failure log](initial-contracts.log) are retained.
No test was skipped or relaxed to fix executable discovery.

## Reproduce

From a Git checkout on Linux, macOS, or Ubuntu/WSL2:

```sh
uv sync --locked
make portfolio-check
```

The helper copies Git-tracked and nonignored new source files, preserves frozen
publication bytes, normalizes working source to LF, and creates a new virtual
environment and cache. It refuses to overwrite an existing result directory.
It runs `make check`, validates the corpus, executes the two fixture demos, and
verifies every publication containing portable grading state. Results and logs
are saved under ignored `artifacts/portfolio-check-<UTC timestamp>/`.

This is same-author, same-PC reproduction, not independent external validation.
It does not rerun fresh inference, browser scenarios, container probes, or the
behavioral release gate. Published grades matching their state does not turn
failed tasks or rejected configurations into successes. Source hashes identify
the captured working snapshot; subsequent documentation publication is separate.
