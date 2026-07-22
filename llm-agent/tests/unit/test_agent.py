import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_ai.exceptions import AgentRunError

from narrative_analysis_agent import (
    KnowledgeGraphOutput,
    NarrativeAnalysisAgent,
    NarrativeAnalysisError,
    ProjectKnowledgeGraphSnapshot,
    SceneAnalysisRequest,
    packaged_prompt_path,
)
from narrative_analysis_agent.models import Character, Document, Entities, Event, Relation
from narrative_analysis_agent.project_graph_reader import ProjectGraphReadError


@dataclass
class FakeResult:
    output: KnowledgeGraphOutput


def _output(
    *,
    chapter_id: str = "scene-01",
    characters: tuple[Character, ...] = (),
    events: tuple[Event, ...] = (),
    relations: tuple[Relation, ...] = (),
) -> KnowledgeGraphOutput:
    return KnowledgeGraphOutput(
        document=Document(chapter_id=chapter_id, summary="", narrative_time="present"),
        entities=Entities(characters=characters, events=events),
        relations=relations,
    )


class RecordingGraphReader:
    def __init__(self, snapshot: ProjectKnowledgeGraphSnapshot) -> None:
        self.snapshot = snapshot
        self.project_ids: list[str] = []

    def read(self, project_id: str) -> ProjectKnowledgeGraphSnapshot:
        self.project_ids.append(project_id)
        return self.snapshot


class GraphRunner:
    def __init__(
        self,
        outputs: tuple[KnowledgeGraphOutput, ...] | None = None,
        *,
        failure_call: int | None = None,
    ) -> None:
        self.outputs = outputs
        self.failure_call = failure_call
        self.calls: list[tuple[str, str]] = []

    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        self.calls.append((user_prompt, instructions))
        if len(self.calls) == self.failure_call:
            raise AgentRunError("provider detail")
        ordinal = json.loads(user_prompt)["chunk"]["ordinal"]
        if self.outputs is None:
            return FakeResult(
                KnowledgeGraphOutput(
                    document=Document(
                        chapter_id="scene-01",
                        summary=f"chunk {ordinal}",
                        narrative_time="present",
                    ),
                    entities=Entities(),
                )
            )
        return FakeResult(self.outputs[len(self.calls) - 1])


class CancelledRunner:
    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        raise asyncio.CancelledError


class ValidationFailureRunner:
    def __init__(self) -> None:
        try:
            KnowledgeGraphOutput.model_validate({})
        except ValidationError as error:
            self.error = error

    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        raise self.error


class FailingGraphReader:
    def read(self, project_id: str) -> ProjectKnowledgeGraphSnapshot:
        raise ProjectGraphReadError("private reader detail")


def _request(text: str = "가" * 551) -> SceneAnalysisRequest:
    return SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=2,
        text=text,
    )


def _agent(
    runner: GraphRunner | CancelledRunner | ValidationFailureRunner,
    *,
    graph_reader: RecordingGraphReader | FailingGraphReader | None = None,
    prompt_path: Path | None = None,
) -> NarrativeAnalysisAgent:
    return NarrativeAnalysisAgent(
        "test",
        graph_reader=graph_reader
        or RecordingGraphReader(ProjectKnowledgeGraphSnapshot.empty("project-01")),
        prompt_path=prompt_path,
        runner=runner,
    )


def test_analyze_scene_reads_graph_once_and_sends_it_to_every_chunk() -> None:
    snapshot = ProjectKnowledgeGraphSnapshot.empty("project-01")
    reader = RecordingGraphReader(snapshot)
    runner = GraphRunner()
    agent = _agent(runner, graph_reader=reader)

    result = asyncio.run(agent.analyze_scene(_request()))

    assert reader.project_ids == ["project-01"]
    assert len(runner.calls) == 3
    prompts = [json.loads(call[0]) for call in runner.calls]
    assert [prompt["existing_graph"] for prompt in prompts] == [
        snapshot.model_dump(mode="json")
    ] * 3
    assert [prompt["chunk"]["ordinal"] for prompt in prompts] == [0, 1, 2]
    assert all(set(prompt) == {"existing_graph", "chunk"} for prompt in prompts)
    assert result.source_snapshot_version == 0


def test_analyze_scene_preserves_chunk_order_and_structured_outputs() -> None:
    runner = GraphRunner()

    analysis = asyncio.run(_agent(runner).analyze_scene(_request()))

    assert [chunk.ordinal for chunk in analysis.chunks] == [0, 1, 2]
    assert [chunk.extraction.document.summary for chunk in analysis.chunks] == [
        "chunk 0",
        "chunk 1",
        "chunk 2",
    ]


