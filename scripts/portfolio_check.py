"""Reproduce checks in a fresh source snapshot and environment, without model inference."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def snapshot(output: Path) -> tuple[Path, dict[str, str]]:
    if output.exists():
        raise ValueError("Preserve previous results; choose a new output directory")
    files = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    target = output / "checkout"
    hashes = {}
    for name in sorted(set(filter(None, files))):
        source, destination = ROOT / name, target / name
        if not source.is_file():
            continue  # Respect deletions in the working tree.
        if (
            source.is_symlink()
            or not source.resolve().is_relative_to(ROOT.resolve())
            or not destination.resolve().is_relative_to(target.resolve())
        ):
            raise ValueError(f"Snapshot requires ordinary repository files: {name}")
        content = source.read_bytes()
        # Frozen publication bytes remain exact; working source uses canonical LF.
        if not name.startswith("docs/evidence/") and b"\0" not in content[:8192]:
            content = content.replace(b"\r\n", b"\n")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    return target, hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if os.name == "nt":
        parser.error("Run this check in Linux, macOS, or the configured Ubuntu/WSL checkout")
    uv = shutil.which("uv") or str(ROOT / ".venv/bin/uv")
    if not Path(uv).is_file():
        parser.error("Install uv or sync the existing checkout first")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (args.output or ROOT / "artifacts" / f"portfolio-check-{stamp}").resolve()
    checkout, hashes = snapshot(output)
    logs = output / "logs"
    logs.mkdir()
    env = os.environ.copy()
    # A repository-local bootstrap uv must also be discoverable by subprocess tests.
    env["PATH"] = str(Path(uv).parent) + os.pathsep + env.get("PATH", "")
    env["UV_CACHE_DIR"] = str(output / "uv-cache")
    env["UV_PROJECT_ENVIRONMENT"] = str(checkout / ".venv")
    env.pop("VIRTUAL_ENV", None)
    commands = [
        ("sync", [uv, "sync", "--locked"]),
        ("contracts", ["make", "check", f"UV={uv}"]),
        ("release-corpus", [uv, "run", "--locked", "agentguard", "release-validate"]),
        ("replay", [uv, "run", "--locked", "agentguard", "demo-replay"]),
        ("durable", [uv, "run", "--locked", "agentguard", "demo-durable"]),
    ]
    for evidence in sorted((checkout / "docs/evidence").glob("*/run/grading-state.json")):
        relative = evidence.parent.relative_to(checkout)
        commands.append(
            (
                "verify-" + evidence.parents[1].name,
                [uv, "run", "--locked", "agentguard", "eval-verify", str(relative)],
            )
        )
    results: list[dict[str, Any]] = []
    for name, command in commands:
        started = time.monotonic()
        with (logs / f"{name}.log").open("wb") as log:
            completed = subprocess.run(
                command,
                cwd=checkout,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        result = {
            "check": name,
            "command": command,
            "exit_code": completed.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "log": f"logs/{name}.log",
        }
        results.append(result)
        record = {
            "version": "portfolio-reproduction-v1",
            "started_utc": stamp,
            "source_files_sha256": hashes,
            "checks": results,
            "all_passed": len(results) == len(commands)
            and all(r["exit_code"] == 0 for r in results),
            "zero_model_calls": True,
            "limits": [
                "Same author and PC; not independent external reproduction.",
                "Fresh environment and source snapshot; network is needed to install dependencies.",
                "Does not rerun inference, Docker containment, or browser scenarios.",
            ],
        }
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        print(
            f"{name}: {'PASS' if completed.returncode == 0 else 'FAIL'} ({result['seconds']}s)",
            flush=True,
        )
        if completed.returncode:
            print(f"Inspect {logs / (name + '.log')}", flush=True)
            sys.exit(completed.returncode)
    print(f"Verified fresh source/environment: {output / 'result.json'}", flush=True)


if __name__ == "__main__":
    main()
