"""Verify same-PC Windows CUDA inference from a WSL application workspace."""

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from agentguard.contracts import digest
from agentguard.model import LocalModel, ModelConfig, ModelFailure
from agentguard.model_setup import sha256_file


def verify_windows_runtime(artifact_root: Path, runtime: dict[str, Any]) -> None:
    destination = (artifact_root / "artifacts/runtime" / f"win-{runtime['release']}").resolve()
    expected: dict[str, str] = {}
    for asset in runtime["assets"]:
        archive = artifact_root / "artifacts/runtime" / asset["filename"]
        if archive.stat().st_size != asset["size_bytes"] or sha256_file(archive) != asset["sha256"]:
            raise ValueError("Windows runtime archive differs from its pinned checksum")
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                if entry.is_dir():
                    continue
                relative = PurePosixPath(entry.filename.replace("\\", "/"))
                if relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
                    raise ValueError("Windows runtime archive member escapes its installation")
                path = destination.joinpath(*relative.parts)
                if path.is_symlink() or not path.resolve().is_relative_to(destination):
                    raise ValueError("Windows runtime member escapes its installation")
                with bundle.open(entry) as stream:
                    archive_hash = hashlib.sha256()
                    while chunk := stream.read(1024 * 1024):
                        archive_hash.update(chunk)
                    checksum = archive_hash.hexdigest()
                name = relative.as_posix().casefold()
                if name in expected and expected[name] != checksum:
                    raise ValueError("Conflicting Windows runtime archive members")
                expected[name] = checksum
                if not path.is_file() or sha256_file(path) != checksum:
                    raise ValueError("Installed Windows runtime differs from its pinned archive")
    files = [path for path in destination.rglob("*") if path.is_file() or path.is_symlink()]
    actual = {path.relative_to(destination).as_posix().casefold() for path in files}
    if actual != expected.keys() or len(files) != len(expected):
        raise ValueError("Installed Windows runtime has missing or unexpected files")


def prepare_pc_model(
    root: Path, profile: dict[str, Any]
) -> tuple[LocalModel, dict[str, Any], dict[str, Any]]:
    artifact_root = Path(profile["artifact_root"]).resolve()
    pinned = json.loads((root / "config/pc-windows-runtime.json").read_text())
    runtime = profile["runtime"]
    if any(runtime[key] != pinned[key] for key in ("release", "commit", "assets", "platform")):
        raise ValueError("PC runtime profile differs from the committed Windows pins")
    model_path = artifact_root / "artifacts/models" / profile["model"]["filename"]
    if (
        model_path.stat().st_size != profile["model"]["size_bytes"]
        or sha256_file(model_path) != profile["model"]["sha256"]
    ):
        raise ValueError("PC model artifact differs from its pinned checksum")
    verify_windows_runtime(artifact_root, runtime)
    model = LocalModel(ModelConfig.model_validate(profile["inference"]))
    try:
        props = json.loads(model.request("/props", None, timeout=10))
        expected_build = runtime["release"] + "-" + runtime["commit"][:9]
        if (
            props["model_alias"] != model.config.model
            or PureWindowsPath(props["model_path"]) != PureWindowsPath(profile["server_model_path"])
            or props["build_info"] != expected_build
            or props["default_generation_settings"]["n_ctx"] != model.config.context_tokens
            or props["total_slots"] != 1
            or not props["chat_template"]
        ):
            raise ValueError("Running Windows server does not match the selected PC profile")
        server = {
            "build_info": props["build_info"],
            "chat_template": props["chat_template"],
            "chat_template_sha256": digest(props["chat_template"]),
            "generation_defaults": props["default_generation_settings"],
            "non_thinking": True,
            "template_source": "embedded in checksum-verified GGUF",
            "total_slots": props["total_slots"],
            "inference_host": "same_pc_windows_cuda",
            "artifact_verification": "model, ZIP archives, and installed files checked from WSL",
        }
    except ModelFailure as exc:
        server = {"preflight_error": str(exc)}
    return model, profile, server
