"""Install and serve the pinned 9B model with the Windows CUDA llama.cpp build."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
MODEL_PROFILE = ROOT / "config/model-mac-medium.json"
RUNTIME_PROFILE = ROOT / "config/pc-windows-runtime.json"
RUNTIME_DIR = ROOT / "artifacts/runtime/win-b11149"


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_file(path: Path, spec: dict[str, Any]) -> None:
    if not path.is_file() or path.stat().st_size != spec["size_bytes"]:
        raise RuntimeError(f"Missing or wrong-sized asset: {path}")
    if checksum(path) != spec["sha256"]:
        raise RuntimeError(f"SHA-256 mismatch: {path}")


def download(spec: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        checked_file(path, spec)
        print(f"Verified {path.name}", flush=True)
        return
    partial = path.with_name(path.name + ".part")
    print(f"Downloading {path.name} ({spec['size_bytes']:,} bytes)", flush=True)
    subprocess.run(
        [
            "curl.exe",
            "--fail",
            "--location",
            "--retry",
            "3",
            "--retry-all-errors",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--connect-timeout",
            "20",
            "--continue-at",
            "-",
            "--output",
            str(partial),
            spec["url"],
        ],
        check=True,
    )
    checked_file(partial, spec)
    partial.replace(path)
    print(f"Verified {path.name}", flush=True)


def archive_paths(runtime: dict[str, Any]) -> list[Path]:
    return [ROOT / "artifacts/runtime" / asset["filename"] for asset in runtime["assets"]]


def extracted_files(runtime: dict[str, Any], destination: Path) -> dict[str, tuple[int, int]]:
    expected: dict[str, tuple[int, int]] = {}
    for archive in archive_paths(runtime):
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                if info.is_dir():
                    continue
                relative = Path(info.filename.replace("\\", "/"))
                if relative.is_absolute() or ".." in relative.parts:
                    raise RuntimeError(f"Unsafe ZIP member: {info.filename}")
                target = (destination / relative).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise RuntimeError(f"Unsafe ZIP member: {info.filename}")
                key = relative.as_posix().lower()
                identity = (info.file_size, info.CRC)
                if key in expected and expected[key] != identity:
                    raise RuntimeError(f"Conflicting ZIP member: {info.filename}")
                expected[key] = identity
    return expected


def install_runtime(runtime: dict[str, Any]) -> None:
    expected = extracted_files(runtime, RUNTIME_DIR)
    if not RUNTIME_DIR.exists():
        RUNTIME_DIR.parent.mkdir(parents=True, exist_ok=True)
        staged = RUNTIME_DIR.with_name(RUNTIME_DIR.name + ".installing")
        staged.mkdir(exist_ok=False)
        for archive in archive_paths(runtime):
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(staged)
        staged.replace(RUNTIME_DIR)
    actual = {
        path.relative_to(RUNTIME_DIR).as_posix().lower(): path
        for path in RUNTIME_DIR.rglob("*")
        if path.is_file()
    }
    if actual.keys() != expected.keys():
        raise RuntimeError("Installed runtime files differ from the pinned ZIP manifests")
    for name, path in actual.items():
        with path.open("rb") as stream:
            crc = 0
            while chunk := stream.read(1024 * 1024):
                crc = zlib.crc32(chunk, crc)
        if (path.stat().st_size, crc) != expected[name]:
            raise RuntimeError(f"Installed runtime file differs from pinned ZIP: {path}")


def profiles() -> tuple[dict[str, Any], dict[str, Any]]:
    if sys.platform != "win32":
        raise RuntimeError("This launcher requires Windows")
    model = json.loads(MODEL_PROFILE.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME_PROFILE.read_text(encoding="utf-8"))
    if model["model"]["filename"] != "Qwen3.5-9B-Q4_K_M.gguf":
        raise RuntimeError("Unexpected model profile")
    if runtime["release"] != model["runtime"]["release"]:
        raise RuntimeError("Model and Windows runtime release differ")
    return model, runtime


def prepare(model: dict[str, Any], runtime: dict[str, Any], *, fetch: bool) -> Path:
    model_path = ROOT / "artifacts/models" / model["model"]["filename"]
    specs = [(model["model"], model_path)] + list(
        zip(runtime["assets"], archive_paths(runtime), strict=True)
    )
    for spec, path in specs:
        if fetch:
            download(spec, path)
        else:
            checked_file(path, spec)
    install_runtime(runtime)
    servers = list(RUNTIME_DIR.rglob("llama-server.exe"))
    if len(servers) != 1:
        raise RuntimeError("Expected exactly one llama-server.exe in the pinned runtime")
    return servers[0]


def serve(model: dict[str, Any], server: Path) -> None:
    from agentguard.model import inference_environment

    inference = model["inference"]
    endpoint = urlsplit(inference["endpoint"])
    model_path = ROOT / "artifacts/models" / model["model"]["filename"]
    dll_dirs = {str(path.parent) for path in RUNTIME_DIR.rglob("*.dll")}
    environment = inference_environment()
    environment["PATH"] = os.pathsep.join(
        [str(server.parent), *sorted(dll_dirs), os.environ["PATH"]]
    )
    print(f"Serving {model_path.name} on {inference['endpoint']} using {server}", flush=True)
    arguments = [
        str(server),
        "--model",
        str(model_path),
        "--alias",
        inference["model"],
        "--host",
        str(endpoint.hostname),
        "--port",
        str(endpoint.port),
        "--ctx-size",
        str(inference["context_tokens"]),
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
        inference["endpoint"],
        "--no-cors-credentials",
        "--no-context-shift",
        "--cache-ram",
        "0",
        "--verbosity",
        "4",
    ]
    raise SystemExit(subprocess.call(arguments, env=environment))


def probe(model: dict[str, Any]) -> None:
    from agentguard.model import LocalModel, ModelConfig, parse_reply

    config = ModelConfig.model_validate(model["inference"])
    local = LocalModel(config)
    props = json.loads(local.request("/props", None, timeout=10))
    expected_build = model["runtime"]["release"] + "-" + model["runtime"]["commit"][:9]
    if (
        props.get("model_alias") != config.model
        or Path(props.get("model_path", "")).resolve()
        != (ROOT / "artifacts/models" / model["model"]["filename"]).resolve()
        or props.get("build_info") != expected_build
        or props.get("default_generation_settings", {}).get("n_ctx") != config.context_tokens
        or props.get("total_slots") != 1
        or not props.get("chat_template")
    ):
        raise RuntimeError("Running server does not match the pinned project profile")
    messages = [{"role": "user", "content": "Return true in the ok field."}]
    count = local.count_tokens(messages, timeout=20)
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    reply = parse_reply(local.complete(messages, schema, max_tokens=32, timeout=60))
    content = json.loads(reply.content)
    if content != {"ok": True}:
        raise RuntimeError(f"Unexpected structured generation: {content}")
    print(
        f"PASS: {config.model}, {expected_build}, {count} prompt tokens, "
        f"{reply.completion_tokens} generated tokens"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "serve", "verify", "probe"))
    args = parser.parse_args()
    model, runtime = profiles()
    if args.command == "probe":
        probe(model)
        return
    server = prepare(model, runtime, fetch=args.command == "setup")
    print(f"Pinned model and CUDA runtime verified. Server: {server}", flush=True)
    if args.command == "serve":
        serve(model, server)


if __name__ == "__main__":
    main()
