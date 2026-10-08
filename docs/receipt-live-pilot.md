# Targeted live feasibility for completion receipts

The receipt's first experiment used authored responses. This pilot uses the pinned
local model to test the known confidential-triage false block, with the same task
and four attacks in both arms. It is a **development pilot, not the 400-episode
release benchmark**.

Two one-task suites reference the existing fixtures without changing them:

- `receipt-live-pilot-control-v1.json`: response clearance, contract v4.
- `receipt-live-pilot-treatment-v1.json`: verified update receipt, contract v5.

Each schedules one clean input and four fixed attacks under **defended only**:
5 + 5 = 10 fresh episodes. Source documents, payloads, task wording, grading,
reviewer rules, model settings, and budgets are identical. The treatment adds the
explicit receipt scope and contract version. No baseline/prompt-only inference is
part of this pilot, so it cannot establish comparative attack reduction.

The task is selected because the earlier authored experiment exposed a false
block. It is a targeted known case, not a random sample or an untouched task.
The additional receipt scope is visible in the model's initial task message, so
the treatment can also affect earlier model behavior. The arms run sequentially,
control first, with the same declared seed; order is not randomized. This comparison reports counts rather than treating one task cluster and one
trial per input as an estimate of generalization.

## Reproduce

Start Docker and the already-installed pinned model:

```sh
make model-serve
```

In another terminal, run these commands separately. Both arms failed the existing smoke exit rules in the published pilot; do not
chain the two commands with `&&`:

```sh
make eval-receipt-pilot-control-live
make eval-receipt-pilot-treatment-live
```

Each prints a UUID directory under `artifacts/suites/`. Both retain every scheduled
result and raw model-call evidence. `--max-episodes` and pause/resume remain
available through the underlying `agentguard eval-suite` CLI; see the
[session runbook](resumable-benchmarks.md). No result is regenerated to replace a
failed trial.

After both finish, verify the cross-run comparison:

```sh
.venv/bin/python scripts/compare_receipt_pilot.py \
  artifacts/suites/<control-run-id> artifacts/suites/<treatment-run-id> \
  > artifacts/receipt-pilot-comparison.json
```

The comparator verifies checksums, complete scheduled identities, raw-call/token
accounting, matching execution/provenance fields, and the exact permitted fixture
difference. It derives counts from individual outcomes, retaining incomplete trials
in denominators and worst-case attack bounds. It also checks whether each attack
payload appears in a saved model request and whether both arms solve the clean
task. Replay exposure is unmeasured (`null`), not zero. A recorded request is not
server-side attestation after a network failure. It rejects missing/incompatible
reports with exit 2. Exit 0 means a **usable comparison**, not passing utility,
security, or release objectives. Its output labels replay explicitly if used on
scripted inputs; replay cannot acquire a fresh-inference label from this command.

Published [live evidence and episode review](evidence/receipt-live-pilot-2026-09-25/README.md)
keep the two arms separate and preserve raw model finals alongside delivered
responses. Those privileged artifacts contain only synthetic organization data,
but are not sanitized by the final-response policy. Inspect both the independently
graded state and the response decision; a tool denial or a completion receipt alone
cannot prove whole-task success.

The next release steps are in [when to run the 400-episode evaluation](release-evaluation.md).
A successful targeted pilot does not replace broader development coverage,
held-out authoring, split review, freeze enforcement, or the release-specific gate.

The next [receipt-disclosure experiment](adr-006-model-visible-receipt-scope.md)
compares the same receipt authority with full-action versus template-only model
input. Its separate suites and `--experiment receipt_disclosure` comparator mode
preserve this pilot's inputs and failures. The original comparator defaults to
`receipt_authority`; do not compare the two studies as interchangeable arms.
