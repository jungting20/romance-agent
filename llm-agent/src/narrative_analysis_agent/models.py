from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class KnownIdentity(StrictModel):
    identity_key: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()


class SceneAnalysisRequest(StrictModel):
    project_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    scene_revision: int = Field(ge=0)
    scene_sequence: int = Field(ge=0)
    text: str
    known_entities: tuple[KnownIdentity, ...] = ()
    known_places: tuple[KnownIdentity, ...] = ()


class Evidence(StrictModel):
    start_offset: int = Field(ge=0)
    end_offset: int
    text: str

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return self


class Entity(StrictModel):
    local_ref: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()


class Place(StrictModel):
    local_ref: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()


class RelationshipEvent(StrictModel):
    subject_ref: str = Field(min_length=1)
    object_ref: str = Field(min_length=1)
    category: Literal[
        "romance",
        "family",
        "friendship",
        "professional",
        "antagonistic",
        "other",
    ]
    description: str
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence: tuple[Evidence, ...] = ()


class LocationEvent(StrictModel):
    character_ref: str = Field(min_length=1)
    place_ref: str = Field(min_length=1)
    event_type: Literal["arrived", "present", "departed"]
    description: str
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence: tuple[Evidence, ...] = ()


class ChunkExtraction(StrictModel):
    summary: str
    entities: tuple[Entity, ...] = ()
    places: tuple[Place, ...] = ()
    relationship_events: tuple[RelationshipEvent, ...] = ()
    location_events: tuple[LocationEvent, ...] = ()


class AnalyzedChunk(StrictModel):
    chunk_id: str
    ordinal: int
    start_offset: int
    end_offset: int
    text: str
    extraction: ChunkExtraction


class SceneAnalysis(StrictModel):
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    chunks: tuple[AnalyzedChunk, ...]
