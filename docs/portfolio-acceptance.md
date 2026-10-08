# Portfolio completion audit

The objective is an inspectable GitHub portfolio project for a senior AI engineering
role. The [architecture plan's acceptance criteria](../arch_plan/secure-agent-platform-plan.md#acceptance-criteria)
allow a portfolio release with explicit evaluation scope and retained product-gate
results. The user-selected utility improvement path also requires a
selected configuration and broader development before another release study.

This audit distinguishes verified work from missing evidence. It does not treat
implemented code or passing unit tests as proof of a live-system claim.

| Requirement | Authoritative evidence | Current conclusion |
|---|---|---|
| Useful real local inference on a documented hardware profile | [PC development](evidence/pc-development-2026-10-07/README.md), pinned runtime/model, saved calls and independent state grades | Verified on the Windows CUDA/WSL PC profile; 10/10 clean and 9/10 attacked development tasks |
| Authorization, approval, isolation, idempotency, and recovery invariants | Current `make check`; [sandbox probes](sandbox.md); [durable execution](durable-execution.md); browser and HTTP restart checks | Current make check passes all 826 Python tests; retained fresh reproduction covers the final 800-test snapshot; [current PC Docker probes](evidence/pc-sandbox-2026-10-07/README.md) pass 24/24, and all sixteen current browser tests pass; each measurement retains its scope |
| Complete frozen release accounting, utility, attacks, uncertainty, and failures | [Original 400-trial release](evidence/release-v1-2026-09-27/README.md) and its freeze/gate | Verified complete; product gate FAIL, including low utility and two unresolved attacks |
| Explicit local release scope and historical gate status | [README](../README.md), [system card](system-card.md), original gate | Implemented; no production or universal resistance claim |
| Measured decision reliability before broader selection | Frozen matched utility studies and independent state regrading | Earlier candidates rejected, including structured v2 in broader development; resource-level completion qualified in its [complete comparison](evidence/pc-resource-completion-2026-10-07/README.md) |
| Broader useful configuration across known workflows | A new frozen development comparison with complete denominators and unchanged graders | Resource completion qualified at 19/20 clean and 37/38 attacked across [all 116 outcomes](evidence/pc-resource-completion-2026-10-07/README.md); earlier workflow rejection is retained |
| A newly declared release study after development decisions | New freeze, declared lineage, independent portable state grades | [58-trial exposed candidate regression](evidence/experimental-v1-candidate-2026-10-08/README.md) passed 20/20 clean and 38/38 attacked, zero wins/unresolved/noncompleted; no holdout or default promotion |
| No public network calls or paid API requests during a measured offline run | Process/network observations covering worker, tool execution, and native model service | [Joint Windows/Linux measurement](evidence/offline-observation-2026-10-08/README.md) observed only loopback project endpoints, zero lost ETW events and pinned-container network denial; finite endpoint/syscall scope, not permanent enforcement |
| Bounded artifact storage and measured exhaustion behavior | A configured quota, rejected over-limit writes, retained state, and recovery tests | Verified for the opt-in [operational ext4 volume](evidence/artifact-storage-adapter-2026-10-08/README.md): 18/18 checks plus two missing-mount checks; 64 MiB exhaustion and explicit 96 MiB recovery. Authored fixture; excludes model/cache/Docker/repository storage |
| Additional live crash/cancellation and orphan cleanup behavior | Fresh model runs with controlled fault timing, journal/effect checks, and process/container accounting | [Four measured live boundaries](evidence/live-recovery-2026-10-08/README.md) accounted for eleven native calls, real SIGKILL/lease expiry, exact effects, cancellation fencing and restart orphan/CLI cleanup; original observer failure and correction retained |
| Clean source/environment reproduction and checksum verification | [Current fresh reproduction](evidence/portfolio-reproduction-resource-2026-10-07/README.md), source hashes, logs, all portable states | Verified for the final 800-test implementation and all 388 PC outcomes; earlier 735- and 766-test snapshots remain separate |
| Small real benchmark runbook from a clean setup | [PC setup](pc-inference.md), locked dependencies, pinned model/tool artifacts, bounded run commands | Implemented and exercised on this PC; independent external reproduction remains open |
| Portfolio package: case study, screenshots, ADRs, system/model card, failure analysis | README links, [case study](portfolio-case-study.md), [walkthrough](reviewer-walkthrough.md), retained publications | Written and linked; current failed experiments retained |
| Recorded reviewer walkthrough with mode/provenance labels and no credentials | A playable recording, exact script, capture provenance, and reviewed frames | Verified: [2:46 V1 fixture console clip](evidence/v1-walkthrough-2026-10-08/README.md), eight decoded/visually reviewed frames and capture hashes; original 3:06 clip retained; no live-model or containment claim |

October 8 incremental WSL validation passes all 826 tests, lint, formatting and
strict types. The retained fresh reproduction still covers its original
800-test snapshot. [Local packaging](release-packaging.md) also passes installed
wheel/console checks; hosted CI and publication are not verified.

Storage, additional live recovery/cancellation/restart cleanup, joint network
observation and the newly declared candidate regression are now measured.
The 1.0.0 wheel/source archive, reviewed recording and checksummed upload bundle
are complete locally. The user performs the remaining hosted CI and full V1
GitHub release using [prepared commands](github-release-commands.md); those
remote results are not claimed. [Final validation](evidence/v1-final-release-validation-2026-10-08/README.md)
records the local checks.
The structured and broader comparisons and recording are
complete; their rejection and scope remain explicit. A favorable small development score does not close these
requirements. Independent external reproduction needs another reviewer and must
remain honestly labeled until that evidence exists.
