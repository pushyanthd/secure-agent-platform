"""Verify a persistent, kernel-bounded Linux artifact filesystem before storage access."""

import json
import os
import stat
from pathlib import Path

from pydantic import Field

from agentguard.contracts import Contract


class ArtifactVolumeUnavailable(RuntimeError):
    """The configured artifact boundary is absent or differs from its declaration."""


class ArtifactVolume(Contract):
    version: str = "ext4-artifact-volume-v1"
    image: Path
    mountpoint: Path
    size_bytes: int = Field(ge=32 * 1024 * 1024)
    filesystem_uuid: str = Field(pattern=r"^[a-f0-9-]{36}$")

    def verify(self, target: Path) -> None:
        """Fail closed on an unmounted/replaced/oversized volume or an escaped target.

        The operator and host kernel are trusted. This is an aggregate capacity
        boundary, not protection against a privileged operator unmount race.
        """
        try:
            image = self.image.resolve(strict=True)
            root = self.mountpoint.resolve(strict=True)
            if image != self.image or root != self.mountpoint:
                raise ValueError("Volume paths must be canonical")
            metadata = image.stat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != self.size_bytes:
                raise ValueError("Backing image differs from the configured capacity")
            if not target.resolve().is_relative_to(root):
                raise ValueError("Storage target escapes the artifact volume")
            device = root.stat().st_dev
            major, minor = os.major(device), os.minor(device)
            # mountinfo escapes paths with octal sequences, including spaces.
            mounts = Path("/proc/self/mountinfo").read_text().splitlines()
            matches = []
            for line in mounts:
                left, right = line.split(" - ", 1)
                fields, filesystem = left.split(), right.split()
                mounted = fields[4]
                escapes = (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\"))
                for escaped, literal in escapes:
                    mounted = mounted.replace(escaped, literal)
                if mounted == str(root):
                    matches.append((fields, filesystem))
            if len(matches) != 1:
                raise ValueError("Declared artifact mount is absent or ambiguous")
            fields, filesystem = matches[0]
            if (
                fields[2] != f"{major}:{minor}"
                or fields[3] != "/"
                or filesystem[0] != "ext4"
                or "rw" not in fields[5].split(",")
                or not {"nodev", "nosuid", "noexec"} <= set(fields[5].split(","))
            ):
                raise ValueError("Unexpected filesystem, device or mount options")
            loop = Path(f"/sys/dev/block/{major}:{minor}/loop")
            backing = Path(loop.joinpath("backing_file").read_text().strip()).resolve()
            if backing != image or loop.joinpath("offset").read_text().strip() != "0":
                raise ValueError("Artifact mount uses a different backing image")
            # Verify the on-disk ext4 superblock UUID, independent of filesystem labels.
            with image.open("rb") as stream:
                stream.seek(1024 + 104)
                raw_uuid = stream.read(16).hex()
            expected = self.filesystem_uuid.replace("-", "")
            if raw_uuid != expected:
                raise ValueError("Artifact filesystem UUID differs")
            if os.statvfs(root).f_blocks * os.statvfs(root).f_frsize > self.size_bytes:
                raise ValueError("Filesystem exceeds its configured image capacity")
        except (OSError, ValueError, IndexError) as exc:
            raise ArtifactVolumeUnavailable("Configured artifact volume unavailable") from exc


def load_volume(manifest: Path) -> ArtifactVolume:
    return ArtifactVolume.model_validate(json.loads(manifest.read_bytes()))
