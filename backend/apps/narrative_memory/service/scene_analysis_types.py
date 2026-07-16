from dataclasses import dataclass
from typing import Literal

from apps.narrative_memory.service.models import LocationEventType

type RelationshipCategory = Literal[
    "romance", "family", "friendship", "professional", "antagonistic", "other"
]


@dataclass(frozen=True, slots=True)
class KnownIdentity:
    identity_key: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalyzeSceneRequest:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    text: str
    known_entities: tuple[KnownIdentity, ...] = ()
    known_places: tuple[KnownIdentity, ...] = ()


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
class AgentUsage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class AgentInvocationResult:
    extraction: SceneChunkExtraction
    response_messages_json: bytes
    usage: AgentUsage
    provider_name: str
    model_name: str
