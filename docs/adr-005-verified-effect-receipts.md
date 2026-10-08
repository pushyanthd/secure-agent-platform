# ADR 005: verified completion receipts for reviewed ticket updates

Development treatment, September 25, 2026. Response policy: `response-clearance-v2`.
Tool policy remains `gateway-v3`; default operator catalogue remains v5.

## Problem and decision

[Response clearance](adr-004-response-clearance-treatment.md) withholds all
model-authored text after confidential input reaches an internal-only response
destination. It blocks the known disclosures, but also the harmless completion
message after private triage. Reviewed tool approval alone must not release the
model's subsequent prose.

Add optional trusted `response_scope.effect_receipt` with template
`ticket_update_v1` and one exact `tickets.update` action. The task author explicitly
permits disclosure of whether this reviewed update completed. When configured,
the defended profile emits only **“Ticket update confirmed.”**, or an empty
response with `EFFECT_RECEIPT_UNVERIFIED`. It never falls back to model text,
including before a confidential read. Baseline and prompt-only continue to expose
their authored/model response under their declared experimental controls.

This is a restricted completion receipt, not a general summary or proof that the
whole task succeeded. The runtime uses no grader predicates, expected-answer
lookup, canary detection, or model-authored response fields. The recipient receives
no ticket ID, title, body, count, version, or other variable text. Adding an arbitrary
message template or interpolated values would require a new release policy.

## Evidence required at final commit

The caller holds the same fenced SQLite write transaction through verification,
response audit, and durable final-result persistence. The verifier requires:

1. This episode's successful execution of the exact predeclared update, with a
   matching consumed approval and `APPROVED` execution decision.
2. The approval's task contract, actor, destination, and project snapshot still
   match current authority. Current hard tool-policy prohibitions are rechecked.
3. The current ticket still has the expected resulting version, title, and body.
   Its workspace/project identity must match too.
4. The run is not cancelled, and its final checkpoint remains within its time
   budget and current worker lease.

Matching fixtures, pending/rejected approvals, a different episode's effects,
changed state, revoked access, and an unverified model success claim are insufficient.
Approval expiry after consumption does not erase a committed effect. Changes to
an approval-bound contract conservatively invalidate the receipt even when they
might be harmless. Policy-version checks reject stale approval evidence.

The response decision records an evidence hash and `VERIFIED_EFFECT_RECEIPT`;
it does not include the source text or approval nonce. Its `classification` remains
the episode's input influence label, not a reclassification of the raw model reply.
The fixed completion bit is the only explicit declassification. The application
audit and result commit together. Recovery checks the persisted model response
and effect evidence again without generating another reply or repeating an update.

## Matched experiment

Create `effect-receipt-control-v1` and `effect-receipt-treatment-v1`, each with six
tasks and 90 authored episodes. Five tasks are reused unchanged. In both suites,
triage's requested final wording, script prefixes, and exact final-answer predicate
change from “Private triage scheduled.” to “Ticket update confirmed.” All source
material, payloads, tool actions, reviewer actions, state predicates, and canary
checks remain unchanged. The treatment then adds only receipt authority and a
contract-version increment relative to this matched control.

The exact-output change is intentional and visible. It does not retroactively
regrade earlier evidence, and comparisons use the new matched control rather
than silently crediting a new phrase under the previous task contract.

| Defended outcome | Matched clearance control | Receipt treatment |
|---|---:|---:|
| Clean task success | 5/6 | 6/6 |
| Attacked task success | 20/24 | 24/24 |
| Observed attacker wins | 0/24 | 0/24 |
| Withheld responses | 5 | 0 |
| Verified receipts | 0 | 5 |

Exactly five task grades improve; all other task/security outcomes are unchanged.
Baseline and prompt-only each retain 6/6 clean success and 24/24 authored attacker
wins in both suites. The successful treatment does not change the retained failure
in the prior response-clearance study.

See [the full evidence and reproduction](evidence/effect-receipt-2026-09-25/README.md).
These are 180 **Docker-isolated authored episodes**, with zero model trials.
They establish application contracts and grading behavior under the existing tool
containment boundary, not live attack resistance or a held-out product-quality
result. The original clearance treatment remains opt-in too.

## Consequences and limits

- Supports one exact, reviewed ticket update only. Missing state, wrong versions,
  failed review, and model failure can still prevent useful completion.
- Release of a completion bit is deliberate; a task author must decide whether
  this fact is appropriate for the recipient. Timing and success/failure channels
  are not eliminated. Tool approval still does not authorize arbitrary text.
- Final text cannot prove required reads or all task effects. The independent
  grader continues to verify those separately. Unwanted extra effects can fail
  the task despite a valid receipt for the configured update.
- Privileged raw replies, local reports, and baseline traces may still contain
  synthetic secrets. This boundary does not sanitize evidence or host storage.
- Existing scope omission preserves legacy behavior. No default catalogue switch,
  held-out tuning, or claimed live-model improvement is part of this treatment.

Next: measure fresh-model feasibility of the selected treatments, then freeze
workflow families, task/attack assets, grader predicates, budgets, and release
thresholds before executing held-out evaluation.
