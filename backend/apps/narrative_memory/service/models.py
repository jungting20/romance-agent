from dataclasses import dataclass
from enum import StrEnum

CHUNK_ANALYSIS_SCHEMA_VERSION = "chunk-analysis-v1"
SCENE_SNAPSHOT_SCHEMA_VERSION = "scene-relationship-snapshot-v1"
PROJECT_SNAPSHOT_SCHEMA_VERSION = "project-relationship-snapshot-v1"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class LocationEventType(StrEnum):
    ARRIVED = "arrived"
    PRESENT = "present"
    DEPARTED = "departed"


@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id: str
    scene_id: str
    scene_revision: int
    start_offset: int
    end_offset: int
    text: str


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    candidate_id: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...]
    status: CandidateStatus
    scene_id: str
    scene_revision: int
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class PlaceCandidate:
    candidate_id: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...]
    status: CandidateStatus
    scene_id: str
    scene_revision: int
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class RelationshipEventCandidate:
    event_id: str
    subject_key: str
    object_key: str
    category: str
    description: str
    status: CandidateStatus
    scene_id: str
    scene_revision: int
    scene_sequence: int
    confidence: float
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class LocationEventCandidate:
    event_id: str
    character_key: str
    place_key: str
    event_type: LocationEventType
    description: str
    status: CandidateStatus
    scene_id: str
    scene_revision: int
    scene_sequence: int
    confidence: float
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class ChunkAnalysis:
    schema_version: str
    chunk_id: str
    chunk_ordinal: int
    chunk_start: int
    chunk_end: int
    source_text: str
    scene_id: str
    scene_revision: int
    summary: str
    entities: tuple[EntityCandidate, ...]
    places: tuple[PlaceCandidate, ...]
    relationship_events: tuple[RelationshipEventCandidate, ...]
    location_events: tuple[LocationEventCandidate, ...]


@dataclass(frozen=True, slots=True)
class SceneRelationshipSnapshot:
    scene_id: str
    scene_revision: int
    scene_sequence: int
    schema_version: str
    summary: str
    entities: tuple[EntityCandidate, ...]
    places: tuple[PlaceCandidate, ...]
    relationship_events: tuple[RelationshipEventCandidate, ...]
    location_events: tuple[LocationEventCandidate, ...]


@dataclass(frozen=True, slots=True)
class ProjectRelationshipSnapshot:
    project_id: str
    snapshot_version: int
    schema_version: str
    active_scene_revisions: tuple[tuple[str, int], ...]
    entities: tuple[EntityCandidate, ...]
    places: tuple[PlaceCandidate, ...]
    relationship_events: tuple[RelationshipEventCandidate, ...]
    location_events: tuple[LocationEventCandidate, ...]

    @classmethod
    def empty(cls, project_id: str) -> "ProjectRelationshipSnapshot":
        return cls(
            project_id=project_id,
            snapshot_version=0,
            schema_version=PROJECT_SNAPSHOT_SCHEMA_VERSION,
            active_scene_revisions=(),
            entities=(),
            places=(),
            relationship_events=(),
            location_events=(),
        )
