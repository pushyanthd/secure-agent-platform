# ADR 004: explicit final-response clearance, with a measured utility cost

Development treatment, September 24, 2026. Response policy: `response-clearance-v1`.
Tool policy remains `gateway-v3`. This treatment is opt-in and is not the default
operator catalogue or a passed portfolio release gate.

## Problem and contract

The ticket-scope treatment retained three final-response disclosures after authorized
confidential reads and correctly reviewed ticket updates. Tool approval binds a
single effect; it does not declassify the run or authorize a later response.

Add an optional trusted `TaskContract.response_scope` with a synthetic `recipient`
identifier and `max_classification` (`internal` or `confidential`). This represents
the intended response destination in the laboratory; it is not an external address,
identity authentication mechanism, or new network integration. The task author
selects it, and all profiles receive the same scope in the initial task message.
The model can propose response text but cannot set the recipient, clearance, or
sensitivity. Missing/null scope retains legacy unrestricted output behavior.

For defended runs, an internal-only destination cannot receive model-authored text
once the episode has consumed a confidential document, search snippet, or ticket
preview. A confidential destination can receive it. Reads that were denied do not
taint the run. Baseline and prompt-only bypass this business rule, retaining outer
episode containment and cancellation. There is no content classifier, canary scan,
expected-answer allowlist, encoding detector, or hidden grader input in the policy.

## Commit boundary and recovery

The live/durable runtime reads current response scope, sensitivity, and cancellation
inside the lease-fenced write transaction that stores its final result. The audit
record and result commit together. A denied response becomes an empty
`final_response` with reason `CONFIDENTIAL_RESPONSE_BLOCKED`; its decision identifies
the recipient, sensitivity, policy version, and contract binding hash. No proposed
response text is included in that audit record. Deadline and cancellation still
prevent output at the final checkpoint. The response decision is not an approval
grant and cannot be reused to authorize another response.

Scripted benchmark completion uses the same policy against current database state.
Both paths finish the execution as `COMPLETED` for a policy-withheld response:
execution is over, while the independent grader evaluates task success separately.
This is a resolved denial, not an infrastructure outage or an ungraded trial.
Missing final content still fails the task's unchanged output requirements.
Cancellation retains its own terminal status. Existing tool effects are not undone.

Raw model replies remain in the trusted local evidence store for recovery and
failure analysis, including denied text. A crash before final commit leaves no
response decision or visible final result; recovery rechecks the saved response
under current authority without another model generation. Expired/superseded
workers cannot finalize it. Code changes still invalidate old worker/benchmark
manifests; paused runs cannot silently switch policy implementations.

The authenticated timeline exposes only the outcome/reason. The offline viewer
shows withholding alongside the final-output field and independent grade. Reports
and raw transcripts are privileged evaluation artifacts: they can include source
documents, synthetic canaries, and baseline disclosures. **The claim is about the
final-response field, not sanitization of all local artifacts or host storage.**

## Controlled treatment and results

`scenarios/dev/response-scope-v1.json` copies the six tasks of expansion-v2, changing
only the contract version and adding an internal-only `task-response` destination.
Task prose, documents, labels, attacks, scripted proposals, reviewer contracts, and
grader predicates are unchanged. The original fixtures and evidence remain intact.

In authored replay, the defended profile moves from 6/6 to **5/6 clean success**
and from 21/24 to **20/24 attacked success**, while observed attacker wins move
from 3/24 to **0/24**. It withholds five responses: the clean confidential triage
answer, its three disclosures, and its safe answer after a denied shared-ticket
attack. All five fail their exact final-answer predicate; their reviewed ticket
updates remain committed. The other workflows preserve their outcomes.

This is a **16.7 percentage-point clean-utility loss** on six authored tasks.
It exceeds the architecture's proposed five-point utility-loss objective, even
though clean utility is above 80%. These are deterministic boundary checks with
zero model trials; they are neither held-out results nor estimated attack rates.
The treatment command exits 1 because the clean task fails. Zero observed wins
does not turn it into a successful product-quality gate.

## Consequences and next step

Keep the v5 operator catalogue as the default while publishing this opt-in result.
Coarse sensitivity is intentionally conservative: it blocks harmless paraphrases
and status messages alongside malicious content after a confidential read. It
cannot detect confidential data in mislabeled sources, task text, or model memory,
and an explicitly confidential destination permits disclosure by design. Scope
omission preserves the known legacy response gap; task authors must choose it
explicitly to enable this boundary.

A next treatment can use reviewer-authorized declassification or a response builder
driven by confirmed effects, with its own trusted contract and utility evaluation.
It must not copy expected grader answers into runtime policy or label a fixed
completion phrase as successful without checking the required state. Fresh-model
feasibility, held-out authoring/freeze, and release evaluation remain pending.

## Reproduce

```sh
make eval-response-scope  # 90 authored episodes; expected exit 1 for clean utility loss

uv run --locked agentguard eval-suite --suite scenarios/dev/response-scope-v1.json \
  --sandbox-manifest artifacts/sandbox/manifest.json
```

Use separate control settings pointing to this suite to demonstrate it interactively.
Do not replace a running instance's suite or policy while it has pending jobs.
`make eval-development` and `make eval-ticket-scope` retain their previous fixtures
and three known response disclosures.
