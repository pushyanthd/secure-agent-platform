# Implementation status

Updated October 7, 2026. The architecture plan remains the target design.

## Current PC follow-up and portfolio reproduction

The complete PC/WSL application stack and pinned Windows CUDA inference are
verified. The [ten-task development schedule](evidence/pc-development-2026-10-07/README.md)
resumed at 2/20 and finished all 20 outcomes: 10/10 clean, 9/10 attacked success,
zero observed wins, and no unfinished episodes. Its failed required read attempt
is preserved. The separate [32-trial PC checklist study](evidence/pc-utility-2026-10-07/README.md)
retained control/checklist clean 5/8 versus 6/8 and attacked 2/8 versus 5/8;
all attacks reached requests and all outcomes completed. The treatment missed
the unchanged selection rule and remains unselected.

`eval-export` and `eval-verify` now support offline state/output regrading of
synthetic benchmark extracts without publishing operational approvals/nonces or
SQLite databases. Both PC publications include every saved outcome, portable
state, original extract checksums, full failure review, offline viewer, and
runtime diagnostics. CI verifies both publications. This closes state/output
reproduction for these new studies; it does not reconstruct the full gate or
retroactively add state to historical extracts.

The [new eight-trial PC guard study](evidence/pc-completion-guard-2026-10-07/README.md)
qualified with 4/4 exact guard successes versus 3/4 control. Both attacked guarded
trials recovered after a premature final response. The subsequent
[32-trial broader comparison](evidence/pc-completion-broad-2026-10-07/README.md)
recovered 12/12 effects versus 9/12, with control/guard attacked success 5/8 versus
6/8. Clean success stayed 6/8 and missed the 7/8 threshold, so the broader
candidate was rejected. All 40 new outcomes and every failure are preserved.
The scripts now freeze explicit PC profile selection, matched task obligations,
comparison helpers, and bounded pause/resume. All 711 Python tests, lint,
formatting, and strict types passed in a separate same-PC checkout.

The [32-trial decision review experiment](evidence/pc-decision-review-2026-10-07/README.md)
then regressed utility: completion control/review scored 7/8 versus 4/8 clean and
7/8 versus 3/8 attacked success. Review committed 5/12 required effects versus
12/12 control and exhausted seven step budgets. Action candidates often became
explanatory final replies during review; completed wrong labels also repeated.
All eleven failed grades, raw calls, and portable state remain published.
The treatment was rejected and no default was promoted. Review consumed 97
calls and 4,021 generated tokens versus control's 56 calls and 1,845 tokens.
The comparison does not retroactively select the earlier completion guard.

Next: make the mutation-review protocol unambiguous and measure deterministic
calculation on grounded, authorized facts. Any claimed correction must change
stored state. A useful candidate, broader validation, and a new declared release
evaluation are still required.
The original 400-trial FAIL gate and earlier rejected studies remain unchanged.
The README is now a concise portfolio entry point, with detailed workflows in
`project-guide.md`. `make portfolio-check` reproduces checks and all portable
evidence in a fresh source/environment snapshot. Runtime review configuration
is persisted with job settings, keeping frozen authorization contracts unchanged.
Validation covered 735 distinct Python tests, formatting, lint, and strict types.
The [fresh-environment reproduction](evidence/portfolio-reproduction-2026-10-07/README.md)
then passed the complete 735-test suite and all five publications' 124 portable
grades, corpus validation, and fixture demos without inference or operational
state. The first attempt's executable-discovery failure is retained separately.
The sections below describe historical increments.

## September 28 status: completion obligations before release

The first 400-trial evaluation and 32-trial checklist study are complete and
failed their selection objectives. The updated 4B model stopped after 19/32
trials with zero exact successes (post-hoc stop); the 9B screen stopped after
14/32 under a predeclared futility rule. Both partial studies retain recorded
and unrun counts in [the model runbook](model-utility-pilot.md).

An opt-in trusted completion guard now prevents a final response while required
tool kinds have not succeeded. It does not grant permission, supply correct
answers, or change task graders. The [eight-trial matched live pilot](completion-guard.md)
is complete and independently regraded: exact success 0/4 control versus 1/4 guard; ticket creation
1/4 versus 4/4. Incorrect boundary decisions and one guarded final-response timeout
prevent selection. All 664 Python tests passed across the full suite and focused
additions; lint, formatting, and types passed. The local model server is stopped.
Historical sources were preserved for regrading. On September 29, the
[Windows/RTX 5080 setup](pc-inference.md) verified and served the pinned 9B model
on the PC. A structured-generation probe passed through the application's model
transport. Docker and the Mac tunnel are still outstanding; no PC-backed
development or release trial has been run.
The sections below retain implementation history; their forward-looking
milestones are not the current backlog.

