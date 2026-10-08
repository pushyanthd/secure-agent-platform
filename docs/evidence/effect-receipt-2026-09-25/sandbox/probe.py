"""Bounded diagnostic operations, shipped only in the separate smoke-test image."""

import errno
import json
import os
import socket
import sys
import time
from pathlib import Path


def blocked_write(path: str) -> bool:
    try:
        Path(path).write_text("probe")
    except OSError as exc:
        return exc.errno in (errno.EROFS, errno.EACCES, errno.ENOENT)
    return False


def inspect_boundary() -> dict:
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    sock = socket.socket()
    sock.settimeout(0.5)
    try:
        sock.connect(("192.0.2.1", 443))  # Reserved documentation address; never a real service.
        network_denied = False
    except OSError as exc:
        network_denied = exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH)
    finally:
        sock.close()
    host_link = Path("/tmp/host-link")
    host_link.symlink_to("/host/agentguard-host-canary")
    return {
        "unprivileged": os.getuid() == 65532 and os.getgid() == 65532,
        "root_read_only": bool(os.statvfs("/").f_flag & os.ST_RDONLY),
        "tool_directory_unwritable": blocked_write("/tool/write-probe"),
        "no_capabilities": int(status["CapEff"].strip(), 16) == 0,
        "no_new_privileges": status["NoNewPrivs"].strip() == "1",
        "seccomp_filter": status["Seccomp"].strip() == "2",
        "network_denied": network_denied,
        # Docker Desktop's kernel may expose dormant tunnel interfaces. Check their
        # IFF_UP bit and routing table instead of assuming they do not exist.
        "no_active_external_interface": all(
            not int(Path(f"/sys/class/net/{name}/flags").read_text().strip(), 16) & 1
            for _, name in socket.if_nameindex()
            if name != "lo"
        ),
        "no_ipv4_routes": len(Path("/proc/net/route").read_text().splitlines()) == 1,
        "no_docker_socket": not Path("/var/run/docker.sock").exists(),
        "no_host_mount": not Path("/host/agentguard-host-canary").exists(),
        "symlink_cannot_reach_host": not host_link.exists(),
        "memory_limit": Path("/sys/fs/cgroup/memory.max").read_text().strip() == "268435456",
        "pids_limit": Path("/sys/fs/cgroup/pids.max").read_text().strip() == "64",
        "cpu_limit": Path("/sys/fs/cgroup/cpu.max").read_text().strip() == "100000 100000",
    }


operation = json.loads(sys.stdin.buffer.read(1024))["probe"]
if operation == "boundary":
    print(json.dumps(inspect_boundary()))
elif operation == "timeout":
    time.sleep(30)
elif operation == "oversized":
    sys.stdout.write("x" * 131072)
elif operation == "memory":
    chunks = [bytearray(16 * 1024 * 1024) for _ in range(32)]
    print(json.dumps({"allocation_survived": len(chunks)}))
else:
    raise SystemExit(2)
