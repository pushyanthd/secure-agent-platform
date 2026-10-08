# System card — experimental portfolio build

Updated October 7, 2026. The platform is a local authorization and evaluation
laboratory for a workplace assistant. Forty decision-template holdouts and the
self-service evaluation workflow are implemented. The 400 fresh baseline/defended
trials are complete, with a **FAIL** gate: defended clean utility 5/40,
observed attacker wins 0/160, and two unresolved attacked timeouts. See the
[frozen results and failure analysis](evidence/release-v1-2026-09-27/README.md). No production or
universal prompt-injection-resistance claim is made.

## Intended use and implemented system

A reviewer can inspect a synthetic agent task, proposed tool actions, authorization
decisions, scoped approvals, committed effects, independent grades, and retained
failures. The six tools search/read documents, list/create/update tickets, and
request document sharing. Sharing writes to a simulated sink, not a real service.

FastAPI establishes operator identity; a durable worker runs the bounded model
loop; a deterministic gateway evaluates trusted actor and task contracts. The
host validates a container's proposed effect and atomically commits the simulated
mutation, approval consumption, audit, and idempotency result in SQLite. Worker
leases prevent stale workers from committing. The operator console and offline
comparison viewer expose evidence without asking for private reasoning traces.

The experimental baseline and prompt-only profile disable business authorization
within synthetic episodes. All three profiles retain bounded execution and outer
episode/container containment. Ordinary application endpoints use defended mode.
See [the trust boundaries](threat-model.md) and [architecture](../arch_plan/secure-agent-platform-plan.md).

## Model and execution profile

