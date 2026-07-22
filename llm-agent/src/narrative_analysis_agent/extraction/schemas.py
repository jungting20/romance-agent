from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceOutput(StrictOutputModel):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    text: str

    @model_validator(mode="after")
    def validate_ordered_offsets(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return self


class EntityOutput(StrictOutputModel):
    local_ref: str
    normalized_name: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    evidence: list[EvidenceOutput] = Field(default_factory=list)


class PlaceOutput(StrictOutputModel):
    local_ref: str
    normalized_name: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    evidence: list[EvidenceOutput] = Field(default_factory=list)


class RelationshipEventOutput(StrictOutputModel):
    subject_ref: str
    object_ref: str
    category: Literal["romance", "family", "friendship", "professional", "antagonistic", "other"]
    description: str
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence: list[EvidenceOutput] = Field(default_factory=list)


class LocationEventOutput(StrictOutputModel):
    character_ref: str
    place_ref: str
    event_type: Literal["arrived", "present", "departed"]
    description: str
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence: list[EvidenceOutput] = Field(default_factory=list)


class ChunkExtractionOutput(StrictOutputModel):
    summary: str
    entities: list[EntityOutput] = Field(default_factory=list)
    places: list[PlaceOutput] = Field(default_factory=list)
    relationship_events: list[RelationshipEventOutput] = Field(default_factory=list)
    location_events: list[LocationEventOutput] = Field(default_factory=list)
