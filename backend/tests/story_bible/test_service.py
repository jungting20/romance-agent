from dataclasses import FrozenInstanceError

import pytest

from apps.story_bible.domain.models import Character, StoryBible, WorldEntry
from apps.story_bible.service.commands import (
    FieldError,
    SaveWorldEntriesCommand,
    WorldEntryAddition,
    WorldEntryUpdate,
)
from apps.story_bible.service.errors import (
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

    result = StoryBibleService(repository, lambda _project_id: "unused").get_story_bible(
        "silver-garden"
    )

    assert result == snapshot()


def test_save_normalizes_updates_and_additions_without_mutating_omitted_entries() -> None:
    repository = RecordingRepository()
    service = StoryBibleService(repository, lambda _project_id: "silver-garden-world-2")
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
        StoryBibleService(repository, lambda _project_id: "unused").save_world_entries(
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
        StoryBibleService(repository, lambda _project_id: "unused").save_world_entries(
            "silver-garden", bad_command
        )

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
        StoryBibleService(repository, lambda _project_id: "world-2").save_world_entries(
            "silver-garden", command(additions=(addition,))
        )

    assert raised.value.message == "세계관 항목을 확인해 주세요."
    assert raised.value.field_errors == (expected_error,)
    assert repository.replace_calls == []


def test_save_accumulates_all_domain_field_errors_for_one_addition() -> None:
    repository = RecordingRepository()

    with pytest.raises(InvalidWorldEntriesError) as raised:
        StoryBibleService(repository, lambda _project_id: "world-2").save_world_entries(
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
        StoryBibleService(repository, fail_if_called).save_world_entries(
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
    service = StoryBibleService(repository, lambda _project_id: next(generated))

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
