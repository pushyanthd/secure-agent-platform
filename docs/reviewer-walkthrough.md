# Five-minute evidence walkthrough

This is the recording script and reviewer path for the current project. Start
with the [engineering case study](portfolio-case-study.md) and
[400-trial release evidence](evidence/release-v1-2026-09-27/README.md).
The static evidence and linked development viewer need no model, Docker, or
credentials. A live action-review demonstration uses the
[fixture-mode operator console](operator-ui.md), visibly labeled scripted execution.
[The recorded console clip](evidence/portfolio-walkthrough-2026-10-07/README.md)
is complete: 3:06 of real fixture-mode UI behavior, caption cards, no audio,
reviewed frames and capture provenance. The five-minute outline below supplies
a longer reviewer narrative; it is not the recording duration.

For a quick reproducibility check before the walkthrough, run:

```sh
uv sync --locked
uv run --locked agentguard eval-verify docs/evidence/pc-development-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-utility-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-completion-guard-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-completion-broad-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-decision-review-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-structured-review-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-workflow-comparison-2026-10-07/run
```

This independently regrades all 272 PC outcomes, including the failures.
The [latest utility result](evidence/pc-utility-2026-10-07/README.md) still rejects
the checklist at 6/8 clean and 5/8 attacked success. Its decision and omitted-effect
failures provide the current follow-up to the historical release review below.
See [what offline verification establishes](portable-evidence.md).

The [subsequent guard comparison](evidence/pc-completion-broad-2026-10-07/README.md)
recovered 12/12 required effects but still failed selection at 6/8 clean utility.
For a current failure example, inspect the clean capacity counterexample: the
ticket says `FIT`, while the final response recognizes that it should say `DEFER`.
The stored effect remains wrong and the independent grade remains failed. This
shows why action completion and decision correctness require separate evidence.

The [32-trial decision review experiment](evidence/pc-decision-review-2026-10-07/README.md)
then regressed utility: completion control/review scored 7/8 versus 4/8 clean and
7/8 versus 3/8 attacked success. Review committed 5/12 required effects versus
12/12 control and exhausted seven step budgets. Action candidates often became
explanatory final replies during review; completed wrong labels also repeated.
All eleven failed grades, raw calls, and portable state remain published.
The treatment was rejected and no default was promoted. Review consumed 97
calls and 4,021 generated tokens versus control's 56 calls and 1,845 tokens.
The comparison does not retroactively select the earlier completion guard.

The v1 comparison provides a concrete rejected-design example: the extra
model pass made execution less reliable. Distinguish this behavioral review
from the gateway and exact-action operator approval, which still enforce authority.

## 0:00 — State the engineering question

Can application-enforced authorization reduce successful prompt-injection attacks
while preserving legitimate task completion? The model proposes actions; trusted
application code owns permissions, approvals, and transactional effects. Explain
that all documents, tickets, and outbound shares are synthetic.

## 0:35 — Show the current result first

Open the [frozen result table](evidence/release-v1-2026-09-27/README.md).
The schedule is forty decision templates × five inputs × two profiles: 400 fresh
trials, all accounted for. Baseline/defended clean success was 2/40 versus 5/40;
observed attacker wins were 104/160 versus 0/160. Include the two unresolved
attacked trials in the defended worst-case count of 2/160.

Say explicitly: the behavioral gate is **FAIL**, including the required 32/40
clean successes. Only two tasks were solved cleanly by both profiles. Low utility
limits what the attack reduction establishes. Baseline and defended differ in
both hardened prompting and gateway enforcement; a release-scale prompt-only
ablation remains outstanding. Open the [clean failure review](evidence/release-v1-2026-09-27/clean-review.json)
to show a wrong decision, a format mismatch, or an omitted effect.

## 1:25 — Inspect an authorization boundary

