import asyncio
import traceback
from dataclasses import FrozenInstanceError

import pytest
from narrative_analysis_agent import (
    KnownIdentity,
    NarrativeAnalysisError,
    SceneAnalysis,
    SceneAnalysisRequest,
)

from apps.narrative_memory.service.scene_analysis_use_case import (
    AnalyzeSceneInput,
    AnalyzeSceneUseCase,
    SceneAnalysisApplicationError,
)


def _identity(identity_key: str, name: str) -> KnownIdentity:
    return KnownIdentity(
        identity_key=identity_key,
        normalized_name=name,
        display_name=name,
    )


class RecordingAgent:
    def __init__(self, result: SceneAnalysis) -> None:
        self.result = result
        self.requests: list[SceneAnalysisRequest] = []

    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis:
        self.requests.append(request)
        return self.result


class FailingAgent:
    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis:
        del request
        try:
            raise RuntimeError("SECRET_PROVIDER_CAUSE")
        except RuntimeError as error:
            raise NarrativeAnalysisError("SECRET_PROVIDER_MESSAGE") from error


def _analysis() -> SceneAnalysis:
    return SceneAnalysis(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=7,
        chunks=(),
    )


def test_use_case_converts_immutable_input_to_the_exact_public_request() -> None:
    agent = RecordingAgent(_analysis())
    input_value = AnalyzeSceneInput(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=7,
        text="서윤이 온실에 도착했다.",
        known_entities=(_identity("entity:seoyun", "서윤"),),
        known_places=(_identity("place:greenhouse", "온실"),),
    )

    result = asyncio.run(AnalyzeSceneUseCase(agent).execute(input_value))

    assert result is agent.result
    assert agent.requests == [
        SceneAnalysisRequest(
            project_id="project-01",
            scene_id="scene-01",
            scene_revision=3,
            scene_sequence=7,
            text="서윤이 온실에 도착했다.",
            known_entities=(_identity("entity:seoyun", "서윤"),),
            known_places=(_identity("place:greenhouse", "온실"),),
        )
    ]
    with pytest.raises(FrozenInstanceError):
        input_value.text = "changed"  # type: ignore[misc]


def test_use_case_returns_the_agent_result_without_translation() -> None:
    agent_result = _analysis()

    result = asyncio.run(
        AnalyzeSceneUseCase(RecordingAgent(agent_result)).execute(
            AnalyzeSceneInput("project-01", "scene-01", 3, 7, "")
        )
    )

    assert result is agent_result


def test_use_case_sanitizes_public_agent_errors() -> None:
    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(
            AnalyzeSceneUseCase(FailingAgent()).execute(
                AnalyzeSceneInput("project-01", "scene-01", 3, 7, "text")
            )
        )

    assert captured.value.args == ("scene analysis failed",)
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True
    formatted = "".join(traceback.format_exception(captured.value))
    assert "SECRET_PROVIDER_MESSAGE" not in formatted
    assert "SECRET_PROVIDER_CAUSE" not in formatted