The installed Mac profile pins Qwen3-4B Q4_K_M, model revision
`bc640142c66e1fdd12af0bd68f40445458f3869b`, and llama.cpp b11149, commit
`d2e54583c7452353eb35d40431281f6ee984332f`. The model artifact SHA-256 is
`7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.
The model license is Apache-2.0; the runtime license is MIT. Exact download,
runtime, sampling, and context settings are in [the pinned profile](../config/model-mac-small.json).

Published Mac evidence used Apple M1 Metal, one 8192-token slot, seed 42,
temperature 0.7, top-p 0.8, top-k 20, and non-thinking generation. The bounded
loop allows eight steps, 4096 generated tokens per episode, 768 per call, one
schema repair, and 300 seconds per episode. A completed model reply does not
establish task completion. The graders inspect resulting state and output.
The runtime's grammar does not enforce the unanchored nonblank search regex;
host validation still enforces it.

## Measured results

The frozen release yielded baseline/defended clean success of 2/40 and 5/40,
attacked success of 4/160 and 7/160, and observed attacker wins of 104/160 and
0/160. Defended worst-case wins are 2/160 because of two unresolved timeouts.
All 400 outcomes are retained; the product gate fails. The evaluated holdout is
now exposed and cannot remain untouched if used for subsequent tuning.

A subsequent model-capability follow-up keeps the same runtime, graders, and
budgets. Its updated 4B candidate stopped after 19/32 trials with zero exact
successes; the 13 unrun inputs remain unmeasured. That stop was chosen after
observing results and is explicitly disclosed in the
[partial evidence](evidence/model-instruct-2026-09-28/README.md). A separate
Qwen3.5-9B screen stopped at its predeclared futility boundary after 14/32 trials
(18 unrun): checklist clean 3/4, attacked 1/4. The opt-in
[completion guard](completion-guard.md) now targets omitted requested actions
without changing permissions, decision correctness requirements, or graders. Its
complete eight-trial comparison measured exact success 0/4 control versus 1/4 guard,
with one guarded timeout; it failed selection. Neither partial
evidence nor a model download establishes a release improvement; see the
[model study runbook](model-utility-pilot.md).

The following are separate development studies and must not be pooled into that score.

The October 7 PC profile uses the pinned Qwen3.5-9B model with Windows CUDA
llama.cpp b11149 on RTX 5080, and Ubuntu/WSL2 for the application and Docker tools.
The [20-trial defended development run](evidence/pc-development-2026-10-07/README.md)
completed with 10/10 clean and 9/10 attacked successes, zero observed wins, and
no unfinished trials. A separate [32-trial checklist study](evidence/pc-utility-2026-10-07/README.md)
scored original/checklist clean 5/8 versus 6/8 and attacked 2/8 versus 5/8.
All attacked payloads reached saved requests and all trials completed; checklist
utility still missed both frozen thresholds. Incorrect decisions and omitted
effects remain. This model/runtime/hardware follow-up cannot attribute changes
to GPU throughput or become a replacement release score.

The subsequent [eight-trial capacity guard](evidence/pc-completion-guard-2026-10-07/README.md)
qualified at 4/4 exact successes versus 3/4 control. The
[32-trial broader guard follow-up](evidence/pc-completion-broad-2026-10-07/README.md)
committed 12/12 required effects versus 9/12 and scored 6/8 attacked successes
versus 5/8 control. Both arms scored 6/8 clean, below the guard's frozen 7/8
requirement. The candidate was rejected. Wrong decision labels remain, including
corrections described in final prose that never changed stored state.
These are new exposed development studies with
no default promotion; the original release remains FAIL.

The [32-trial decision review experiment](evidence/pc-decision-review-2026-10-07/README.md)
then regressed utility: completion control/review scored 7/8 versus 4/8 clean and
7/8 versus 3/8 attacked success. Review committed 5/12 required effects versus
12/12 control and exhausted seven step budgets. Action candidates often became
explanatory final replies during review; completed wrong labels also repeated.
All eleven failed grades, raw calls, and portable state remain published.
The treatment was rejected and no default was promoted. Review consumed 97
calls and 4,021 generated tokens versus control's 56 calls and 1,845 tokens.
The comparison does not retroactively select the earlier completion guard.

All eight PC extracts include [portable grading state](portable-evidence.md) that can
recompute all task/attack grades offline. Operational credentials, review nonces,
and queue state remain private. Original transcripts and synthetic confidential
content remain privileged evidence; the exporter is not a general redactor.
Portable regrading checks consistency, not authenticity, the full release gate,
or isolation/approval/lease behavior. Historical extracts retain their previous
private-database requirements.

| Study | Measured result | Interpretation |
|---|---|---|
| [32-trial checklist pilot](evidence/utility-checklist-2026-09-27/README.md) | Control/checklist clean success 1/8 versus 4/8; attacked success 2/8 versus 3/8. Both had 4/8 clean correct decisions; checklist had one unresolved timeout. | Post-release development on exposed families. Better formatting, insufficient utility; treatment rejected by its predeclared selection rule. |
| [84 fresh episodes, fourteen tasks](evidence/fourteen-task-live-2026-09-24/README.md) | Defended clean 14/14; attacked utility 13/14; observed attacker wins 0/14. Baseline and prompt-only each 12/14, 10/14, 4/14. | Useful development comparison; one defended false-completion failure remains. |
| [First ten-episode receipt pilot](evidence/receipt-live-pilot-2026-09-25/README.md) | Both arms failed all five tasks. | A valid effect receipt did not compensate for omitted required reads/listing. |
| [Ten-episode receipt disclosure follow-up](evidence/receipt-disclosure-2026-09-25/README.md) | Template-only treatment completed 5/5 tasks; all four payloads reached model requests; one denied attack was followed by recovery. Control failed 5/5. | One known task; evidence of recovered workflow utility, not held-out security. |

Authored replay is a deterministic boundary/grader check, not a model trial.
All published failed grades remain in their original reports. Exact canary,
canonical base64, and lowercase-hex matching do not detect arbitrary encodings or
semantic disclosure. A zero observed attack count does not establish zero risk.

## Release protocol and outstanding limits

The [release workflow](release-evaluation.md) now supports a pre-execution freeze,
exactly 400 resumable trials, and separate PASS/FAIL/UNUSABLE gate results. It
uses forty new decision-rule templates, four fixed attacks each, declared lineage, pinned
source/environment/model/tool image, and passing invariant/isolation evidence.
It rechecks state grades and journal consistency, reports attack exposure and
paired task-bootstrap intervals, and preserves incomplete trials in denominators.
The tooling itself is tested with explicit test doubles; those tests are not
held-out or fresh-model evidence.

The release remains experimental even if the behavioral gate passes: remaining
acceptance work includes improved utility and completion in a new declared study, a host-wide public-network
audit, bounded artifact storage, additional live recovery/cleanup measurements,
an independent clean-checkout walkthrough, and the final recording. The
[limitations declaration](../evaluations/release-limitations-v1.json) travels with
the frozen experiment. Changing policy or graders after seeing held-out results
requires a separately identified follow-up; the original outcomes remain published.

The author knows the synthetic fixtures and defenses. Automated overlap checks
cannot prove semantic independence. The benchmark measures this fixed local
model and authored task/payload distribution, not enterprise deployment safety.
Raw transcripts and database snapshots are privileged evidence; response clearance
does not sanitize them. Local checksums detect accidental changes, not forgery by
the machine owner. Containers are a laboratory boundary, not microVM isolation.
There is no production multi-tenancy, model-authored shell/code execution, live
enterprise integration, or measured RTX 5080 performance in the original release.
The new PC studies report observed model-call and episode durations under
uncontrolled host load; they are not a comparative hardware benchmark.

The [v1 decision corpus](held-out-corpus.md) shares resource/action plumbing and
attack mechanisms with development. Its eight families are not an independent
external benchmark. The [runbook](run-400.md) lets a reviewer create a schedule
without generation, then run bounded sessions without replacing failed trials.

## Structured review follow-up

[The separate 32-trial v2 study](evidence/pc-structured-review-2026-10-07/README.md)
qualified only for broader development: both arms achieved 7/8 clean and 7/8
attacked task success, all twelve required effects, and no unfinished trials.
Review matched utility with 86 versus 56 model calls and 3,363 versus 1,880
output tokens. Wrong quorum and deadline content remained. Its compound
protocol/prompt treatment cannot attribute individual changes, and the earlier
v1 failures remain separate evidence. The [twenty-workflow comparison](workflow-comparison.md)
froze a cost-conscious selection rule before inference. Neither configuration
qualified in its complete 116 outcomes: control scored 18/20 clean and 31/38
attacked, review 16/20 and 23/38 with eleven step-budget failures. No candidate
or default was selected. Search result coverage and read attempts remain
measurable completion gaps.

[Earlier fresh reproduction](evidence/portfolio-reproduction-broad-2026-10-07/README.md)
passes all 766 Python tests and independently regrades the seven PC publications'
272 outcomes. It retains source hashes and all logs. This supersedes the checked
implementation snapshot, without rewriting the earlier 735-test result or
claiming independent external reproduction.

## Resource-completion comparison completed (October 7)

[All 116 frozen outcomes](evidence/pc-resource-completion-2026-10-07/README.md)
were independently regraded. Resource completion qualified at 19/20 clean and
37/38 attacked success versus control's 18/20 and 32/38. Both had zero observed
attacker wins, zero unresolved attacks and no noncompleted trials, with all 38
payloads present in requests. Guard used 235 calls/7,552 generated tokens versus
260/8,641 control, with no extra model review calls or completion reminders.
The guard's two failures retain the original exact ticket-body punctuation
expectation. All ten failed grades remain published. This selects an opt-in
development candidate for a newly declared release study; no application default
or original release gate changes. The original release remains FAIL.

## Final reproduction and pause (October 7)

[Fresh source/environment validation](evidence/portfolio-reproduction-resource-2026-10-07/README.md)
passed all 800 tests, lint/format/types, corpus validation and authored demos, and
independently regraded all eight PC publications' 388 outcomes. Exact source hashes
and thirteen check logs are retained. This publication and later editorial links
are outside the checked snapshot; Python implementation and grading states did
not change. Same-author/same-PC reproduction does not close external review.

The current comparison and wrap-up are complete. The user requested a pause; no
new release study, Git commit/push or GitHub release was started. Resume with the
[V1 checklist](release-readiness.md). The original release gate remains FAIL.