def test_analyze_scene_stops_at_first_agent_failure() -> None:
    runner = GraphRunner(failure_call=2)

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed") as captured:
        asyncio.run(_agent(runner).analyze_scene(_request()))

    assert len(runner.calls) == 2
    assert captured.value.__cause__ is None
    assert "provider detail" not in str(captured.value)


def test_analyze_scene_sanitizes_graph_read_errors_before_provider_call() -> None:
    runner = GraphRunner()

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed") as captured:
        asyncio.run(_agent(runner, graph_reader=FailingGraphReader()).analyze_scene(_request()))

    assert runner.calls == []
    assert captured.value.__cause__ is None
    assert "private reader detail" not in str(captured.value)


def test_analyze_scene_sanitizes_structured_output_validation_errors() -> None:
    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed") as captured:
        asyncio.run(_agent(ValidationFailureRunner()).analyze_scene(_request("본문")))

    assert captured.value.__cause__ is None


def test_analyze_scene_rejects_mismatched_chapter_without_retry() -> None:
    runner = GraphRunner((_output(chapter_id="other-scene"),))

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed"):
        asyncio.run(_agent(runner).analyze_scene(_request("본문")))

    assert len(runner.calls) == 1


def test_analyze_scene_rejects_evidence_absent_from_chunk_without_retry() -> None:
    character = Character(
        id="character_001",
        canonical_name="서윤",
        description="",
        gender="unknown",
        age=None,
        occupation=None,
        affiliation=None,
        status="unknown",
        first_mention="원문에 없음",
        confidence=0.8,
    )
    runner = GraphRunner((_output(characters=(character,)),))

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed"):
        asyncio.run(_agent(runner).analyze_scene(_request("서윤이 들어왔다.")))

    assert len(runner.calls) == 1


def test_analyze_scene_rejects_unknown_event_character_reference_without_retry() -> None:
    event = Event(
        id="event_001",
        event_type="ARRIVAL",
        name="도착",
        summary="서윤이 도착했다.",
        participant_ids=("character_999",),
        location_ids=(),
        time_expression=None,
        narrative_time="present",
        sequence=0,
        evidence="도착했다",
        confidence=0.8,
    )
    runner = GraphRunner((_output(events=(event,)),))

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed"):
        asyncio.run(_agent(runner).analyze_scene(_request("서윤이 도착했다.")))

    assert len(runner.calls) == 1


def test_analyze_scene_rejects_unknown_relation_endpoint_without_retry() -> None:
    relation = Relation(
        id="relation_001",
        source_id="character_999",
        relation_type="KNOWS",
        target_id="character_998",
        state="active",
        directed=True,
        start_event_id=None,
        end_event_id=None,
        time_expression=None,
        scene_sequence=2,
        evidence="알고 있다",
        inference=False,
        confidence=0.8,
    )
    runner = GraphRunner((_output(relations=(relation,)),))

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed"):
        asyncio.run(_agent(runner).analyze_scene(_request("두 사람은 서로 알고 있다.")))

    assert len(runner.calls) == 1


def test_analyze_scene_loads_a_custom_prompt_for_each_request(tmp_path: Path) -> None:
    prompt_path = tmp_path / "system.md"
    prompt_path.write_text("사용자 지시", encoding="utf-8")
    runner = GraphRunner()
    agent = _agent(runner, prompt_path=prompt_path)

    asyncio.run(agent.analyze_scene(_request("본문")))

    assert runner.calls[0][1] == "사용자 지시"


def test_analyze_scene_sanitizes_prompt_read_errors(tmp_path: Path) -> None:
    agent = _agent(GraphRunner(), prompt_path=tmp_path / "missing.md")

    with pytest.raises(NarrativeAnalysisError, match="unable to load scene analysis prompt"):
        asyncio.run(agent.analyze_scene(_request("")))


def test_analyze_scene_preserves_async_cancellation() -> None:
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_agent(CancelledRunner()).analyze_scene(_request("본문")))


def test_packaged_prompt_contains_semantics_without_json_template() -> None:
    content = packaged_prompt_path().read_text(encoding="utf-8")

    assert not content.startswith("---")
    assert "## 분석 목표" in content
    assert "## confidence 기준" in content
    assert "## 출력 형식" not in content
    assert "{{CHAPTER_ID}}" not in content
    assert '"document"' not in content
