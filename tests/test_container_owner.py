import json

import pytest

from agentguard.computation import ToolFailure
from agentguard.container_owner import PREFIX, owner_is_dead
from agentguard.supervisor import DockerComputer

CURRENT = {
    PREFIX + key: value
    for key, value in {
        "version": "1",
        "host": "local",
        "boot": "current",
        "pid": "20",
        "start": "100",
    }.items()
}


@pytest.mark.parametrize("start,dead", [("100", False), ("101", True), (None, True)])
def test_owner_pid_reuse_and_live_owner(monkeypatch, start, dead):
    monkeypatch.setattr("agentguard.container_owner.process_start", lambda pid: start)
    assert owner_is_dead(CURRENT, CURRENT) is dead


@pytest.mark.parametrize(
    "key,value,dead",
    [
        ("host", "other", False),
        ("version", "2", False),
        ("boot", "previous", True),
        ("pid", "0", False),
        ("start", "", False),
    ],
)
def test_only_valid_local_owners_can_be_reclaimed(key, value, dead):
    assert owner_is_dead(CURRENT | {PREFIX + key: value}, CURRENT) is dead


def test_reconcile_preserves_live_and_unrelated_containers(monkeypatch):
    image = "sha256:" + "a" * 64
    identifiers = [letter * 64 for letter in "bcde"]
    records = [
        {
            "Id": item,
            "Image": image,
            "Name": "/agentguard-" + "a" * 32,
            "Config": {"Labels": CURRENT | {PREFIX + "start": "99"}},
        }
        for item in identifiers
    ]
    records[1]["Config"]["Labels"] = CURRENT
    records[2]["Image"] = "sha256:" + "f" * 64
    records[3]["Config"]["Labels"][PREFIX + "host"] = "other"
    monkeypatch.setattr("agentguard.supervisor.owner_labels", lambda: CURRENT)
    monkeypatch.setattr("agentguard.container_owner.process_start", lambda pid: "100")
    monkeypatch.setattr(
        "agentguard.supervisor.bounded_process",
        lambda command, *a, **k: (
            "\n".join(identifiers).encode()
            if command[1] == "ps"
            else json.dumps([records[identifiers.index(command[2])]]).encode()
        ),
    )
    removed = []
    monkeypatch.setattr(DockerComputer, "_remove", staticmethod(lambda name: removed.append(name)))
    assert DockerComputer(image).reconcile_orphans() == [identifiers[0]]
    assert removed == [identifiers[0]]


def test_reconcile_daemon_loss_aborts_admission(monkeypatch):
    monkeypatch.setattr("agentguard.supervisor.owner_labels", lambda: CURRENT)

    def fail(*args, **kwargs):
        raise ToolFailure("RUNTIME_UNAVAILABLE")

    monkeypatch.setattr("agentguard.supervisor.bounded_process", fail)
    with pytest.raises(ToolFailure):
        DockerComputer("sha256:" + "a" * 64).reconcile_orphans()
