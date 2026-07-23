from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from apps.story_bible.domain.models import Character, StoryBible, WorldEntry
from apps.story_bible.service.commands import (
    CreateCharacterCommand,
    FieldError,
    SaveWorldEntriesCommand,
    UpdateCharacterCommand,
    WorldEntryAddition,
    WorldEntryUpdate,
)
from apps.story_bible.service.errors import (
    CharacterNotFoundError,
    InvalidCharacterError,
    InvalidWorldEntriesError,
    StoryBibleRevisionConflictError,
)
from apps.story_bible.service.models import StoryBibleSnapshot
from apps.story_bible.service.story_bible import StoryBibleService


def snapshot(*, revision: int = 1) -> StoryBibleSnapshot:
    return StoryBibleSnapshot(
        story_bible=StoryBible(
            project_id="silver-garden",
            characters=(
                Character(
                    id="silver-garden-character-1",
                    name="서윤",
                    role="protagonist",
                    desire="선택을 지키고 싶다.",
                    hidden_feeling="진심을 확인하고 싶다.",
                ),
            ),
            world_entries=(
                WorldEntry(
                    id="silver-garden-world-1",
                    kind="place",
                    title="비가 그친 온실",
                    description="마지막 만남의 장소",
                ),
                WorldEntry(
                    id="silver-garden-world-3",
                    kind="object",
                    title="은빛 반지",
                    description="오래된 약속",
                ),
            ),
        ),
        revision=revision,
    )


class RecordingRepository:
    def __init__(self, current: StoryBibleSnapshot | None = None) -> None:
        self.current = current or snapshot()
        self.replace_calls: list[tuple[str, int, StoryBible]] = []

    def get(self, project_id: str) -> StoryBibleSnapshot:
        return self.current

    def replace(
        self,
        project_id: str,
        expected_revision: int,
        story_bible: StoryBible,
    ) -> StoryBibleSnapshot:
        self.replace_calls.append((project_id, expected_revision, story_bible))
        if expected_revision != self.current.revision:
            raise StoryBibleRevisionConflictError
        self.current = StoryBibleSnapshot(story_bible=story_bible, revision=expected_revision + 1)
        return self.current

    def modify(
        self,
        project_id: str,
        transform: Callable[[StoryBible], StoryBible],
    ) -> StoryBibleSnapshot:
        self.current = StoryBibleSnapshot(
            story_bible=transform(self.current.story_bible),
            revision=self.current.revision + 1,
        )
        return self.current


def create_character_command(**changes: str) -> CreateCharacterCommand:
    values = {
        "name": "  민서  ",
        "gender": "여성",
        "age": "29세",
        "role": "서점 주인",
        "personality": "차분하다",
        "prose_style": "짧은 문장",
        "dialogue_style": "정중한 말투",
        "desire": "서점을 지키고 싶다",
        "hidden_feeling": "두렵다",
    }
    values.update(changes)
    return CreateCharacterCommand(**values)


def test_create_character_appends_once_with_unique_generated_id() -> None:
    repository = RecordingRepository()
    generated = iter(["silver-garden-character-1", "silver-garden-character-2"])
    service = StoryBibleService(
        repository,
        lambda _project_id: "unused-world-id",
        lambda _project_id: next(generated),
    )
    existing_world_entries = repository.current.story_bible.world_entries

    saved = service.create_character("silver-garden", create_character_command())

    assert saved.revision == 2
    assert [character.id for character in saved.story_bible.characters] == [
        "silver-garden-character-1",
        "silver-garden-character-2",
    ]
    assert saved.story_bible.characters[-1].name == "민서"
    assert saved.story_bible.characters[-1].age == "29세"
    assert saved.story_bible.world_entries is existing_world_entries


@pytest.mark.parametrize("name", ["", "  \n"])
def test_create_character_rejects_blank_name_without_modification(name: str) -> None:
    repository = RecordingRepository()

    with pytest.raises(InvalidCharacterError) as raised:
        StoryBibleService(
            repository,
            lambda _project_id: "world-id",
            lambda _project_id: "character-2",
        ).create_character("silver-garden", create_character_command(name=name))

    assert raised.value.field_errors == (FieldError("name", "인물 이름을 입력해 주세요."),)
    assert repository.current == snapshot()


