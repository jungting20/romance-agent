import math
from collections.abc import Iterable

from narrative_analysis_agent import (
    PROJECT_GRAPH_SCHEMA_VERSION,
    KnowledgeGraphOutput,
    ProjectKnowledgeGraphSnapshot,
)


class ProjectInvariantError(ValueError):
    pass


def validate_project_snapshot(snapshot: ProjectKnowledgeGraphSnapshot) -> None:
    if not isinstance(snapshot.project_id, str) or not snapshot.project_id:
        raise ProjectInvariantError("project ID must be a non-empty string")
    if type(snapshot.snapshot_version) is not int or snapshot.snapshot_version < 0:
        raise ProjectInvariantError("snapshot version must be a non-negative integer")
    if snapshot.schema_version != PROJECT_GRAPH_SCHEMA_VERSION:
        raise ProjectInvariantError("unsupported project snapshot schema")

    _require_unique((document.chapter_id for document in snapshot.documents), "chapter IDs")
    _validate_graph(snapshot)


def validate_scene_graph(graph: KnowledgeGraphOutput) -> None:
    _validate_graph(graph)


def _validate_graph(graph: KnowledgeGraphOutput | ProjectKnowledgeGraphSnapshot) -> None:
    character_ids = {character.id for character in graph.entities.characters}
    location_ids = {location.id for location in graph.entities.locations}
    event_ids = {event.id for event in graph.entities.events}
    entity_ids = character_ids | location_ids | event_ids
    _require_unique(
        (
            *(character.id for character in graph.entities.characters),
            *(location.id for location in graph.entities.locations),
            *(event.id for event in graph.entities.events),
            *(relation.id for relation in graph.relations),
        ),
        "graph IDs",
    )

    for location in graph.entities.locations:
        _require_reference(location.parent_location_id, location_ids, "location parent")
    for event in graph.entities.events:
        _require_references(event.participant_ids, character_ids, "event participant")
        _require_references(event.location_ids, location_ids, "event location")
    for relation in graph.relations:
        _require_reference(relation.source_id, entity_ids, "relation source")
        _require_reference(relation.target_id, entity_ids, "relation target")
        _require_reference(relation.start_event_id, event_ids, "relation start event")
        _require_reference(relation.end_event_id, event_ids, "relation end event")
    for movement in graph.movements:
        _require_reference(movement.character_id, character_ids, "movement character")
        _require_reference(movement.from_location_id, location_ids, "movement origin")
        _require_reference(movement.to_location_id, location_ids, "movement destination")
        _require_reference(movement.event_id, event_ids, "movement event")
    for coreference in graph.coreferences:
        _require_reference(
            coreference.resolved_entity_id,
            entity_ids,
            "coreference target",
        )
    for unresolved in graph.unresolved_references:
        _require_references(
            unresolved.possible_entity_ids,
            entity_ids,
            "unresolved reference candidate",
        )
    for contradiction in graph.contradictions:
        _require_reference(contradiction.subject_id, entity_ids, "contradiction subject")

    confidence_values = (
        *(item.confidence for item in graph.entities.characters),
        *(item.confidence for item in graph.entities.locations),
        *(item.confidence for item in graph.entities.events),
        *(item.confidence for item in graph.relations),
        *(item.confidence for item in graph.movements),
        *(item.confidence for item in graph.coreferences),
    )
    if any(
        not isinstance(confidence, int | float)
        or isinstance(confidence, bool)
        or not math.isfinite(confidence)
        or not 0.8 <= confidence <= 1.0
        for confidence in confidence_values
    ):
        raise ProjectInvariantError("confidence must be finite and between 0.8 and 1.0")

    evidence_values = (
        *(item.first_mention for item in graph.entities.characters),
        *(item.first_mention for item in graph.entities.locations),
        *(item.evidence for item in graph.entities.events),
        *(item.evidence for item in graph.relations),
        *(item.evidence for item in graph.movements),
        *(item.evidence for item in graph.coreferences),
        *(item.evidence for item in graph.contradictions),
    )
    if any(not isinstance(value, str) or not value for value in evidence_values):
        raise ProjectInvariantError("evidence and first mention must be non-empty strings")


def _require_unique(values: Iterable[str], label: str) -> None:
    sequence = tuple(values)
    if len(sequence) != len(set(sequence)):
        raise ProjectInvariantError(f"{label} must be unique")


def _require_reference(reference: str | None, allowed: set[str], label: str) -> None:
    if reference is not None and reference not in allowed:
        raise ProjectInvariantError(f"{label} references an unknown or wrong-kind ID")


def _require_references(references: Iterable[str], allowed: set[str], label: str) -> None:
    if not set(references) <= allowed:
        raise ProjectInvariantError(f"{label} references an unknown or wrong-kind ID")
