"""Read-only, bounded preflight. Never download models or start services implicitly."""

import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def probe(command: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        return result.returncode == 0, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False, ""


def inventory(root: Path) -> dict[str, Any]:
    hardware: dict[str, str] = {}
    if sys.platform == "darwin":
        ok, output = probe(["system_profiler", "SPHardwareDataType"])
        if ok:
            # Never retain serial numbers, hardware UUIDs, provisioning IDs or hostnames.
            for line in output.splitlines():
                key, _, value = line.strip().partition(": ")
                if key in {"Chip", "Memory", "Model Name"}:
                    hardware[key] = value
    docker = shutil.which("docker")
    docker_ready, docker_version = (
        probe([docker, "version", "--format", "{{.Server.Version}}"]) if docker else (False, "")
    )
    llama = shutil.which("llama-server")
    local_llama = root / "artifacts/runtime"
    local_servers = sorted(
        str(path.relative_to(root))
        for pattern in ("*/llama-*/llama-server", "win-*/llama-server.exe")
        for path in local_llama.glob(pattern)
    )
    model_root = root / "artifacts" / "models"
    models = sorted(str(path.relative_to(root)) for path in model_root.glob("*.gguf"))
    return {
        "schema_version": 1,
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "os": platform.system(),
        "hardware": hardware,
        "free_disk_gib": round(shutil.disk_usage(root).free / 2**30, 1),
        "docker_cli": bool(docker),
        "docker_daemon": docker_ready,
        "docker_server_version": docker_version if docker_ready else None,
        "llama_server_on_path": bool(llama),
        "project_local_llama_servers": local_servers,
        "model_files": models,
        "replay_ready": sys.version_info >= (3, 12),
        "live_feasibility": "NOT_VALIDATED",
        "next_steps": [
            *([] if docker_ready else ["Start Docker Desktop, then rerun preflight."]),
            *(
                []
                if llama or local_servers
                else ["Run make models-fetch to install a pinned runtime."]
            ),
            *(
                []
                if models
                else ["Explicitly download and checksum a model into artifacts/models/."]
            ),
            "Run real structured-generation and isolated-tool smoke checks "
            "before claiming feasibility.",
        ],
    }
