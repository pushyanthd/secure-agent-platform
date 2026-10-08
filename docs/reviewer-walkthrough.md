# Five-minute V1 engineering walkthrough

Start with the [V1 console recording](evidence/v1-walkthrough-2026-10-08/README.md)
and [case study](portfolio-case-study.md). The recording uses authored responses
in the real application. It needs no model, Docker or credentials to watch.
The timeline below is an interview narrative, not recording timestamps.

## 0:00 — State the engineering question

How do you connect an agent to useful tools while keeping authority, durable
effects and evaluation outside the model? This local platform has six typed
workplace tools, synthetic resources, a durable worker and an operator console.
The model proposes actions; trusted application code decides what may commit.

## 0:40 — Follow an exact-action approval

Inspect the original task, proposed action and approval binding in the recording.
Review requires acknowledgement and becomes disabled during an API restart.
Approval is expiring and single-use, bound to the exact action, resource state
and policy. The host rechecks current authority before committing the effect,
approval consumption, audit event and execution key in one transaction.
The resulting ticket count is one.

## 1:30 — Explain durable recovery and containment

Persisted model responses separate generation from execution. Worker leases
and commit fencing prevent stale workers from applying effects. The
[live measurement](evidence/live-recovery-2026-10-08/README.md) uses actual
SIGKILL and lease expiry at saved-response and committed-effect boundaries.
It also measures restart cleanup of a real paused tool container and
cancellation before response persistence. These are separate from the video's
fixture-mode API restart.

The pinned Docker tool computes against a snapshot with no network, host mounts
or database access. The host validates its proposal. Restart cleanup recognizes
dead local owners by host, boot, PID and process start ticks, preserving live
or foreign owners.

## 2:30 — Show operational limits and their measurements

The opt-in [artifact volume](artifact-storage.md) bounds aggregate files and
SQLite state. A measured 64 MiB volume exhausts, then recovers after an explicit
increase to 96 MiB, retaining evidence and avoiding duplicated effects.
Missing mounts fail admission rather than writing outside the boundary.

[Joint Windows/Linux observation](evidence/offline-observation-2026-10-08/README.md)
accounts for the native model process and Linux worker descendants during
measured runs: 781 loopback native connections, zero lost ETW events and no
observed public project endpoint. State its finite endpoint/syscall scope.
Container network denial has separate Docker probe evidence.

## 3:30 — Present the declared candidate evaluation

The frozen [58-trial candidate regression](evidence/experimental-v1-candidate-2026-10-08/README.md)
completed 20/20 clean and 38/38 attacked task successes. All outcomes were
independently regraded from committed state. Resource-completion plans require
the actual document, search result or effect demanded by the legitimate task;
an allowed tool call alone does not establish completion.

This is candidate-only evaluation over exposed, self-authored workflows, with
one model and seed. It has no untouched holdout or fresh matched control.
Resource completion stays opt-in. Earlier studies and the original 400-trial
FAIL gate remain in the [case study](portfolio-case-study.md#the-measured-result).

## 4:30 — Demonstrate reproducibility

```sh
uv sync --locked
uv run --locked agentguard eval-verify docs/evidence/experimental-v1-candidate-2026-10-08/run
make check
```

Portable grading needs no inference, original private database or credentials.
The final source has 826 Python tests and sixteen browser tests; all 446
published PC outcomes can be verified. Hosted CI also checks Docker containment,
real storage exhaustion/recovery and installation of the release wheel rebuilt
from its source archive. See [release packaging](release-packaging.md).

V1 is a local AI engineering release with synthetic resources. The
[system card](system-card.md) identifies its scope and open work, including
external reproduction and a release-scale prompt-only ablation.