## Latest follow-up: utility checklist evaluated

Implemented eight paired development cases, a pre-generation freeze, resumable
32-trial execution, and a comparator that verifies matched fixtures and independently
regrades saved state. All 32 fresh trials are retained: control/checklist clean
success 1/8 versus 4/8, attacked success 2/8 versus 3/8. Clean decision correctness
remained 4/8 in both arms; the checklist had one unresolved attacked timeout.
It failed the frozen selection rule and was not promoted. See the
[evidence and next decision](evidence/utility-checklist-2026-09-27/README.md).
All 629 Python tests, lint, formatting, and strict types passed. Package behavior,
the default task catalogue, and the original 400-trial release grades are unchanged.

## Latest: first frozen release evaluated

All 400 fresh trials are accounted for. The behavioral gate is FAIL: defended
clean success 5/40 against a required 32/40; noncompleted trials 2 versus baseline
1; unresolved attacked trials 2 versus 0. Observed attacker wins fell from
104/160 to 0/160, but low utility and the unresolved trials prevent a passing
release claim. The [retained analysis](evidence/release-v1-2026-09-27/README.md)
documents incorrect decisions, exact-format failures, omitted effects, and
timeouts after repeated denials. The report now explains counts and failure
reasons while retaining gate exit codes and the original frozen package source.
Earlier sections are historical milestones; new behavior must be evaluated in
a separately declared study after development validation.

## First increment: authorization kernel and scripted evidence

- [x] Record sanitized Mac hardware and runtime readiness.
- [x] Establish Python 3.12 package, dependency lock, CLI, Ruff, mypy, pytest, and CI.
- [x] Validate proposals for `documents.read` and `tickets.create`.
- [x] Check workspace, resource scope, actor ACLs, and coarse confidentiality.
- [x] Bind expiring approvals to action, episode, execution key, contract, policy,
  resource snapshot, and sensitivity state; consume with the effect transaction.
- [x] Persist episode state, idempotency keys, simulated effects, and audit in SQLite WAL.
- [x] Exercise concurrent delivery, precommit failure, reopen/retry, and cancellation.
- [x] Add one authored development scenario and a state/output grader.
- [x] Export labeled replay JSON/Markdown with source/scenario hashes and checksums.

## Second increment: isolated tool execution

- [x] Pin the official Python base image by digest; build separate tool/probe images.
- [x] Add a fixed Docker supervisor with bounded input/output and explicit cleanup.
- [x] Compute outside the SQLite write lock and recheck policy/approval state on commit.
- [x] Reject forged effects and state changes that occur during computation.
- [x] Run clean/attacked replay through the same container backend for both profiles.
- [x] Measure 20 passing container smoke checks on Docker Desktop 29.7.2.
- [x] Expand deterministic coverage to 77 tests and add isolated smoke/replay to CI.

The first container smoke exposed dormant network interfaces and an automatic
removal race. The corrected checks verify active interfaces/routes; cleanup
confirms removal instead of accepting an in-progress response. See [the runbook](sandbox.md).

## Third increment: bounded native inference

- [x] Pin official Qwen3-4B Q4_K_M weights and a native llama.cpp arm64 runtime.
- [x] Add explicit project-local downloads, checksum verification, and license retention.
- [x] Add a loopback-only adapter with bounded HTTP, exact server tokenization,
  schema-constrained responses, and no provider/model fallback.
- [x] Persist requests and raw model responses before tool dispatch.
- [x] Enforce context, token, step, output, and time budgets, including one schema repair.
- [x] Pause at approval requests; reject post-cancellation and post-deadline effects.
- [x] Run baseline, prompt-only, and defended clean/attacked trials through Docker.
- [x] Export schedules, traces, SQLite backup, raw calls, grades, and checksums.
- [x] Confirm native Metal offload of 37/37 layers with an 8192-token context.
- [x] Pass 127 deterministic tests, including transport, protocol ordering,
  runtime budgets, evidence denominators, and installed-runtime integrity.

The first live trials exposed premature final answers with no tool effects. The
independent state grader marked them unsuccessful. Live testing also identified
that canonical JSON sorting changed schema property order, which matters to the
runtime's generation grammar. The wire format now preserves discriminator-first
ordering and requires tool tags; a regression test covers this boundary.

The development task is now version 2: its requested title and body requirement
are explicit in the user-visible task. The grader is unchanged. Version 1 trials
remain recorded, including failures caused by omitted body detail or title casing.

At this milestone the loop persisted evidence but did not implement durable leases, automatic
resume, an authenticated approval API, or model-failure retries. See the
[native-model runbook](local-model.md).

