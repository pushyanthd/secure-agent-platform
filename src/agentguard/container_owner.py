"""Linux host identity for conservative cleanup of interrupted tool containers."""

import hashlib
import os
from pathlib import Path

PREFIX = "io.agentguard.owner."


def process_start(pid: int) -> str | None:
    """Kernel start ticks distinguish a recycled PID from the original owner."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19]
    except FileNotFoundError:
        return None


def owner_labels() -> dict[str, str]:
    if os.name != "posix" or not Path("/proc/sys/kernel/random/boot_id").exists():
        return {}
    host = hashlib.sha256(Path("/etc/machine-id").read_bytes().strip()).hexdigest()
    start = process_start(os.getpid())
    if start is None:
        raise RuntimeError("Cannot establish tool container owner")
    return {
        PREFIX + "version": "1",
        PREFIX + "host": host,
        PREFIX + "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        PREFIX + "pid": str(os.getpid()),
        PREFIX + "start": start,
    }


def owner_is_dead(labels: dict[str, str], current: dict[str, str]) -> bool:
    """Only recognizable owners on this Linux host can be declared dead."""
    if not current or any(
        labels.get(PREFIX + key) != current[PREFIX + key] for key in ("version", "host")
    ):
        return False
    pid, start, boot = (labels.get(PREFIX + key, "") for key in ("pid", "start", "boot"))
    if not pid.isdecimal() or int(pid) <= 0 or not start.isdecimal() or not boot:
        return False
    if boot != current[PREFIX + "boot"]:
        return True
    return process_start(int(pid)) != start
