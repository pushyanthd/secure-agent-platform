"""Create an Ubuntu working copy and install project-local development tools."""

import argparse
import hashlib
import os
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from sync_wsl import copy_changes

NODE_VERSION = "24.21.0"


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.home() / "secure-agent-platform")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    target = args.target.resolve()
    if target.exists():
        raise SystemExit(f"Refusing to overwrite an existing working copy: {target}")
    run("git", "clone", "--no-hardlinks", str(source), str(target), cwd=source)
    run("git", "config", "core.autocrlf", "false", cwd=target)
    # Carry the current working tree, including uncommitted work, into the new copy.
    copy_changes(source, target)
    bootstrap = target / "artifacts/bootstrap-venv"
    run("python3", "-m", "venv", str(bootstrap), cwd=target)
    run(str(bootstrap / "bin/python"), "-m", "pip", "install", "uv==0.12.18", cwd=target)
    uv = str(bootstrap / "bin/uv")
    os.environ["UV_CACHE_DIR"] = str(target / "artifacts/uv-cache")
    run(uv, "sync", "--locked", cwd=target)
    (target / ".venv/bin/uv").symlink_to(uv)
    runtime = target / "artifacts/runtime"
    runtime.mkdir(exist_ok=True)
    filename = f"node-v{NODE_VERSION}-linux-x64.tar.xz"
    base = f"https://nodejs.org/dist/v{NODE_VERSION}/"
    checksums = urllib.request.urlopen(base + "SHASUMS256.txt", timeout=30).read().decode()
    expected = next(line.split()[0] for line in checksums.splitlines() if line.endswith(filename))
    archive = runtime / filename
    urllib.request.urlretrieve(base + filename, archive)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise SystemExit("Node archive checksum mismatch")
    (runtime / (filename + ".sha256")).write_text(expected + "\n")
    with tarfile.open(archive) as bundle:
        bundle.extractall(runtime, filter="data")
    node_bin = runtime / f"node-v{NODE_VERSION}-linux-x64/bin"
    os.environ["PATH"] = str(node_bin) + os.pathsep + os.environ["PATH"]
    os.environ["NPM_CONFIG_CACHE"] = str(target / "artifacts/npm-cache")
    run("npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund", cwd=target / "frontend")
    print(f"Ubuntu working copy ready: {target}", flush=True)
    print(f"Run make with UV={uv}", flush=True)


if __name__ == "__main__":
    main()
