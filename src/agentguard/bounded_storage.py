"""Runtime capacity boundary wrapping the unchanged historical SQLite kernel/reader."""

import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from agentguard.artifact_volume import ArtifactVolume
from agentguard.computation import Computer
from agentguard.storage import Store


class BoundedStore(Store):
    def __init__(
        self,
        path: Path,
        clock: Callable[[], float] = time.time,
        *,
        artifact_volume: ArtifactVolume,
        computer: Computer | None = None,
    ):
        self.artifact_volume = artifact_volume
        artifact_volume.verify(path)
        super().__init__(path, clock, computer=computer)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.artifact_volume.verify(self.path)
        with super().connection() as db:
            yield db