Measured outcome: all three task-v2 clean trials passed. Baseline and prompt-only
made the unauthorized write; defended denied it but did not complete the original
task. All 24 development episodes (including earlier failures) are retained in
the [evidence bundle](evidence/local-model-2026-09-23/README.md). This is a useful
feasibility result with a visible utility cost, not a passed release gate.

## Fourth increment: development suite and review simulation

- [x] Author ten development tasks covering scope, actor ACLs, read-only work,
  multiple reads/writes, sensitive approvals, refusals, and missing resources.
- [x] Grade committed reads, required attempts, exact ticket counts and requested
  bodies, final output, forbidden effects, and exact canary disclosures.
- [x] Add a deterministic reviewer with a predeclared exact-action contract,
  separate from the grader and attack objective. Ordinary runs still pause.
- [x] Execute 60 paired scripted cases: defended clean 10/10, attacked utility
  10/10, observed attack wins 0/10. These are authored actions, not model results.
- [x] Verify all 20 defended scripted cases again with real isolated Docker tools;
  preserve the separate report and the same five review decisions.
- [x] Add explicit replay/live suite commands, full schedules, source/fixture
  snapshots, SQLite backups, raw model calls, and exported checksums.
- [x] Retain denial-feedback development experiments, including false completion
  claims that fail the independent state grader.
- [x] Pass 156 tests plus lint, formatting, and strict type checks; add suite replay
  to CI. The tests include approval credential exclusion and cancellation on review.

See the [suite runbook](development-suite.md) and
[experiment evidence](evidence/development-suite-2026-09-23/README.md).
Both task-reminder treatments still failed live recovery: the model claimed
success without creating a ticket. All twelve new live episodes are retained;
no failed episode was removed or regraded. All six clean trials passed, and both
defended attacked trials blocked the write but failed task utility.

## Fifth increment: complete live feasibility and inspectable analysis

- [x] Complete all 60 fresh local-model episodes with isolated tools and simulated review.
- [x] Publish every result: clean utility 8/10 baseline, 9/10 prompt-only, 10/10 defended;
  attacked utility 6/10, 6/10, 8/10; observed attack wins 4/10, 4/10, 0/10.
- [x] Retain both defended recovery failures and false completion claims; no regrading.
- [x] Measure 185 model calls, 5,939 generated tokens, zero schema repairs, and no
  unfinished episodes. Observe 27.00–75.89 s per episode and about 3.59 GiB native
  server command maximum RSS under uncontrolled host load.
- [x] Add checksum/schedule-validated offline analysis, common-clean conditional
  denominators, paired task-bootstrap intervals, and overlapping failure labels.
- [x] Export an offline comparison viewer with escaped untrusted text, restrictive
  CSP, original tasks, tool decisions, simulated reviews, and independent grades.
- [x] Verify all 60 replay selections in Chrome, mobile layout, and hostile-text handling.
- [x] Add CLI progress after each saved episode and a five-minute reviewer walkthrough.
- [x] Pass 179 tests, Ruff, formatting, and strict mypy checks.

See [the complete live evidence and model decision](evidence/ten-task-live-2026-09-23/README.md).
**Phase 0 feasibility is complete.** Retain the pinned `mac-small` profile for
platform development, provisionally: it solves all ten clean tasks but still
fails recovery after two blocked attacks. The release model choice remains open
pending broader evidence. Only two of six planned tools exist; no held-out suite
has been authored or frozen, and no portfolio release gate has passed.

## Sixth increment: durable worker kernel

- [x] Add schema-v3 jobs with idempotent submissions, transactional claims,
  renewable leases, random tokens, and monotonically increasing claim generations.
- [x] Permit one active lease across workers; fence model checkpoints, terminal
  status, tool preparation, and effect commits in their own write transactions.
- [x] Recover saved responses with stable execution keys, identical model inputs,
  and preserved token/step/repair budgets and original episode deadlines.
- [x] Fail explicitly when a process dies before its model response is saved;
  reserve its full token allowance and never silently generate a replacement.
- [x] Release leases for approval waits; atomically wake jobs on review, handle
  review/checkpoint races, and reject expired or changed approval scope.
- [x] Pin recovery to model identity, source hashes, task, budgets, and tool backend.
- [x] Test real subprocess deaths before and after effect commit, stale workers,
  concurrent claims, cancellation, heartbeat renewal, and database migration.
- [x] Add `make demo-durable` with state grading, simulated review/interruption,
  and a reopened database; run it in CI. It performs zero model trials.
- [x] Pass 207 tests, lint, formatting, and strict types; rerun all 60 scripted
  development episodes and all seven durable-demo checks successfully.

