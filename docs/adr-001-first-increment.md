# ADR 001: begin with a small authorization kernel

Status: accepted for the first implementation increment, September 23, 2026.

The repository starts with only an architecture plan. The Mac has Python 3.12,
but its container daemon is stopped and no local model runtime/weights were found.
We can establish the correctness of deterministic permission checks independently
while keeping real feasibility work visible.

Implement two fixed synthetic operations and a transactional SQLite effect kernel.
Use authored action sequences to exercise clean and redirected-write episodes.
Label this mode `scripted_replay`, with zero model trials and no container claim.
This is not a captured transcript from an earlier model run.

This gives later inference and container adapters a tested execution contract.
It also postpones model feasibility, so Phase 0 remains open. Do not grow the UI
or release benchmark before the real model/tool smoke succeeds.

Approval state is kept beside simulated effects to make consumption atomic.
The future API must authenticate operators before invoking review and must never
hand a worker the operator nonce. The future worker must add lease fencing to
every effect/checkpoint transaction; idempotency alone is insufficient.

Tooling references:

- [uv lock and sync semantics](https://docs.astral.sh/uv/concepts/projects/sync/)
- [llama.cpp structured-output integration tests](https://github.com/ggml-org/llama.cpp/blob/master/scripts/server-test-structured.py)

Runtime/model links are discovery references, not reproducibility pins. No model
artifact or llama.cpp build has been selected yet.
