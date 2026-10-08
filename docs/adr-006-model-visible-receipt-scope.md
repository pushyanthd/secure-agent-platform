# ADR 006: separate receipt authority from model-visible scope

Development experiment, September 25, 2026. Tool and response authorization
policies and the default v5 catalogue are unchanged.

## Problem and decision

The [first live receipt pilot](evidence/receipt-live-pilot-2026-09-25/README.md)
produced five valid receipts but zero successful tasks in its receipt arm. The
model skipped required document reads and ticket listing. Its initial scope
included the complete receipt action, including the ticket's expected version.
Providing that action may have encouraged the shortcut; this is a hypothesis
from one development task, not an established general cause.

Add a trusted `effect_receipt.model_disclosure` selector:

- `full_action` preserves the original model-visible action and is the default.
- `template_only` exposes only `{"template":"ticket_update_v1"}` as the receipt
  scope. The exact action remains mandatory in the trusted task contract.

The selector itself is omitted from model input. The projection keeps actor,
workspace, document/project permissions, editable ticket IDs, response recipient,
and response clearance. Both initial prompts and denial reminders use it. No
additional workflow instruction is introduced, and the model still discovers
ticket versions through `tickets.list`. The existing full-action prompt content
is preserved byte for byte.

The gateway, reviewer, and final-response verifier continue reading the complete
trusted contract. Presentation cannot grant permission or weaken effect checks.
The model output schema cannot configure receipts. A template-only scope cannot
be parsed as a complete trusted receipt contract because its action is absent.

## Durable recovery

Previously the runtime reconstructed a `TaskContract` from the initial model
message to replay saved calls. A projected scope deliberately lacks authority
details, so it must never serve that purpose.

Recovery now restores the original presentation as presentation, checks the
original task and system prompt, and reconstructs denial feedback consistently.
The worker's execution manifest still binds recovery to source, model, and tool
backend. Tool execution and receipt verification independently load current
trusted authority, including revocations made during an approval wait. No database
migration is needed. Existing jobs require the original execution manifest.

Regression checks cover both receipt presentations: missing effects, stale state,
revoked permissions, changed contracts, missing/unused approvals, cancellation,
deadlines, and recovery after finalization failure. A separate recovery case
changes presentation and revokes ticket access while waiting; the saved prompt
stays narrow and the update is denied under current authority.

## Matched experiment

`receipt-disclosure-control-v1` reuses the original full-action receipt fixture,
contract v5. `receipt-disclosure-treatment-v1` uses contract v6 and adds only
`model_disclosure: template_only`. Task prose, documents, ticket state, four
payloads, scripts, reviewer actions, and every grading predicate are unchanged.

Each arm runs five defended episodes: one clean and four attacked. Model,
sampling, budgets, source, and Docker tool image must match. The comparator's
`receipt_disclosure` mode rejects differences outside the selector and contract
version, checks complete episode identities and provenance, and reports required
read/list completion and payload exposure separately from valid receipts.

These are new paired executions. They do not pool with or regrade the previous
clearance-versus-receipt pilot. The new control is full-action receipt authority,
not response clearance without receipts. Control runs first, without randomized
order. One task and one trial per input cannot establish generalization or
comparative attack reduction against baseline/prompt-only.

## Reproduce

Start Docker and the pinned model with `make model-serve`. Run separately so a
failed control grade does not suppress treatment execution:

```sh
make eval-receipt-disclosure-control-live
make eval-receipt-disclosure-treatment-live

.venv/bin/python scripts/compare_receipt_pilot.py \
  artifacts/suites/<control-run-id> artifacts/suites/<treatment-run-id> \
  --experiment receipt_disclosure
```

Comparator exit 0 means compatible evidence, not passed utility or release
objectives. Use the same suites without `--live` for authored regression replay;
that performs zero inference and cannot measure recovery of model behavior.

Keep this treatment opt-in. Broader development feasibility, held-out authoring,
lineage review, freeze enforcement, and the release gate remain separate work.

## Measured result

The [ten-episode live follow-up](evidence/receipt-disclosure-2026-09-25/README.md)
recovered 1/1 clean and 4/4 attacked task success in treatment; full-action control
retained 0/1 and 0/4. Required reads/listing completed in 5/5 treatment episodes,
and all four treatment payloads reached saved model requests. One induced shared
write was denied and the model recovered. Both arms had five valid receipts and
zero observed attacker wins, but the control encountered no payloads. All grades
were independently rechecked. This supports the targeted workflow hypothesis,
not general attack resistance or a held-out release claim.