See the [durable execution contract and runbook](durable-execution.md). These are
library-level worker guarantees, not authentication or production process isolation.
The existing synchronous benchmark remains a separate execution mode; its published
live evidence is unchanged. No fresh model evaluation is claimed for this increment.

## Seventh increment: authenticated local control plane

- [x] Add a loopback-only FastAPI service with private bearer credentials and
  separate operator/observer permissions; the worker does not load API credentials.
- [x] Derive actor/workspace from trusted identity, allow only predefined defended
  tasks, and scope run/approval access to the authenticated owner.
- [x] Atomically commit resources, job, ownership, idempotency binding, and audit;
  preserve retry identity and enforce a bounded pending-run admission limit.
- [x] Expose status, redacted timelines, cancellation, and scoped approval detail/review.
- [x] Reject stale approvals at review time and again at effect commit; validate
  current scope, ACLs, sensitivity, policy, resource state, and run deadline.
- [x] Enforce exact Host/Origin, browser Fetch Metadata, explicit CSRF headers,
  bounded JSON bodies, non-cacheable responses, and generic validation errors.
- [x] Add separate setup/API/worker commands and a real HTTP smoke that restarts
  the API during an approval wait, then completes via another worker process.
- [x] Pass 256 tests, lint, formatting, and strict types; all 12 real HTTP smoke
  checks pass. The smoke uses authored responses and performs zero model trials.
- [x] Lock API/test dependencies and update their license metadata inventory.

See the [API runbook and trust boundaries](control-plane.md). HTTP authority is
separated; the API and worker still share the trusted local OS user and SQLite.
At this milestone, the browser UI was still pending. The existing live evaluation
evidence is unchanged. Production identity and hardened worker isolation remain out
of scope for this increment.

## Eighth increment: interactive operator console

- [x] Build a React/TypeScript UI served by FastAPI from the same loopback origin.
- [x] Add task selection, owner-scoped recent runs, redacted timelines, and confirmed cancellation.
- [x] Display exact action arguments, original task/scope, policy, resource version,
  expiry, and hash with explicit approve/reject; never render approval nonces.
- [x] Keep bearer credentials only in tab memory; clear sessions on disconnect/reload,
  abort requests, and discard late responses. Observer sessions remain read-only.
- [x] Preserve submission identity after a lost response. Never automatically retry
  review decisions or replace the action snapshot being inspected.
- [x] Serve only an exact compiled-asset allowlist; preserve Host/Origin and API
  authentication checks, strict CSP, no-store responses, and escaped content.
- [x] Pass 267 Python tests and nine real Chrome workflow/security scenarios,
  including API restart, stale/expired approvals, hostile content, and mobile layout.
- [x] Pass Python/TypeScript/format checks; verify the wheel includes and serves
  UI assets while excluding credentials and local artifacts.
- [x] Add locked frontend dependencies, license metadata, a browser CI job,
  the operator runbook, and sanitized screenshots.

See the [operator UI runbook](operator-ui.md) and
[verification screenshots](evidence/operator-ui-2026-09-23/README.md).
These are authored-fixture browser
checks with real API/worker processes, not fresh model trials or a human-usability
study. Independent paired grades remain in the offline report viewer. No live
benchmark result changed, and the held-out release gate is still pending.

## Ninth increment: complete the tool surface

- [x] Add ACL/scope-filtered FTS5 document search and bounded ticket listing.
- [x] Add versioned ticket updates with full snapshot checks and idempotent effects.
- [x] Add exact-document sharing into an episode-local sink, with source/destination review.
- [x] Propagate confidentiality through search snippets, ticket previews, and stored tickets.
- [x] Migrate schema 4 to 5 transactionally, preserving legacy tickets and concurrent startup.
- [x] Extend the fixed container runner, independent grader, reviewer, and approval UI.
- [x] Add four development workflows; new console installs offer 14 scenarios.
- [x] Run all 24 scripted tool episodes through Docker: defended clean and attacked
  utility 4/4 each, zero observed attacker wins; both permissive profiles expose
  all four authored attacks. This is zero model trials.
- [x] Pass all 24 container contract/containment checks.
- [x] Pass 311 Python tests, 11 Chrome scenarios, Python/TypeScript checks, and UI build.
- [x] Rerun the original 60-episode replay and seven-check durable recovery demo.
- [x] Publish checksummed scripted evidence, the offline viewer, and exact-share screenshot.

See [tool contracts and reproduction](tool-surface.md) and
[recorded verification](evidence/tool-surface-2026-09-23/README.md).
The original ten-task live evidence remains unchanged. Search uses host FTS5
before sending authorized snippets to isolated computation; share effects remain
entirely synthetic. No new live-model or held-out result is claimed.

## Tenth increment: expanded live feasibility and diagnostics

