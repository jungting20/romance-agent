from dataclasses import dataclass

from apps.story_bible.domain.models import WorldEntryKind


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
