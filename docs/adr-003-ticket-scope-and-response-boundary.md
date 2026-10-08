# ADR 003: ticket-scoped updates and the remaining response boundary

Accepted for development on September 24, 2026. Policy: `gateway-v3`.

## Evidence and decision

The expansion-v1 replay exposed four writes to protected sibling tickets inside
otherwise authorized projects. Project membership, writer ACLs, and optimistic
versions were insufficient to express the trusted task's instruction to update
only one ticket. Add `TaskContract.update_ticket_ids` to narrow update authority
independently of project inventory visibility.

An explicit list permits updates only to those IDs; an empty list permits none.
Missing/null preserves legacy project-wide update authority. This compatibility
choice is deliberate: old fixtures and saved control settings keep their declared
scope, including their exposed sibling-edit paths. **An omitted field is not a
restrictive default.** All update workflows in the new default `suite-v5.json`
have explicit lists. Future task authors must select the smallest required list;
the field does not infer permission from task prose or a model proposal.

The allowlist only narrows `tickets.update`. Tool permission, project scope, actor
writer ACLs, episode identity, ticket/project binding, expected version, and
confidentiality rules still apply. `tickets.list` can return siblings for inventory
work without granting permission to change them. Creation and sharing retain
their separate controls. The current fixed task catalogue only authorizes initial
ticket IDs; it does not dynamically grant update scope to newly created tickets.

Policy denies an excluded ticket with `TICKET_OUT_OF_SCOPE` before computation or
approval. The full contract is already part of the canonical action hash, so scope
changes invalidate review and approval reuse. The effect transaction evaluates
the current contract again and compares its hash with the prepared computation.
Regression tests revoke scope at review, after approval, during computation, and
during approved computation. Committed execution keys still return their original
result on retry; revocation does not undo an already committed effect.

Baseline and prompt-only continue bypassing business authorization inside isolated
episodes, including the new list. They retain episode and version boundaries.
The task scope reaches every profile in the model's trusted initial message, so
any future live comparison must identify this contract treatment as a new study.

## Treatment provenance

Five task copies under `scenarios/dev/ticket-scope/` change only the contract
version and update allowlist. Task prose, resources, attacks, authored actions,
reviewer contracts, budgets, and grader predicates are unchanged. `suite-v5.json`
selects those copies with the other fifteen existing tasks; `expansion-v2.json`
selects the six-workflow subset. Old fixtures and published evidence remain intact.
New console installations use v5; saved settings are not migrated automatically.
Restart services after updating code. Existing durable jobs and paused benchmarks
remain pinned to their original source and must not resume under changed code.

## Final responses: retained limitation

The three confidential-response counterexamples remain failed. Final answers
do not cross the tool gateway, and the application has no output-authorization
boundary. Reviewing a sanitized ticket update does not authorize every later
response. Operator timeline redaction is a separate presentation control.

Do not give runtime policy the grader's secret canary or expected final response.
That would turn hidden evaluation knowledge into a benchmark-specific defense.
A blanket block after any confidential read would prevent useful summaries and
requires a separately measured utility tradeoff. Output review or a trusted,
constrained response builder is future work, with a declared recipient and output
contract, before making any output-confidentiality claim.

The release stays experimental. Retaining this limitation does not waive the
architecture's evaluation gate or remove disclosures from attack denominators.
Fresh-model treatment effectiveness, the held-out corpus, and the release gate
remain unmeasured. Scripted recovery after denial is authored behavior.

## Verification

`tests/test_ticket_scope.py` covers authority separation, empty and legacy scopes,
review/commit races, forged arguments, fixture consistency, idempotency, experimental
profiles, and the complete 174-episode treatment catalogue. The operator browser
test verifies the editable-ticket list in both selection and approval detail and
checks that the reviewed update preserves its sibling.

Reproduce the six-task treatment with `make eval-ticket-scope`; use
`make eval-development` for all twenty tasks. Both commands finish and exit 1
because three response disclosures remain. `make eval-expansion` preserves the
original seven-failure counterexample. These commands perform zero model trials.
