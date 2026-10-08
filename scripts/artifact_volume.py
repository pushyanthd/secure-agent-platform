"""Create/mount/grow a dedicated Linux artifact volume; never format an existing image."""

import argparse
import json
import os
import subprocess
import uuid
from pathlib import Path

from agentguard.artifact_volume import ArtifactVolume, load_volume


def run(*command: str) -> None:
    subprocess.run(command, check=True, stdin=subprocess.DEVNULL)


def save(path: Path, volume: ArtifactVolume) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("x") as stream:
        stream.write(volume.model_dump_json(indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def mount(volume: ArtifactVolume) -> None:
    if os.path.ismount(volume.mountpoint):
        volume.verify(volume.mountpoint)
        return
    if any(volume.mountpoint.iterdir()):
        raise ValueError("Refusing to hide existing files beneath the artifact mount")
    if volume.image.stat().st_size != volume.size_bytes:
        raise ValueError("Image capacity differs; repair the declaration before mounting")
    run("mount", "-o", "loop,nodev,nosuid,noexec", str(volume.image), str(volume.mountpoint))
    volume.verify(volume.mountpoint)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("create", "mount", "status", "grow", "unmount"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--size-mib", type=int, default=256)
    parser.add_argument("--owner-uid", type=int, default=1000)
    args = parser.parse_args()
    if os.name != "posix" or not Path("/proc/self/mountinfo").exists():
        parser.error("Run in Linux/WSL, not the Windows checkout")
    directory = args.directory.absolute()
    if directory.resolve() != directory:
        parser.error("Use a canonical path without symlinks or parent traversals")
    manifest = directory / "volume.json"
    if args.operation != "status" and os.geteuid() != 0:
        parser.error("Volume administration requires root; API and worker run as the owner UID")
    if args.size_mib < 32 or args.owner_uid <= 0:
        parser.error("Capacity must be at least 32 MiB and the runtime owner must be non-root")
    if args.operation == "create":
        directory.mkdir(mode=0o755, parents=True, exist_ok=False)
        image, mountpoint = directory / "artifacts.ext4", directory / "data"
        size = args.size_mib * 1024 * 1024
        with image.open("xb") as stream:
            # Allocate capacity now; a sparse image could later exhaust the host disk.
            os.posix_fallocate(stream.fileno(), 0, size)
        mountpoint.mkdir(mode=0o755)
        volume = ArtifactVolume(
            image=image, mountpoint=mountpoint, size_bytes=size, filesystem_uuid=str(uuid.uuid4())
        )
        run("mkfs.ext4", "-q", "-F", "-m", "0", "-U", volume.filesystem_uuid, str(image))
        save(manifest, volume)
        mount(volume)
        os.chown(mountpoint, args.owner_uid, args.owner_uid)
        os.chmod(mountpoint, 0o700)
    else:
        volume = load_volume(manifest)
        if args.operation == "mount":
            mount(volume)
        elif args.operation == "unmount":
            volume.verify(volume.mountpoint)
            run("umount", str(volume.mountpoint))
            return
        elif args.operation == "grow":
            volume.verify(volume.mountpoint)
            size = args.size_mib * 1024 * 1024
            if size <= volume.size_bytes:
                parser.error("Recovery growth must increase capacity; shrinking is unsupported")
            # umount rejects active users; do not use lazy/forced unmount.
            run("umount", str(volume.mountpoint))
            with volume.image.open("r+b") as stream:
                os.posix_fallocate(stream.fileno(), 0, size)
            run("e2fsck", "-f", "-p", str(volume.image))
            run("resize2fs", str(volume.image))
            volume = volume.model_copy(update={"size_bytes": size})
            save(manifest, volume)
            mount(volume)
    volume.verify(volume.mountpoint)
    usage = os.statvfs(volume.mountpoint)
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "capacity_bytes": volume.size_bytes,
                "filesystem_bytes": usage.f_blocks * usage.f_frsize,
                "available_bytes": usage.f_bavail * usage.f_frsize,
                "mountpoint": str(volume.mountpoint),
                "verified": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