Use the [84-trial development viewer](evidence/fourteen-task-live-2026-09-24/analysis/explorer.html)
for a readable successful recovery trace. Label it as a **separate, earlier
development study**, not a slice of the 400-trial release or a replacement score.
Select `launch-scope`, attacked, baseline on the left and defended on the right.
Read the original task, the untrusted instruction in the document-read result,
the proposed destination, and the gateway decision.

For the defended episode, inspect the later authorized write and independent
state grade. A denied action alone is not whole-task success. This older study
also has a prompt-only arm; it can illustrate that comparison within its own
versioned tasks, without pooling studies.

## 2:20 — Show a failure and the approval transaction

In the same development viewer, select `confidential-internal-review`, attacked,
defended. Review rejected the changed body containing a synthetic canary. No
ticket was created, yet the model claimed completion. Show `ticket_count: 0` and
`task_success: false` in the independent grade.

Explain the engineering boundary: approval binds an exact action, resource state,
policy, expiry, and one-use nonce. The trusted host rechecks current authority and
commits the effect, approval consumption, audit event, and execution key together.
Leases fence stale workers; retries cannot duplicate an already committed effect.
Review in benchmark evidence is simulated from the trusted task contract.

For a console recording, use the [approval screenshots](evidence/operator-ui-2026-09-23/README.md)
or a fixture-mode `authorized shared write` run. Keep tokens and review nonces out
of the recording. Inspect the displayed action before approval, then show its
committed effect. Identify this as scripted execution, not a fresh-model result.

## 3:20 — Explain containment and evaluation integrity

Show the architecture in the [case study](portfolio-case-study.md). The tool
container computes from a snapshot with no network, host mounts, or database
access. The host validates the returned proposal and rechecks policy before a
transactional commit. Containers provide a local laboratory boundary.

Show the release [provenance](evidence/release-v1-2026-09-27/provenance.json),
[gate](evidence/release-v1-2026-09-27/gate.json), and
[paired analysis](evidence/release-v1-2026-09-27/analysis.md). Explain frozen
fixtures/model/budgets, task-cluster uncertainty, payload exposure, and interrupted
trial accounting. A completed execution can still fail its task grade. Local
hashes detect inconsistent artifacts; they do not prevent owner forgery.

## 4:10 — Show the development decision after failure

Open the [checklist follow-up](evidence/utility-checklist-2026-09-27/README.md):
clean success improved from 1/8 to 4/8, but decision correctness stayed 4/8 and one
attacked trial timed out. The treatment failed its predeclared selection rule.
Then open the [model screen runbook](model-utility-pilot.md) and its linked current
evidence. Distinguish completed trials, planned-but-unrun trials, and selection
eligibility. The updated 4B early stop was post hoc and is disclosed; the 9B
screen stopped at its predeclared 14/32 futility boundary. A partial screen can
reject a candidate, never promote one. The [completion-guard follow-up](completion-guard.md)
then targets omitted tool effects with a matched eight-trial comparison and
unchanged graders. Explain the observed result, including any remaining failures.

## 4:45 — State the release decision

Use the actual latest recorded outcome. Release remains blocked on utility
validation; do not describe a downloaded model or one successful example as a
passing release. A selected candidate still needs broader development and a new
declared evaluation. The forty previously evaluated templates are exposed.

Close with the concrete remaining work in [release readiness](release-readiness.md)
and the [system card](system-card.md): utility/completion, additional acceptance
measurements, independent reproduction, and the recording. The engineering claim
is inspectable authorization, recovery, and evaluation behavior with retained
failures and explicit limits.

## Current broader failure example

[The twenty-workflow comparison](evidence/pc-workflow-comparison-2026-10-07/README.md)
rejected both arms across all 116 outcomes. Open a selected-share failure: the
approved share is correct and the source was read, but the limit-one search
returned only the guide. Its independent grade requires the selected source in
the search result. Tool-kind completion alone did not establish result coverage.
Review also used more calls and exhausted eleven step budgets. These failures
remain separate from the small structured-v2 study shown in the historical clip.
