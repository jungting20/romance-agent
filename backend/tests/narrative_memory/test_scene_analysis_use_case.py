import asyncio
import traceback
from dataclasses import FrozenInstanceError

import pytest
from narrative_analysis_agent import (
    KnownIdentity,
    NarrativeAnalysisError,
    SceneAnalysisRequest,
    SceneAnalysisResult,
)
from narrative_analysis_agent import (
    SceneRelationshipSnapshot as AgentSceneSnapshot,
)

from apps.narrative_memory.service.models import SceneRelationshipSnapshot
from apps.narrative_memory.service.scene_analysis_use_case import (
    AnalyzedScene,
    AnalyzeSceneInput,
    AnalyzeSceneUseCase,
    SceneAnalysisApplicationError,
)


class RecordingAgent:
    def __init__(self, result: SceneAnalysisResult) -> None:
        self.result = result
        self.requests: list[SceneAnalysisRequest] = []

    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysisResult:
        self.requests.append(request)
        return self.result


class FailingAgent:
    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysisResult:
        del request
        try:
            raise RuntimeError("SECRET_PROVIDER_CAUSE")
        except RuntimeError as error:
            raise NarrativeAnalysisError("SECRET_PROVIDER_MESSAGE", run_id="run-failed") from error


def test_use_case_converts_immutable_input_to_the_exact_public_request() -> None:
    agent_result = SceneAnalysisResult(
        run_id="run-01",
        snapshot=AgentSceneSnapshot.empty("scene-01", 3, 7),
    )
    agent = RecordingAgent(agent_result)
    input_value = AnalyzeSceneInput(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=7,
        text="서윤이 온실에 도착했다.",
        known_entities=(KnownIdentity("entity:seoyun", "서윤", "서윤"),),
        known_places=(KnownIdentity("place:greenhouse", "온실", "온실"),),
    )

    asyncio.run(AnalyzeSceneUseCase(agent).execute(input_value))

    assert agent.requests == [
        SceneAnalysisRequest(
            project_id="project-01",
            scene_id="scene-01",
            scene_revision=3,
            scene_sequence=7,
            text="서윤이 온실에 도착했다.",
            known_entities=(KnownIdentity("entity:seoyun", "서윤", "서윤"),),
            known_places=(KnownIdentity("place:greenhouse", "온실", "온실"),),
        )
    ]
    with pytest.raises(FrozenInstanceError):
        input_value.text = "changed"  # type: ignore[misc]


def test_use_case_returns_the_mapped_backend_domain_snapshot() -> None:
    agent_result = SceneAnalysisResult(
        run_id="run-01",
        snapshot=AgentSceneSnapshot.empty("scene-01", 3, 7),
    )

    result = asyncio.run(
        AnalyzeSceneUseCase(RecordingAgent(agent_result)).execute(
            AnalyzeSceneInput("project-01", "scene-01", 3, 7, "")
        )
    )

    assert result == AnalyzedScene(
        run_id="run-01",
        snapshot=SceneRelationshipSnapshot(
            scene_id="scene-01",
            scene_revision=3,
            scene_sequence=7,
            schema_version="scene-relationship-snapshot-v1",
            summary="",
            entities=(),
            places=(),
            relationship_events=(),
            location_events=(),
        ),
    )


def test_use_case_sanitizes_public_agent_errors_and_preserves_run_id() -> None:
    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(
            AnalyzeSceneUseCase(FailingAgent()).execute(
                AnalyzeSceneInput("project-01", "scene-01", 3, 7, "text")
            )
        )

    assert captured.value.args == ("scene analysis failed",)
    assert captured.value.run_id == "run-failed"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    formatted = "".join(traceback.format_exception(captured.value))
    assert "SECRET_PROVIDER_MESSAGE" not in formatted
    assert "SECRET_PROVIDER_CAUSE" not in formatted
