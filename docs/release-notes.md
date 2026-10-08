# Secure Agent Platform V1 — v1.0.0

A local agent execution platform that connects typed workplace tools, a
deterministic authorization gateway, exact-action approvals, durable workers,
isolated computation and an authenticated operator console.

## Shipped in V1

- Six typed document/ticket/share tools with actor ACLs and explicit resource scope.
- Single-use approvals bound to the exact action, resource version and policy.
- Atomic effects, audit and idempotency; persisted responses, worker leases and
  stale-worker fencing. Dead-owner Docker containers are reconciled on restart.
- Opt-in aggregate artifact capacity with real exhaustion and recovery measurement.
- Opt-in resource-completion requirements and independent committed-state grading.
- React/TypeScript console, local inference runbooks, portable evidence and hosted CI.

## Validation

The frozen candidate regression completed **20/20 clean and 38/38 attacked task
successes**, with zero observed wins, unresolved attacks or unfinished trials.
All 58 outcomes were independently regraded. The protocol uses exposed,
self-authored workflows, one seed and no fresh matched control or holdout.

Local validation passed **826 Python tests**, lint, formatting, strict types and
offline verification of **446 portable outcomes**. The console has sixteen
browser tests; Docker 29.8.2 passed 24/24 containment probes. Four controlled
live boundaries measured SIGKILL recovery, committed-effect recovery,
cancellation fencing and restart orphan cleanup. A dedicated artifact volume
recovered from 64 MiB exhaustion after an explicit increase to 96 MiB.

Joint Windows/Linux observations retained 781 loopback native connections and
zero lost ETW events, with no observed public project endpoint in the measured
scope. This is finite endpoint/syscall observation with separate container
network-denial proof, not permanent enforcement or every-packet attribution.

## Assets and setup

The release includes the wheel with built console, source distribution, release
notes, SHA-256 manifest and a console walkthrough. Model weights, CUDA binaries,
databases and credentials are excluded. Use the source distribution for fixtures
and follow the repository runbooks to prepare the live Docker/model environment.
The wheel alone is not a complete live installation. Recording mode and source
provenance are identified alongside the video.

## Scope and evaluation history

V1 is a local AI engineering platform using synthetic resources. It does not
establish production multi-tenancy, enterprise integrations or universal
prompt-injection resistance. Resource completion and storage limits remain
opt-in. Independent external reproduction and a release-scale prompt-only
ablation remain open.

The original 400-trial gate remains **FAIL** and its forty templates are exposed.
The new regression is a separate protocol; all prior grades, failed outcomes,
observer corrections, frozen sources and checksums remain available. See the
[system card](system-card.md), [case study](portfolio-case-study.md) and
[release readiness](release-readiness.md) for the complete technical record.
