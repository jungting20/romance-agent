from dataclasses import dataclass
from typing import Protocol

from narrative_analysis_agent import ProjectKnowledgeGraphSnapshot

from apps.narrative_memory.service.models import SceneGraphRecord


class SnapshotVersionConflict(RuntimeError):
    pass


class SnapshotCorruptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoredProjectSnapshot:
    snapshot: ProjectKnowledgeGraphSnapshot
    payload: bytes
    content_hash: str


class SnapshotRepository(Protocol):
    def initialize(self) -> None:
        raise NotImplementedError

    def get_current(self, project_id: str) -> StoredProjectSnapshot | None:
        raise NotImplementedError

    def get_scene_graphs(self, project_id: str) -> tuple[SceneGraphRecord, ...]:
        raise NotImplementedError

    def commit_scene(
        self,
        expected_version: int | None,
        scene: SceneGraphRecord,
        snapshot: ProjectKnowledgeGraphSnapshot,
    ) -> StoredProjectSnapshot:
        raise NotImplementedError
