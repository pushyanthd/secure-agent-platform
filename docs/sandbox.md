# Fixed tool sandbox

From the repository root, with Docker Desktop running:

```sh
make sandbox-build
make sandbox-smoke
make demo-isolated
```

Only `sandbox-build` downloads/builds images. The base digest is committed in
`config/sandbox.json` and the Dockerfile. The tiny build context contains only
the Dockerfile, fixed runner, and diagnostics. The tool image excludes diagnostic
code. Build output records local image IDs and source hashes in
`artifacts/sandbox/manifest.json`. Runtime uses the immutable local ID and
`--pull=never`; there is no fallback to a tag or the in-process backend.

`sandbox-smoke` writes JSON evidence and checksums under `artifacts/sandbox-smoke/`.
`demo-isolated` writes the same clean/attacked scenario reports as `demo-replay`,
with `containment: docker_isolated` and the tool image ID. Both baseline and
defended episodes use the same image and supervisor configuration.

## Boundary and controls

The host resolves resources and checks policy before sending an approved snapshot
to the container. The container returns a document result or proposed ticket,
never a database mutation. The host verifies exact content/target agreement,
rechecks authoritative state and approvals, and commits effects atomically.
Changed state results in denial; callers may submit a new execution key after
reconsidering the changed context. A committed retry returns its original result.

Fixed launch settings: UID/GID 65532, network none, read-only root, 16 MiB tmpfs,
all capabilities dropped, no-new-privileges, default seccomp, 256 MiB memory with
no extra swap, 64 PIDs, one CPU, and no host mounts. No credentials or Docker socket
are sent to the tool. Input is limited to 128 KiB, stdout to 64 KiB, stderr to
4 KiB, and execution to 10 seconds. These are transport limits; the typed schemas
also bound individual text fields. The 64 KiB envelope accommodates a 12,000-character
Unicode document; final model-context budgeting remains future work.

The supervisor drains pipes incrementally and times out stalled input writes.
It force-removes its named container after failure, retrying Docker's automatic
removal race briefly. An unconfirmed cleanup is an error. Hard supervisor crashes
and worker lease/orphan reconciliation are future recovery work.

These settings follow Docker's [runtime controls](https://docs.docker.com/engine/containers/run/)
and [default seccomp behavior](https://docs.docker.com/engine/security/seccomp/).
They are a local lab boundary, not a guarantee against kernel or Docker exploits.

## Measured September 23, 2026

On the Apple M1 Mac with Docker Desktop server 29.7.2, all 20 smoke checks passed:

- Document read and ticket effect computation succeeded (0.341 s and 0.302 s in
  one run, including startup/cleanup; not performance percentiles).
- UID/GID, read-only root, unwritable tool directory, dropped capabilities,
  no-new-privileges, and active seccomp matched the requested restrictions.
- An outbound connection to a reserved documentation address was unreachable;
  no external interface was active and no IPv4 route existed.
- No Docker socket or test host path was visible; a symlink to that host path
  did not provide access. The supervisor mounts no host directories.
- Cgroup memory, PID, and CPU limits matched the configuration. The memory probe
  attempting 512 MiB was killed with exit status 137 under the 256 MiB cap.
- A sleeping probe timed out and an oversized stdout probe was stopped. Container
  removal was confirmed rather than inferred from the Docker CLI's termination.

The first run failed two checks: Docker Desktop exposes dormant tunnel interfaces,
and `docker rm --force` can race automatic `--rm` removal. The network check now
tests the active-interface flags and routes. Cleanup retries the in-progress
response until deletion is confirmed; it still fails on daemon loss.

The diagnostic image is trusted test code. These checks do not demonstrate every
escape path, PID exhaustion behavior, arbitrary hostile-code safety, or model
resistance to prompt injection. Model trials remain zero.
