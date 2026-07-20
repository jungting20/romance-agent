from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

WorldEntryKind = Literal["place", "object", "rule"]


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    role: Literal["protagonist"]
    desire: str
    hidden_feeling: str


@dataclass(frozen=True)
class WorldEntry:
    id: str
    kind: WorldEntryKind
    title: str
    description: str


@dataclass(frozen=True)
class StoryBible:
    project_id: str
    characters: tuple[Character, ...]
    world_entries: tuple[WorldEntry, ...]


@dataclass(frozen=True)
class StoryBibleSnapshot:
    story_bible: StoryBible
    revision: int


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


class StoryBibleNotFoundError(Exception):
    """The requested project's Story Bible does not exist."""


class StoryBibleRevisionConflictError(Exception):
    """The expected revision does not exactly match the stored revision."""


class InvalidWorldEntriesError(Exception):
    def __init__(self, message: str, field_errors: tuple[FieldError, ...]) -> None:
        super().__init__(message)
        self.message = message
        self.field_errors = field_errors


class StoryBiblePersistenceError(Exception):
    """Stored Story Bible data cannot be safely read or written."""


class StoryBibleRepository(Protocol):
    def get(self, project_id: str) -> StoryBibleSnapshot: ...

    def replace(
        self,
        project_id: str,
        expected_revision: int,
        story_bible: StoryBible,
    ) -> StoryBibleSnapshot: ...


class StoryBibleService:
    def __init__(
        self,
        repository: StoryBibleRepository,
        world_entry_id_factory: Callable[[str], str],
    ) -> None:
        self._repository = repository
        self._world_entry_id_factory = world_entry_id_factory

    def get_story_bible(self, project_id: str) -> StoryBibleSnapshot:
        return self._repository.get(project_id)

    def save_world_entries(
        self,
        project_id: str,
        command: SaveWorldEntriesCommand,
    ) -> StoryBibleSnapshot:
        current = self._repository.get(project_id)
        if command.expected_revision != current.revision:
            raise StoryBibleRevisionConflictError

        normalized_updates, normalized_additions = self._validate_and_normalize(
            command, current.story_bible
        )
        updates_by_id = {update.id: update for update in normalized_updates}
        entries = tuple(
            (
                WorldEntry(
                    id=entry.id,
                    kind=update.kind,
                    title=update.title,
                    description=update.description,
                )
                if (update := updates_by_id.get(entry.id)) is not None
                else entry
            )
            for entry in current.story_bible.world_entries
        )

        used_ids = {entry.id for entry in entries}
        added_entries: list[WorldEntry] = []
        for addition in normalized_additions:
            new_id = self._next_unique_id(project_id, used_ids)
            used_ids.add(new_id)
            added_entries.append(
                WorldEntry(
                    id=new_id,
                    kind=addition.kind,
                    title=addition.title,
                    description=addition.description,
                )
            )

        replacement = StoryBible(
            project_id=current.story_bible.project_id,
            characters=current.story_bible.characters,
            world_entries=entries + tuple(added_entries),
        )
        return self._repository.replace(
            project_id, command.expected_revision, replacement
        )

    def _next_unique_id(self, project_id: str, used_ids: set[str]) -> str:
        while (candidate := self._world_entry_id_factory(project_id)) in used_ids:
            pass
        return candidate

    @staticmethod
    def _validate_and_normalize(
        command: SaveWorldEntriesCommand,
        story_bible: StoryBible,
    ) -> tuple[tuple[WorldEntryUpdate, ...], tuple[WorldEntryAddition, ...]]:
        if not command.updates and not command.additions:
            raise InvalidWorldEntriesError(
                "수정하거나 추가할 세계관 항목이 필요합니다.",
                (
                    FieldError(
                        "updates", "수정 또는 추가 항목을 한 개 이상 입력해 주세요."
                    ),
                    FieldError(
                        "additions", "수정 또는 추가 항목을 한 개 이상 입력해 주세요."
                    ),
                ),
            )

        field_errors: list[FieldError] = []
        normalized_updates: list[WorldEntryUpdate] = []
        normalized_additions: list[WorldEntryAddition] = []
        seen_update_ids: set[str] = set()
        existing_ids = {entry.id for entry in story_bible.world_entries}

        for index, update in enumerate(command.updates):
            title = update.title.strip()
            description = update.description.strip()
            if not title:
                field_errors.append(
                    FieldError(f"updates[{index}].title", "제목을 입력해 주세요.")
                )
            if not description:
                field_errors.append(
                    FieldError(f"updates[{index}].description", "설명을 입력해 주세요.")
                )
            if update.id in seen_update_ids:
                field_errors.append(
                    FieldError(
                        f"updates[{index}].id", "수정 항목 식별자가 중복되었습니다."
                    )
                )
            elif update.id not in existing_ids:
                field_errors.append(
                    FieldError(
                        f"updates[{index}].id",
                        "현재 세계관에 존재하는 항목을 선택해 주세요.",
                    )
                )
            seen_update_ids.add(update.id)
            normalized_updates.append(
                WorldEntryUpdate(update.id, update.kind, title, description)
            )

        for index, addition in enumerate(command.additions):
            title = addition.title.strip()
            description = addition.description.strip()
            if not title:
                field_errors.append(
                    FieldError(f"additions[{index}].title", "제목을 입력해 주세요.")
                )
            if not description:
                field_errors.append(
                    FieldError(
                        f"additions[{index}].description", "설명을 입력해 주세요."
                    )
                )
            normalized_additions.append(
                WorldEntryAddition(addition.kind, title, description)
            )

        if field_errors:
            if any("중복" in error.message for error in field_errors):
                message = "같은 세계관 항목을 두 번 수정할 수 없습니다."
            elif any("현재 세계관" in error.message for error in field_errors):
                message = "수정할 세계관 항목을 찾을 수 없습니다."
            else:
                message = "세계관 항목을 확인해 주세요."
            raise InvalidWorldEntriesError(message, tuple(field_errors))

        return tuple(normalized_updates), tuple(normalized_additions)
