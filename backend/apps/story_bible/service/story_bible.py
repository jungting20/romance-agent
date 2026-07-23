from apps.story_bible.domain.errors import InvalidDomainValueError
from apps.story_bible.domain.models import (
    Character,
    StoryBible,
    WorldEntry,
    WorldEntryKind,
)
from apps.story_bible.service.commands import (
    CreateCharacterCommand,
    FieldError,
    SaveWorldEntriesCommand,
    UpdateCharacterCommand,
)
from apps.story_bible.service.errors import (
    CharacterNotFoundError,
    InvalidCharacterError,
    InvalidWorldEntriesError,
    StoryBibleRevisionConflictError,
)
from apps.story_bible.service.models import StoryBibleSnapshot
from apps.story_bible.service.ports import (
    CharacterIdGenerator,
    StoryBibleRepository,
    WorldEntryIdGenerator,
)

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
        character_id_factory: CharacterIdGenerator,
    ) -> None:
        self._repository = repository
        self._world_entry_id_factory = world_entry_id_factory
        self._character_id_factory = character_id_factory

    def get_story_bible(self, project_id: str) -> StoryBibleSnapshot:
        return self._repository.get(project_id)

    def create_character(
        self,
        project_id: str,
        command: CreateCharacterCommand,
    ) -> StoryBibleSnapshot:
        values = self._validated_character_values(command)

        def add_to_latest(story_bible: StoryBible) -> StoryBible:
            used_ids = {character.id for character in story_bible.characters}
            character_id = self._next_unique_character_id(project_id, used_ids)
            return story_bible.add_character(Character(id=character_id, **values))

        return self._repository.modify(project_id, add_to_latest)

    def update_character(
        self,
        project_id: str,
        character_id: str,
        command: UpdateCharacterCommand,
    ) -> StoryBibleSnapshot:
        if all(value is None for value in command.__dict__.values()):
            raise InvalidCharacterError("수정할 인물 정보가 필요합니다.", ())
        if command.name is not None and not command.name.strip():
            raise InvalidCharacterError(
                "인물 정보를 확인해 주세요.",
                (FieldError("name", "인물 이름을 입력해 주세요."),),
            )

        def update_latest(story_bible: StoryBible) -> StoryBible:
            current = next(
                (character for character in story_bible.characters if character.id == character_id),
                None,
            )
            if current is None:
                raise CharacterNotFoundError
            updated = Character(
                id=current.id,
                name=current.name if command.name is None else command.name,
                gender=current.gender if command.gender is None else command.gender,
                age=current.age if command.age is None else command.age,
                role=current.role if command.role is None else command.role,
                personality=(
                    current.personality if command.personality is None else command.personality
                ),
                prose_style=(
                    current.prose_style if command.prose_style is None else command.prose_style
                ),
                dialogue_style=(
                    current.dialogue_style
                    if command.dialogue_style is None
                    else command.dialogue_style
                ),
                desire=current.desire if command.desire is None else command.desire,
                hidden_feeling=(
                    current.hidden_feeling
                    if command.hidden_feeling is None
                    else command.hidden_feeling
                ),
            )
            return story_bible.update_character(updated)

        return self._repository.modify(project_id, update_latest)

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
                    FieldError("updates", "수정 또는 추가 항목을 한 개 이상 입력해 주세요."),
                    FieldError("additions", "수정 또는 추가 항목을 한 개 이상 입력해 주세요."),
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
                    FieldError(f"updates[{index}].id", "수정 항목 식별자가 중복되었습니다.")
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
        return self._repository.replace(project_id, command.expected_revision, replacement)

    def _next_unique_id(self, project_id: str, used_ids: set[str]) -> str:
        while (candidate := self._world_entry_id_factory(project_id)) in used_ids:
            pass
        return candidate

    def _next_unique_character_id(self, project_id: str, used_ids: set[str]) -> str:
        while (candidate := self._character_id_factory(project_id)) in used_ids:
            pass
        return candidate

    @staticmethod
    def _validated_character_values(command: CreateCharacterCommand) -> dict[str, str]:
        try:
            character = Character(
                id="validation-id",
                name=command.name,
                gender=command.gender,
                age=command.age,
                role=command.role,
                personality=command.personality,
                prose_style=command.prose_style,
                dialogue_style=command.dialogue_style,
                desire=command.desire,
                hidden_feeling=command.hidden_feeling,
            )
        except InvalidDomainValueError as error:
            if error.field == "name":
                raise InvalidCharacterError(
                    "인물 정보를 확인해 주세요.",
                    (FieldError("name", "인물 이름을 입력해 주세요."),),
                ) from error
            raise
        return {
            "name": character.name,
            "gender": character.gender,
            "age": character.age,
            "role": character.role,
            "personality": character.personality,
            "prose_style": character.prose_style,
            "dialogue_style": character.dialogue_style,
            "desire": character.desire,
            "hidden_feeling": character.hidden_feeling,
        }

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
