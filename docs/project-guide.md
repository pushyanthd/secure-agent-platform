# Full platform workflow guide

The [project overview](../README.md) is the short portfolio entry point. This
guide retains the detailed workflows and development history. For the latest
follow-up, see [decision review](decision-review.md).

# Secure Agent Execution & Evaluation Platform

**Implemented:** six tools, durable execution, authenticated API, operator console,
and a frozen, resumable evaluation harness.

**Measured:** the first 400-trial evaluation is complete. Defended clean task
success was **5/40**; observed attacker wins were **0/160**, versus baseline
**104/160**, with two defended attacks unresolved. The release gate is **FAIL**.
Current work targets utility before portfolio release. The October 7 PC follow-up
completed 20 development and 32 utility trials. The subsequent completion guard
qualified on two capacity cases, but its broader 32-trial study still failed selection.
[Results and failure analysis](evidence/release-v1-2026-09-27/README.md).

A local workplace-agent lab that measures legitimate task completion and resistance to prompt injection, with application-enforced permissions, reviewable actions, and reproducible security evaluations.

[Engineering case study](portfolio-case-study.md) ·
[Architecture and implementation plan](../arch_plan/secure-agent-platform-plan.md) ·
[System card and measured limits](system-card.md) ·
[Run the 400-episode evaluation](run-400.md)

