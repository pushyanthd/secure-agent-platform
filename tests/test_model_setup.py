import io
import tarfile

import pytest

from agentguard.model_setup import verify_runtime


def test_installed_runtime_must_match_archive(tmp_path):
    archive = tmp_path / "runtime.tar.gz"
    destination = tmp_path / "installed"
    destination.mkdir()
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("llama-server")
        info.size = 4
        bundle.addfile(info, io.BytesIO(b"real"))
    (destination / "llama-server").write_bytes(b"real")
    verify_runtime(archive, destination)
    (destination / "llama-server").write_bytes(b"fake")
    with pytest.raises(ValueError, match="differs from pinned archive"):
        verify_runtime(archive, destination)


def test_runtime_symlink_cannot_escape_installation(tmp_path):
    archive = tmp_path / "runtime.tar.gz"
    destination = tmp_path / "installed"
    destination.mkdir()
    (tmp_path / "outside").write_bytes(b"real")
    (destination / "llama-server").symlink_to(tmp_path / "outside")
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("llama-server")
        info.size = 4
        bundle.addfile(info, io.BytesIO(b"real"))
    with pytest.raises(ValueError, match="escapes"):
        verify_runtime(archive, destination)


def test_runtime_symlink_cannot_select_different_bundled_library(tmp_path):
    archive = tmp_path / "runtime.tar.gz"
    destination = tmp_path / "installed"
    destination.mkdir()
    with tarfile.open(archive, "w:gz") as bundle:
        for name in ("first", "second"):
            info = tarfile.TarInfo(name)
            info.size = 4
            bundle.addfile(info, io.BytesIO(b"real"))
            (destination / name).write_bytes(b"real")
        link = tarfile.TarInfo("alias")
        link.type = tarfile.SYMTYPE
        link.linkname = "first"
        bundle.addfile(link)
    (destination / "alias").symlink_to("second")
    with pytest.raises(ValueError, match="symlink differs"):
        verify_runtime(archive, destination)


def test_unlisted_runtime_backend_is_rejected(tmp_path):
    archive = tmp_path / "runtime.tar.gz"
    destination = tmp_path / "installed"
    destination.mkdir()
    with tarfile.open(archive, "w:gz"):
        pass
    (destination / "libggml-unlisted.dylib").write_bytes(b"unlisted")
    with pytest.raises(ValueError, match="unexpected files"):
        verify_runtime(archive, destination)
