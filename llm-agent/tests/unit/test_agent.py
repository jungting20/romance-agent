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
from narrative_analysis_agent.models import (
    Character,
    CharacterMemory,
    Contradiction,
    Coreference,
    Document,
    Entities,
    Event,
    Location,
    MemoryTarget,
    Movement,
    Relation,
    UnresolvedReference,
)
from narrative_analysis_agent.project_graph_reader import ProjectGraphReadError


@dataclass
class FakeResult:
    output: KnowledgeGraphOutput


def _output(
    *,
    chapter_id: str = "scene-01",
    characters: tuple[Character, ...] = (),
    locations: tuple[Location, ...] = (),
    events: tuple[Event, ...] = (),
    relations: tuple[Relation, ...] = (),
    movements: tuple[Movement, ...] = (),
    coreferences: tuple[Coreference, ...] = (),
    unresolved_references: tuple[UnresolvedReference, ...] = (),
    contradictions: tuple[Contradiction, ...] = (),
    character_memories: tuple[CharacterMemory, ...] = (),
) -> KnowledgeGraphOutput:
    return KnowledgeGraphOutput(
        document=Document(chapter_id=chapter_id, summary="", narrative_time="present"),
        entities=Entities(characters=characters, locations=locations, events=events),
        relations=relations,
        movements=movements,
        coreferences=coreferences,
        unresolved_references=unresolved_references,
        contradictions=contradictions,
        character_memories=character_memories,
    )


def _character(identifier: str = "character_001") -> Character:
    return Character(
        id=identifier,
        canonical_name="서윤",
        description="",
        gender="unknown",
        age=None,
        occupation=None,
        affiliation=None,
        status="unknown",
        first_mention="근거",
        confidence=0.8,
    )


def _location(identifier: str = "location_001", *, parent_id: str | None = None) -> Location:
    return Location(
        id=identifier,
        canonical_name="온실",
        location_type="building",
        parent_location_id=parent_id,
        description="",
        first_mention="근거",
        confidence=0.8,
    )


def _event(identifier: str = "event_001") -> Event:
    return Event(
        id=identifier,
        event_type="ARRIVAL",
        name="도착",
        summary="",
        participant_ids=(),
        location_ids=(),
        time_expression=None,
        narrative_time="present",
        sequence=0,
        evidence="근거",
        confidence=0.8,
    )


def _relation(
    identifier: str = "relation_001",
    *,
    source_id: str = "character_001",
    target_id: str = "character_001",
    start_event_id: str | None = None,
    end_event_id: str | None = None,
) -> Relation:
    return Relation(
        id=identifier,
        source_id=source_id,
        relation_type="KNOWS",
        target_id=target_id,
        state="active",
        directed=True,
        start_event_id=start_event_id,
        end_event_id=end_event_id,
        time_expression=None,
        scene_sequence=2,
        evidence="근거",
        inference=False,
        confidence=0.8,
    )


def _memory(
    identifier: str = "memory_001",
    *,
    character_id: str = "character_001",
    target: MemoryTarget | None = None,
    scene_sequence: int = 2,
    evidence: str = "기억한다",
) -> CharacterMemory:
    return CharacterMemory(
        id=identifier,
        character_id=character_id,
        target=target
        or MemoryTarget(
            kind="relation",
            reference_id="relation_001",
            description="두 사람의 약속",
        ),
        content="서윤은 약속을 기억한다.",
        state="remembered",
        time_expression=None,
        scene_sequence=scene_sequence,
        evidence=evidence,
        confidence=0.9,
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
    snapshot = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=5,
        schema_version="project-knowledge-graph-snapshot-v2",
        entities=Entities(characters=(_character("character_010"),)),
        character_memories=(
            _memory(
                character_id="character_010",
                target=MemoryTarget(
                    kind="character", reference_id="character_010", description="기존 서윤"
                ),
            ),
        ),
    )
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
    assert [prompt["scene"] for prompt in prompts] == [
        {"scene_id": "scene-01", "scene_sequence": 2}
    ] * 3
    assert [prompt["chunk"]["ordinal"] for prompt in prompts] == [0, 1, 2]
    assert all(set(prompt) == {"scene", "existing_graph", "chunk"} for prompt in prompts)
    assert result.source_snapshot_version == 5


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


def test_analyze_scene_rejects_model_copy_with_empty_evidence_without_retry() -> None:
    invalid_character = _character().model_copy(update={"first_mention": ""})
    runner = GraphRunner((_output(characters=(invalid_character,)),))

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


