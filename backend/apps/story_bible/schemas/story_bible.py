from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

NonemptyString = Annotated[StrictStr, Field(min_length=1)]
PositiveInteger = Annotated[StrictInt, Field(ge=1)]
WorldEntryKind = Literal["place", "object", "rule"]


class CharacterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonemptyString
    name: NonemptyString
    gender: StrictStr
    age: StrictStr
    role: StrictStr
    personality: StrictStr
    prose_style: StrictStr = Field(alias="proseStyle")
    dialogue_style: StrictStr = Field(alias="dialogueStyle")
    desire: StrictStr
    hidden_feeling: StrictStr = Field(alias="hiddenFeeling")


class CreateCharacterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    gender: StrictStr
    age: StrictStr
    role: StrictStr
    personality: StrictStr
    prose_style: StrictStr = Field(alias="proseStyle")
    dialogue_style: StrictStr = Field(alias="dialogueStyle")
    desire: StrictStr
    hidden_feeling: StrictStr = Field(alias="hiddenFeeling")


class UpdateCharacterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr = Field(default_factory=lambda: None)
    gender: StrictStr = Field(default_factory=lambda: None)
    age: StrictStr = Field(default_factory=lambda: None)
    role: StrictStr = Field(default_factory=lambda: None)
    personality: StrictStr = Field(default_factory=lambda: None)
    prose_style: StrictStr = Field(default_factory=lambda: None, alias="proseStyle")
    dialogue_style: StrictStr = Field(default_factory=lambda: None, alias="dialogueStyle")
    desire: StrictStr = Field(default_factory=lambda: None)
    hidden_feeling: StrictStr = Field(default_factory=lambda: None, alias="hiddenFeeling")


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
        "PROJECT_NOT_FOUND",
        "STORY_BIBLE_NOT_FOUND",
        "CHARACTER_NOT_FOUND",
        "STORY_BIBLE_REVISION_CONFLICT",
        "INVALID_CHARACTER",
        "INVALID_WORLD_ENTRIES",
        "INTERNAL_ERROR",
    ]
    message: NonemptyString
    field_errors: tuple[FieldErrorResponse, ...] = Field(alias="fieldErrors")
