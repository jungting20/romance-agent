from dataclasses import dataclass

from apps.story_bible.domain.models import WorldEntryKind


@dataclass(frozen=True)
class CreateCharacterCommand:
    name: str
    gender: str
    age: str
    role: str
    personality: str
    prose_style: str
    dialogue_style: str
    desire: str
    hidden_feeling: str


@dataclass(frozen=True)
class UpdateCharacterCommand:
    name: str | None = None
    gender: str | None = None
    age: str | None = None
    role: str | None = None
    personality: str | None = None
    prose_style: str | None = None
    dialogue_style: str | None = None
    desire: str | None = None
    hidden_feeling: str | None = None


@dataclass(frozen=True)
class WorldEntryUpdate:
    id: str
    kind: WorldEntryKind
    title: str
    description: str


@dataclass(frozen=True)
class WorldEntryAddition:
    kind: WorldEntryKind
    title: str
    description: str


@dataclass(frozen=True)
class SaveWorldEntriesCommand:
    expected_revision: int
    updates: tuple[WorldEntryUpdate, ...]
    additions: tuple[WorldEntryAddition, ...]


@dataclass(frozen=True)
class FieldError:
    path: str
    message: str
