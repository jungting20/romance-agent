from dataclasses import dataclass
from typing import Protocol

from apps.narrative_memory.service.models import ProjectRelationshipSnapshot


class SnapshotVersionConflict(RuntimeError):
    pass


class SnapshotCorruptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoredProjectSnapshot:
    snapshot: ProjectRelationshipSnapshot
    payload: bytes
    content_hash: str


class SnapshotRepository(Protocol):
    def initialize(self) -> None:
        raise NotImplementedError

    def get_current(self, project_id: str) -> StoredProjectSnapshot | None:
        raise NotImplementedError

    def get_version(self, project_id: str, version: int) -> StoredProjectSnapshot | None:
        raise NotImplementedError

    def commit(
        self,
        expected_version: int | None,
        snapshot: ProjectRelationshipSnapshot,
    ) -> StoredProjectSnapshot:
        raise NotImplementedError