def test_update_character_changes_only_supplied_fields() -> None:
    repository = RecordingRepository()
    service = StoryBibleService(
        repository, lambda _project_id: "unused", lambda _project_id: "unused"
    )
    original = repository.current.story_bible.characters[0]
    original_world_entries = repository.current.story_bible.world_entries

    saved = service.update_character(
        "silver-garden",
        original.id,
        UpdateCharacterCommand(name="  서윤 수정  ", age="31세", role=""),
    )

    updated = saved.story_bible.characters[0]
    assert saved.revision == 2
    assert updated.id == original.id
    assert updated.name == "서윤 수정"
    assert updated.age == "31세"
    assert updated.role == ""
    assert updated.desire == original.desire
    assert saved.story_bible.world_entries is original_world_entries


def test_update_character_rejects_empty_command_and_unknown_character() -> None:
    repository = RecordingRepository()
    service = StoryBibleService(
        repository, lambda _project_id: "unused", lambda _project_id: "unused"
    )

    with pytest.raises(InvalidCharacterError) as empty:
        service.update_character(
            "silver-garden", "silver-garden-character-1", UpdateCharacterCommand()
        )
    assert empty.value.field_errors == ()

    with pytest.raises(CharacterNotFoundError):
        service.update_character("silver-garden", "missing", UpdateCharacterCommand(role="조언자"))

    assert repository.current == snapshot()


def command(
    *,
    expected_revision: int = 1,
    updates: tuple[WorldEntryUpdate, ...] = (),
    additions: tuple[WorldEntryAddition, ...] = (),
) -> SaveWorldEntriesCommand:
    return SaveWorldEntriesCommand(
        expected_revision=expected_revision,
        updates=updates,
        additions=additions,
    )


def test_get_story_bible_delegates_to_repository() -> None:
    repository = RecordingRepository()

    result = StoryBibleService(
        repository,
        lambda _project_id: "unused",
        lambda _project_id: "unused",
    ).get_story_bible("silver-garden")

    assert result == snapshot()


def test_save_normalizes_updates_and_additions_without_mutating_omitted_entries() -> None:
    repository = RecordingRepository()
    service = StoryBibleService(
        repository,
        lambda _project_id: "silver-garden-world-2",
        lambda _project_id: "unused",
    )
    original_characters = repository.current.story_bible.characters
    original_omitted = repository.current.story_bible.world_entries[1]

    saved = service.save_world_entries(
        "silver-garden",
        command(
            updates=(
                WorldEntryUpdate(
                    id="silver-garden-world-1",
                    kind="place",
                    title="  비가 그친 유리 온실  ",
                    description="  마지막 만남의 장소  ",
                ),
            ),
            additions=(
                WorldEntryAddition(kind="rule", title=" 왕실의 서약 ", description=" 계승권 규칙 "),
            ),
        ),
    )

    assert saved.revision == 2
    assert saved.story_bible.characters is original_characters
    assert saved.story_bible.world_entries == (
        WorldEntry(
            id="silver-garden-world-1",
            kind="place",
            title="비가 그친 유리 온실",
            description="마지막 만남의 장소",
        ),
        original_omitted,
        WorldEntry(
            id="silver-garden-world-2",
            kind="rule",
            title="왕실의 서약",
            description="계승권 규칙",
        ),
    )
    assert repository.replace_calls == [("silver-garden", 1, saved.story_bible)]


def test_domain_and_command_values_are_immutable() -> None:
    entry = snapshot().story_bible.world_entries[0]

    with pytest.raises(FrozenInstanceError):
        entry.title = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        command(additions=(WorldEntryAddition("rule", "제목", "설명"),)).expected_revision = 2  # type: ignore[misc]


@pytest.mark.parametrize("expected_revision", [0, 2])
def test_save_rejects_lower_or_higher_revision_before_replace(expected_revision: int) -> None:
    repository = RecordingRepository()

    with pytest.raises(StoryBibleRevisionConflictError):
        StoryBibleService(
            repository,
            lambda _project_id: "unused",
            lambda _project_id: "unused",
        ).save_world_entries(
            "silver-garden",
            command(
                expected_revision=expected_revision,
                additions=(WorldEntryAddition("rule", "제목", "설명"),),
            ),
        )

    assert repository.replace_calls == []


