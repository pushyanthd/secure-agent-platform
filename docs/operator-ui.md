# Local operator console

The React/TypeScript console is served by FastAPI at `http://127.0.0.1:8000/`.
It supports scenario selection, owner-scoped recent runs, redacted timelines,
cancellation, and exact-action approval/rejection with fixture or live execution.
Each run displays its persisted execution mode.

## Start a fixture demonstration

Requires the Python environment from the README and Node.js 24 LTS for building.
Node is not required to serve an already built UI. On the development Mac the
Makefile also finds the checksum-verified Node 24.21.0 runtime under ignored
`artifacts/runtime/`; a clean checkout should install Node separately.

```sh
uv sync --locked
make ui-setup ui-build
uv run --locked agentguard control-init --fixture
make api-serve       # Terminal 1
make worker          # Terminal 2
```

Open `http://127.0.0.1:8000/` using the exact loopback address. Read
`artifacts/control/operator.token` in a local editor and paste it into the access
field. Setup refuses to overwrite existing control directories: reuse existing
settings/tokens and skip `control-init` if already initialized. For another
directory/port, use the CLI options in the [API runbook](control-plane.md).

Choose **authorized shared write**, start the run, and inspect the action when it
pauses. Check its title, body, destination, resource version, policy, expiry, and
original task. Check the acknowledgment to enable **Approve exact action**, or
choose **Reject action** without it. The worker rechecks scope before committing.
Try **unauthorized read** to see a denial. Application runs always use defended
policy; benchmark baseline profiles are not exposed here.

For read-only inspection, disconnect and use `observer.token`. Observers cannot
submit, cancel, or review, and cannot retrieve approval snapshots or nonces.

Fixture mode uses authored responses and in-process synthetic tools: **zero model
trials**. For fresh inference, initialize a separate directory without `--fixture`
and start the pinned model server and Docker per the [model runbook](local-model.md).
This UI increment does not claim new live evaluation results.

## State and review behavior

- Polling refreshes state every 1.5 seconds. Connection failures pause review
  actions and reconnect automatically. API restart preserves approval waits.
- Opening approval detail fetches a fixed snapshot. Background polling never
  silently replaces it. Changed/expired approvals show an error, clear the
  snapshot, and require another explicit inspection. Reviews are never retried
  automatically after an ambiguous response.
- A lost submission response retains its idempotency key in memory. **Retry
  submission** uses the same scenario/key. Reload or disconnect clears that
  intent; inspect recent runs before resubmitting after an ambiguous response.
- Cancellation requires confirmation and uses worker fencing. It does not imply
  immediate interruption of active inference.
- **Completed** means execution finished, not a task-success grade. Raw output
  stays redacted. Independent grades and paired comparisons remain in the
  [offline report viewer](evaluation-analysis.md).
- Counters cover the latest 50 owner-visible runs, not all historical runs.

## Browser security boundary

Only `/` and an exact startup allowlist of compiled JS/CSS files are public.
Every API route still requires authentication. Static requests retain exact
Host/Origin and Fetch Metadata checks. Unknown paths, source maps, workspace
files, and symlink escapes are not served. A missing build returns a setup hint
with HTTP 503 while API authentication remains active.

Requests are same-origin, with no cookies, redirects, or response cache. Tokens
stay in tab memory and are cleared from the password field on submission.
Disconnect aborts requests and discards run/review data; reload and page
restoration require reconnecting. Tokens and nonces are never rendered in the
run UI, stored in browser storage, placed in URLs, or handed to the worker. The
browser necessarily receives the nonce when an operator inspects an action.

Returned strings render as text, with no active HTML/Markdown, inline executable
script, remote asset, or third-party font. CSP restricts scripts/styles/API calls
to the same origin, blocks framing and base-URL changes, and uses neither
`unsafe-inline` nor `unsafe-eval`. The host user and browser extensions remain
outside the boundary; this is not hardened process isolation.

## Build, test, and package

```sh
make check
make ui-check ui-build ui-test
```

Browser tests use a temporary real API, separate worker invocations, and
out-of-band fixture mutations, with no test-only HTTP routes. They cover
approval/rejection effects, API restart, stale/expired review, cancellation,
observer access, hostile text, mobile overflow, submission retry, and session
cleanup. Tests use installed Chrome on macOS; Linux CI installs Chromium:

```sh
cd frontend
npx --no-install playwright install --with-deps chromium
```

Browser traces/videos are disabled because they could capture authentication
headers. Token files are deleted on normal teardown. Sanitized screenshots and
local state remain in ignored `artifacts/browser-tests/`.

Dependencies are pinned by `frontend/package-lock.json`; [license metadata](frontend-dependency-licenses.json)
is regenerated with `npm run licenses` in `frontend/`. Prettier and TypeScript
check the sources. Vite writes the build into ignored `src/agentguard/ui/`.
Restart the API after rebuilding to refresh its asset allowlist. Build before
producing a Python wheel to include the UI assets. No development proxy or
relaxed CORS mode is needed. See the [Vite production build documentation](https://vite.dev/guide/build).