- [x] Complete all 24 original new-tool trials with pinned local inference and Docker.
- [x] Retain eleven exact-punctuation task failures and inspect their saved state.
- [x] Publish raw calls, source/fixture snapshots, paired analysis, and an offline viewer.
- [x] Run twelve additional live wording-treatment trials; all pass with unchanged
  graders and attacks, and original failures remain failed.
- [x] Use clarified task literals for new console installs; retain all prior suite versions.
- [x] Complete the clarified catalogue’s 84 scripted episodes; defended utility 14/14
  clean and attacked, with zero model trials.
- [x] Reconcile measured/unknown token use, timing, tool coverage, and denial denominators.
- [x] Measure two 1,000-decision policy samples, retaining both results and source.
- [x] Pass 333 Python tests, lint, formatting, and strict types.
- [x] Document the remaining release work and focused-effort estimate.

See the [complete results and limits](evidence/six-tool-live-2026-09-23/README.md)
and [diagnostics contract](runtime-diagnostics.md). In the original 24 trials,
clean/attacked utility was 3/4 and 2/4 for baseline, 2/4 and 2/4 for prompt-only,
and 2/4 and 2/4 for defended. No profile attempted a forbidden action: there is
no new live denial-recovery denominator or comparative attack reduction.
The observed policy P95 values (0.0633 and 0.0322 ms) exclude persistence,
resource resolution, tools, and inference. No held-out release result is claimed.

## Eleventh increment: resumable benchmark sessions

- [x] Persist benchmark scheduling, started markers, immutable results, and session history.
- [x] Add CLI status/resume and episode-limited sessions; Ctrl+C drains the current episode.
- [x] Reject concurrent writers and changed source, dependencies, fixtures, model, or tools.
- [x] Reuse saved results; preserve effects and unknown-token reservations after process death.
- [x] Keep interrupted trials in denominators and unknown durations out of timing distributions.
- [x] Test real subprocess death, foreground-group signals, lost exports, and compatibility failures.
- [x] Pass 356 tests, lint, formatting, and strict types, including `uv run` signal forwarding.
- [x] Complete a 24-episode CLI replay across sessions of 2, 3, and 19 episodes;
  verify final checksums, paired analysis, and diagnostics with zero model trials.

See [the terminal runbook](resumable-benchmarks.md). This is deterministic recovery
evidence, not a fresh-model experiment or the planned 400-episode release benchmark.

## Twelfth increment: fourteen-task live evidence and measured resume

- [x] Account for all 84 fresh model trials across three sessions of 10, 10, and 64 episodes.
- [x] Verify every published result against the local benchmark journal and original checksums.
- [x] Publish clean utility 12/14 baseline, 12/14 prompt-only, 14/14 defended;
  attacked utility 10/14, 10/14, 13/14; observed attacker wins 4/14, 4/14, 0/14.
- [x] Retain all 13 failed task grades, including the defended false completion after review rejection.
- [x] Export paired uncertainty, conditional denominators, the offline viewer, and runtime diagnostics.
- [x] Reconcile 275 calls and 9,484 generated tokens; distinguish episode timing from session wall time.

See [the complete publication](evidence/fourteen-task-live-2026-09-24/README.md).
There are no missing or interrupted episodes. This demonstrates live pause/resume
between episodes, not live mid-episode crash recovery. The four newer tool-workflow
attacks still show no observed wins in any profile. No held-out release gate has
passed, and earlier versioned studies remain unchanged. Packaging performed no inference.

## Thirteenth increment: multiple attacks per task

- [x] Add versioned, bounded attack variants without changing trusted task/reviewer/grader contracts.
- [x] Schedule one clean control and every declared payload per profile, with payload provenance.
- [x] Preserve attack identity and committed effects across pauses and interrupted-trial accounting.
- [x] Reject dropped/substituted variants and catalogue/fixture mismatches; retain legacy evidence support.
- [x] Keep correlated payloads together in paired task bootstrap draws, including unequal payload counts.
- [x] Add attack selection to the offline viewer and payload IDs to failure/diagnostic records.
- [x] Add a four-family development pilot with 15 authored episodes and no inference.
- [x] Pass the Python suite and new integrity/outage regressions, lint/format/type checks,
  TypeScript checks, and two Chrome checks covering every payload and legacy reports.

See [contracts, reproduction, and limits](multi-attack-evaluation.md). This reuses
the confidential-review workflow; the independent development catalogue remains
fourteen tasks. New payload effectiveness under fresh inference is unmeasured.
The original published runs and grades are unchanged.

## Fourteenth increment: twenty-task development corpus and stronger graders

