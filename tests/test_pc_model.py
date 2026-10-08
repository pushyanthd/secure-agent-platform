import json
import zipfile

import pytest

from agentguard import live, pc_model
from agentguard.model import ModelConfig, ModelFailure
from agentguard.model_setup import sha256_file


@pytest.fixture
def pc_profile(tmp_path, monkeypatch):
    runtime_directory = tmp_path / "artifacts/runtime"
    installed = runtime_directory / "win-test"
    installed.mkdir(parents=True)
    archive = runtime_directory / "test.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, content in {
            "llama-server.exe": b"test executable",
            "cuda.dll": b"test DLL",
        }.items():
            bundle.writestr(name, content)
            (installed / name).write_bytes(content)
    runtime = {
        "platform": "Windows-x64",
        "release": "test",
        "commit": "123456789abcdef",
        "assets": [
            {
                "filename": archive.name,
                "size_bytes": archive.stat().st_size,
                "sha256": sha256_file(archive),
            }
        ],
    }
    config = tmp_path / "config"
    config.mkdir()
    (config / "pc-windows-runtime.json").write_text(json.dumps(runtime))
    model_file = tmp_path / "artifacts/models/test.gguf"
    model_file.parent.mkdir()
    model_file.write_bytes(b"test double, not model weights")
    profile = {
        "schema_version": 1,
        "artifact_root": str(tmp_path),
        "server_model_path": "C:\\project\\artifacts\\models\\test.gguf",
        "runtime": runtime | {"format": "windows-cuda-zip"},
        "model": {
            "filename": model_file.name,
            "size_bytes": model_file.stat().st_size,
            "sha256": sha256_file(model_file),
        },
        "inference": ModelConfig().model_dump(),
    }
    props = {
        "model_alias": profile["inference"]["model"],
        "model_path": profile["server_model_path"],
        "build_info": "test-123456789",
        "default_generation_settings": {"n_ctx": 8192},
        "total_slots": 1,
        "chat_template": "test template",
    }

    class TestModel:
        def __init__(self, config):
            self.config = config

        def request(self, *args, **kwargs):
            return json.dumps(props)

    monkeypatch.setattr(pc_model, "LocalModel", TestModel)
    return tmp_path, profile, props


def test_wsl_preflight_verifies_same_pc_server_and_records_scope(pc_profile):
    root, profile, _ = pc_profile
    path = root / "profile.json"
    path.write_text(json.dumps(profile))
    _, recorded, server = live.prepare_local_model(root, path)
    assert recorded == profile
    assert server["inference_host"] == "same_pc_windows_cuda"
    assert "preflight_error" not in server


@pytest.mark.parametrize("change", ["archive", "installed", "extra", "model", "pins"])
def test_pc_preflight_rejects_changed_local_artifacts(pc_profile, change):
    root, profile, _ = pc_profile
    directory = root / "artifacts/runtime"
    if change == "archive":
        (directory / "test.zip").write_bytes(b"modified archive")
    elif change == "installed":
        (directory / "win-test/cuda.dll").write_bytes(b"modified DLL")
    elif change == "extra":
        (directory / "win-test/unlisted.dll").write_bytes(b"unlisted DLL")
    elif change == "model":
        (root / "artifacts/models/test.gguf").write_bytes(b"modified model")
    else:
        profile["runtime"]["commit"] = "other"
    with pytest.raises(ValueError):
        pc_model.prepare_pc_model(root, profile)


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_alias", "wrong"),
        ("model_path", "C:\\other\\test.gguf"),
        ("build_info", "wrong"),
        ("total_slots", 2),
        ("chat_template", ""),
        ("default_generation_settings", {"n_ctx": 4096}),
    ],
)
def test_pc_preflight_rejects_mismatched_running_server(pc_profile, field, value):
    root, profile, props = pc_profile
    props[field] = value
    with pytest.raises(ValueError, match="does not match"):
        pc_model.prepare_pc_model(root, profile)


def test_pc_model_outage_remains_explicit_and_does_not_fallback(pc_profile, monkeypatch):
    root, profile, _ = pc_profile

    def unavailable(*args, **kwargs):
        raise ModelFailure("MODEL_TRANSPORT_FAILED")

    monkeypatch.setattr(pc_model.LocalModel, "request", unavailable)
    _, _, server = pc_model.prepare_pc_model(root, profile)
    assert server == {"preflight_error": "MODEL_TRANSPORT_FAILED"}


def test_pc_archive_cannot_escape_installation(pc_profile):
    root, profile, _ = pc_profile
    archive = root / "artifacts/runtime/test.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.dll", b"escape")
    profile["runtime"]["assets"][0].update(
        {"size_bytes": archive.stat().st_size, "sha256": sha256_file(archive)}
    )
    with pytest.raises(ValueError, match="escapes"):
        pc_model.verify_windows_runtime(root, profile["runtime"])
