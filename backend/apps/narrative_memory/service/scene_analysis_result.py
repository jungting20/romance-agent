from narrative_analysis_agent import EntityCandidate as AgentEntityCandidate
from narrative_analysis_agent import Evidence as AgentEvidence
from narrative_analysis_agent import LocationEventCandidate as AgentLocationEventCandidate
from narrative_analysis_agent import PlaceCandidate as AgentPlaceCandidate
from narrative_analysis_agent import (
    RelationshipEventCandidate as AgentRelationshipEventCandidate,
)
from narrative_analysis_agent import SceneRelationshipSnapshot as AgentSceneSnapshot

from apps.narrative_memory.service.models import (
    CandidateStatus,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    LocationEventType,
    PlaceCandidate,
    RelationshipEventCandidate,
    SceneRelationshipSnapshot,
)


def to_domain_scene_snapshot(snapshot: AgentSceneSnapshot) -> SceneRelationshipSnapshot:
    return SceneRelationshipSnapshot(
        scene_id=snapshot.scene_id,
        scene_revision=snapshot.scene_revision,
        scene_sequence=snapshot.scene_sequence,
        schema_version=snapshot.schema_version,
        summary=snapshot.summary,
        entities=tuple(_to_domain_entity(item) for item in snapshot.entities),
        places=tuple(_to_domain_place(item) for item in snapshot.places),
        relationship_events=tuple(
            _to_domain_relationship(item) for item in snapshot.relationship_events
        ),
        location_events=tuple(_to_domain_location(item) for item in snapshot.location_events),
    )


def _to_domain_evidence(item: AgentEvidence) -> Evidence:
    return Evidence(
        chunk_id=item.chunk_id,
        scene_id=item.scene_id,
        scene_revision=item.scene_revision,
        start_offset=item.start_offset,
        end_offset=item.end_offset,
        text=item.text,
    )


def _to_domain_entity(item: AgentEntityCandidate) -> EntityCandidate:
    return EntityCandidate(
        candidate_id=item.candidate_id,
        normalized_name=item.normalized_name,
        display_name=item.display_name,
        aliases=tuple(item.aliases),
        status=CandidateStatus(item.status.value),
        scene_id=item.scene_id,
        scene_revision=item.scene_revision,
        evidence=tuple(_to_domain_evidence(evidence) for evidence in item.evidence),
    )


def _to_domain_place(item: AgentPlaceCandidate) -> PlaceCandidate:
    return PlaceCandidate(
        candidate_id=item.candidate_id,
        normalized_name=item.normalized_name,
        display_name=item.display_name,
        aliases=tuple(item.aliases),
        status=CandidateStatus(item.status.value),
        scene_id=item.scene_id,
        scene_revision=item.scene_revision,
        evidence=tuple(_to_domain_evidence(evidence) for evidence in item.evidence),
    )


def _to_domain_relationship(
    item: AgentRelationshipEventCandidate,
) -> RelationshipEventCandidate:
    return RelationshipEventCandidate(
        event_id=item.event_id,
        subject_key=item.subject_key,
        object_key=item.object_key,
        category=item.category,
        description=item.description,
        status=CandidateStatus(item.status.value),
        scene_id=item.scene_id,
        scene_revision=item.scene_revision,
        scene_sequence=item.scene_sequence,
        confidence=item.confidence,
        evidence=tuple(_to_domain_evidence(evidence) for evidence in item.evidence),
    )


def _to_domain_location(item: AgentLocationEventCandidate) -> LocationEventCandidate:
    return LocationEventCandidate(
        event_id=item.event_id,
        character_key=item.character_key,
        place_key=item.place_key,
        event_type=LocationEventType(item.event_type.value),
        description=item.description,
        status=CandidateStatus(item.status.value),
        scene_id=item.scene_id,
        scene_revision=item.scene_revision,
        scene_sequence=item.scene_sequence,
        confidence=item.confidence,
        evidence=tuple(_to_domain_evidence(evidence) for evidence in item.evidence),
    )
