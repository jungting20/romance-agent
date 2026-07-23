from dataclasses import dataclass
from typing import Literal

from apps.story_bible.domain.errors import (
    CharacterNotFoundError,
    InvalidDomainValueError,
    WorldEntryChangeError,
)

WorldEntryKind = Literal["place", "object", "rule"]


def _require_nonempty(value: str, field: str) -> None:
    if not value:
        raise InvalidDomainValueError(field, f"{field} must not be empty")


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    role: str
    desire: str
    hidden_feeling: str
    gender: str = ""
    age: str = ""
    personality: str = ""
    prose_style: str = ""
    dialogue_style: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.id, "id")
        name = self.name.strip()
        if not name:
            raise InvalidDomainValueError("name", "Character name must not be blank")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True)
class WorldEntry:
    id: str
    kind: WorldEntryKind
    title: str
    description: str

    def __post_init__(self) -> None:
        _require_nonempty(self.id, "id")
        if self.kind not in {"place", "object", "rule"}:
            raise InvalidDomainValueError("kind", "Unsupported world entry kind")
        title = self.title.strip()
        description = self.description.strip()
        if not title:
            raise InvalidDomainValueError("title", "World entry title must not be blank")
        if not description:
            raise InvalidDomainValueError(
                "description", "World entry description must not be blank"
            )
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)


@dataclass(frozen=True)
class StoryBible:
    project_id: str
    characters: tuple[Character, ...]
    world_entries: tuple[WorldEntry, ...]

    def __post_init__(self) -> None:
        _require_nonempty(self.project_id, "project_id")
        if len({item.id for item in self.characters}) != len(self.characters):
            raise InvalidDomainValueError("characters", "Character IDs must be unique")
        if len({item.id for item in self.world_entries}) != len(self.world_entries):
            raise InvalidDomainValueError("world_entries", "World entry IDs must be unique")

    def apply_world_entry_changes(
        self,
        *,
        updates: tuple[WorldEntry, ...],
        additions: tuple[WorldEntry, ...],
    ) -> "StoryBible":
        updates_by_id = {item.id: item for item in updates}
        if len(updates_by_id) != len(updates):
            duplicate = next(
                item.id for item in updates if sum(value.id == item.id for value in updates) > 1
            )
            raise WorldEntryChangeError("duplicate_update", duplicate)
        existing_ids = {item.id for item in self.world_entries}
        unknown = next((item.id for item in updates if item.id not in existing_ids), None)
        if unknown is not None:
            raise WorldEntryChangeError("unknown_update", unknown)
        used_ids = set(existing_ids)
        for addition in additions:
            if addition.id in used_ids:
                raise WorldEntryChangeError("addition_id_conflict", addition.id)
            used_ids.add(addition.id)
        entries = tuple(updates_by_id.get(item.id, item) for item in self.world_entries)
        return StoryBible(self.project_id, self.characters, entries + additions)

    def add_character(self, character: Character) -> "StoryBible":
        if any(item.id == character.id for item in self.characters):
            raise InvalidDomainValueError("id", "Character ID must be unique")
        return StoryBible(
            self.project_id,
            self.characters + (character,),
            self.world_entries,
        )

    def update_character(self, character: Character) -> "StoryBible":
        if not any(item.id == character.id for item in self.characters):
            raise CharacterNotFoundError(character.id)
        return StoryBible(
            self.project_id,
            tuple(character if item.id == character.id else item for item in self.characters),
            self.world_entries,
        )
