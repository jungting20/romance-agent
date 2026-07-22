import math
from collections.abc import Iterable

from narrative_analysis_agent.contracts import (
    EntityCandidate,
    LocationEventCandidate,
    PlaceCandidate,
    RelationshipEventCandidate,
    SceneRelationshipSnapshot,
)

from .models import SCENE_SNAPSHOT_SCHEMA_VERSION


class MergeInvariantError(ValueError):
    pass


type SceneCandidate = (
    EntityCandidate | PlaceCandidate | RelationshipEventCandidate | LocationEventCandidate
)


def validate_scene_snapshot(scene: SceneRelationshipSnapshot) -> None:
    if scene.schema_version != SCENE_SNAPSHOT_SCHEMA_VERSION:
        raise MergeInvariantError("unsupported scene snapshot schema")
    candidates = _all_candidates(scene)
    candidate_ids = tuple(candidate.candidate_id for candidate in (*scene.entities, *scene.places))
    event_ids = tuple(
        event.event_id for event in (*scene.relationship_events, *scene.location_events)
    )
    if len(candidate_ids) != len(set(candidate_ids)):
        raise MergeInvariantError("scene candidate IDs must be unique")
    if len(event_ids) != len(set(event_ids)):
        raise MergeInvariantError("scene event IDs must be unique")
    for candidate in candidates:
        if candidate.scene_id != scene.scene_id or candidate.scene_revision != scene.scene_revision:
            raise MergeInvariantError("candidate provenance does not match scene snapshot")
        if isinstance(candidate, (RelationshipEventCandidate, LocationEventCandidate)):
            if candidate.scene_sequence != scene.scene_sequence:
                raise MergeInvariantError("event sequence does not match containing scene")
            validate_confidence(candidate.confidence)
        validate_candidate_evidence(candidate)


def validate_confidence(confidence: float) -> None:
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise MergeInvariantError("confidence must be finite and between 0.0 and 1.0")


def validate_candidate_evidence(candidate: SceneCandidate) -> None:
    for evidence in candidate.evidence:
        if not 0 <= evidence.start_offset < evidence.end_offset:
            raise MergeInvariantError("evidence range must satisfy 0 <= start < end")
        if (
            evidence.scene_id != candidate.scene_id
            or evidence.scene_revision != candidate.scene_revision
        ):
            raise MergeInvariantError("evidence provenance does not match candidate")


def require_unique(values: Iterable[str], label: str) -> None:
    sequence = tuple(values)
    if len(sequence) != len(set(sequence)):
        raise MergeInvariantError(f"{label} must be unique")


def _all_candidates(scene: SceneRelationshipSnapshot) -> tuple[SceneCandidate, ...]:
    return (*scene.entities, *scene.places, *scene.relationship_events, *scene.location_events)
