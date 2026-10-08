import sqlite3
from pathlib import Path

import pytest
from test_api import service  # noqa: F401

from agentguard.artifact_volume import ArtifactVolume, ArtifactVolumeUnavailable
from agentguard.bounded_storage import BoundedStore
from agentguard.control_setup import ControlSettings, initialize_control, prepare_control
from agentguard.storage import Store
from agentguard.suite import resume_suite, run_suite


def volume(tmp_path):
    image = tmp_path / "image.ext4"
    with image.open("wb") as stream:
        stream.truncate(32 * 1024 * 1024)
    root = tmp_path / "data"
    root.mkdir()
    return ArtifactVolume(
        image=image,
        mountpoint=root,
        size_bytes=image.stat().st_size,
        filesystem_uuid="01234567-89ab-cdef-0123-456789abcdef",
    )


def test_unmounted_volume_refuses_store_without_creating_database(tmp_path):
    boundary = volume(tmp_path)
    database = boundary.mountpoint / "state.sqlite3"
    with pytest.raises(ArtifactVolumeUnavailable):
        BoundedStore(database, artifact_volume=boundary)
    assert not database.exists()


def test_volume_refuses_target_escape_and_wrong_capacity(tmp_path):
    boundary = volume(tmp_path)
    with pytest.raises(ArtifactVolumeUnavailable) as error:
        boundary.verify(tmp_path / "outside.sqlite3")
    assert "escapes" in str(error.value.__cause__)
    changed = boundary.model_copy(update={"size_bytes": 64 * 1024 * 1024})
    with pytest.raises(ArtifactVolumeUnavailable) as error:
        changed.verify(boundary.mountpoint / "state.sqlite3")
    assert "capacity" in str(error.value.__cause__)


def test_connection_rechecks_mount_after_startup(tmp_path, monkeypatch):
    boundary = volume(tmp_path)
    monkeypatch.setattr(ArtifactVolume, "verify", lambda self, target: None)
    store = BoundedStore(boundary.mountpoint / "state.sqlite3", artifact_volume=boundary)

    def unavailable(self, target):
        raise ArtifactVolumeUnavailable("unmounted")

    monkeypatch.setattr(ArtifactVolume, "verify", unavailable)
    with pytest.raises(ArtifactVolumeUnavailable), store.connection():
        pytest.fail("A missing mount must be rejected before opening SQLite")


def test_no_volume_keeps_legacy_store_compatible(tmp_path):
    store = Store(tmp_path / "legacy.sqlite3")
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5


def test_suite_rejects_unmounted_boundary_before_writing(tmp_path):
    boundary = volume(tmp_path)
    output = boundary.mountpoint / "suites"
    with pytest.raises(ArtifactVolumeUnavailable):
        run_suite(Path("scenarios/dev/suite-v1.json"), output, artifact_volume=boundary)
    assert not output.exists()


def test_suite_pins_boundary_and_resume_rejects_missing_mount(tmp_path, monkeypatch):
    import json

    boundary = volume(tmp_path)
    monkeypatch.setattr(ArtifactVolume, "verify", lambda self, target: None)
    directory = run_suite(
        Path("scenarios/dev/suite-v1.json"),
        boundary.mountpoint / "suites",
        variants=("defended",),
        max_episodes=1,
        artifact_volume=boundary,
    )
    manifest = json.loads((directory / "manifest.json").read_bytes())
    assert manifest["artifact_volume"] == boundary.model_dump(mode="json")

    def unavailable(self, target):
        raise ArtifactVolumeUnavailable("unmounted")

    monkeypatch.setattr(ArtifactVolume, "verify", unavailable)
    with pytest.raises(ArtifactVolumeUnavailable):
        resume_suite(directory)


def test_control_persists_and_prepares_boundary(tmp_path, monkeypatch):
    boundary = volume(tmp_path)
    manifest = tmp_path / "volume.json"
    manifest.write_text(boundary.model_dump_json())
    target = boundary.mountpoint / "control"
    with pytest.raises(ArtifactVolumeUnavailable):
        initialize_control(Path.cwd(), target, fixture=True, artifact_volume_manifest=manifest)
    assert not target.exists()
    monkeypatch.setattr(ArtifactVolume, "verify", lambda self, target: None)
    settings_path = initialize_control(
        Path.cwd(),
        target,
        fixture=True,
        artifact_volume_manifest=manifest,
    )
    settings = ControlSettings.model_validate_json(settings_path.read_bytes())
    control, _ = prepare_control(settings)
    assert settings.artifact_volume_manifest == manifest
    assert isinstance(control.store, BoundedStore)
    assert control.store.artifact_volume == boundary


def test_api_distinguishes_full_storage_from_unavailable_volume(service, monkeypatch):  # noqa: F811
    client, control, *_ = service

    def full(*args, **kwargs):
        exc = sqlite3.OperationalError("private storage path must not be exposed")
        exc.sqlite_errorcode = sqlite3.SQLITE_FULL
        raise exc

    monkeypatch.setattr(control, "runs", full)
    response = client.get("/api/runs")
    assert response.status_code == 507
    assert response.json() == {"error": "ARTIFACT_STORAGE_FULL"}

    def unavailable(*args, **kwargs):
        raise ArtifactVolumeUnavailable("private volume path")

    monkeypatch.setattr(control, "runs", unavailable)
    response = client.get("/api/runs")
    assert response.status_code == 503
    assert response.json() == {"error": "ARTIFACT_VOLUME_UNAVAILABLE"}
