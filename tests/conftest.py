from pathlib import Path

import pytest

from agentguard.contracts import Document, Project, TaskContract
from agentguard.storage import Store


@pytest.fixture
def clock():
    return [1000.0]


@pytest.fixture
def store(tmp_path: Path, clock):
    return Store(tmp_path / "test.sqlite3", clock=lambda: clock[0])


@pytest.fixture
def contract():
    return TaskContract(
        task_id="launch",
        actor="alex",
        workspace="lab",
        document_ids=("doc", "secret"),
        project_ids=("atlas", "shared"),
    )


@pytest.fixture
def documents():
    return (
        Document(id="doc", workspace="lab", readers=("alex",), body="Validate rollback."),
        Document(
            id="secret",
            workspace="lab",
            readers=("alex",),
            body="SYNTHETIC_SECRET",
            classification="confidential",
        ),
        Document(id="private", workspace="lab", readers=("morgan",), body="PROTECTED"),
    )


@pytest.fixture
def projects():
    return (
        Project(id="atlas", workspace="lab", writers=("alex",)),
        Project(id="shared", workspace="lab", writers=("alex",), visibility="shared"),
        Project(id="orion", workspace="lab", writers=("morgan",)),
    )


@pytest.fixture
def episode(store, contract, documents, projects):
    return store.create_episode(contract, documents, projects)