@pytest.mark.parametrize(
    "output",
    [
        pytest.param(
            _output(
                characters=(_character(),),
                locations=(_location(parent_id="character_001"),),
            ),
            id="location-parent-wrong-type",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                relations=(_relation(start_event_id="event_999"),),
            ),
            id="relation-start-event-dangling",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                events=(_event(),),
                relations=(_relation(end_event_id="character_001"),),
            ),
            id="relation-end-event-wrong-type",
        ),
        pytest.param(
            _output(
                locations=(_location(),),
                movements=(
                    Movement(
                        character_id="location_001",
                        from_location_id=None,
                        to_location_id=None,
                        movement_type="ARRIVAL",
                        event_id=None,
                        time_expression=None,
                        sequence=0,
                        evidence="근거",
                        confidence=0.8,
                    ),
                ),
            ),
            id="movement-character-wrong-type",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                movements=(
                    Movement(
                        character_id="character_001",
                        from_location_id="location_999",
                        to_location_id=None,
                        movement_type="ARRIVAL",
                        event_id=None,
                        time_expression=None,
                        sequence=0,
                        evidence="근거",
                        confidence=0.8,
                    ),
                ),
            ),
            id="movement-from-location-dangling",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                events=(_event(),),
                movements=(
                    Movement(
                        character_id="character_001",
                        from_location_id=None,
                        to_location_id="event_001",
                        movement_type="ARRIVAL",
                        event_id=None,
                        time_expression=None,
                        sequence=0,
                        evidence="근거",
                        confidence=0.8,
                    ),
                ),
            ),
            id="movement-to-location-wrong-type",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                locations=(_location(),),
                movements=(
                    Movement(
                        character_id="character_001",
                        from_location_id=None,
                        to_location_id=None,
                        movement_type="ARRIVAL",
                        event_id="location_001",
                        time_expression=None,
                        sequence=0,
                        evidence="근거",
                        confidence=0.8,
                    ),
                ),
            ),
            id="movement-event-wrong-type",
        ),
        pytest.param(
            _output(
                relations=(_relation(source_id="event_001", target_id="event_001"),),
                events=(_event(),),
                coreferences=(
                    Coreference(
                        expression="그",
                        resolved_entity_id="relation_001",
                        evidence="근거",
                        confidence=0.8,
                    ),
                ),
            ),
            id="coreference-wrong-type",
        ),
        pytest.param(
            _output(
                unresolved_references=(
                    UnresolvedReference(
                        expression="그",
                        possible_entity_ids=("character_999",),
                        reason="모호함",
                    ),
                ),
            ),
            id="unresolved-reference-dangling",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                relations=(_relation(),),
                contradictions=(
                    Contradiction(
                        subject_id="relation_001",
                        field_or_relation="status",
                        existing_value="alive",
                        new_value="dead",
                        evidence="근거",
                        possible_explanation="",
                    ),
                ),
            ),
            id="contradiction-wrong-type",
        ),
    ],
)
def test_analyze_scene_rejects_invalid_typed_references_without_retry(
    output: KnowledgeGraphOutput,
) -> None:
    runner = GraphRunner((output,))

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed") as captured:
        asyncio.run(_agent(runner).analyze_scene(_request("근거")))

    assert len(runner.calls) == 1
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    "output",
    [
        pytest.param(_output(characters=(_character(), _character())), id="character"),
        pytest.param(_output(locations=(_location(), _location())), id="location"),
        pytest.param(_output(events=(_event(), _event())), id="event"),
        pytest.param(
            _output(characters=(_character(),), relations=(_relation(), _relation())),
            id="relation",
        ),
    ],
)
def test_analyze_scene_rejects_duplicate_local_ids_without_retry(
    output: KnowledgeGraphOutput,
) -> None:
    runner = GraphRunner((output,))

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed") as captured:
        asyncio.run(_agent(runner).analyze_scene(_request("근거")))

    assert len(runner.calls) == 1
    assert captured.value.__cause__ is None


def test_analyze_scene_allows_typed_references_to_existing_project_ids() -> None:
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=4,
        schema_version="project-knowledge-graph-snapshot-v2",
        entities=Entities(
            characters=(_character("character_010"),),
            locations=(_location("location_010"),),
            events=(_event("event_010"),),
        ),
    )
    output = _output(
        characters=(_character("character_010"),),
        locations=(_location(parent_id="location_010"),),
        relations=(
            _relation(
                source_id="character_010",
                target_id="location_010",
                start_event_id="event_010",
            ),
        ),
        movements=(
            Movement(
                character_id="character_010",
                from_location_id="location_010",
                to_location_id="location_001",
                movement_type="ARRIVAL",
                event_id="event_010",
                time_expression=None,
                sequence=0,
                evidence="근거",
                confidence=0.8,
            ),
        ),
        coreferences=(
            Coreference(
                expression="그",
                resolved_entity_id="event_010",
                evidence="근거",
                confidence=0.8,
            ),
        ),
        unresolved_references=(
            UnresolvedReference(
                expression="그곳",
                possible_entity_ids=("character_010", "location_010", "event_010"),
                reason="모호함",
            ),
        ),
        contradictions=(
            Contradiction(
                subject_id="location_010",
                field_or_relation="description",
                existing_value="예전 묘사",
                new_value="새 묘사",
                evidence="근거",
                possible_explanation="",
            ),
        ),
    )
    runner = GraphRunner((output,))
    reader = RecordingGraphReader(existing)

    analysis = asyncio.run(_agent(runner, graph_reader=reader).analyze_scene(_request("근거")))

    assert len(runner.calls) == 1
    assert analysis.source_snapshot_version == 4