@pytest.mark.parametrize(
    ("bad_command", "expected_errors"),
    [
        (
            command(),
            (
                FieldError("updates", "수정 또는 추가 항목을 한 개 이상 입력해 주세요."),
                FieldError("additions", "수정 또는 추가 항목을 한 개 이상 입력해 주세요."),
            ),
        ),
        (
            command(additions=(WorldEntryAddition("place", "  ", "설명"),)),
            (FieldError("additions[0].title", "제목을 입력해 주세요."),),
        ),
        (
            command(additions=(WorldEntryAddition("place", "제목", "\n "),)),
            (FieldError("additions[0].description", "설명을 입력해 주세요."),),
        ),
        (
            command(
                updates=(
                    WorldEntryUpdate("silver-garden-world-1", "place", "첫째", "설명"),
                    WorldEntryUpdate("silver-garden-world-1", "place", "둘째", "설명"),
                )
            ),
            (FieldError("updates[1].id", "수정 항목 식별자가 중복되었습니다."),),
        ),
        (
            command(updates=(WorldEntryUpdate("missing", "place", "제목", "설명"),)),
            (FieldError("updates[0].id", "현재 세계관에 존재하는 항목을 선택해 주세요."),),
        ),
    ],
)
def test_invalid_command_is_all_or_nothing(
    bad_command: SaveWorldEntriesCommand,
    expected_errors: tuple[FieldError, ...],
) -> None:
    repository = RecordingRepository()

    with pytest.raises(InvalidWorldEntriesError) as raised:
        StoryBibleService(
            repository,
            lambda _project_id: "unused",
            lambda _project_id: "unused",
        ).save_world_entries("silver-garden", bad_command)

    assert raised.value.field_errors == expected_errors
    assert repository.replace_calls == []
    assert repository.current == snapshot()


@pytest.mark.parametrize(
    ("addition", "expected_error"),
    [
        (
            WorldEntryAddition("place", "  ", "설명"),
            FieldError("additions[0].title", "제목을 입력해 주세요."),
        ),
        (
            WorldEntryAddition("place", "제목", "\n"),
            FieldError("additions[0].description", "설명을 입력해 주세요."),
        ),
    ],
)
def test_save_translates_domain_errors_to_existing_field_errors(
    addition: WorldEntryAddition,
    expected_error: FieldError,
) -> None:
    repository = RecordingRepository()

    with pytest.raises(InvalidWorldEntriesError) as raised:
        StoryBibleService(
            repository,
            lambda _project_id: "world-2",
            lambda _project_id: "unused",
        ).save_world_entries("silver-garden", command(additions=(addition,)))

    assert raised.value.message == "세계관 항목을 확인해 주세요."
    assert raised.value.field_errors == (expected_error,)
    assert repository.replace_calls == []


def test_save_accumulates_all_domain_field_errors_for_one_addition() -> None:
    repository = RecordingRepository()

    with pytest.raises(InvalidWorldEntriesError) as raised:
        StoryBibleService(
            repository,
            lambda _project_id: "world-2",
            lambda _project_id: "unused",
        ).save_world_entries(
            "silver-garden",
            command(additions=(WorldEntryAddition("place", "  ", "\n"),)),
        )

    assert raised.value.message == "세계관 항목을 확인해 주세요."
    assert raised.value.field_errors == (
        FieldError("additions[0].title", "제목을 입력해 주세요."),
        FieldError("additions[0].description", "설명을 입력해 주세요."),
    )
    assert repository.replace_calls == []


def test_invalid_addition_does_not_generate_an_id() -> None:
    repository = RecordingRepository()

    def fail_if_called(_project_id: str) -> str:
        raise AssertionError("ID generator must not run for invalid commands")

    with pytest.raises(InvalidWorldEntriesError) as raised:
        StoryBibleService(
            repository,
            fail_if_called,
            lambda _project_id: "unused",
        ).save_world_entries(
            "silver-garden",
            command(additions=(WorldEntryAddition("place", "  ", "설명"),)),
        )

    assert raised.value.message == "세계관 항목을 확인해 주세요."
    assert raised.value.field_errors == (FieldError("additions[0].title", "제목을 입력해 주세요."),)
    assert repository.replace_calls == []


def test_generated_ids_avoid_existing_and_same_command_collisions() -> None:
    repository = RecordingRepository()
    generated = iter(
        [
            "silver-garden-world-1",
            "silver-garden-world-3",
            "silver-garden-world-2",
            "silver-garden-world-2",
            "silver-garden-world-4",
        ]
    )
    service = StoryBibleService(
        repository,
        lambda _project_id: next(generated),
        lambda _project_id: "unused",
    )

    saved = service.save_world_entries(
        "silver-garden",
        command(
            additions=(
                WorldEntryAddition("rule", "첫째", "설명"),
                WorldEntryAddition("object", "둘째", "설명"),
            )
        ),
    )

    assert [entry.id for entry in saved.story_bible.world_entries] == [
        "silver-garden-world-1",
        "silver-garden-world-3",
        "silver-garden-world-2",
        "silver-garden-world-4",
    ]
