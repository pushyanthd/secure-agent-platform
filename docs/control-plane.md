# Authenticated local control plane

The FastAPI control plane connects owner-scoped task submission, run status,
redacted timelines, cancellation, and exact-action review to the durable worker.
It binds only to `127.0.0.1`. The API server and worker run in separate processes;
only the server reads the operator credential file. The [operator console](operator-ui.md)
provides a same-origin browser workflow. This API does not expose arbitrary tool execution or unsafe
benchmark profiles.

## Run without weights or containers

```sh
uv sync --locked
uv run --locked agentguard control-init --fixture
make api-serve     # Terminal 1: http://127.0.0.1:8000
make worker        # Terminal 2
```

Setup creates a new private `artifacts/control/` directory. It refuses to overwrite
existing settings or keys. The `operator.token` can submit, cancel, and review;
`observer.token` can inspect the same owner's redacted runs. `credentials.json`
contains their SHA-256 fingerprints and trusted principal mappings, not the raw
tokens. All setup files have mode 0600; the directory has mode 0700. Setup prints
paths, never token values. Keep this ignored directory local.

The fixture mode uses authored responses and trusted in-process synthetic tools.
It performs **zero model trials**. API identity and run detail explicitly label it
`authored_fixture`. No reviewer simulator is attached to the worker: the shared-write
task pauses until an authenticated operator submits a decision.

Use `--directory` and `--port` at initialization for another instance. Pass the
resulting `--settings` path to both commands and its `--credentials` path to
`api-serve`. `worker --once` processes one claim and exits; the default worker polls
for more work. A cancelled or superseded worker stops on lease loss; restart it to
continue draining unrelated jobs.

## Submit and review a task

In a third terminal, run this Python client from the repository root. It reads the
bearer credential from disk so the credential does not appear in process arguments.
Only the local fixed port is contacted, without proxies or redirect following.
Inspect the original task, exact action, target resource/version, policy version,
and expiry before entering a decision.

```python
import json
import time
from http.client import HTTPConnection
from pathlib import Path
from uuid import uuid4

directory = Path("artifacts/control")
settings = json.loads((directory / "settings.json").read_text())
token = (directory / "operator.token").read_text().strip()


def request(method, path, body=None, key=None):
    connection = HTTPConnection("127.0.0.1", settings["port"], timeout=5)
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "X-Agentguard-Request": "1",
    }
    if key:
        headers["Idempotency-Key"] = key
    try:
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        if response.status >= 400:
            raise RuntimeError(response.status, result)
        return result
    finally:
        connection.close()


print(json.dumps(request("GET", "/api/identity"), indent=2))
run = request("POST", "/api/runs", {"scenario_id": "authorized-shared-write"}, uuid4().hex)
path = "/api/runs/" + run["episode_id"]
deadline = time.monotonic() + 120
while time.monotonic() < deadline:
    state = request("GET", path)
    if state["status"] not in ("QUEUED", "RUNNING"):
        break
    time.sleep(0.5)
print(json.dumps(state, indent=2))
if state["status"] == "WAITING_APPROVAL":
    pending = request("GET", path + "/approvals")
    approval_path = path + "/approvals/" + pending[-1]["id"]
    detail = request("GET", approval_path)
    print(json.dumps({key: value for key, value in detail.items() if key != "nonce"}, indent=2))
    decision = input("Type approve or reject after reviewing the exact action: ").strip()
    if decision not in ("approve", "reject"):
        raise SystemExit("No decision submitted")
    print(
        request(
            "POST",
            approval_path + "/review",
            {
                "expected_hash": detail["action_hash"],
                "nonce": detail["nonce"],
                "approve": decision == "approve",
            },
        )
    )
print("Run status:", path)
```

Poll `GET /api/runs/{episode_id}` for completion after review, and inspect
`GET /api/runs/{episode_id}/timeline` for decisions. `COMPLETED` means the bounded
execution finished; it is not an independent task-success grade. The smoke test
below also runs the existing state grader.

## Endpoint contract

All API endpoints require `Authorization: Bearer <token>`. The compiled browser
shell and its exact asset allowlist are public but contain no run data or credentials.
Mutations additionally
require `X-Agentguard-Request: 1` and `Content-Type: application/json`.

