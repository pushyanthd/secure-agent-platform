# V1 release checklist

Updated October 8, 2026. V1 is a **local AI engineering portfolio release** with
synthetic resources, a documented execution profile and measured controls.
The original 400-trial behavioral gate remains **FAIL**. The new 58-trial
candidate regression passes its separate exposed-task protocol. Release scope
and retained evidence do not establish production readiness.

## Complete

- Six typed tools, deterministic authorization, exact one-use approvals,
  transactional effects, durable jobs, authenticated API and React console.
- All 400 original release outcomes accounted for, with utility, attack exposure,
  uncertainty and failure analysis retained.
- Portfolio README, architecture/ADRs, case study, system card and runbooks.
- [Reviewed 2:46 V1 console recording](evidence/v1-walkthrough-2026-10-08/README.md)
  with explicit fixture-mode provenance and no displayed credentials.
- [24/24 current Docker containment probes](evidence/pc-sandbox-2026-10-07/README.md)
  and sixteen browser tests passed within their documented scopes.
- Final [fresh-environment reproduction](evidence/portfolio-reproduction-resource-2026-10-07/README.md)
  passes **800 Python tests**, lint, formatting, strict types, release corpus and
  fixture demos, and independently regrades all **388 PC outcomes**.
- [Complete resource-completion comparison](evidence/pc-resource-completion-2026-10-07/README.md):
  all 116 outcomes saved/regraded; guard qualified at **19/20 clean and 37/38
  attacked**, with zero unfinished trials or unresolved attack grades.
- Final publication checksums, documentation links and source whitespace checks pass.
- [Aggregate operational storage](evidence/artifact-storage-adapter-2026-10-08/README.md):
  opt-in fixed-size ext4 volume; 18/18 exhaustion/recovery checks and two actual
  missing-mount checks passed. Capacity grew explicitly from 64 to 96 MiB without
  deleting retained evidence or duplicating effects. Authored fixture, zero fresh
  model calls; storage outside the configured volume is excluded.
- Incremental WSL checks pass 826 Python tests, lint, formatting and strict types;
  UI build/check and installation of the packaged wheel also pass. The earlier
  fresh reproduction remains evidence for its separate 800-test snapshot.
- [V1 package](release-packaging.md) builds a wheel with the console,
  source archive, notes and checksums. CI now defines storage and packaging jobs;
  hosted execution and publication remain outstanding.

## Final V1 acceptance

| Work | Completion evidence |
|---|---|
| Newly declared release evaluation | [58-trial candidate regression](evidence/experimental-v1-candidate-2026-10-08/README.md): frozen before inference, 20/20 clean and 38/38 attacked, zero observed wins/unresolved/noncompleted; independently regraded. Exposed tasks, one seed, no fresh matched control or holdout. |
| Additional live recovery and cancellation | [Four live boundaries](evidence/live-recovery-2026-10-08/README.md): actual SIGKILL, real lease expiry, saved-response/effect recovery, cancellation fencing and restart orphan removal. Original observer failure retained; separate correction passed without inference. |
| Measured offline behavior | [Joint Windows/Linux observation](evidence/offline-observation-2026-10-08/README.md): zero observed public project endpoints, zero lost ETW events, loopback positive controls and separate pinned-container network denial. Finite endpoint/syscall scope, not permanent enforcement. |
| GitHub publication | User-managed: push the prepared source, pass hosted CI and publish `v1.0.0` with the package and reviewed recording. [Exact commands](github-release-commands.md) are prepared; no push, remote tag or release has been performed by the agent. |

The [resource-completion runbook](resource-completion.md) records the current
bounded treatment: resource-specific required observations with no extra review
calls, expected decision labels or permission grants. A favorable development
result only qualifies a candidate; it does not pass a new release gate or change
the default automatically.

## Scope that stays explicitly limited

The release-scale prompt-only ablation, stronger OS separation between operator
and worker, broader telemetry and independent external reproduction remain open.
An external reproduction requires another reviewer. Historical extracts without
portable SQLite grading state retain their original verification limits.
Additional hardware profiles, multi-seed repeats, external AgentDojo integration,
cloud deployment and dashboards are outside the shortest V1 path.

The [completion audit](portfolio-acceptance.md), [system card](system-card.md) and
[frozen limitations](../evaluations/release-limitations-v1.json) are authoritative
for claim scope. The original gate failed on low utility and two unresolved
attacks; zero observed wins cannot compensate for those failures.

## Publication status

Storage, live fault/cancellation/restart cleanup, measured network observation and
the newly declared candidate regression are complete within their documented
scopes. Local 1.0.0 packaging is complete; user-managed hosted CI precedes the
full V1 release. See
[packaging and publication](release-packaging.md) for the current publication state.
No completed historical inference study was rerun or regraded differently.
