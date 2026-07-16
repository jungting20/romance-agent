import asyncio
import math
import traceback

import pytest
from pydantic import ValidationError
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from apps.narrative_memory.service.models import LocationEventType
from apps.narrative_memory.service.scene_analysis_ports import (
    ProviderCallError,
    SceneAnalysisCall,
)
from apps.narrative_memory.service.scene_analysis_types import (
    AgentUsage,
    ExtractedEntity,
    ExtractedLocationEvent,
    ExtractedPlace,
    ExtractedRelationshipEvent,
    RelativeEvidence,
    SceneChunkExtraction,
)
from infrastructure.llm.pydantic_ai_scene_analysis import PydanticAISceneAnalysisAgent
from infrastructure.llm.scene_analysis_schemas import ChunkExtractionOutput
from infrastructure.llm.scripted_scene_analysis import ScriptedSceneAnalysisAgent


def _output_payload() -> dict[str, object]:
    evidence = {"start_offset": 0, "end_offset": 4, "text": "Alex"}
    return {
        "summary": "Alex arrived at home.",
        "entities": [
            {
                "local_ref": "entity:alex",
                "normalized_name": "alex",
                "display_name": "Alex",
                "aliases": ["A"],
                "evidence": [evidence],
            }
        ],
        "places": [
            {
                "local_ref": "place:home",
                "normalized_name": "home",
                "display_name": "Home",
                "aliases": [],
                "evidence": [{"start_offset": 16, "end_offset": 20, "text": "home"}],
            }
        ],
        "relationship_events": [
            {
                "subject_ref": "entity:alex",
                "object_ref": "known:blair",
                "category": "romance",
                "description": "Alex misses Blair.",
                "confidence": 0.75,
                "evidence": [evidence],
            }
        ],
        "location_events": [
            {
                "character_ref": "entity:alex",
                "place_ref": "place:home",
                "event_type": "arrived",
                "description": "Alex arrived home.",
                "confidence": 1.0,
                "evidence": [evidence],
            }
        ],
    }


def _domain_extraction(summary: str = "first") -> SceneChunkExtraction:
    return SceneChunkExtraction(summary=summary)


def _call() -> SceneAnalysisCall:
    return SceneAnalysisCall(
        chunk_id="scene-01:r1:0000",
        system_prompt="Extract scene facts.",
        user_prompt='{"chunk":"Alex arrived at home."}',
    )


def test_strict_output_converts_to_provider_independent_domain_types() -> None:
    output = ChunkExtractionOutput.model_validate(_output_payload())

    assert output.to_domain() == SceneChunkExtraction(
        summary="Alex arrived at home.",
        entities=(
            ExtractedEntity(
                local_ref="entity:alex",
                normalized_name="alex",
                display_name="Alex",
                aliases=("A",),
                evidence=(RelativeEvidence(0, 4, "Alex"),),
            ),
        ),
        places=(
            ExtractedPlace(
                local_ref="place:home",
                normalized_name="home",
                display_name="Home",
                aliases=(),
                evidence=(RelativeEvidence(16, 20, "home"),),
            ),
        ),
        relationship_events=(
            ExtractedRelationshipEvent(
                subject_ref="entity:alex",
                object_ref="known:blair",
                category="romance",
                description="Alex misses Blair.",
                confidence=0.75,
                evidence=(RelativeEvidence(0, 4, "Alex"),),
            ),
        ),
        location_events=(
            ExtractedLocationEvent(
                character_ref="entity:alex",
                place_ref="place:home",
                event_type=LocationEventType.ARRIVED,
                description="Alex arrived home.",
                confidence=1.0,
                evidence=(RelativeEvidence(0, 4, "Alex"),),
            ),
        ),
    )
    with pytest.raises(ValidationError, match="frozen"):
        output.summary = "changed"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("unexpected",), True),
        (("relationship_events", 0, "category"), "acquaintance"),
        (("location_events", 0, "event_type"), "visited"),
        (("relationship_events", 0, "confidence"), math.nan),
        (("relationship_events", 0, "confidence"), -0.01),
        (("relationship_events", 0, "confidence"), 1.01),
        (("entities", 0, "evidence", 0, "start_offset"), -1),
        (("entities", 0, "evidence", 0, "end_offset"), 0),
    ],
)
def test_strict_output_rejects_invalid_provider_values(
    path: tuple[str | int, ...], value: object
) -> None:
    payload = _output_payload()
    target: object = payload
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(ValidationError):
        ChunkExtractionOutput.model_validate(payload)


def test_strict_evidence_rejects_end_before_start() -> None:
    payload = _output_payload()
    payload["entities"][0]["evidence"][0] = {  # type: ignore[index]
        "start_offset": 5,
        "end_offset": 4,
        "text": "x",
    }

    with pytest.raises(ValidationError, match="end_offset"):
        ChunkExtractionOutput.model_validate(payload)


def test_scripted_agent_consumes_per_chunk_sequences_and_copies_input() -> None:
    first = _domain_extraction("first")
    second = _domain_extraction("second")
    source_script = [first, ProviderCallError("retry"), second]
    agent = ScriptedSceneAnalysisAgent(scripts={_call().chunk_id: source_script})
    source_script.clear()

    first_result = asyncio.run(agent.analyze(_call()))

    assert first_result.extraction == first
    assert first_result.response_messages_json == b"[]"
    assert first_result.usage == AgentUsage()
    assert len(agent.calls) == 1
    with pytest.raises(ProviderCallError, match="retry"):
        asyncio.run(agent.analyze(_call()))
    assert asyncio.run(agent.analyze(_call())).extraction == second


def test_scripted_agent_defaults_to_empty_extraction() -> None:
    result = asyncio.run(ScriptedSceneAnalysisAgent().analyze(_call()))

    assert result.extraction == SceneChunkExtraction(summary="")
    assert result.response_messages_json == b"[]"
    assert result.usage == AgentUsage()


def test_pydantic_ai_adapter_returns_validated_output_messages_usage_and_identity() -> None:
    model = TestModel(custom_output_args=_output_payload(), model_name="scene-test-model")
    adapter = PydanticAISceneAnalysisAgent(model)

    result = asyncio.run(adapter.analyze(_call()))

    assert result.extraction == ChunkExtractionOutput.model_validate(_output_payload()).to_domain()
    assert isinstance(result.response_messages_json, bytes)
    assert result.response_messages_json != b"[]"
    assert result.usage.requests == 1
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.provider_name == "test"
    assert result.model_name == "scene-test-model"


class _FailingAgent:
    async def run(self, *args: object, **kwargs: object) -> object:
        raise UnexpectedModelBehavior("structured output retries exhausted", body="secret body")


def test_pydantic_ai_adapter_translates_agent_run_errors_without_provider_body() -> None:
    adapter = PydanticAISceneAnalysisAgent(
        TestModel(model_name="scene-test-model"), agent=_FailingAgent()
    )

    with pytest.raises(ProviderCallError) as captured:
        asyncio.run(adapter.analyze(_call()))

    assert "secret body" not in str(captured.value)
    assert "structured output retries exhausted" not in str(captured.value)
    assert "secret body" not in "".join(
        traceback.format_exception(
            captured.type,
            captured.value,
            captured.tb,
        )
    )
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True
    assert captured.value.args == ("scene analysis provider call failed",)
