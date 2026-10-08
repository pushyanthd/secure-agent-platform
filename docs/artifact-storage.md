# Aggregate operational artifact storage

The Linux/WSL runtime can use a dedicated **fixed-size ext4 image**, allocated
before use and mounted with `nodev,nosuid,noexec`. The kernel enforces one
aggregate capacity across SQLite main/WAL/shared-memory files, traces, exports,
logs and temporary files placed on that filesystem. Filesystem metadata consumes
part of the configured capacity; usable bytes are reported separately.

The API/worker configuration uses `artifact_volume_manifest`. `BoundedStore` verifies
the image size, exact mount, filesystem type/options, loop backing file and UUID
before construction and every connection. A missing or replaced mount fails
closed rather than opening an unbounded database underneath the mountpoint.
The adapter wraps the unchanged SQLite kernel/reader, preserving strict frozen
source checks and all historical portable grading behavior.
`eval-suite --artifact-volume-manifest` likewise validates its output root and
pins the boundary in the run manifest; resume verifies the saved boundary.
Existing configurations without the option preserve their historical behavior
and **do not gain a quota automatically**.

This bounds a configured operational volume, not the whole user's home directory.
Model weights, dependency caches, Docker storage, repository publications and
measurement-controller output remain outside this volume. Application logs and
exports must be explicitly directed inside it. The trusted operator can allocate
other volumes or raise capacity. Host-level disk exhaustion remains possible;
preallocation avoids relying on a sparse backing image. Privileged concurrent
unmount/replacement is outside the application's trusted-host boundary.

## Configure in Ubuntu/WSL

Run administration as root and the API/worker as your ordinary user. In Windows,
`wsl -d Ubuntu -u root --cd /home/pushy/secure-agent-platform -- ...` can execute
the administration commands without changing the runtime's identity.

```sh
cd /home/pushy/secure-agent-platform
mkdir -p artifacts  # Run as the ordinary user before privileged volume creation.
sudo .venv/bin/python scripts/artifact_volume.py create \
  --directory "$PWD/artifacts/runtime-volume-v1" --size-mib 256 --owner-uid "$(id -u)"
.venv/bin/uv run --locked agentguard control-init \
  --directory artifacts/runtime-volume-v1/data/control \
  --artifact-volume-manifest artifacts/runtime-volume-v1/volume.json \
  --model-profile artifacts/pc-wsl/model-profile.json
.venv/bin/uv run --locked agentguard api-serve \
  --settings artifacts/runtime-volume-v1/data/control/settings.json \
  --credentials artifacts/runtime-volume-v1/data/control/credentials.json \
  > artifacts/runtime-volume-v1/data/api.log 2>&1
# Separate terminal; use the same settings and keep worker logs in the volume.
.venv/bin/uv run --locked agentguard worker \
  --settings artifacts/runtime-volume-v1/data/control/settings.json \
  > artifacts/runtime-volume-v1/data/worker.log 2>&1
```

`create` refuses an existing directory/image. After a WSL reboot, `mount` verifies
the declaration and refuses to hide files underneath the mountpoint. Do not run
the worker as root. The administrator owns the image and manifest; the runtime
owns the mounted data root.

## Exhaustion and recovery

File writes fail with `ENOSPC`; SQLite may report `SQLITE_FULL`. The API returns
507 `ARTIFACT_STORAGE_FULL` for the latter; missing mount returns 503
`ARTIFACT_VOLUME_UNAVAILABLE`. A running worker stops on these conditions without
an automatic retry. A terminal result may itself require unavailable space: the
durable job can remain RUNNING until capacity and its lease are recovered.

Stop all users of the volume and preserve a copy of its backing image outside
the volume before recovery. Do not delete journals, approvals, traces or effects.
`grow` performs an ordinary unmount, allocates a larger image, checks/resizes ext4,
updates the declared capacity and remounts. It rejects shrinking and active
mounts; no forced or lazy unmount is used.

```sh
sudo .venv/bin/python scripts/artifact_volume.py grow \
  --directory "$PWD/artifacts/runtime-volume-v1" --size-mib 512
```

If an administrative operation fails between image growth and manifest update,
leave services stopped, preserve the files and inspect the image/manifest before
repair. The application rejects mismatched capacity. Runtime settings refer to
the current manifest and can recover after explicit growth; a frozen benchmark
pins capacity, so changing it requires a separately declared protocol rather
than silently editing its manifest.

An intent whose response was not durably saved still fails as
`MODEL_RESPONSE_LOST` after capacity recovery. An already committed effect and
saved response are replayed through idempotency instead of regenerated. Absolute
episode deadlines and original permissions still apply.

## Measured scope

[October 8 measurement](evidence/artifact-storage-adapter-2026-10-08/README.md): a new
64 MiB volume exhausted after the first batch ticket committed. File writes and
SQLite checkpoints failed; a separate effect/audit transaction rolled back.
Explicit growth to 96 MiB retained the filler and evidence, reused both original
saved responses and completed with exactly two tickets and a passing state grade.
The fixture uses authored responses and in-process tools, with simulated lease
expiry: **zero fresh model calls** and no live crash, network or Docker claim.
CI runs the same real filesystem measurement on a fresh dedicated volume.
