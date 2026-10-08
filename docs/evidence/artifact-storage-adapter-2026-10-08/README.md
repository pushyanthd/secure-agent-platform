# Measured aggregate storage exhaustion and recovery

October 8, 2026. A new dedicated ext4 filesystem under the documented Ubuntu/WSL
profile enforced a **64 MiB aggregate image capacity**. Usable filesystem space
was lower because ext4 metadata occupies part of that image. The backing image
was allocated before use; SQLite main/WAL files and the synthetic filler shared
the same kernel-enforced bound.

**18/18 exhaustion/recovery checks passed**, plus two real missing-mount checks.
This run used authored model responses, in-process synthetic tools and simulated
lease expiry: **zero fresh model calls**, no live crash, offline or Docker claim.

| Observation | Measured outcome |
|---|---|
| Fill immediately after the first ticket commits | File writes reject with ENOSPC; the subsequent worker checkpoint rejects with SQLITE_FULL |
| Separate over-limit ticket transaction | Effect and audit roll back; no ticket is reported as committed |
| Durable state at exhaustion | One ticket, both saved responses, RUNNING job and successful SQLite integrity check remain |
| Explicit offline growth from 64 to 96 MiB | Filler and retained evidence remain; neither is deleted to recover capacity |
| Worker recovery | Both original responses reused byte-for-byte; only two remaining authored calls added; exactly two tickets and a passing independent state/output grade |
| Actual unmount | Store rejects the absent mount and creates no fallback database; the same image remounts successfully |

[Raw final report](report.json), [exhaustion checkpoint](exhaustion.json),
[missing-mount checks](unmounted.json), [publication provenance](publication.json),
[exact measured source](measured-source.tar.gz), [validation log](validation.log)
and [publication checksums](checksums.json) retain the observed scope.
Synthetic full-state SQLite copies and both backing images remain local and
unpublished. Earlier attempts and the source-transfer validation failure are
accounted for in publication provenance; no historical evidence was changed.

The full current implementation passes **808 Python tests**, lint, formatting
and strict types. This is an incremental WSL check, not a new claim of external
reproduction. The eight prior PC inference publications retain their separate
388-outcome results. The original 400-trial release gate remains **FAIL**.

The final runtime uses `BoundedStore` while the historical storage reader remains
unchanged. [All eight portable verification logs](portable-verification/results.json)
account for all 388 saved outcomes with their original grades and zero inference.
The earlier direct-integration source/measurement remains preserved in the
[separate publication](../artifact-storage-2026-10-08/README.md).

See [configuration, boundaries and recovery](../../artifact-storage.md).
The quota is opt-in: existing unconfigured deployments remain unbounded.
Worker/operator share a trusted host boundary; this does not prevent a
privileged operator from changing mounts/capacity. Logs and exports must be
directed into the bounded filesystem; model weights, caches, Docker storage,
repository publications and controller output are outside the operational quota.