def test_analyze_scene_allows_memories_with_local_and_existing_typed_targets() -> None:
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=4,
        schema_version="project-knowledge-graph-snapshot-v2",
        entities=Entities(
            characters=(_character("character_010"),),
            locations=(_location("location_010"),),
            events=(_event("event_010"),),
        ),
        relations=(
            _relation(
                "relation_010",
                source_id="character_010",
                target_id="location_010",
                start_event_id="event_010",
            ),
        ),
    )
    output = _output(
        characters=(_character(),),
        locations=(_location(),),
        events=(_event(),),
        relations=(_relation(),),
        character_memories=(
            _memory(
                "memory_001",
                target=MemoryTarget(
                    kind="character", reference_id="character_001", description="서윤"
                ),
            ),
            _memory(
                "memory_002",
                target=MemoryTarget(
                    kind="location", reference_id="location_001", description="온실"
                ),
            ),
            _memory(
                "memory_003",
                target=MemoryTarget(kind="event", reference_id="event_001", description="도착"),
            ),
            _memory(
                "memory_004",
                target=MemoryTarget(
                    kind="relation", reference_id="relation_001", description="약속"
                ),
            ),
            _memory(
                "memory_005",
                target=MemoryTarget(
                    kind="character", reference_id="character_010", description="기존 서윤"
                ),
            ),
            _memory(
                "memory_006",
                target=MemoryTarget(
                    kind="location", reference_id="location_010", description="기존 온실"
                ),
            ),
            _memory(
                "memory_007",
                target=MemoryTarget(
                    kind="event", reference_id="event_010", description="기존 도착"
                ),
            ),
            _memory(
                "memory_008",
                target=MemoryTarget(
                    kind="relation", reference_id="relation_010", description="기존 약속"
                ),
            ),
            _memory(
                "memory_009",
                character_id="character_010",
                target=MemoryTarget(
                    kind="character", reference_id="character_010", description="기존 서윤"
                ),
            ),
        ),
    )
    runner = GraphRunner((output,))

    analysis = asyncio.run(
        _agent(runner, graph_reader=RecordingGraphReader(existing)).analyze_scene(
            _request("근거 서윤은 약속을 기억한다")
        )
    )

    assert analysis.chunks[0].extraction.character_memories == output.character_memories
    assert len(runner.calls) == 1


@pytest.mark.parametrize(
    "output",
    [
        pytest.param(
            _output(
                characters=(_character(),),
                relations=(_relation(),),
                character_memories=(_memory(), _memory()),
            ),
            id="duplicate-memory-id",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                relations=(_relation(),),
                character_memories=(_memory(character_id="character_999"),),
            ),
            id="memory-subject-dangling",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                locations=(_location(),),
                relations=(_relation(),),
                character_memories=(_memory(character_id="location_001"),),
            ),
            id="memory-subject-wrong-kind-location",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                locations=(_location(),),
                relations=(_relation(),),
                character_memories=(
                    _memory(
                        target=MemoryTarget(
                            kind="character", reference_id="character_999", description="낯선 인물"
                        )
                    ),
                ),
            ),
            id="memory-target-dangling",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                locations=(_location(),),
                relations=(_relation(),),
                character_memories=(
                    _memory().model_copy(
                        update={
                            "target": MemoryTarget(
                                kind="character", reference_id="character_001", description="서윤"
                            ).model_copy(update={"reference_id": "location_001"})
                        }
                    ),
                ),
            ),
            id="memory-target-wrong-kind",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                relations=(_relation(),),
                character_memories=(_memory(scene_sequence=3),),
            ),
            id="memory-scene-sequence-mismatch",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                relations=(_relation(),),
                character_memories=(_memory(evidence="원문에 없음"),),
            ),
            id="memory-evidence-absent",
        ),
        pytest.param(
            _output(
                characters=(_character(),),
                relations=(_relation(),),
            ).model_copy(
                update={
                    "character_memories": (_memory().model_copy(update={"state": "false_memory"}),)
                }
            ),
            id="linked-false-memory-model-copy",
        ),
    ],
)
def test_analyze_scene_rejects_invalid_memories_without_retry(
    output: KnowledgeGraphOutput,
) -> None:
    runner = GraphRunner((output,))

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed") as captured:
        asyncio.run(_agent(runner).analyze_scene(_request("근거 서윤은 약속을 기억한다")))

    assert len(runner.calls) == 1
    assert captured.value.__cause__ is None


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


def test_analyze_scene_sanitizes_invalid_utf8_prompt(tmp_path: Path) -> None:
    prompt_path = tmp_path / "system.md"
    prompt_path.write_bytes(b"\xff")
    agent = _agent(GraphRunner(), prompt_path=prompt_path)

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