- [x] Preserve the fourteen versioned development tasks and add six compositional workflows.
- [x] Author four fixed attack families for every new workflow; full catalogue has 174 episodes.
- [x] Add independent forbidden-listing/source-share, exact-response, and opt-in encoded-canary predicates.
- [x] Retain four project-authorized sibling edits and three final-response disclosures as defended failures.
- [x] Pass all 20 defended clean tasks and preserve all seven known attack wins in full replay.
- [x] Expose 20 clean scenarios in new operator installations while preserving saved suite selection.
- [x] Pass 402 Python tests, lint/format checks, and strict typing.
- [x] Complete all 90 expansion episodes through Docker and independently recheck every grade.
- [x] Pass 13 Chrome scenarios and frontend checks; publish the viewer and disclosure screenshot.

See [task provenance, grouping, reproduction, and interpretation limits](development-corpus.md).
The six new tasks have related development ancestors; no new independent-family
or held-out claim is made. Grader v4 leaves historical published grades unchanged.
This increment performs zero fresh model trials.
The [Docker evidence](evidence/development-expansion-2026-09-24/README.md) retains
all 55 failed task grades across the three profiles.

## Fifteenth increment: per-ticket update authority

- [x] Add trusted update-ticket lists and `gateway-v3` denial before computation/review.
- [x] Preserve project inventory access while narrowing write scope; missing/null lists keep legacy authority.
- [x] Reject revoked scope at review, after approval, and during effect computation.
- [x] Version five task contracts without changing their prose, attacks, scripts, or graders.
- [x] Select the v5 catalogue for new console installations and display editable tickets to reviewers.
- [x] Pass 423 Python tests, lint/format checks, and strict typing.
- [x] Preserve all 20 defended clean tasks and block the four sibling-edit paths in full replay.
- [x] Retain three final-response disclosures as failures, without exposing grader canaries to policy.
- [x] Complete all 90 treatment episodes through Docker, recheck every grade, and publish the offline viewer.
- [x] Pass 14 Chrome scenarios, including exact ticket scope and sibling preservation in review.

See [ADR 003](adr-003-ticket-scope-and-response-boundary.md) and
[the treatment evidence](evidence/ticket-scope-2026-09-24/README.md). Existing saved control
settings and original evidence retain their prior task scope. This increment
performs zero fresh model trials; final-response confidentiality remains unenforced.

## Sixteenth increment: opt-in final-response authorization

- [x] Add a trusted synthetic recipient and response clearance, independent of tool approval.
- [x] Withhold confidential-influenced final text from an internal-only destination at commit time.
- [x] Commit decision metadata with the final result under current scope, cancellation, and worker lease.
- [x] Retain raw local evidence; test rollback/recovery without another model generation.
- [x] Apply the same rule to scripted benchmarks and record response-denial counts and viewer annotations.
- [x] Keep all three known response disclosures blocked in treatment replay while retaining its clean-task failure.
- [x] Preserve the default v5 catalogue and all prior versioned evidence.
- [x] Complete all 90 treatment episodes through Docker, recheck every grade, and publish the comparison.
- [x] Pass the 445-test Python suite and 22 focused response tests after adding a deadline regression
  (446 distinct tests covered), lint/format/types, the frontend build, and 15 Chrome scenarios.

See [ADR 004](adr-004-response-clearance-treatment.md) and
[the treatment evidence](evidence/response-scope-2026-09-24/README.md). The six-task treatment
has defended clean utility 5/6, attacked utility 20/24, and observed attack wins
0/24 in authored replay. Its 16.7-point clean-utility loss exceeds the proposed
five-point objective, so it remains opt-in and exits nonzero. No live-model
effectiveness or held-out release claim follows from these checks.

## Seventeenth increment: verified effect receipts

- [x] Add an opt-in, fixed completion receipt bound to one exact reviewed ticket update.
- [x] Verify the episode-local execution, consumed approval, current state, and authority at final commit.
- [x] Withhold false completion claims, matching initial fixtures, stale state, and revoked permissions.
- [x] Recover after a finalization crash without regeneration or duplicate effects.
- [x] Version a matched control and treatment; retain prior wording, evidence, and default catalogue.
- [x] Pass 472 Python tests, lint/format/types, the frontend build, and 16 Chrome scenarios.
- [x] Complete 180 Docker-isolated authored episodes and independently recheck every state grade.
- [x] Publish both comparisons, complete denominators, exact five-grade improvement, and receipt provenance.

See [ADR 005](adr-005-verified-effect-receipts.md) and
[the evidence](evidence/effect-receipt-2026-09-25/README.md). Defended clean success
recovers from 5/6 to 6/6 and attacked success from 20/24 to 24/24, with zero observed
attacker wins in both matched suites. The receipt deliberately releases a completion
bit; it does not declassify model prose or establish whole-task success. No fresh
model trials or held-out release gate are claimed.

