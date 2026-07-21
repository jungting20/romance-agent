from apps.story_bible.domain.errors import InvalidDomainValueError
from apps.story_bible.domain.models import WorldEntry, WorldEntryKind
from apps.story_bible.service.commands import FieldError, SaveWorldEntriesCommand
from apps.story_bible.service.errors import (
    InvalidWorldEntriesError,
    StoryBibleRevisionConflictError,
)
from apps.story_bible.service.models import StoryBibleSnapshot
from apps.story_bible.service.ports import StoryBibleRepository, WorldEntryIdGenerator

_FIELD_MESSAGES = {
    "id": "수정할 세계관 항목을 선택해 주세요.",
    "kind": "세계관 항목 종류를 확인해 주세요.",
    "title": "제목을 입력해 주세요.",
    "description": "설명을 입력해 주세요.",
}


class StoryBibleService:
    def __init__(
        self,
        repository: StoryBibleRepository,
        world_entry_id_factory: WorldEntryIdGenerator,
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
        validated_updates: list[WorldEntry] = []
        seen_update_ids: set[str] = set()
        existing_ids = {entry.id for entry in current.story_bible.world_entries}

        for index, update in enumerate(command.updates):
            validated = self._validate_world_entry(
                path=f"updates[{index}]",
                entry_id=update.id,
                kind=update.kind,
                title=update.title,
                description=update.description,
                field_errors=field_errors,
            )
            if validated is not None:
                validated_updates.append(validated)
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

        validated_addition_values: list[WorldEntry] = []
        for index, addition in enumerate(command.additions):
            validated = self._validate_world_entry(
                path=f"additions[{index}]",
                entry_id="validation-id",
                kind=addition.kind,
                title=addition.title,
                description=addition.description,
                field_errors=field_errors,
            )
            if validated is not None:
                validated_addition_values.append(validated)

        if field_errors:
            if any("중복" in error.message for error in field_errors):
                message = "같은 세계관 항목을 두 번 수정할 수 없습니다."
            elif any("현재 세계관" in error.message for error in field_errors):
                message = "수정할 세계관 항목을 찾을 수 없습니다."
            else:
                message = "세계관 항목을 확인해 주세요."
            raise InvalidWorldEntriesError(message, tuple(field_errors))

        validated_additions: list[WorldEntry] = []
        used_ids = set(existing_ids)
        for addition in validated_addition_values:
            new_id = self._next_unique_id(project_id, used_ids)
            validated_additions.append(
                WorldEntry(
                    id=new_id,
                    kind=addition.kind,
                    title=addition.title,
                    description=addition.description,
                )
            )
            used_ids.add(new_id)

        replacement = current.story_bible.apply_world_entry_changes(
            updates=tuple(validated_updates),
            additions=tuple(validated_additions),
        )
        return self._repository.replace(
            project_id, command.expected_revision, replacement
        )

    def _next_unique_id(self, project_id: str, used_ids: set[str]) -> str:
        while (candidate := self._world_entry_id_factory(project_id)) in used_ids:
            pass
        return candidate

    @staticmethod
    def _validate_world_entry(
        *,
        path: str,
        entry_id: str,
        kind: WorldEntryKind,
        title: str,
        description: str,
        field_errors: list[FieldError],
    ) -> WorldEntry | None:
        candidate_id = entry_id
        candidate_kind = kind
        candidate_title = title
        candidate_description = description
        is_valid = True

        while True:
            try:
                entry = WorldEntry(
                    id=candidate_id,
                    kind=candidate_kind,
                    title=candidate_title,
                    description=candidate_description,
                )
            except InvalidDomainValueError as error:
                is_valid = False
                field_errors.append(
                    FieldError(
                        f"{path}.{error.field}",
                        _FIELD_MESSAGES[error.field],
                    )
                )
                if error.field == "id":
                    candidate_id = "validation-id"
                elif error.field == "kind":
                    candidate_kind = "place"
                elif error.field == "title":
                    candidate_title = "validation-title"
                elif error.field == "description":
                    candidate_description = "validation-description"
                continue
            return entry if is_valid else None
