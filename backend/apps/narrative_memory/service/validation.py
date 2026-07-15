import math
import re
from collections.abc import Iterable
from dataclasses import replace

from apps.narrative_memory.service.models import (
    PROJECT_SNAPSHOT_SCHEMA_VERSION,
    CandidateStatus,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    PlaceCandidate,
    ProjectRelationshipSnapshot,
    RelationshipEventCandidate,
)


class ProjectInvariantError(ValueError):
    pass


type CatalogCandidate = EntityCandidate | PlaceCandidate
type TemporalEvent = RelationshipEventCandidate | LocationEventCandidate


def normalize_reference(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def validate_project_snapshot(snapshot: ProjectRelationshipSnapshot) -> None:
    if snapshot.schema_version != PROJECT_SNAPSHOT_SCHEMA_VERSION:
        raise ProjectInvariantError("unsupported project snapshot schema")

    active_revisions = _active_revision_map(snapshot)
    _require_unique(
        (candidate.candidate_id for candidate in (*snapshot.entities, *snapshot.places)),
        "candidate IDs",
    )
    _require_unique(
        (event.event_id for event in (*snapshot.relationship_events, *snapshot.location_events)),
        "event IDs",
    )
    _validate_identity_catalog(snapshot.entities, "entity")
    _validate_identity_catalog(snapshot.places, "place")

    for candidate in (*snapshot.entities, *snapshot.places):
        _validate_candidate(candidate, active_revisions)

    scene_sequences: dict[str, int] = {}
    for event in (*snapshot.relationship_events, *snapshot.location_events):
        _validate_candidate(event, active_revisions)
        if not math.isfinite(event.confidence) or not 0.0 <= event.confidence <= 1.0:
            raise ProjectInvariantError("confidence must be finite and between 0.0 and 1.0")
        existing = scene_sequences.setdefault(event.scene_id, event.scene_sequence)
        if existing != event.scene_sequence:
            raise ProjectInvariantError("event sequences conflict within containing scene")

    entity_references = _catalog_reference_map(snapshot.entities)
    place_references = _catalog_reference_map(snapshot.places)
    for event in snapshot.relationship_events:
        subject = _resolve_reference(event.subject_key, entity_references, "relationship subject")
        object_ = _resolve_reference(event.object_key, entity_references, "relationship object")
        if event.status is CandidateStatus.APPROVED and (
            subject.status is not CandidateStatus.APPROVED
            or object_.status is not CandidateStatus.APPROVED
        ):
            raise ProjectInvariantError(
                "approved relationship dependency must reference approved entities"
            )
    for event in snapshot.location_events:
        character = _resolve_reference(event.character_key, entity_references, "location character")
        place = _resolve_reference(event.place_key, place_references, "location place")
        if event.status is CandidateStatus.APPROVED and (
            character.status is not CandidateStatus.APPROVED
            or place.status is not CandidateStatus.APPROVED
        ):
            raise ProjectInvariantError(
                "approved location dependency must reference approved entity and place"
            )


def downgrade_invalid_approvals(
    snapshot: ProjectRelationshipSnapshot,
) -> ProjectRelationshipSnapshot:
    active_revisions = _active_revision_map(snapshot)
    entities = tuple(
        _downgrade_stale_candidate(candidate, active_revisions) for candidate in snapshot.entities
    )
    places = tuple(
        _downgrade_stale_candidate(candidate, active_revisions) for candidate in snapshot.places
    )
    entity_references = _catalog_reference_map(entities)
    place_references = _catalog_reference_map(places)

    relationships = tuple(
        _downgrade_relationship(event, active_revisions, entity_references)
        for event in snapshot.relationship_events
    )
    locations = tuple(
        _downgrade_location(
            event,
            active_revisions,
            entity_references,
            place_references,
        )
        for event in snapshot.location_events
    )
    return replace(
        snapshot,
        entities=entities,
        places=places,
        relationship_events=relationships,
        location_events=locations,
    )


def build_canonical_reference_map(
    candidates: tuple[CatalogCandidate, ...],
    candidate_id_map: dict[str, str] | None = None,
) -> dict[str, str]:
    result = {
        normalize_reference(value): candidate.candidate_id
        for candidate in candidates
        for value in (candidate.candidate_id, candidate.normalized_name, *candidate.aliases)
    }
    if candidate_id_map:
        result.update(
            {
                normalize_reference(source_id): target_id
                for source_id, target_id in candidate_id_map.items()
            }
        )
    return result


def _active_revision_map(snapshot: ProjectRelationshipSnapshot) -> dict[str, int]:
    result: dict[str, int] = {}
    for scene_id, revision in snapshot.active_scene_revisions:
        if scene_id in result:
            raise ProjectInvariantError("active scene revisions must contain unique scene IDs")
        result[scene_id] = revision
    return result


def _require_unique(values: Iterable[str], label: str) -> None:
    sequence = tuple(values)
    if len(sequence) != len(set(sequence)):
        raise ProjectInvariantError(f"{label} must be unique")


def _validate_identity_catalog(
    candidates: tuple[CatalogCandidate, ...],
    label: str,
) -> None:
    token_sets = tuple(_identity_tokens(candidate) for candidate in candidates)
    for right_index, right_tokens in enumerate(token_sets):
        if any(token_sets[left_index] & right_tokens for left_index in range(right_index)):
            raise ProjectInvariantError(f"{label} identities must be consolidated")


def _identity_tokens(candidate: CatalogCandidate) -> set[str]:
    return {
        normalized
        for value in (candidate.normalized_name, *candidate.aliases)
        if (normalized := normalize_reference(value))
    }


def _validate_candidate(
    candidate: CatalogCandidate | TemporalEvent,
    active_revisions: dict[str, int],
) -> None:
    active_revision = active_revisions.get(candidate.scene_id)
    if active_revision is None or candidate.scene_revision != active_revision:
        raise ProjectInvariantError("candidate provenance does not match active scene revision")
    for evidence in candidate.evidence:
        _validate_evidence(evidence, candidate.status, active_revisions)


def _validate_evidence(
    evidence: Evidence,
    status: CandidateStatus,
    active_revisions: dict[str, int],
) -> None:
    if not 0 <= evidence.start_offset < evidence.end_offset:
        raise ProjectInvariantError("evidence range must satisfy 0 <= start < end")
    active_revision = active_revisions.get(evidence.scene_id)
    if active_revision is None or evidence.scene_revision > active_revision:
        raise ProjectInvariantError("evidence provenance is outside active project scenes")
    if status is not CandidateStatus.NEEDS_REVIEW and evidence.scene_revision != active_revision:
        raise ProjectInvariantError("stale evidence revision is allowed only on needs_review")


def _catalog_reference_map(
    candidates: tuple[CatalogCandidate, ...],
) -> dict[str, CatalogCandidate]:
    return {
        normalize_reference(value): candidate
        for candidate in candidates
        for value in (candidate.candidate_id, candidate.normalized_name, *candidate.aliases)
    }


def _resolve_reference(
    reference: str,
    catalog: dict[str, CatalogCandidate],
    label: str,
) -> CatalogCandidate:
    candidate = catalog.get(normalize_reference(reference))
    if candidate is None:
        raise ProjectInvariantError(f"{label} reference is absent from catalog")
    return candidate


def _has_stale_evidence(
    candidate: CatalogCandidate | TemporalEvent,
    active_revisions: dict[str, int],
) -> bool:
    return any(
        active_revisions.get(evidence.scene_id) != evidence.scene_revision
        for evidence in candidate.evidence
    )


def _downgrade_stale_candidate[
    Candidate: CatalogCandidate,
](candidate: Candidate, active_revisions: dict[str, int]) -> Candidate:
    if candidate.status is CandidateStatus.APPROVED and _has_stale_evidence(
        candidate, active_revisions
    ):
        return replace(candidate, status=CandidateStatus.NEEDS_REVIEW)
    return candidate


def _downgrade_relationship(
    event: RelationshipEventCandidate,
    active_revisions: dict[str, int],
    entities: dict[str, CatalogCandidate],
) -> RelationshipEventCandidate:
    if event.status is not CandidateStatus.APPROVED:
        return event
    subject = entities.get(normalize_reference(event.subject_key))
    object_ = entities.get(normalize_reference(event.object_key))
    if (
        _has_stale_evidence(event, active_revisions)
        or subject is None
        or object_ is None
        or subject.status is not CandidateStatus.APPROVED
        or object_.status is not CandidateStatus.APPROVED
    ):
        return replace(event, status=CandidateStatus.NEEDS_REVIEW)
    return event


def _downgrade_location(
    event: LocationEventCandidate,
    active_revisions: dict[str, int],
    entities: dict[str, CatalogCandidate],
    places: dict[str, CatalogCandidate],
) -> LocationEventCandidate:
    if event.status is not CandidateStatus.APPROVED:
        return event
    character = entities.get(normalize_reference(event.character_key))
    place = places.get(normalize_reference(event.place_key))
    if (
        _has_stale_evidence(event, active_revisions)
        or character is None
        or place is None
        or character.status is not CandidateStatus.APPROVED
        or place.status is not CandidateStatus.APPROVED
    ):
        return replace(event, status=CandidateStatus.NEEDS_REVIEW)
    return event
