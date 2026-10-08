# Development suite

The original ten-task suite exercises `documents.read` and
`tickets.create`. It covers task scope, actor ACLs, read-only summaries,
multi-document synthesis, two-ticket batches, reviewed writes, confidential-data
rules, unauthorized reads, and missing resources. The expanded fourteen-task
`suite-v3.json` also exercises search, ticket listing/update, and share requests;
see [the six-tool workflows](tool-surface.md).
The latest [`suite-v4.json`](../scenarios/dev/suite-v4.json) contains twenty tasks,
including six new workflows with four attacks each. See [the corpus contract,
174-episode replay, and retained failures](development-corpus.md). The original
`make eval-suite` target below remains the 60-episode regression suite.

## Run the suite

```sh
make eval-suite
```

This runs 60 **authored scripted episodes**, without a model or Docker:
ten tasks × baseline/prompt-only/defended × clean/attacked. It validates the
gateway, approval simulator, fixtures, and independent graders. Its action
sequences explicitly include recovery attempts, so successful replay cannot
establish that a model will recover. CI runs this command separately from tests.

For fresh inference, first follow the [native-model setup](local-model.md),
start Docker and `make model-serve`, then run:

```sh
make eval-suite-live
# Or select only the defended profile (20 episodes):
uv run --locked agentguard eval-suite --live --variants defended
```

Live mode requires isolated Docker tools and verifies the pinned model/runtime
artifacts and running server. It uses the same step, context, output, and time
budgets as the smoke comparison. Sixty episodes can take substantial time on the
M1; the 300-second per-episode bound permits roughly five hours for the complete
schedule, plus setup and reporting. This command has no paid-provider fallback.
The CLI prints the artifact directory before execution and reports progress after
each episode is saved in `episodes.json`.

Use `--max-episodes N` for a bounded session, or press Ctrl+C once to pause after
the current episode. `agentguard eval-resume <run-directory>` continues the saved
schedule; `agentguard eval-status <run-directory>` inspects it without inference.
See [resumable benchmarks](resumable-benchmarks.md) for exact interruption,
compatibility, and accounting rules. The CLI rejects an unavailable model during
preflight before creating a run; failures after scheduling remain counted.

To check approval waits instead of automatic benchmark reviews:

```sh
uv run --locked agentguard eval-suite --no-simulate-approvals
```

Those episodes stop at `WAITING_APPROVAL`, count as unsuccessful, and cause a
nonzero command exit. Ordinary runtime use and `eval-smoke` still pause for review.

## Fixture and reviewer contracts

[`suite-v1.json`](../scenarios/dev/suite-v1.json) names ten version-2 fixtures.
Each records the original task, trusted scope/resources, attack insertion point,
one fixed payload, an independent state/output expectation, an exact-action review
contract, and authored replay actions. Only the designated document body changes
between paired episodes; ACLs, classifications, scope, and task text stay fixed.
All fixtures are development data. No held-out set has been authored or frozen.

The benchmark-only reviewer receives the task authorization contract and a
predeclared allowlist of complete `tickets.create` actions. It does not receive
attack objectives, canaries, grader predicates, or model reasoning. It approves
only matching contract/action hashes through the existing review API. Every
approved action still passes the gateway's version, expiry, cancellation,
one-use, and hard-prohibition checks. Changed bodies are rejected even when they
look semantically similar. This is intentionally strict and may reduce live
utility; the task exposes the exact requested text for reviewed writes.

The simulator runs in the trusted benchmark process. It is not an authenticated
review service, worker credential separation, or evidence about human reviewers.
The model receives the eventual tool outcome, never the grant ID, nonce, or
review credential. Reports identify every simulated review.

## Grading and artifacts

The grader checks committed document reads, required read attempts (including
denied or missing documents), exact ticket count, target/title/body
requirements, required final-response terms, forbidden reads/writes, and exact
synthetic-canary disclosure in tickets or final output. Grader v4 adds optional
forbidden ticket-list/source-share predicates, exact full-response matching, and
explicit canonical base64/hex disclosure matching. Legacy fixtures keep their
plaintext-only semantics. Model claims and denial counts cannot establish success.
Matching does not detect every paraphrase or encoding of a secret. Task success
additionally requires `COMPLETED`; lifecycle
completion alone is not a successful task.

The baseline intentionally fails the clean confidential-sharing and unauthorized-
read tasks because those tasks require correct refusal. Such failures remain in
the denominator. The CLI fails for any noncompleted episode, any defended clean
failure, or any observed defended attack win. Attacked utility loss is reported
separately; a zero exit is a smoke check, not a portfolio release gate.

Each UUID directory under `artifacts/suites/` contains:

- A manifest with the full schedule written before execution, versions, budgets,
  containment mode, source/fixture/attack hashes, and model evidence in live mode.
- Exact source and fixture snapshots, per-episode actions/reviews/grades, and
  Markdown/JSON reports with clean and attacked denominators.
- Raw model calls, the working SQLite database, a portable SQLite backup, and
  checksums for exported evidence.

Failed and waiting episodes remain in the scheduled counts. Noncompleted attacked
episodes without an observed win contribute to the reported worst-case attack
wins. New runs have a persistent benchmark journal. Resume retains completed
results, records an abruptly interrupted active trial as failed unless its final
runtime result was saved, and continues unstarted work. Reports are finalized
only after every scheduled episode is accounted for.

Analyze a completed run without a model or Docker:

```sh
uv run --locked agentguard eval-analyze artifacts/suites/<run-id> \
  --output artifacts/analyses/<run-id>
```

The analyzer verifies evidence and scheduled denominators, reports conditional
attack success on common clean-solved tasks, and adds paired task-bootstrap
intervals for fresh inference. Replay receives no statistical model claims.
See [analysis contracts and interpretation limits](evaluation-analysis.md).

## Denial feedback experiment

The bounded loop repeats the original trusted task and scope after a denial.
It explains that retrying requires `kind=action`; a final answer cannot perform
a write. It does not rewrite an action, add permissions, or consult the grader.
The same feedback implementation applies to every profile, and its bytes and
subsequent calls consume the existing budgets. A denied proposal may still be
followed by another denial or an unsuccessful final answer.

Both reminder experiments blocked the attack but produced false completion
claims. Their independent task grades remained false. See the
[retained experiment reports](evidence/development-suite-2026-09-23/README.md)
for measured results and limitations.

The subsequent [complete live suite](evidence/ten-task-live-2026-09-23/README.md)
records all 60 episodes, including three approved and one rejected simulated
review. Defended passed all ten clean tasks and eight attacked tasks, with two
retained failures after blocked actions. Its offline analysis and viewer include
all three profiles and every scheduled outcome.
