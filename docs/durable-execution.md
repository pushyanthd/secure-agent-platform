# Durable execution

The durable worker is a trusted library around the bounded runtime and transactional
effect gateway. It supports ordinary defended episodes; unsafe benchmark profiles
remain confined to the existing synchronous evaluation harness.

The [authenticated local API](control-plane.md) now wraps this worker for task
submission and operator review. The kernel contracts below remain library-level.

## Inspect the demonstration

```sh
make check
make demo-durable
```

The demo writes `report.json`, `report.md`, and `state.sqlite3` into a new directory
under `artifacts/durable/`. It reads the authored shared-write development fixture,
pauses for an exact-action simulated review, interrupts after committing the ticket,
then reopens the database and finishes after simulated lease expiry. The state grader
checks the requested ticket and document read. Seven checks cover waiting, recovery,
single consumption, completion, and one saved response per scripted turn.

This is authored replay with in-process tools, **zero model trials**, an injected
exception, and a simulated clock advance. It is not a measured outage or live-model
recovery experiment. Separate tests abruptly exit real child processes with
`os._exit()` before and after effect commit and recover from the resulting database.

## Queue and runtime contract

`Worker(store, model, model_identity=verified_manifest)` creates a worker whose
recovery identity includes source hashes, model identity, and the tool mode/image/
timeout. The trusted caller supplies verified model provenance; the worker does
not independently attest a model server. Use `prepare_local_model()` for the pinned
local adapter, reject a `preflight_error`, and supply `DockerComputer` to the store
for isolated live tools. The model identity should include the verified profile
and server template/settings. The scripted demo explicitly supplies a fixture identity.

Call `worker.submit(episode_id, task, budgets)` once for an unused defended episode.
Repeating identical inputs is idempotent; changing task, budgets, or identity fails.
`worker.run_once()` claims one compatible job and returns a result or `None` when
no compatible job is claimable. Invoke it again to continue draining the queue.
A changed source tree/model/backend cannot resume the old job; use the original
environment or start a new episode. Jobs are not silently migrated to new models.

Claims use `BEGIN IMMEDIATE`. At most one unexpired worker lease exists in the
database. A claim has a random token, increasing generation, and expiry. A background
thread renews the lease at one-third of its duration while model/tool calls run.
After a crash, another worker can reclaim the job once its lease expires. Old
processes may still be running, but their expired/superseded tokens cannot commit.
`LeaseLost` propagates so the stale worker exits without overwriting the new state.

Each runtime checkpoint and both phases of a tool execution validate the token
inside the same write transaction as the mutation. This includes model requests,
raw responses, errors, run results, approvals created by execution, and effects.
Calling `Runtime.run()` or `Store.execute()` without a token cannot bypass a job's
fence. Existing synchronous benchmark episodes deliberately have no queue entry.

On recovery, the runtime reconstructs messages from saved raw responses and
committed execution results. It verifies each stored request and output allowance,
uses the original model-visible task scope, and dispatches actions with the original
`step-N:call-0` execution key. The gateway loads current permissions and resource
versions. Committed actions return their original output; uncommitted actions
undergo current authorization. This preserves ticket IDs in subsequent prompts
and prevents a second effect after an interrupted successful commit.

## Approvals and cancellation

An approval wait stores the request ID and releases the lease. A trusted caller
reads `Store.approval()` and submits `Store.review()` with its exact hash and nonce.
The review transaction also requeues the waiting job. If review wins the race with
the runtime's waiting checkpoint, that checkpoint notices the decision and requeues
instead of losing the wakeup. If the process dies before the waiting checkpoint,
recovery finds the persisted decision by execution key.

Approved actions are rechecked at effect commit. Rejections and expirations become
bounded denials; changed scope/resource state cannot reuse the old approval. Queue
claims also wake expired approval waits and timed-out episodes. Approval identifiers
and nonces stay out of model feedback. The built-in worker has no automatic reviewer.

Cancellation atomically marks the job terminal and clears its lease. Pending review
is rejected and a running worker cannot persist its response or effect afterward.
It does not immediately kill an active model request or container; existing transport
and tool timeouts remain the resource bound. Host-crash orphan cleanup is future work.

## Budgets and recovery limits

The episode deadline starts at the **first claim**, not submission. It includes
approval waiting and downtime and is never reset on recovery. The default remains
300 seconds; callers can explicitly select a longer bounded budget for an interactive
review demonstration. Saved responses retain step, generated-token, and schema-repair
charges. Reports rebuild token counts from persisted calls even after timeout.

If the worker dies after reserving a model request but before saving its response,
the outcome is unknown. Recovery fails with `MODEL_RESPONSE_LOST` (or the stored
model failure), does not dispatch an action, and does not call the model again.
`generated_tokens` reports known usage; `reserved_generated_tokens` records the
full allowance for missing/invalid envelopes; `charged_generated_tokens` is their sum.
No retry is counted as a new clean trial, and unknown generation is not reported as
known zero consumption. A new attempt requires a new episode.

SQLite is local-disk WAL with a busy timeout. Persisted leases/deadlines use the
trusted host wall clock; individual attempts also use a monotonic deadline. Large
clock adjustments can change when a lease expires. This is a single-host laboratory,
not a distributed clock or hostile-host design. `Store` migrates schemas 0–3 to 4
without modifying existing episode evidence and rejects unknown newer versions.

## Validation and remaining work

`tests/test_worker.py` covers concurrent claims, token forgery/expiry/supersession,
fencing after computation, stale model responses and finalization, real process
death on both sides of commit, lost responses, heartbeat renewal, approval/review
races, stale scope, cancellation, budget preservation, saved final answers, migration,
and the CLI demonstration. The tests run with the existing authorization and
containment suite through `make check`; CI also runs `make demo-durable`.

The worker still shares the trusted OS user/database boundary with operator code.
The API and worker now launch separately and the worker does not read API credentials.
The approval/timeline UI, hardened credential/process isolation, supervisor orphan
reconciliation, immediate subprocess cancellation, and a fresh-model crash experiment
remain later work. Existing published live results describe the synchronous harness;
they are not evidence that these new recovery paths have been measured with the model.