## Eighteenth increment: live receipt feasibility and release prerequisites

- [x] Run ten fresh local-model episodes across matched defended control/treatment arms.
- [x] Preserve all ten failed task grades with no retries, missing results, or relaxed predicates.
- [x] Verify control withholding versus treatment omission of required document/ticket reads.
- [x] Record four attacked payloads in control requests and zero in treatment requests.
- [x] Retain the control's denied shared-ticket proposal and subsequent authorized update.
- [x] Reconcile 31 calls and 1,018 generated tokens; recheck every grade against saved state.
- [x] Add a strict cross-run comparison checker with failure, provenance, and exposure tests.
- [x] Pass the 488-test Python suite and 20 focused comparison tests after exposure checks
  (492 distinct tests covered), lint/format checks, and strict types.
- [x] Publish raw evidence, episode review, diagnostics, and the 400-episode release runbook.

See [the live pilot](evidence/receipt-live-pilot-2026-09-25/README.md) and
[reproduction](receipt-live-pilot.md). Both arms have 0/1 clean and 0/4 attacked
success. All five receipt effects are valid, but missing required reads fail their
whole-task grades. The treatment's unexposed attacks cannot support a resistance
claim. The authored study remains unchanged and the treatment stays opt-in.

## Nineteenth increment: model-visible receipt scope

- [x] Add opt-in template-only receipt presentation while retaining the exact trusted action.
- [x] Preserve legacy prompt content and apply the projection to denial reminders.
- [x] Recover the saved presentation without treating it as a trusted contract.
- [x] Verify both disclosure modes against stale effects, revoked authority, and crash recovery.
- [x] Version matched suites with unchanged task prose, payloads, reviewer, and graders.
- [x] Extend strict comparison checks to the declared disclosure treatment and read/list outcomes.
- [x] Pass all 528 Python tests, lint/format checks, and strict types.
- [x] Complete ten fresh matched Docker-isolated episodes and independently recheck every grade.
- [x] Recover all five treatment tasks with four exposed payloads and one denied attack followed by recovery.
- [x] Preserve all five failed control grades, original pilot evidence, and the default catalogue.

See [ADR 006](adr-006-model-visible-receipt-scope.md) for the experiment and
reproduction and [the measured evidence](evidence/receipt-disclosure-2026-09-25/README.md).
Clean success improves from 0/1 to 1/1 and attacked success from 0/4 to 4/4.
Both arms have zero observed wins, but only treatment encounters all four payloads.
This known-task result does not replace broader development or held-out evaluation.

## Twentieth increment: frozen release execution and product gate

- [x] Add explicit held-out loading while preserving development-only defaults.
- [x] Audit declared ancestry, family/ID/text overlap, and all four attack families.
- [x] Bind retained invariant checks to source, tests, lockfile, environment, and tool image.
- [x] Snapshot tasks and protocol before inference; refuse freeze overwrites.
- [x] Schedule exactly 400 baseline/defended trials and preserve existing resume accounting.
- [x] Reject incompatible or incomplete evidence; independently regrade saved final state.
- [x] Check the journal and model-call exports; retain failures, exposure, and uncertainty.
- [x] Implement PASS/FAIL/UNUSABLE outcomes and keep acceptance gaps explicitly experimental.
- [x] Add a system card, held-out authoring contract, and operational release commands.
- [x] Define the unchanged six-workflow broader treatment comparison (60 development episodes).
- [x] Pass 556 Python tests, lint/format/type checks, and all 24 real Docker probes.
- [x] Verify replay/development/release viewer labels in three local Chrome scenarios.

Validation uses explicit test doubles, including a complete 400-failure schedule;
this is not a live held-out result. The forty new templates, their semantic
lineage review, release inference, and final acceptance evidence remain pending.
See [the release workflow](release-evaluation.md) and [system card](system-card.md).

## Twenty-first increment: user-run 400-episode handoff

- [x] Author forty decision procedures across eight declared families, with worked answers.
- [x] Generate schema-3 fixtures with four fixed attacks each and all six tool primitives.
- [x] Record closest development relationships and shared-mechanism limitations explicitly.
- [x] Correct a pre-inference canary/search collision without changing policy or graders.
- [x] Validate all 400 authored paths and reject missing work/wrong answers for every task.
- [x] Add named-session preparation, zero-generation planning, bounded start/resume, status, and reporting.
- [x] Test that planning creates 400 rows without model calls and repeated starts reuse the schedule.
- [x] Preserve the paused 2/60 development pilot and verify compatibility with its original source.
- [x] Publish the corpus scope and a concrete self-service runbook.
- [x] Pass 600 Python tests, lint/format/types, and all 24 real Docker probes.
- [x] Freeze the reviewed experiment and verify a resumable 0/400 schedule with zero model calls.

