# Offline state regrading

The published October 7 PC studies include enough committed state to independently
recompute every task and attack grade. No model weights, Docker, server, operator
token, or original SQLite database are needed after dependency installation.

```sh
uv sync --locked
uv run --locked agentguard eval-verify docs/evidence/pc-development-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-utility-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-completion-guard-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-completion-broad-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-decision-review-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-structured-review-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-workflow-comparison-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-resource-completion-2026-10-07/run
```

The commands verify 20, 32, 8, 32, 32, 32, 116, and 116 saved outcomes, respectively. Successful verification
means the published grades agree with the published state, including all failed
tasks. It does not mean the model passed a utility selection rule or release gate.

## Export a completed synthetic benchmark

```sh
uv run --locked agentguard eval-export artifacts/suites/<run-id> \
  --output artifacts/publication/<run-id>/run
uv run --locked agentguard eval-verify artifacts/publication/<run-id>/run
uv run --locked agentguard eval-analyze artifacts/publication/<run-id>/run \
  --output artifacts/publication/<run-id>/analysis
uv run --locked agentguard eval-diagnostics artifacts/publication/<run-id>/run \
  --output artifacts/publication/<run-id>/diagnostics
```

The exporter requires complete checksummed evidence, the original SQLite backup,
matching benchmark journal/model-call exports, and the original grader, contracts,
and storage source. It rejects pending database WAL data, overwritten destinations,
and output inside the original run. It copies the database into temporary storage
and verifies the extracted grades before creating the publication directory.
The original evidence remains unchanged.

`grading-state.json` contains each scheduled episode's final tickets, final shares,
proposal hashes, and saved tool outcomes. Failed read attempts are retained even
when they produced no allowed result. Approval references are removed from the
state projection; approvals, nonces, worker tokens, credentials, and operational
queue tables are not exported. Other published run files preserve the original
fixtures, source, requests, responses, traces, grades, and session history.

`original-run-checksums.json` binds the metadata to its original extract, including
the checksum of the excluded database. The publication's own `checksums.json`
also covers the new state projection. All state rows must match the complete
scheduled results in order. Unknown state fields are rejected.

## What verification establishes

The verifier imports only the typed grading fields into a temporary database. It
runs the existing independent state/output grader and requires exact agreement
with every saved grade, including detailed failure evidence and completion status.
It never dispatches a tool, contacts a model, resumes an episode, or executes
Python from the evidence bundle. It requires the installed `scenarios.py`,
`contracts.py`, and `storage.py` to match the frozen source captured for that run.
Future incompatible code requires the corresponding source checkout.

Checksums detect inconsistent or accidentally modified evidence. The publisher can
rewrite both state and checksums, so they are not proof against forgery. This
projection cannot recheck approval lifecycle, audit integrity, worker fencing,
containment, or the complete release gate. Those require original operational
evidence and separate checks. Historical extracts without grading state remain
limited to their previously documented review capabilities.

This is an exporter for this project's synthetic benchmark runs. It does not
redact arbitrary secrets from transcripts or fixtures. Raw model/tool content
remains privileged evaluation data and must be reviewed before publication.
