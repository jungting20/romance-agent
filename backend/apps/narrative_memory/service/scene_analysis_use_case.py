import asyncio
from dataclasses import dataclass
from typing import Protocol

from narrative_analysis_agent import (
    NarrativeAnalysisError,
    ProjectKnowledgeGraphSnapshot,
    SceneAnalysis,
    SceneAnalysisRequest,
)

from apps.narrative_memory.repository.snapshot_repository import (
    SnapshotCorruptionError,
    SnapshotRepository,
    SnapshotVersionConflict,
)
from apps.narrative_memory.service.merge import (
    MergeInvariantError,
    assemble_scene_graph,
    rebuild_project_graph,
)


@dataclass(frozen=True, slots=True)
class AnalyzeSceneInput:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    text: str


class SceneAnalysisFacade(Protocol):
    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis: ...


class SceneAnalysisApplicationError(RuntimeError):
    pass


class AnalyzeSceneUseCase:
    def __init__(self, agent: SceneAnalysisFacade, repository: SnapshotRepository) -> None:
        self._agent = agent
        self._repository = repository

    async def execute(self, input_value: AnalyzeSceneInput) -> SceneAnalysis:
        try:
            analysis = await self._agent.analyze_scene(
                SceneAnalysisRequest(
                    project_id=input_value.project_id,
                    scene_id=input_value.scene_id,
                    scene_revision=input_value.scene_revision,
                    scene_sequence=input_value.scene_sequence,
                    text=input_value.text,
                )
            )
            current = self._repository.get_current(input_value.project_id)
            current_version = None if current is None else current.snapshot.snapshot_version
            if (0 if current_version is None else current_version) != (
                analysis.source_snapshot_version
            ):
                raise SnapshotVersionConflict("analysis used a stale project graph")
            existing = (
                ProjectKnowledgeGraphSnapshot.empty(input_value.project_id)
                if current is None
                else current.snapshot
            )
            scene = assemble_scene_graph(analysis, existing)
            scenes = tuple(
                item
                for item in self._repository.get_scene_graphs(input_value.project_id)
                if item.scene_id != scene.scene_id
            ) + (scene,)
            next_version = 0 if current_version is None else current_version + 1
            project = rebuild_project_graph(input_value.project_id, next_version, scenes)
            self._repository.commit_scene(current_version, scene, project)
            return analysis
        except asyncio.CancelledError:
            raise
        except (
            NarrativeAnalysisError,
            MergeInvariantError,
            SnapshotCorruptionError,
            SnapshotVersionConflict,
        ):
            raise SceneAnalysisApplicationError("scene analysis failed") from None
