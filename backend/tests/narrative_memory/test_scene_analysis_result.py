from narrative_analysis_agent import (
    CandidateStatus as AgentCandidateStatus,
)
from narrative_analysis_agent import (
    EntityCandidate as AgentEntityCandidate,
)
from narrative_analysis_agent import (
    Evidence as AgentEvidence,
)
from narrative_analysis_agent import (
    LocationEventCandidate as AgentLocationEventCandidate,
)
from narrative_analysis_agent import (
    LocationEventType as AgentLocationEventType,
)
from narrative_analysis_agent import (
    PlaceCandidate as AgentPlaceCandidate,
)
from narrative_analysis_agent import (
    RelationshipEventCandidate as AgentRelationshipEventCandidate,
)
from narrative_analysis_agent import (
    SceneRelationshipSnapshot as AgentSceneRelationshipSnapshot,
)

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
from apps.narrative_memory.service.scene_analysis_result import to_domain_scene_snapshot


def test_public_scene_snapshot_maps_field_by_field_to_backend_domain() -> None:
    agent_evidence = AgentEvidence(
        chunk_id="scene-01:r2:0000",
        scene_id="scene-01",
        scene_revision=2,
        start_offset=0,
        end_offset=2,
        text="서연",
    )
    agent_snapshot = AgentSceneRelationshipSnapshot(
        scene_id="scene-01",
        scene_revision=2,
        scene_sequence=7,
        schema_version="scene-relationship-snapshot-v1",
        summary="서연이 카페에서 민준을 만났다.",
        entities=(
            AgentEntityCandidate(
                candidate_id="entity-seoyeon",
                normalized_name="서연",
                display_name="서연",
                aliases=("연이",),
                status=AgentCandidateStatus.PENDING,
                scene_id="scene-01",
                scene_revision=2,
                evidence=(agent_evidence,),
            ),
        ),
        places=(
            AgentPlaceCandidate(
                candidate_id="place-cafe",
                normalized_name="카페",
                display_name="카페",
                aliases=("단골집",),
                status=AgentCandidateStatus.PENDING,
                scene_id="scene-01",
                scene_revision=2,
                evidence=(agent_evidence,),
            ),
        ),
        relationship_events=(
            AgentRelationshipEventCandidate(
                event_id="relationship-01",
                subject_key="entity-seoyeon",
                object_key="entity-minjun",
                category="first_meeting",
                description="서연이 민준을 만났다.",
                status=AgentCandidateStatus.PENDING,
                scene_id="scene-01",
                scene_revision=2,
                scene_sequence=7,
                confidence=0.8,
                evidence=(agent_evidence,),
            ),
        ),
        location_events=(
            AgentLocationEventCandidate(
                event_id="location-01",
                character_key="entity-seoyeon",
                place_key="place-cafe",
                event_type=AgentLocationEventType.ARRIVED,
                description="서연이 카페에 도착했다.",
                status=AgentCandidateStatus.PENDING,
                scene_id="scene-01",
                scene_revision=2,
                scene_sequence=7,
                confidence=0.9,
                evidence=(agent_evidence,),
            ),
        ),
    )
    evidence = Evidence("scene-01:r2:0000", "scene-01", 2, 0, 2, "서연")
    expected = SceneRelationshipSnapshot(
        scene_id="scene-01",
        scene_revision=2,
        scene_sequence=7,
        schema_version="scene-relationship-snapshot-v1",
        summary="서연이 카페에서 민준을 만났다.",
        entities=(
            EntityCandidate(
                "entity-seoyeon",
                "서연",
                "서연",
                ("연이",),
                CandidateStatus.PENDING,
                "scene-01",
                2,
                (evidence,),
            ),
        ),
        places=(
            PlaceCandidate(
                "place-cafe",
                "카페",
                "카페",
                ("단골집",),
                CandidateStatus.PENDING,
                "scene-01",
                2,
                (evidence,),
            ),
        ),
        relationship_events=(
            RelationshipEventCandidate(
                "relationship-01",
                "entity-seoyeon",
                "entity-minjun",
                "first_meeting",
                "서연이 민준을 만났다.",
                CandidateStatus.PENDING,
                "scene-01",
                2,
                7,
                0.8,
                (evidence,),
            ),
        ),
        location_events=(
            LocationEventCandidate(
                "location-01",
                "entity-seoyeon",
                "place-cafe",
                LocationEventType.ARRIVED,
                "서연이 카페에 도착했다.",
                CandidateStatus.PENDING,
                "scene-01",
                2,
                7,
                0.9,
                (evidence,),
            ),
        ),
    )

    result = to_domain_scene_snapshot(agent_snapshot)

    assert result == expected
    assert isinstance(result.entities[0], EntityCandidate)
    assert isinstance(result.places[0], PlaceCandidate)
    assert isinstance(result.relationship_events[0], RelationshipEventCandidate)
    assert isinstance(result.location_events[0], LocationEventCandidate)
