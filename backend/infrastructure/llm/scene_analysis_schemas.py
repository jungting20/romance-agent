from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.narrative_memory.service.models import LocationEventType
from apps.narrative_memory.service.scene_analysis_types import (
    ExtractedEntity,
    ExtractedLocationEvent,
    ExtractedPlace,
    ExtractedRelationshipEvent,
    RelationshipCategory,
    RelativeEvidence,
    SceneChunkExtraction,
)


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
    category: RelationshipCategory
    description: str
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence: list[EvidenceOutput] = Field(default_factory=list)


class LocationEventOutput(StrictOutputModel):
    character_ref: str
    place_ref: str
    event_type: LocationEventType
    description: str
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence: list[EvidenceOutput] = Field(default_factory=list)


class ChunkExtractionOutput(StrictOutputModel):
    summary: str
    entities: list[EntityOutput] = Field(default_factory=list)
    places: list[PlaceOutput] = Field(default_factory=list)
    relationship_events: list[RelationshipEventOutput] = Field(default_factory=list)
    location_events: list[LocationEventOutput] = Field(default_factory=list)

    def to_domain(self) -> SceneChunkExtraction:
        return SceneChunkExtraction(
            summary=self.summary,
            entities=tuple(
                ExtractedEntity(
                    local_ref=item.local_ref,
                    normalized_name=item.normalized_name,
                    display_name=item.display_name,
                    aliases=tuple(item.aliases),
                    evidence=tuple(
                        RelativeEvidence(
                            start_offset=evidence.start_offset,
                            end_offset=evidence.end_offset,
                            text=evidence.text,
                        )
                        for evidence in item.evidence
                    ),
                )
                for item in self.entities
            ),
            places=tuple(
                ExtractedPlace(
                    local_ref=item.local_ref,
                    normalized_name=item.normalized_name,
                    display_name=item.display_name,
                    aliases=tuple(item.aliases),
                    evidence=tuple(
                        RelativeEvidence(
                            start_offset=evidence.start_offset,
                            end_offset=evidence.end_offset,
                            text=evidence.text,
                        )
                        for evidence in item.evidence
                    ),
                )
                for item in self.places
            ),
            relationship_events=tuple(
                ExtractedRelationshipEvent(
                    subject_ref=item.subject_ref,
                    object_ref=item.object_ref,
                    category=item.category,
                    description=item.description,
                    confidence=item.confidence,
                    evidence=tuple(
                        RelativeEvidence(
                            start_offset=evidence.start_offset,
                            end_offset=evidence.end_offset,
                            text=evidence.text,
                        )
                        for evidence in item.evidence
                    ),
                )
                for item in self.relationship_events
            ),
            location_events=tuple(
                ExtractedLocationEvent(
                    character_ref=item.character_ref,
                    place_ref=item.place_ref,
                    event_type=item.event_type,
                    description=item.description,
                    confidence=item.confidence,
                    evidence=tuple(
                        RelativeEvidence(
                            start_offset=evidence.start_offset,
                            end_offset=evidence.end_offset,
                            text=evidence.text,
                        )
                        for evidence in item.evidence
                    ),
                )
                for item in self.location_events
            ),
        )
