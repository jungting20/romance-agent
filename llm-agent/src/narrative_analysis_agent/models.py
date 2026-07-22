from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PROJECT_GRAPH_SCHEMA_VERSION = "project-knowledge-graph-snapshot-v2"
UpperSnake = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$"),
]
HighConfidence = Annotated[float, Field(ge=0.8, le=1.0, allow_inf_nan=False)]
NarrativeTime = Literal["present", "flashback", "flashforward", "mixed", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Document(StrictModel):
    chapter_id: str = Field(min_length=1)
    summary: str
    narrative_time: NarrativeTime


class Character(StrictModel):
    id: str = Field(pattern=r"^character_[0-9]+$")
    canonical_name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    description: str
    gender: Literal["male", "female", "nonbinary", "unknown"]
    age: int | str | None
    occupation: str | None
    affiliation: str | None
    status: Literal["alive", "dead", "missing", "unknown"]
    first_mention: str
    confidence: HighConfidence


class Location(StrictModel):
    id: str = Field(pattern=r"^location_[0-9]+$")
    canonical_name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    location_type: Literal[
        "country",
        "city",
        "village",
        "building",
        "room",
        "school",
        "company",
        "hospital",
        "street",
        "nature",
        "vehicle",
        "virtual",
        "other",
    ]
    parent_location_id: str | None
    description: str
    first_mention: str
    confidence: HighConfidence


class Event(StrictModel):
    id: str = Field(pattern=r"^event_[0-9]+$")
    event_type: UpperSnake
    name: str
    summary: str
    participant_ids: tuple[str, ...] = ()
    location_ids: tuple[str, ...] = ()
    time_expression: str | None
    narrative_time: Literal["present", "flashback", "flashforward", "unknown"]
    sequence: int = Field(ge=0)
    evidence: str
    confidence: HighConfidence


class Entities(StrictModel):
    characters: tuple[Character, ...] = ()
    locations: tuple[Location, ...] = ()
    events: tuple[Event, ...] = ()


class Relation(StrictModel):
    id: str = Field(pattern=r"^relation_[0-9]+$")
    source_id: str
    relation_type: UpperSnake
    target_id: str
    state: Literal["active", "ended", "uncertain", "perceived"]
    directed: bool
    start_event_id: str | None
    end_event_id: str | None
    time_expression: str | None
    scene_sequence: int = Field(ge=0)
    evidence: str
    inference: bool
    confidence: HighConfidence


class Movement(StrictModel):
    character_id: str
    from_location_id: str | None
    to_location_id: str | None
    movement_type: UpperSnake
    event_id: str | None
    time_expression: str | None
    sequence: int = Field(ge=0)
    evidence: str
    confidence: HighConfidence


class Coreference(StrictModel):
    expression: str
    resolved_entity_id: str
    evidence: str
    confidence: HighConfidence


class UnresolvedReference(StrictModel):
    expression: str
    possible_entity_ids: tuple[str, ...] = ()
    reason: str


class Contradiction(StrictModel):
    subject_id: str
    field_or_relation: str
    existing_value: str
    new_value: str
    evidence: str
    possible_explanation: str


class KnowledgeGraphOutput(StrictModel):
    document: Document
    entities: Entities
    relations: tuple[Relation, ...] = ()
    movements: tuple[Movement, ...] = ()
    coreferences: tuple[Coreference, ...] = ()
    unresolved_references: tuple[UnresolvedReference, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()


class ProjectKnowledgeGraphSnapshot(StrictModel):
    project_id: str = Field(min_length=1)
    snapshot_version: int = Field(ge=0)
    schema_version: Literal["project-knowledge-graph-snapshot-v2"]
    documents: tuple[Document, ...] = ()
    entities: Entities = Entities()
    relations: tuple[Relation, ...] = ()
    movements: tuple[Movement, ...] = ()
    coreferences: tuple[Coreference, ...] = ()
    unresolved_references: tuple[UnresolvedReference, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()

    @classmethod
    def empty(cls, project_id: str) -> "ProjectKnowledgeGraphSnapshot":
        return cls(
            project_id=project_id,
            snapshot_version=0,
            schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        )


class SceneAnalysisRequest(StrictModel):
    project_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    scene_revision: int = Field(ge=0)
    scene_sequence: int = Field(ge=0)
    text: str


class AnalyzedChunk(StrictModel):
    chunk_id: str
    ordinal: int = Field(ge=0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    text: str
    extraction: KnowledgeGraphOutput


class SceneAnalysis(StrictModel):
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    source_snapshot_version: int = Field(ge=0)
    chunks: tuple[AnalyzedChunk, ...]
