# Runtime diagnostics contract

Use `agentguard eval-diagnostics <run-directory> --output <directory>` after a
completed development-suite run. It performs no inference and does not modify
source evidence. The report is separate from task/security grading and the paired
statistical analysis.

## Inputs and integrity checks

The input directory must pass the existing checksum, source provenance, fixture,
schedule, and episode-identity checks. The diagnostics additionally require:

- Every saved model call belongs to a scheduled episode, with no duplicate
  `(episode_id, step)` identities and a contiguous zero-based step sequence.
- The number of saved calls equals the episode's `model_calls` count.
- Parsed response usage equals `generated_tokens`. When recorded, reserved and
  charged totals must agree too. A missing or malformed response reserves the
  request's complete output allowance; its actual generation remains unknown.
- Scripted replay contains no model calls. Latencies are finite and nonnegative;
  boolean values cannot masquerade as integer call fields.

These checks detect inconsistent evidence, not malicious modification by an owner
who can rewrite the evidence and its checksums. Response usage is reported by the
local server, not independently measured GPU work.

An abruptly interrupted benchmark episode may have unknown (`null`) elapsed time.
It remains in all outcome denominators but is excluded from duration distributions;
`unknown_episode_durations` reports this missing measurement. Available calls and
reserved allowances are reconciled exactly as for other episodes.

## What the report measures

The report includes per-episode and aggregate prompt/output token counts, reserved
allowances, reported context headroom, observed call and episode durations,
completion/failure reasons, schema repairs recorded by the runner, and tool counts
split by profile. Zero-use tools remain visible, so missing coverage cannot look
like complete coverage.

Context headroom is `context_tokens - reported_prompt_tokens - reported_output_tokens`.
It is computed only for valid response envelopes. The runtime's admission check
uses a separate tokenizer request, the next output allowance, and a 32-token
reserve. Those preflight counts are not stored in the current ledger; the
report deliberately does not label response headroom as admission headroom.

Tool counts describe actions with a recorded execution decision. A failed model
proposal or tool computation may not produce such an entry; inspect the raw calls
and failure reason for those cases. Simulated reviews are counted separately from
the final allowed/denied outcome. A review followed by an allowed effect is one
recorded action, not two effects.

For episodes with at least one denial, the report shows both final independent
task success and the narrower observation of a later allowed action followed by
task success. A refusal task can legitimately finish without a later action.
These are observations of the trace and final state, not a causal claim that the
policy improved recovery or a semantic classifier of false completion claims.

## Reproduce

```sh
make model-serve
# Separate terminal, with the fixed sandbox image available:
make eval-tools-live
uv run --locked agentguard eval-analyze artifacts/suites/<run-id> \
  --output artifacts/analyses/<run-id>
uv run --locked agentguard eval-diagnostics artifacts/suites/<run-id> \
  --output artifacts/diagnostics/<run-id>
```

Both output directories must be outside the immutable input directory and must
not already exist. Each output includes JSON, Markdown, implementation source,
and checksums. Reports preserve missing measurements as undefined. Observed
latencies under concurrent local load are not controlled performance comparisons.

## Policy cost, measured separately

```sh
uv run --locked agentguard policy-benchmark \
  --suite scenarios/dev/tools-v1.json \
  --samples 1000 --output artifacts/diagnostics/policy-<measurement-id>
```

This microbenchmark resolves authoritative development-fixture snapshots before
timing, then cycles through clean/attacked scripted proposals with both sensitivity
states. It performs 100 unmeasured warmup decisions and the requested number of
measured decisions. It never applies effects, calls a model, or runs a container.
The elapsed interval includes deterministic policy rules and canonical full-state
hashing; it excludes schema parsing, resource lookup/FTS, database persistence,
operator review, tool startup, and inference.

The export includes all raw decision durations, case/tool/outcome counts, fixture
and source hashes, and the initial architecture objective of P95 below 20 ms.
The objective result is descriptive, not a flaky CI timing gate or a claim about
whole-gateway latency. Compare it with end-to-end observations only after stating
these different boundaries. Uncontrolled local load and preconstructed snapshots
limit generalization to another machine or workload.
