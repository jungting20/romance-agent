from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

NonemptyString = Annotated[StrictStr, Field(min_length=1)]
PositiveInteger = Annotated[StrictInt, Field(ge=1)]
WorldEntryKind = Literal["place", "object", "rule"]


class CharacterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonemptyString
    name: NonemptyString
    role: Literal["protagonist"]
    desire: StrictStr
    hidden_feeling: StrictStr = Field(alias="hiddenFeeling")


class WorldEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonemptyString
    kind: WorldEntryKind
    title: NonemptyString
    description: NonemptyString


class StoryBibleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: NonemptyString = Field(alias="projectId")
    characters: tuple[CharacterResponse, ...]
    world_entries: tuple[WorldEntryResponse, ...] = Field(alias="worldEntries")


class StoryBibleSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_bible: StoryBibleResponse = Field(alias="storyBible")
    story_bible_revision: PositiveInteger = Field(alias="storyBibleRevision")


class WorldEntryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonemptyString
    kind: WorldEntryKind
    title: StrictStr
    description: StrictStr


class WorldEntryAdditionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: WorldEntryKind
    title: StrictStr
    description: StrictStr


class SaveWorldEntriesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: PositiveInteger = Field(alias="expectedRevision")
    updates: tuple[WorldEntryUpdateRequest, ...]
    additions: tuple[WorldEntryAdditionRequest, ...]


class FieldErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: NonemptyString
    message: NonemptyString


class ApiErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "MALFORMED_REQUEST",
        "STORY_BIBLE_NOT_FOUND",
        "STORY_BIBLE_REVISION_CONFLICT",
        "INVALID_WORLD_ENTRIES",
        "INTERNAL_ERROR",
    ]
    message: NonemptyString
    field_errors: tuple[FieldErrorResponse, ...] = Field(alias="fieldErrors")