| Endpoint | Access | Result |
|---|---|---|
| `GET /api/identity` | Either role | Authenticated subject, actor, workspace, role, current mode |
| `GET /api/scenarios` | Either role | Only trusted tasks matching the principal's actor/workspace |
| `POST /api/runs` | Operator | Submit `{ "scenario_id": "..." }` with an `Idempotency-Key` |
| `GET /api/runs?limit=50` | Either role | Up to 100 of this owner's latest runs |
| `GET /api/runs/{run}` | Owner, either role | Status, fixed deadline, mode, and bounded usage metrics |
| `GET /api/runs/{run}/timeline` | Owner, either role | Step, tool, in-scope target, decision, and approval state |
| `POST /api/runs/{run}/cancel` | Owning operator | Revoke active lease; terminal results stay terminal |
| `GET /api/runs/{run}/approvals` | Owner, either role | Approval IDs, status, expiry, and consumption flags |
| `GET /api/runs/{run}/approvals/{id}` | Owning operator | Original task, canonical action snapshot, hash, nonce, expiry |
| `POST /api/runs/{run}/approvals/{id}/review` | Owning operator | Strict boolean decision plus matching hash and nonce |

The submission body cannot set actor, workspace, task text, budgets, model endpoint,
policy profile, attack payload, or grants. Those come from trusted configuration
and the selected fixture. Episode resources, the job, ownership, idempotency binding,
and audit event commit in one transaction. Identical retries return the original
episode; changed content under the same key returns 409. At most 32 unfinished
runs per owner are admitted; identical retries still work when the limit is reached.

Run and approval lookups require the subject, actor, and workspace to match the
stored submission. Other owners see 404 even if they know an ID or approval nonce.
An observer token cannot read review credentials or mutate state. Lease tokens
are not accepted as API credentials. The reviewer identity comes from authentication
and cannot be supplied in a request body.

Review rechecks current permissions, sensitivity, policy, resource versions,
run deadline/status, hash, nonce, and expiry inside its transaction. A changed
approval returns 409 without authorizing an effect. Approved actions undergo the
same checks again when the worker commits. Review and queue wakeup remain atomic.

## Browser and disclosure boundaries

The API checks the exact Host including port, rejects foreign/null Origin headers
and cross-site or same-site Fetch Metadata, and requires a custom header on mutations.
There are no ambient cookies and no permissive CORS policy. Requests without an
Origin are supported for explicit bearer clients such as the Python example.
Uvicorn ignores proxy headers. Duplicate security headers, non-JSON writes, and
bodies exceeding 16 KiB (including chunked bodies) are rejected. Reading the body
has a five-second deadline.

All responses are non-cacheable and use `nosniff`, a restrictive CSP, and no-referrer
headers. Validation and error responses omit input values. General status/timeline
responses omit document bodies, free-text action arguments, final answers, raw model
envelopes, approval nonces/hashes, and worker lease tokens. Out-of-scope proposal
targets are redacted. Exact arguments are intentionally visible only in the owning
operator's approval detail. This is field-level redaction, not a general secret
detector. The UI renders every returned string as escaped text.

Credentials are loaded at server startup. To revoke/rotate a token, stop the API,
replace its private token and fingerprint entry, then restart. The worker does not
load any credential file or receive credentials in its model/tool inputs. However,
both processes currently run as the same local OS user and trust the same database.
A compromised worker with arbitrary host code could read files or modify SQLite.
This is HTTP authority separation, not a hardened OS/process security boundary.

## Live mode and verification

To create a live instance, start Docker and the pinned model server using the
[local-model runbook](local-model.md), then initialize without `--fixture` into a
fresh directory. Startup verifies local artifacts, server identity/template, and
context budget; an unavailable model fails startup. The store uses the fixed Docker
tool image. No weights are downloaded, and there is no paid-provider fallback.

The application config uses a 900-second episode budget to allow manual review.
The worker still preserves the original deadline across review waits and downtime;
individual approvals still expire after 300 seconds. Existing feasibility evaluation
budgets and published results are unchanged. A run's mode comes from its persisted
manifest, even if a later API instance uses different settings.

```sh
make check
make control-smoke
```

The smoke command creates a temporary local API instance, sends real HTTP requests,
executes separate worker processes, restarts the API during approval wait, reviews
the action using a generated operator credential, and checks the independently graded
result. It shuts down its server and deletes temporary bearer credentials. The
database, server log, and sanitized report remain under `artifacts/control-smoke/`.
The 12 checks cover auth rejection, idempotency, review restrictions, replay, restart,
credential exclusion from model inputs, completion, one ticket, and state grading.
It uses authored fixture responses and scripted HTTP review: **zero live-model or
human-usability trials**. CI runs it separately from the in-process API security tests.

Schema v4 adds ownership/idempotency records without rewriting old run evidence.
Older benchmark/library episodes have no API owner and are not exposed through these
endpoints. Richer safe output inspection, hard worker isolation,
immediate subprocess cancellation, and held-out release evaluation remain future work.

Implementation references: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/),
[Starlette middleware](https://www.starlette.io/middleware/), and
[Starlette's current HTTPX2 test-client contract](https://starlette.dev/testclient/).
