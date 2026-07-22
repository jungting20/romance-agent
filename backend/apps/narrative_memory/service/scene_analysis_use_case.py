from dataclasses import dataclass
from typing import Protocol

from narrative_analysis_agent import (
    KnownIdentity,
    NarrativeAnalysisError,
    SceneAnalysisRequest,
    SceneAnalysisResult,
)

from apps.narrative_memory.service.models import SceneRelationshipSnapshot
from apps.narrative_memory.service.scene_analysis_result import to_domain_scene_snapshot


@dataclass(frozen=True, slots=True)
class AnalyzeSceneInput:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    text: str
    known_entities: tuple[KnownIdentity, ...] = ()
    known_places: tuple[KnownIdentity, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalyzedScene:
    run_id: str
    snapshot: SceneRelationshipSnapshot


class SceneAnalysisFacade(Protocol):
    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysisResult: ...


class SceneAnalysisApplicationError(RuntimeError):
    def __init__(self, *, run_id: str | None) -> None:
        super().__init__("scene analysis failed")
        self.run_id = run_id


class AnalyzeSceneUseCase:
    def __init__(self, agent: SceneAnalysisFacade) -> None:
        self._agent = agent

    async def execute(self, input_value: AnalyzeSceneInput) -> AnalyzedScene:
        request = SceneAnalysisRequest(
            project_id=input_value.project_id,
            scene_id=input_value.scene_id,
            scene_revision=input_value.scene_revision,
            scene_sequence=input_value.scene_sequence,
            text=input_value.text,
            known_entities=input_value.known_entities,
            known_places=input_value.known_places,
        )
        try:
            result = await self._agent.analyze_scene(request)
        except NarrativeAnalysisError as error:
            raise SceneAnalysisApplicationError(run_id=error.run_id) from None
        return AnalyzedScene(
            run_id=result.run_id,
            snapshot=to_domain_scene_snapshot(result.snapshot),
        )