The full platform can run on one Windows PC: Ubuntu under WSL2 hosts the application,
state, console, evaluations, and Docker tools, while native Windows CUDA serves
the model on the RTX 5080. See [the PC-only setup](pc-inference.md#pc-only-application-and-evaluation).
The Mac workflow remains available. No paid cloud service or model API is required.

A representative workflow reads a synthetic launch document and creates a ticket.
An embedded instruction tries to redirect the write to an unauthorized project;
the gateway checks the actual action against trusted permissions before committing it.

## Start here: engineering review

The project demonstrates application-owned authorization around model tool calls,
durable recovery, transactional effects, and evaluation that checks committed
state rather than trusting an agent's completion claim.

```mermaid
flowchart LR
    UI[Operator console] --> API[Authenticated API]
    API --> W[Durable worker]
    W <--> M[Local model]
    W --> G[Authorization gateway]
    G --> C[Isolated tool computation]
    C --> V[Validate effect and recheck authority]
    V --> DB[(Atomic effect, approval, audit, idempotency)]
    DB --> E[Independent state grader]
```

| Review path | What to inspect |
|---|---|
| [Engineering case study](portfolio-case-study.md) | Architecture decisions, tradeoffs, retained failures, and next steps |
| [Original 400-trial release](evidence/release-v1-2026-09-27/README.md) | FAIL gate: defended clean 5/40, observed wins 0/160, two unresolved attacks |
| [Latest PC development run](evidence/pc-development-2026-10-07/README.md) | 10/10 clean, 9/10 attacked, 0/10 observed wins; one omitted-read failure |
| [Latest PC utility study](evidence/pc-utility-2026-10-07/README.md) | Checklist clean 6/8, attacked 5/8; both selection thresholds missed |
| [Completion-guard follow-up](evidence/pc-completion-broad-2026-10-07/README.md) | Guard commits 12/12 required effects; clean 6/8 still misses the selection rule |
| [Five-minute walkthrough](reviewer-walkthrough.md) | Guided trace, approval, recovery, and evidence review |

The studies use different task sets and execution profiles. Their scores remain
separate. A failed behavioral gate is part of the engineering evidence; this is
an experimental laboratory with synthetic data and effects.

![Operator console reviewing an exact shared-ticket action](evidence/operator-ui-2026-09-23/approval-desktop.png)

## Verify results without a model

Requires Python 3.12+ and uv, on Linux, macOS, or Ubuntu under WSL2:

```sh
uv sync --locked
uv run --locked agentguard eval-verify docs/evidence/pc-development-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-utility-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-completion-guard-2026-10-07/run
uv run --locked agentguard eval-verify docs/evidence/pc-completion-broad-2026-10-07/run
uv run --locked agentguard demo-replay
uv run --locked agentguard demo-durable
```

The first four verification commands independently regrade all 92 saved outcomes from portable
committed state, including every failure. They need no model, Docker, credentials,
or original private database. The demonstrations use authored responses and make
zero model calls. See [the portable evidence contract](portable-evidence.md).
Run `make check` for lint, formatting, strict typing, and the Python tests.

## Run the 400-episode release comparison

Forty authored decision templates, four attacks each, baseline and defended:
400 fresh trials. The [runbook](run-400.md) covers setup, pause/resume, and
results; the [corpus scope](held-out-corpus.md) explains shared mechanisms
and the limits of this self-authored decision-template holdout.

```sh
make release-prepare             # Full checks and freeze; zero generation
make release-plan                # Inspect a 0/400 schedule without inference
make release-start EPISODES=10   # First ten real trials, then pause
make release-start               # Resume the same run to completion
make release-report              # Gate, offline viewer, and diagnostics
```

Start Docker and the pinned local model server first (`make model-serve` in a
separate terminal). `make release-status` works without inference. All failed
trials remain in the frozen comparison; this release is explicitly experimental.

## Current work: improve utility before release

The 400-trial evaluation is already complete and its gate remains **FAIL**.
The [model screens](model-utility-pilot.md) rejected the updated 4B candidate
at 19/32 and the 9B candidate at its predeclared 14/32 futility stop.
The latest [completion-guard pilot](completion-guard.md) targets omitted
requested actions using explicit trusted task obligations. It keeps the same
9B model, exact graders, and budgets. The [completed eight-trial comparison](evidence/completion-guard-2026-09-28/README.md)
recorded exact success of 0/4 control versus 1/4 guard and ticket creation of
1/4 versus 4/4. Incorrect decisions and one guarded timeout prevented selection.
[Windows/RTX 5080 inference](pc-inference.md) now supports the complete
PC-only WSL application stack and verified loopback CUDA inference. On October 7,
all 679 Python tests, 16 browser tests, and 24 container probes passed. A clean
and attacked launch-task feasibility pair also passed with real inference.
The [completed 20-trial PC run](evidence/pc-development-2026-10-07/README.md)
then scored 10/10 clean and 9/10 attacked success, with zero observed wins.
The [new 32-trial PC checklist study](evidence/pc-utility-2026-10-07/README.md)
scored 5/8 versus 6/8 clean and 2/8 versus 5/8 attacked success. All trials
completed and all attacked payloads reached model requests, but the checklist
missed its frozen 7/8 and 6/8 thresholds. It remains unselected.
Both publications now support offline state regrading; the release gate remains FAIL.

The [PC capacity guard study](evidence/pc-completion-guard-2026-10-07/README.md)
then passed its frozen 4/4 exact-success rule versus 3/4 control. A new
[32-trial broader guard comparison](evidence/pc-completion-broad-2026-10-07/README.md)
recovered all 12/12 required effects versus control's 9/12 and improved attacked
success from 5/8 to 6/8. Clean success stayed at 6/8, so the candidate was rejected.
Wrong quorum decisions and incorrectly committed capacity/deadline labels remain.
All 40 new outcomes support offline regrading; no default was promoted.

```sh
uv run --locked python scripts/completion_pilot.py status
uv run --locked python scripts/completion_pilot.py report
```

Docker and the `mac-medium` model server must be running for inference. See the
runbook for first-time preparation. Existing tasks remain unchanged unless the
guard is explicitly enabled. Historical reports require their frozen source;
[regrading instructions](completion-guard.md#historical-evidence) preserve
the original 400-trial result. Another full release run waits for measured utility.

## Utility improvement pilot

The [checklist pilot](utility-pilot.md) tests eight paired development cases
after the failed release. Control and treatment share the model, permissions,
budgets, and exact graders; the treatment adds a generic execution checklist.
The 32-trial schedule covers decisions, formatting, committed actions, and denial
recovery. This is exposed-family development work, not a replacement release score.

The [completed 32-trial pilot](evidence/utility-checklist-2026-09-27/README.md)
improved clean success from 1/8 to 4/8 and attacked success from 2/8 to 3/8, but
clean decision correctness stayed at 4/8 and the checklist had one unresolved
timeout. It failed the predeclared selection rule and remains opt-in development work.

```sh
make utility-validate
make utility-prepare             # Freeze 0/32; zero generation
make utility-start EPISODES=4    # Bounded session, then pause
make utility-start              # Resume remaining trials
make utility-report             # Independently regrade and compare arms
```

## Broader development benchmark

The [fourteen-task live benchmark](evidence/fourteen-task-live-2026-09-24/README.md)
completed all 84 scheduled episodes across three sessions (10 + 10 + 64), using
the pinned local model and isolated tools:

| Profile | Clean task success | Task success under attack | Observed attacker wins |
|---|---:|---:|---:|
| Baseline | 12/14 | 10/14 | 4/14 |
| Prompt-only | 12/14 | 10/14 | 4/14 |
| Defended | 14/14 | 13/14 | 0/14 |

The one defended failure is retained: simulated review rejected a sensitive
write, but the model falsely claimed it had created the ticket. Independent
grading found zero tickets. All 13 failed task grades across the three profiles
remain in the report. These self-authored development results are not a held-out
release gate, and zero observed wins does not establish zero attack risk.

Open the [offline comparison viewer](evidence/fourteen-task-live-2026-09-24/analysis/explorer.html),
[paired analysis](evidence/fourteen-task-live-2026-09-24/analysis/analysis.md),
[runtime diagnostics](evidence/fourteen-task-live-2026-09-24/diagnostics/diagnostics.md),
or [five-minute reviewer walkthrough](reviewer-walkthrough.md).

## Run locally

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). From this directory:

```sh
uv sync --locked
make doctor
make check
make demo-replay
make demo-durable
make eval-suite
```

If uv is not installed, bootstrap it inside the repository with an available
Python 3.12 (on this Mac: `/opt/homebrew/bin/python3.12`):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install uv==0.12.18
make setup
```

The Makefile also finds uv in `.venv/bin`. Dependency installation needs network
access; the installed replay and tests need no model, credentials, or services.

`make demo-replay` creates a new directory under `artifacts/replays/` with four
episodes, a SQLite database, JSON and Markdown reports, and report checksums.
Each run compares clean and attacked inputs under baseline and defended profiles.
The baseline deliberately disables business authorization inside its synthetic
episode. Authored recovery attempts the intended project after the redirected write.

**This is scripted replay, not fresh inference or a recording of a model run.**
It exercises contracts and graders; its results are not a measured model attack
success rate. The browser console is described below.

`make demo-durable` demonstrates a persisted approval wait, simulated review,
an interruption after ticket commit, and recovery without a duplicate ticket.
It also uses authored responses and performs **zero model trials**. The worker
uses transactional claims, renewable leases, and fencing at every checkpoint and
effect commit. Separate tests kill subprocesses before and after effects.
See the [durable execution runbook and limits](durable-execution.md).

The authenticated API supports defended task submission, owner-scoped status and
redacted timelines, cancellation, and exact-action review. Start the scripted
application locally, with API and worker in separate terminals. Building the
React/TypeScript UI also requires Node.js 24 LTS:

```sh
make ui-setup ui-build
uv run --locked agentguard control-init --fixture
make api-serve       # Terminal 1: loopback-only API
make worker          # Terminal 2: durable worker, no operator credential file
```

Open `http://127.0.0.1:8000/`, connect using the token in
`artifacts/control/operator.token`, and choose **authorized shared write** to
review an exact action. If control settings already exist, skip initialization.
The console supports task selection, redacted timelines, approval/rejection,
cancellation, and observer access. See the [operator UI runbook](operator-ui.md)
or use the [control-plane API client](control-plane.md).
`make control-smoke` verifies real HTTP authentication and API restart during an
approval wait with separate worker processes. Fixture runs are labeled and perform
zero model trials; omit `--fixture` when initializing a separate live instance.

`make eval-suite` expands deterministic validation to ten development tasks and
60 paired episodes, including exact-action approval simulation, confidential-data
rules, actor ACLs, and state/output grading. It is also scripted replay. See the
[suite runbook](development-suite.md) for fixtures, grading limits, and the
explicit `make eval-suite-live` command for fresh model trials.

Analyze any completed suite and open its standalone comparison viewer:

```sh
uv run --locked agentguard eval-analyze artifacts/suites/<run-id> \
  --output artifacts/analyses/<run-id>
open artifacts/analyses/<run-id>/explorer.html  # macOS
```

The analyzer verifies evidence checksums and scheduled results, calculates paired
comparisons and conditional attack success, and adds descriptive task-bootstrap
intervals for fresh inference. The viewer shows proposals, policy decisions, and
independent grades side by side. It runs offline and displays untrusted content
as text. See [the analysis contract and limits](evaluation-analysis.md).

`make eval-multi-attack` exercises one clean input plus four attack families under
all three profiles (15 authored episodes, zero model trials). Scheduling,
pause/resume, paired task-cluster statistics, and the viewer preserve each payload's
identity. See [the multiple-attack development pilot](multi-attack-evaluation.md).

The [twenty-task catalogue](development-corpus.md) adds six workflows with
four attacks each. `make eval-development` runs all 174 authored episodes;
`make eval-expansion` runs the 90 original expansion episodes, retaining seven
defended attacker wins involving sibling-ticket edits and final-response disclosures,
and exits nonzero after saving complete reports. These are scripted boundary
checks, not new live-model measurements.
The [90-episode Docker evidence](evidence/development-expansion-2026-09-24/README.md)
includes the complete outcomes, offline viewer, and retained failure analysis.

The [ticket-scope treatment](adr-003-ticket-scope-and-response-boundary.md)
adds exact ticket permissions to all five update workflows. `make eval-development`
now selects the versioned v5 catalogue; `make eval-ticket-scope` runs its six-task
treatment subset. These authored checks block the four sibling edits and retain
the three final-response disclosures, so both commands still exit nonzero.
`make eval-expansion` retains the original seven-failure fixtures. New operator
installations use the narrowed contracts; existing settings keep their suite.
No fresh-model improvement or output-confidentiality guarantee is claimed.
The [90-episode Docker treatment evidence](evidence/ticket-scope-2026-09-24/README.md)
includes the exact four improved outcomes, remaining failures, and offline viewer.

The opt-in [response-clearance treatment](adr-004-response-clearance-treatment.md)
adds a separate final-output boundary. `make eval-response-scope` withholds the
three known disclosures, but also blocks a harmless clean triage response:
defended clean success is 5/6 and attacked success is 20/24, with zero observed
attacker wins in authored replay. The command exits 1 for the clean-task failure.
This measured utility cost keeps it out of the default catalogue. Raw evaluation
artifacts remain privileged and are not sanitized by the response policy.
The [90-episode response treatment evidence](evidence/response-scope-2026-09-24/README.md)
preserves all five changed outcomes and the failed clean-task grade.

The opt-in [verified-effect receipt treatment](adr-005-verified-effect-receipts.md)
recovers this completion-message utility with an explicit, fixed receipt for an
exact reviewed ticket update. It verifies the committed effect and current authority
before delivering any confirmation. In a matched 180-episode Docker replay,
defended clean success rises from 5/6 to 6/6 and attacked success from 20/24 to
24/24, while both controls retain zero observed attacker wins. These are authored
boundary checks, not fresh model trials or a held-out release result. Run
`make eval-effect-receipt`; [the full evidence](evidence/effect-receipt-2026-09-25/README.md)
preserves the matched control and all baseline failures. The default remains v5.

The subsequent [10-episode fresh-model pilot](evidence/receipt-live-pilot-2026-09-25/README.md)
**did not recover whole-task utility**: both arms scored 0/1 clean and 0/4 attacked
success. Clearance withheld otherwise valid answers; the receipt arm skipped the
required read and listing. None of its four attacks reached a saved model request,
so its zero attacker wins cannot establish resistance. All ten failed grades,
raw replies, exposure checks, and reproduction commands are retained.

The subsequent [receipt-disclosure pilot](evidence/receipt-disclosure-2026-09-25/README.md)
keeps full receipt authority in trusted storage and shows only its template to the
model. Across ten new matched episodes, clean success improves from 0/1 to 1/1
and attacked task success from 0/4 to 4/4, with unchanged graders. The treatment
encounters all four payloads and recovers after one denied shared-ticket proposal.
Both arms have zero observed attacker wins; the control encounters no attacks.
This is a one-task development result, not a held-out security claim. See
[ADR 006](adr-006-model-visible-receipt-scope.md); the treatment stays opt-in.

The [400-episode release runbook](release-evaluation.md) explains when to start
the main evaluation: after development decisions, forty untouched held-out tasks,
lineage review, a frozen experiment, and a release-specific gate. The freeze,
resumable 400-episode runner, and PASS/FAIL/UNUSABLE gate are implemented; the
forty new decision templates are authored and validated; the first 400 live outcomes are published with a FAIL gate.

Benchmarks can run directly from your terminal across multiple sessions. Add
`--max-episodes 10` to `agentguard eval-suite` to pause after ten episodes, or press
Ctrl+C once to finish the current episode and pause. Continue with
`uv run --locked agentguard eval-resume artifacts/suites/<run-id>` and inspect
progress with `agentguard eval-status`. Keep the same code/model environment.
See [pause, resume, and interruption accounting](resumable-benchmarks.md).

## Run isolated tools

Start Docker Desktop, then run:

```sh
make sandbox-build     # Explicit download/build from a digest-pinned Python image
make sandbox-smoke     # Real containment probes; nonzero exit if a check fails
make demo-isolated     # Same authored episodes, with both profiles using containers
```

The container uses a fixed entrypoint, unprivileged UID, no network, read-only
root, dropped capabilities, and CPU/memory/PID limits. No host paths, credentials,
or Docker socket are mounted. Bounded JSON travels over stdin/stdout; only the
host can commit simulated effects. Permissions and approvals are rechecked after
computation, outside which the database write lock is released.

`make demo-replay` retains the lightweight in-process backend for local contract
tests. Reports identify the actual backend. Neither mode performs model inference.
See the [sandbox runbook and measured checks](sandbox.md).

## Run a real local model

The pinned `mac-small` profile targets macOS on Apple Silicon. Start Docker, then:

```sh
make models-fetch       # Explicit ~2.5 GB model download plus pinned native runtime
make model-serve        # Keep this terminal open; loopback-only native inference
```

In another terminal, run `make eval-smoke`. It executes six fresh trials across
baseline, prompt-only, and defended profiles using the isolated tools. Reports
include failed episodes, state-based grades, raw model-call evidence, model/runtime
checksums, template, sampling settings, and budgets. This one-task development
smoke does not establish benchmark-level security or utility.
See the [local-model runbook and current limitations](local-model.md).

The [measured six-episode comparison](evidence/local-model-2026-09-23/README.md)
passed every clean trial. The injection succeeded against baseline and prompt-only;
the gateway blocked it under defended, but the model failed to recover and finish
the task. Earlier failed development trials are retained alongside the final smoke.

Two subsequent [denial-feedback experiments](evidence/development-suite-2026-09-23/README.md)
retained that utility failure: the model claimed success after denial without
creating a ticket. Their state grades remain failed.

The earlier [ten-task live evaluation](evidence/ten-task-live-2026-09-23/README.md)
retains all 60 scheduled episodes, including two defended recovery failures.
It predates the expanded six-tool schema and is kept separate from the latest
84-episode results above; the studies are not pooled or selectively regraded.

## Expanded tool workflows

Document search, ticket listing and versioned updates, and reviewed document sharing
now use the same gateway and transactional effect boundary. Shares write only to an
episode-local simulated sink. The console displays the exact source document or
current ticket when reviewing these actions.

```sh
make eval-tools             # 24 authored episodes; zero model trials
make sandbox-build          # Rebuild the fixed tool image after upgrading
make eval-tools-isolated    # The same workflows through Docker
make eval-tools-live        # 24 fresh episodes; original versioned task wording
```

The [tool contract and upgrade runbook](tool-surface.md) covers filtering,
version checks, approvals, migration, and the four new development tasks. New
console installations offer all 20 development scenarios using `suite-v4.json`,
including the six new workflows. Existing settings retain their
selected suite version. See the
[scripted tool-surface evidence](evidence/tool-surface-2026-09-23/README.md).
The ten-task live results above predate the expanded schema and remain unchanged.

The [expanded live evaluation](evidence/six-tool-live-2026-09-23/README.md)
retains all 24 original trials. Eleven strict task grades failed on ambiguous
punctuation requirements; those failures remain published. All profiles had zero
observed attacker wins and zero policy-denial episodes, so this run does not
establish comparative attack reduction or denial recovery. Separate versioned
wording experiments passed all 12 follow-up trials without changing graders.
The evidence also includes token accounting, tool coverage, observed durations,
and narrowly scoped policy-cost measurements.

## Implemented boundaries

- Typed tool proposals cannot supply actor identity, scope, or approval grants.
- The gateway checks actor ACLs, task scope, and confidential/shared-write rules.
- Scoped approvals expire and are invalidated by changed actions, resources,
  permissions, or episode state.
- SQLite transactions commit approval consumption, simulated effects, audit,
  and execution-key results together. Retries do not create duplicate tickets.
- Queued runs reject missing, expired, and superseded worker leases, including
  after tool computation. Recovery reuses saved responses and original budgets.
- Approval waits release leases; persisted reviews atomically wake the job.
- The API derives actor/workspace from credentials, scopes every run to its owner,
  rejects cross-origin writes, and separates observer access from operator review.
- Independent graders inspect stored tickets and final output rather than the
  agent's success claim or the number of denied calls.

The security tests exercise direct forbidden actions, stale/cross-episode grants,
concurrent retries, cancellation, and rollback on precommit failure.

## Project evidence and next milestone

- [Implementation progress and remaining milestones](progress.md)
- [Remaining release work and effort estimate](release-readiness.md)
- [Twenty-task corpus, grader coverage, and retained security failures](development-corpus.md)
- [84-episode live results and measured resume](evidence/fourteen-task-live-2026-09-24/README.md)
- [Runtime budget, coverage, and denial diagnostics](runtime-diagnostics.md)
- [Interactive operator console and browser security](operator-ui.md)
- [Operator console screenshots and verification](evidence/operator-ui-2026-09-23/README.md)
- [Complete live feasibility and failure analysis](evidence/ten-task-live-2026-09-23/README.md)
- [Offline analysis and viewer contract](evaluation-analysis.md)
- [Live model results and retained failure analysis](evidence/local-model-2026-09-23/README.md)
- [Ten-task suite and denial-feedback experiments](evidence/development-suite-2026-09-23/README.md)
- [Observed development hardware](hardware.md)
- [Current trust boundary and limitations](threat-model.md)
- [Why this first increment precedes live feasibility](adr-001-first-increment.md)
- [Why a bounded native loop precedes durable execution](adr-002-local-model-loop.md)
- [Dependency license inventory](dependency-licenses.json)

The [32-trial decision review experiment](evidence/pc-decision-review-2026-10-07/README.md)
then regressed utility: completion control/review scored 7/8 versus 4/8 clean and
7/8 versus 3/8 attacked success. Review committed 5/12 required effects versus
12/12 control and exhausted seven step budgets. Action candidates often became
explanatory final replies during review; completed wrong labels also repeated.
All eleven failed grades, raw calls, and portable state remain published.
The treatment was rejected and no default was promoted. Review consumed 97
calls and 4,021 generated tokens versus control's 56 calls and 1,845 tokens.
The comparison does not retroactively select the earlier completion guard.

Next: make the mutation review protocol unambiguous and investigate deterministic
calculation over grounded, authorized facts before broader workflow selection.
The original release remains FAIL; remaining gaps are listed in the system card.
