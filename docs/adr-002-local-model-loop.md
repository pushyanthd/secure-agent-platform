# ADR 002: Bounded local inference before a durable worker

Status: accepted for the feasibility increment, September 23, 2026.

## Context

The authorization kernel and fixed tool container already had deterministic
coverage. Authored replay could not establish that a local model would use those
tools, recover from a denial, or finish the intended task. Before adding queue,
API, or UI complexity, the project needed measured native inference through the
existing gateway and an independent state grader.

## Decision

Use a single-process Python loop with one JSON proposal per model turn. A proposal
is either an existing typed action or a bounded final answer. This keeps the model
surface aligned with the audited kernel and avoids a framework or provider SDK.
The local llama.cpp server constrains generation to the response schema, while
Pydantic and the gateway still validate every returned action independently.

Render and tokenize the server's actual chat template before generation. Reserve
output capacity, disallow server-side context shifting, and charge schema repairs
to the same step/token/time budgets. Commit raw responses before parsing or tool
dispatch. Check the episode deadline again inside the effect transaction.

The HTTP adapter accepts literal loopback endpoints only. Its subprocess boundary
enforces total wall time and output size even if a server slowly streams data.
HTTP redirects, environment proxies, credential inheritance, and implicit model
fallbacks are absent. The added subprocess overhead is acceptable relative to
native generation latency in this feasibility experiment.

Pin the official quantized model, runtime archive, licenses, sampling, template,
and context. Check extracted runtime files and symlinks against the pinned archive.
Downloads are a separate explicit command. The model server is native on the Mac;
only fixed tool computation runs inside Docker.

## Evidence-driven corrections

The first trials produced final success claims without tool effects. The state
grader correctly rejected them. A prompt-only revision did not resolve this.
Canonical JSON serialization had alphabetized the response schema properties,
contradicting the discriminator-first examples under llama.cpp's ordered grammar.
The model transport now preserves schema property order and requires tool tags.
Canonical sorting remains appropriate for action/approval hashes and is unchanged
there. A wire-level regression test protects this distinction.

Subsequent trials performed real tool calls, exposing a second evaluation issue:
the development grader required an exact title and a term in the body, while the
original user task did not explicitly specify those requirements. Task version 2
states them directly. The grader and earlier recorded scores remain unchanged.
Development iterations are reported separately; they are not repeated independent
samples or held-out evidence of improved security.

## Consequences

This increment provides a reproducible live smoke and inspectable failure
evidence. It does not provide durable queue ownership, lease fencing, automatic
resume, model-failure retries, an authenticated approval API, or immediate in-flight
cancellation. Sensitive actions pause with their pending request intact. Re-entering
the same episode is rejected until explicit recovery semantics are implemented.

A process that terminates mid-run leaves its full schedule and partial journal.
It does not receive a successful final report. Later recovery/reporting work must
account for every unfinished scheduled episode rather than silently dropping it.