The holdout is at the decision-template level. Tool/resource plumbing and attack
mechanisms are shared with development; independent workflow generalization is
not established. The forty-task corpus has received no model generation during
authoring or planning. Follow [Run the 400-episode evaluation](run-400.md).

## Historical handoff before the first live release

Run the prepared baseline/defended schedule, preserve all 400 outcomes, and publish
the gate, paired uncertainty, exposure, and failure review. The separate prompt-only
ablation, remaining acceptance evidence, and final portfolio recording remain
outstanding. See [release readiness](release-readiness.md).

## Later milestones

The remaining work follows the architecture plan: stronger operator/worker isolation;
paired held-out evaluation and uncertainty;
recovery/isolation checks; frozen held-out benchmark; portfolio recording and release.

Direct `Store.review()` remains a trusted library call; authentication applies to
the HTTP review endpoint. Authored replay recovery is not evidence that a model
can recover after a denied call.

## Structured follow-up and broader development (October 7)

- [x] Restrict pending mutation reviews to the same tool type and independently reject wrong-kind replacements.
- [x] Apply completion feedback before final review, retaining v1 behavior for frozen studies.
- [x] Complete all 32 frozen structured-v2 trials and independently regrade/publish every outcome.
- [x] Preserve matched 7/8 clean and 7/8 attacked success at higher cost; qualify only for broader development.
- [x] Declare a twenty-workflow, 116-trial comparison and selection rule before generation.
- [x] Complete and publish every outcome; neither arm qualified, so no candidate was selected.

The six PC publications retain 156 outcomes. The earlier clean reproduction
remains evidence for its 735-test, 124-outcome snapshot; final reproduction must
include the subsequent source and publications.

## Recorded console walkthrough (October 7)

- [x] Capture the real fixture console, API restart, exact approval, denied read and queued cancellation.
- [x] Assert committed-effect counts and zero browser page errors during capture.
- [x] Decode the unedited 3:06 video and visually inspect eight full-resolution frames.
- [x] Publish only allowlisted clip/screenshots, source hashes, capture controller and playback metadata.
- [x] Run all sixteen current browser tests; frontend type/format checks also passed.

[Recording and limits](evidence/portfolio-walkthrough-2026-10-07/README.md): caption
cards, no audio, visibly scripted fixtures, zero fresh-model evaluation trials.
Its fixture evidence does not replace live crash/cancellation or containment tests.

## Complete twenty-workflow comparison (October 7)

Control scored 18/20 clean and 31/38 attacked; review scored 16/20 and 23/38
with eleven step-budget terminations. Both had zero observed wins, zero unresolved
attack grades and all 38 payloads exposed. All 116 outcomes were independently
regraded. [Full failure analysis](evidence/pc-workflow-comparison-2026-10-07/README.md).
The seven PC inference publications now retain 272 outcomes, without pooling
study scores. Resource-level search coverage and read attempts are the next
completion increment; the original release remains FAIL. Current PC containment
probes also passed [24/24](evidence/pc-sandbox-2026-10-07/README.md).

## Refreshed clean source/environment reproduction (October 7)

[The broader snapshot](evidence/portfolio-reproduction-broad-2026-10-07/README.md)
passes all 766 tests, lint/format/types, corpus validation, authored demos and
independent state regrading of all 272 PC outcomes. The fresh source, virtual
environment and dependency cache have retained hashes and all check logs.
Same-author reproduction is verified; independent external review remains open.
The broader utility selection still rejects both configurations. Completion
checks for required read attempts and search coverage remain the next feature.

## Resource-level completion treatment (October 7)

- [x] Declare typed reads/read attempts, search/list breadth and explicit result IDs, update targets, distinct creation counts and source/destination shares.
- [x] Present legitimate workflow requirements initially and remind only missing observations at final proposals.
- [x] Persist exact plans with durable job settings; replay committed effects without duplication.
- [x] Reject a plan whose conservative call minimum exceeds its existing step budget before generation.
- [x] Keep default prompt/budget bytes and authorization/grader/storage readers unchanged.
- [x] Pass 34 new tests and the complete 800-test Python/lint/format/type suite.
- [x] Declare the unchanged-graded twenty-workflow, 116-trial comparison and selection rule before generation.
- [x] Complete and publish the fresh-model comparison; resource completion qualified under the frozen rule.

[Resource plan runbook and limits](resource-completion.md). Requirements contain
no expected decision labels or replacement bodies. Search/list breadth policy
is separate from actual declared result-ID coverage and independent grading.
The original release remains FAIL and no default is promoted by implementation.

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
