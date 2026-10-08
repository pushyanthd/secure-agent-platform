# Development hardware

Observed September 23, 2026. Only non-identifying fields are recorded.

| Item | Observation |
|---|---|
| Mac | MacBook Pro, Apple M1, 8 CPU cores, arm64 |
| Unified memory | 16 GB |
| Free filesystem space | Approximately 33 GiB at initial inventory |
| Project Python | Homebrew CPython 3.12.12 |
| Default shell Python | 3.10.0; do not use for this project |
| Docker CLI | 29.7.2, desktop-linux context |
| Docker daemon | Not running at initial inventory |
| Native llama.cpp | `llama-server` not found on PATH |
| Model files | No GGUF files found in the project or user cache inspected |
| PC OS / driver / runtime | Unverified; PC not needed for scripted replay |
| Live latency / memory / model compatibility | Not measured |

Follow-up on the same date: Docker Desktop was started and server version 29.7.2
was verified. The fixed-tool container smoke passed 20 checks; isolated document
read and ticket computation each took about 0.3 seconds in that smoke, including
container startup/cleanup. These are two individual observations, not percentiles
or model inference measurements. See [sandbox evidence](sandbox.md).

`make doctor` emits a fresh JSON inventory. It checks project-local models in
`artifacts/models/`, performs no downloads, and does not start services. System
profiler output is reduced to model name, chip, and memory before reporting;
serial numbers and device identifiers are excluded.

This inventory supports starting a small-model feasibility test. It is not proof
that a specific model fits an 8K context or meets a latency target. Reserve disk
for the container image, weights, temporary downloads, and retained artifacts.

## Native inference follow-up

The project-local `mac-small` profile now uses official Qwen3-4B Q4_K_M weights
and llama.cpp b11149 (`d2e54583c`). The server reports Apple M1 Metal, offload of
37/37 layers, a single 8192-token slot, and non-thinking generation. It reported
a 2375.91 MiB Metal-mapped model buffer and a 1152 MiB Metal KV buffer. These are
runtime allocation observations, not a process peak or independent quantities to
sum on unified memory. Model and native runtime downloads occupy about 2.5 GB.

The executable lives under `artifacts/runtime/`, rather than the system PATH.
`make doctor` recognizes this project-local installation. See the
[local model runbook](local-model.md) for reproducible commands and remaining limits.

The final task-v2 smoke completed six episodes in 48.67–55.76 seconds each. Its
foreground native server command reported maximum RSS of 3,852,435,456 bytes
(about 3.59 GiB) via macOS `/usr/bin/time -l`. This measures the command process
tree's maximum RSS, not whole-machine or Docker memory. Unrelated Postgres and
TripML containers were stopped before this run. See the [raw observations and
interpretation](evidence/local-model-2026-09-23/README.md).

The subsequent [complete ten-task live suite](evidence/ten-task-live-2026-09-23/README.md)
ran all 60 episodes on this Mac with the same pinned profile and isolated tools.
Observed episode durations were 27.00–75.89 seconds (median 51.89 seconds); native
server command maximum RSS was 3,852,910,592 bytes, about 3.59 GiB. Tests and browser
checks ran concurrently during part of the session, so these are feasibility
observations rather than controlled performance measurements. The server was
stopped afterward, and Docker reported no running containers at cleanup.

## Expanded six-tool evaluation

The [six-tool live evidence](evidence/six-tool-live-2026-09-23/README.md) contains
24 original episodes and two separate six-episode wording follow-ups. The
original episode durations were 91.43–178.00 seconds (median 136.61), with
54.04 minutes of summed episode time. The native server command’s maximum RSS
across all three runs was 3,800,367,104 bytes (3.54 GiB). All 37 layers
were offloaded to Metal. Tests/analysis overlapped parts of inference, so neither
the timing nor the difference from earlier sessions is a controlled comparison.
The server was stopped afterward, port 8101 had no listener, and no `agentguard-`
containers remained. Whole-machine memory and public-network traffic were not measured.

## September 28 utility candidates

Both additional pinned model profiles ran on this M1 Mac. The updated 4B
candidate used approximately 2.5 GB of weights; Qwen3.5-9B Q4_K_M used
5,680,522,464 bytes. The 9B runtime reported 33/33 layers offloaded to Metal,
a 5406.91 MiB Metal-mapped model buffer, 545.62 MiB CPU-mapped model buffer,
and 256 MiB Metal KV buffer. These are runtime allocation observations, not
whole-machine peak memory measurements or independent quantities to sum.

The [9B screen](evidence/model-medium-2026-09-28/README.md) stopped for utility
futility at 14/32 under its predeclared rule. Fitting the model in memory did not
establish useful task completion. The [completion-guard comparison](completion-guard.md)
uses the same model and budgets. Prompt caching remains explicitly disabled in
both arms; calls reprocess the full prompt. Reported timings reflect uncontrolled
host load and should not be treated as controlled performance benchmarks.
