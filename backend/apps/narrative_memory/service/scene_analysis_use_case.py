from dataclasses import dataclass
from typing import Protocol

from narrative_analysis_agent import (
    KnownIdentity,
    NarrativeAnalysisError,
    SceneAnalysis,
    SceneAnalysisRequest,
)


@dataclass(frozen=True, slots=True)
class AnalyzeSceneInput:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    text: str
    known_entities: tuple[KnownIdentity, ...] = ()
    known_places: tuple[KnownIdentity, ...] = ()


class SceneAnalysisFacade(Protocol):
    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis: ...


class SceneAnalysisApplicationError(RuntimeError):
    pass


class AnalyzeSceneUseCase:
    def __init__(self, agent: SceneAnalysisFacade) -> None:
        self._agent = agent

    async def execute(self, input_value: AnalyzeSceneInput) -> SceneAnalysis:
        try:
            return await self._agent.analyze_scene(
                SceneAnalysisRequest(
                    project_id=input_value.project_id,
                    scene_id=input_value.scene_id,
                    scene_revision=input_value.scene_revision,
                    scene_sequence=input_value.scene_sequence,
                    text=input_value.text,
                    known_entities=input_value.known_entities,
                    known_places=input_value.known_places,
                )
            )
        except NarrativeAnalysisError:
            raise SceneAnalysisApplicationError("scene analysis failed") from None
