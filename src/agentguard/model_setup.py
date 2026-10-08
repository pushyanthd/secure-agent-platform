"""Explicit, project-local pinned downloads and foreground serving; never called by inference."""

import hashlib
import json
import platform
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agentguard.model import ModelConfig


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_profile(path: Path) -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(path.read_text())
    if profile["schema_version"] != 1:
        raise ValueError("Unsupported model profile")
    ModelConfig.model_validate(profile["inference"])
    return profile


def model_paths(root: Path, profile: dict[str, Any]) -> tuple[Path, Path]:
    return (
        root / "artifacts/models" / profile["model"]["filename"],
        root / "artifacts/runtime" / profile["runtime"]["filename"],
    )


def verify_runtime(archive: Path, destination: Path) -> None:
    """Verify the installed executable and libraries against the pinned archive too."""
    with tarfile.open(archive) as bundle:
        expected_paths = {member.name.rstrip("/") for member in bundle.getmembers()}
        actual_paths = {path.relative_to(destination).as_posix() for path in destination.rglob("*")}
        if actual_paths != expected_paths:
            raise ValueError("Installed runtime contains missing or unexpected files")
        for member in bundle.getmembers():
            path = destination / member.name
            if not path.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Runtime member escapes its installation directory")
            if member.issym():
                if not path.is_symlink() or path.readlink().as_posix() != member.linkname:
                    raise ValueError("Installed runtime symlink differs from pinned archive")
            elif member.islnk():
                if not path.samefile(destination / member.linkname):
                    raise ValueError("Installed runtime hardlink differs from pinned archive")
            elif member.isdir():
                if not path.is_dir() or path.is_symlink():
                    raise ValueError("Installed runtime directory differs from pinned archive")
            elif member.isfile():
                stream = bundle.extractfile(member)
                assert stream is not None
                checksum = hashlib.sha256()
                with stream:
                    while chunk := stream.read(1024 * 1024):
                        checksum.update(chunk)
                expected = checksum.hexdigest()
                if sha256_file(path) != expected:
                    raise ValueError("Installed runtime differs from pinned archive")
            else:
                raise ValueError("Unsupported runtime archive member")


def fetch_models(root: Path, profile_path: Path) -> None:
    profile = load_profile(profile_path)
    if f"{platform.system()}-{platform.machine()}" != profile["platform"]:
        raise ValueError("This pinned runtime profile requires macOS arm64")
    for spec, path in zip(
        (profile["model"], profile["runtime"]), model_paths(root, profile), strict=True
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            partial = path.with_suffix(path.suffix + ".part")
            subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--location",
                    "--proto",
                    "=https",
                    "--proto-redir",
                    "=https",
                    "--max-time",
                    "900",
                    "--max-filesize",
                    str(spec["size_bytes"]),
                    "--output",
                    str(partial),
                    spec["url"],
                ],
                check=True,
            )
            if sha256_file(partial) != spec["sha256"]:
                raise ValueError("Downloaded artifact checksum mismatch")
            partial.replace(path)
        if path.stat().st_size != spec["size_bytes"] or sha256_file(path) != spec["sha256"]:
            raise ValueError("Local artifact checksum mismatch")
        license_path = path.parent / (spec["filename"] + ".LICENSE")
        if not license_path.exists():
            subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--location",
                    "--proto",
                    "=https",
                    "--proto-redir",
                    "=https",
                    "--max-time",
                    "30",
                    "--output",
                    str(license_path),
                    spec["license_url"],
                ],
                check=True,
            )
    _, archive = model_paths(root, profile)
    destination = root / "artifacts/runtime" / profile["runtime"]["release"]
    if not destination.exists():
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            staged = Path(temporary) / "bundle"
            with tarfile.open(archive) as bundle:
                bundle.extractall(staged, filter="data")
            verify_runtime(archive, staged)
            staged.replace(destination)
    verify_runtime(archive, destination)


def serve_command(root: Path, profile_path: Path) -> list[str]:
    profile = load_profile(profile_path)
    model, archive = model_paths(root, profile)
    for spec, path in zip((profile["model"], profile["runtime"]), (model, archive), strict=True):
        if sha256_file(path) != spec["sha256"]:
            raise ValueError("Artifact checksum mismatch; run models-fetch")
    verify_runtime(archive, root / "artifacts/runtime" / profile["runtime"]["release"])
    binaries = list(
        (root / "artifacts/runtime" / profile["runtime"]["release"]).rglob("llama-server")
    )
    if len(binaries) != 1:
        raise ValueError("Expected one extracted llama-server; run models-fetch")
    config = ModelConfig.model_validate(profile["inference"])
    endpoint = urlsplit(config.endpoint)
    return [
        str(binaries[0]),
        "--model",
        str(model),
        "--alias",
        config.model,
        "--host",
        str(endpoint.hostname),
        "--port",
        str(endpoint.port),
        "--ctx-size",
        str(config.context_tokens),
        "--parallel",
        "1",
        "--n-gpu-layers",
        "99",
        "--jinja",
        "--reasoning",
        "off",
        "--offline",
        "--no-webui",
        "--no-agent",
        "--cors-origins",
        "http://127.0.0.1:8101",
        "--no-cors-credentials",
        "--no-context-shift",
        "--cache-ram",
        "0",
        "--verbosity",
        "4",
    ]
