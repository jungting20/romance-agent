import asyncio
import json
from pathlib import Path
from typing import Protocol, cast

from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from narrative_analysis_agent.chunking import SceneChunk, chunk_scene
from narrative_analysis_agent.models import (
    AnalyzedChunk,
    KnowledgeGraphOutput,
    ProjectKnowledgeGraphSnapshot,
    SceneAnalysis,
    SceneAnalysisRequest,
)
from narrative_analysis_agent.project_graph_reader import ProjectGraphReader, ProjectGraphReadError


class NarrativeAnalysisError(RuntimeError):
    pass


class AgentResult(Protocol):
    output: KnowledgeGraphOutput


class AgentRunner(Protocol):
    async def run(self, user_prompt: str, *, instructions: str) -> AgentResult: ...


class GraphReader(Protocol):
    def read(self, project_id: str) -> ProjectKnowledgeGraphSnapshot: ...


def packaged_prompt_path() -> Path:
    return Path(__file__).parent / "prompts" / "scene-analysis" / "system.md"


class NarrativeAnalysisAgent:
    def __init__(
        self,
        model: Model | str,
        project_graph_path: Path | None = None,
        *,
        prompt_path: Path | None = None,
        graph_reader: GraphReader | None = None,
        runner: AgentRunner | None = None,
    ) -> None:
        if graph_reader is None and project_graph_path is None:
            raise TypeError("project_graph_path is required when graph_reader is not provided")
        self.prompt_path = prompt_path or packaged_prompt_path()
        self._graph_reader = graph_reader or ProjectGraphReader(cast(Path, project_graph_path))
        self._runner = runner or cast(
            AgentRunner,
            Agent(
                model,
                output_type=KnowledgeGraphOutput,
                retries=0,
                defer_model_check=True,
            ),
        )

    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis:
        try:
            instructions = self.prompt_path.read_text(encoding="utf-8")
        except OSError:
            raise NarrativeAnalysisError("unable to load scene analysis prompt") from None

        try:
            existing = self._graph_reader.read(request.project_id)
        except ProjectGraphReadError:
            raise NarrativeAnalysisError("scene analysis failed") from None

        analyzed: list[AnalyzedChunk] = []
        for chunk in chunk_scene(request.scene_id, request.scene_revision, request.text):
            try:
                result = await self._runner.run(
                    _render_user_prompt(existing, chunk),
                    instructions=instructions,
                )
                _validate_output(result.output, request, chunk, existing)
            except asyncio.CancelledError:
                raise
            except (AgentRunError, ValidationError, ValueError):
                raise NarrativeAnalysisError("scene analysis failed") from None
            analyzed.append(
                AnalyzedChunk(
                    chunk_id=chunk.chunk_id,
                    ordinal=chunk.ordinal,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    text=chunk.text,
                    extraction=result.output,
                )
            )

        return SceneAnalysis(
            project_id=request.project_id,
            scene_id=request.scene_id,
            scene_revision=request.scene_revision,
            scene_sequence=request.scene_sequence,
            source_snapshot_version=existing.snapshot_version,
            chunks=tuple(analyzed),
        )


def _render_user_prompt(existing: ProjectKnowledgeGraphSnapshot, chunk: SceneChunk) -> str:
    envelope = {
        "existing_graph": existing.model_dump(mode="json"),
        "chunk": {
            "chunk_id": chunk.chunk_id,
            "ordinal": chunk.ordinal,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            "text": chunk.text,
        },
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def _validate_output(
    output: KnowledgeGraphOutput,
    request: SceneAnalysisRequest,
    chunk: SceneChunk,
    existing: ProjectKnowledgeGraphSnapshot,
) -> None:
    if output.document.chapter_id != request.scene_id:
        raise ValueError("chapter ID does not match the scene")

    local_character_ids = tuple(item.id for item in output.entities.characters)
    local_location_ids = tuple(item.id for item in output.entities.locations)
    local_event_ids = tuple(item.id for item in output.entities.events)
    local_relation_ids = tuple(item.id for item in output.relations)
    _validate_unique_ids(local_character_ids, "character")
    _validate_unique_ids(local_location_ids, "location")
    _validate_unique_ids(local_event_ids, "event")
    _validate_unique_ids(local_relation_ids, "relation")

    local_characters = set(local_character_ids)
    local_locations = set(local_location_ids)
    local_events = set(local_event_ids)
    known_characters = {item.id for item in existing.entities.characters}
    known_locations = {item.id for item in existing.entities.locations}
    known_events = {item.id for item in existing.entities.events}
    characters = local_characters | known_characters
    locations = local_locations | known_locations
    events = local_events | known_events
    entities = characters | locations | events

    for location in output.entities.locations:
        _validate_reference(location.parent_location_id, locations, "location parent is unknown")
    for event in output.entities.events:
        if not set(event.participant_ids) <= characters:
            raise ValueError("event references an unknown character")
        if not set(event.location_ids) <= locations:
            raise ValueError("event references an unknown location")
    for relation in output.relations:
        if relation.source_id not in entities:
            raise ValueError("relation source is unknown")
        if relation.target_id not in entities:
            raise ValueError("relation target is unknown")
        _validate_reference(relation.start_event_id, events, "relation start event is unknown")
        _validate_reference(relation.end_event_id, events, "relation end event is unknown")
    for movement in output.movements:
        _validate_reference(movement.character_id, characters, "movement character is unknown")
        _validate_reference(
            movement.from_location_id,
            locations,
            "movement origin is unknown",
        )
        _validate_reference(
            movement.to_location_id,
            locations,
            "movement destination is unknown",
        )
        _validate_reference(movement.event_id, events, "movement event is unknown")
    for coreference in output.coreferences:
        _validate_reference(
            coreference.resolved_entity_id,
            entities,
            "coreference target is unknown",
        )
    for unresolved in output.unresolved_references:
        if not set(unresolved.possible_entity_ids) <= entities:
            raise ValueError("unresolved reference candidate is unknown")
    for contradiction in output.contradictions:
        _validate_reference(
            contradiction.subject_id,
            entities,
            "contradiction subject is unknown",
        )

    evidence_values = [
        *(item.first_mention for item in output.entities.characters),
        *(item.first_mention for item in output.entities.locations),
        *(item.evidence for item in output.entities.events),
        *(item.evidence for item in output.relations),
        *(item.evidence for item in output.movements),
        *(item.evidence for item in output.coreferences),
        *(item.evidence for item in output.contradictions),
    ]
    if any(value and value not in chunk.text for value in evidence_values):
        raise ValueError("evidence is not present in the chunk")


def _validate_unique_ids(ids: tuple[str, ...], kind: str) -> None:
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {kind} ID")


def _validate_reference(reference: str | None, allowed: set[str], message: str) -> None:
    if reference is not None and reference not in allowed:
        raise ValueError(message)
