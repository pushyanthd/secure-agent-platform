# Native local-model feasibility

The `mac-small` profile pins the official Qwen3-4B Q4_K_M GGUF and an official
llama.cpp macOS arm64 binary archive. Exact revisions, sizes, checksums, licenses,
and sampling settings are in [the profile](../config/model-mac-small.json).
The model download is approximately 2.5 GB. No paid API is used.

## Reproduce

From the repository root, with Python dependencies installed and Docker running:

```sh
make models-fetch PROFILE=mac-small  # Explicit network/download phase
make sandbox-build                 # If the fixed tool image has not been built
make model-serve PROFILE=mac-small  # Foreground; keep this terminal open
```

In another terminal:

```sh
make eval-smoke PROFILE=mac-small
```

Setup verifies the downloaded weights and runtime archive, retains license files,
and installs the runtime under `artifacts/runtime/`. Subsequent setup calls verify
the existing installation without overwriting loaded executables. Serving and
evaluation verify the installed executables/libraries against that archive too.
Setup stages new runtime extraction before atomically installing it.

Serving binds to `127.0.0.1:8101`, enables Metal, uses one 8192-token slot, and
disables thinking, context shifting, downloads, the runtime's browser UI, and
its built-in agent tools. CORS is restricted. The trusted Python gateway is the
only path from model proposals to simulated business effects. Stop the foreground
server with Ctrl-C when finished.

Inference processes receive a small environment allowlist, excluding business/API
credentials, proxy settings, Python path injection, and implicit runtime overrides.

The evaluation command is explicitly experimental: it alone selects permissive
baseline and prompt-only profiles in addition to defended. All three use the same
model settings and Docker tool isolation. The smoke creates six fresh episodes:
one clean and one attacked episode per profile. It never follows the scenario's
scripted action lists. A scope-only task message and schema are visible to the
model; document bodies are supplied only after a gateway-authorized read.
Grader predicates and attack objectives stay outside the model input.

## Artifacts and accounting

Each invocation creates a UUID directory under `artifacts/live/` containing:

- The complete six-episode schedule, model/runtime pins, prompt/source/schema
  hashes, exact server chat template and generation defaults, and budgets. Source
  and scenario snapshots preserve the inputs when the working tree changes later.
- A SQLite journal containing requests and raw model responses, committed before
  any action is parsed or dispatched. `evidence.sqlite3` uses SQLite's backup API.
- JSON/Markdown reports, exported model-call records, and file checksums.

`COMPLETED` means the loop produced a final response. Task success is independently
graded from ticket state and final output; the model's claim cannot satisfy it.
Noncompleted episodes cannot count as useful task successes. Reports retain all
scheduled failures and show unresolved attacked episodes and worst-case attacker
wins. There are no statistical confidence or broad security claims from one task.
The command exits nonzero if an episode is incomplete or a clean task fails its
grader. An attacked baseline task can fail as the intended experimental outcome.

The endpoint accepts only a literal loopback IP with an explicit port. HTTP does
not use environment proxies or follow redirects. A child process imposes total
wall-time and byte limits, including slow HTTP streams. There is no provider,
model, or paid-service fallback. Request failures are recorded with bounded reason
codes; raw responses remain local evidence, not default log messages.

Each episode allows at most eight generation attempts, 4096 generated tokens,
768 tokens per response, 12000 bytes per tool result, and 300 seconds. One
schema-repair attempt shares those same budgets. The adapter renders the server's
chat template and tokenizes it before generation; it reserves output space and
rejects oversized contexts without truncating the user task. A small token reserve
covers template bookkeeping. The transaction rechecks cancellation and the episode
deadline after tool computation, before committing an effect.

## Current limits

This is a single-process feasibility runner. It does not provide durable worker
leases, automatic resume, retries after model failure, or an authenticated approval
API. A pending sensitive action ends the run in `WAITING_APPROVAL`, without automatic
approval or a claim that the workflow finished. Calling the runner twice on the same
episode is rejected. The separate [durable worker](durable-execution.md) now provides
lease-fenced recovery and restartable approval waits for queued application episodes;
the [authenticated local API](control-plane.md) now wraps that worker. The published
feasibility benchmark still uses this synchronous runner.

The adapter bounds a model call and closes its connection on timeout. Cancellation
during generation is observed when that call returns or times out; active container
computation has its own supervisor timeout. No effect can commit after cancellation
or the episode deadline, but immediate process interruption remains future work.

Server properties and local file hashes are checked, but they are not remote
attestation of a hostile server. The model's tokenizer/template are pinned through
the official GGUF artifact; the publisher's exact upstream conversion recipe is
not independently reproduced. Metal buffers and process resident memory must be
reported separately, not added together as independent allocations on unified memory.
The offline flag and loopback adapter restrict routes; a measured public-network
traffic audit remains outstanding.

Only short-lived `agentguard-*` tool containers are needed. This project does not
use a Postgres container or a Kubernetes cluster; persistent containers from other
projects can be stopped to free resources while running native inference.

Protocol references: [llama.cpp server documentation at the pinned commit](https://github.com/ggml-org/llama.cpp/blob/d2e54583c7452353eb35d40431281f6ee984332f/tools/server/README.md)
and [official pinned Qwen GGUF repository](https://huggingface.co/Qwen/Qwen3-4B-GGUF/tree/bc640142c66e1fdd12af0bd68f40445458f3869b).
