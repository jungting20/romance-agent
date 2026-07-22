from dataclasses import dataclass
from typing import Literal

from narrative_analysis_agent.contracts import (
    CandidateStatus,
    EntityCandidate,
    Evidence,
    KnownIdentity,
    LocationEventCandidate,
    LocationEventType,
    PlaceCandidate,
    RelationshipEventCandidate,
    SceneRelationshipSnapshot,
)

CHUNK_ANALYSIS_SCHEMA_VERSION = "chunk-analysis-v1"
SCENE_SNAPSHOT_SCHEMA_VERSION = "scene-relationship-snapshot-v1"

type RelationshipCategory = Literal[
    "romance", "family", "friendship", "professional", "antagonistic", "other"
]


@dataclass(frozen=True, slots=True)
class RelativeEvidence:
    start_offset: int
    end_offset: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedEntity:
    local_ref: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...]
    evidence: tuple[RelativeEvidence, ...]


@dataclass(frozen=True, slots=True)
class ExtractedPlace:
    local_ref: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...]
    evidence: tuple[RelativeEvidence, ...]


@dataclass(frozen=True, slots=True)
class ExtractedRelationshipEvent:
    subject_ref: str
    object_ref: str
    category: RelationshipCategory
    description: str
    confidence: float
    evidence: tuple[RelativeEvidence, ...]


@dataclass(frozen=True, slots=True)
class ExtractedLocationEvent:
    character_ref: str
    place_ref: str
    event_type: LocationEventType
    description: str
    confidence: float
    evidence: tuple[RelativeEvidence, ...]


@dataclass(frozen=True, slots=True)
class SceneChunkExtraction:
    summary: str
    entities: tuple[ExtractedEntity, ...] = ()
    places: tuple[ExtractedPlace, ...] = ()
    relationship_events: tuple[ExtractedRelationshipEvent, ...] = ()
    location_events: tuple[ExtractedLocationEvent, ...] = ()


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


__all__ = [
    "CHUNK_ANALYSIS_SCHEMA_VERSION",
    "SCENE_SNAPSHOT_SCHEMA_VERSION",
    "CandidateStatus",
    "ChunkAnalysis",
    "EntityCandidate",
    "Evidence",
    "ExtractedEntity",
    "ExtractedLocationEvent",
    "ExtractedPlace",
    "ExtractedRelationshipEvent",
    "KnownIdentity",
    "LocationEventCandidate",
    "LocationEventType",
    "PlaceCandidate",
    "RelativeEvidence",
    "RelationshipEventCandidate",
    "SceneChunkExtraction",
    "SceneRelationshipSnapshot",
]
