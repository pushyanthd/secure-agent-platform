# PC container boundary checks

All 24 `make sandbox-smoke` checks passed in Ubuntu/WSL with Docker on October 7.
[Report and pinned images/source](report.json) | [Original checksums](checksums.json).
This is real container computation with zero model trials.

The checks cover all six tool computations; unprivileged execution, read-only
root/tool directory, capabilities, no-new-privileges and seccomp; denied network,
no active external interface or IPv4 routes; no Docker socket/host mounts and
symlink isolation; configured memory/process/CPU limits; timeout, oversized
output and memory exhaustion outcomes. The report retains every check.

These are local container probes. They do not establish host-wide offline
behavior, kernel-escape resistance, aggregate artifact quotas, or model utility.
The model service and worker run on the host and need separate network observations.
Pinned image identities and sandbox sources remain in report.json. To repeat:

```sh
make sandbox-build
make sandbox-smoke
```

The original release FAIL remains unchanged. [Containment contract](../../sandbox.md).
