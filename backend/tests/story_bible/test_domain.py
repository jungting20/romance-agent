import pytest

from apps.story_bible.domain.errors import (
    CharacterNotFoundError,
    InvalidDomainValueError,
    WorldEntryChangeError,
)
from apps.story_bible.domain.models import Character, StoryBible, WorldEntry


def character(identifier: str = "character-1") -> Character:
    return Character(identifier, "서윤", "protagonist", "욕망", "숨은 감정")


def entry(identifier: str = "world-1") -> WorldEntry:
    return WorldEntry(identifier, "place", " 온실 ", " 마지막 만남의 장소 ")


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (lambda: character(""), "id"),
        (lambda: Character("character-1", "", "protagonist", "", ""), "name"),
        (lambda: WorldEntry("", "place", "제목", "설명"), "id"),
        (lambda: WorldEntry("world-1", "invalid", "제목", "설명"), "kind"),
        (lambda: WorldEntry("world-1", "place", "  ", "설명"), "title"),
        (lambda: WorldEntry("world-1", "place", "제목", "\n"), "description"),
        (lambda: StoryBible("", (), ()), "project_id"),
    ],
)
def test_domain_values_reject_invalid_fields(factory: object, field: str) -> None:
    with pytest.raises(InvalidDomainValueError) as raised:
        factory()  # type: ignore[operator]

    assert raised.value.field == field


def test_world_entry_normalizes_owned_text() -> None:
    result = entry()

    assert result.title == "온실"
    assert result.description == "마지막 만남의 장소"


def test_character_normalizes_name_and_allows_empty_optional_strings() -> None:
    result = Character("character-1", "  서윤  ", "", "", "")

    assert result.name == "서윤"
    assert result.gender == ""
    assert result.age == ""
    assert result.personality == ""
    assert result.prose_style == ""
    assert result.dialogue_style == ""


def test_add_and_update_character_preserve_identity_order_and_world_entries() -> None:
    first = character()
    world_entries = (entry(),)
    current = StoryBible("project-1", (first,), world_entries)
    added = Character("character-2", "민서", "조언자", "목표", "감정")

    with_added = current.add_character(added)
    updated = Character("character-1", "서윤 수정", "주인공", "새 욕망", "새 감정")
    result = with_added.update_character(updated)

    assert result.characters == (updated, added)
    assert result.world_entries is world_entries
    assert first.id == result.characters[0].id


def test_update_character_rejects_unknown_identity() -> None:
    current = StoryBible("project-1", (character(),), ())

    with pytest.raises(CharacterNotFoundError):
        current.update_character(Character("missing", "민서", "", "", ""))


def test_story_bible_rejects_duplicate_character_ids() -> None:
    with pytest.raises(InvalidDomainValueError) as raised:
        StoryBible("project-1", (character(), character()), ())

    assert raised.value.field == "characters"


def test_story_bible_rejects_duplicate_world_entry_ids() -> None:
    with pytest.raises(InvalidDomainValueError) as raised:
        StoryBible("project-1", (), (entry(), entry()))

    assert raised.value.field == "world_entries"


def test_apply_changes_preserves_omitted_state_and_order() -> None:
    omitted = WorldEntry("world-2", "object", "반지", "약속의 증표")
    current = StoryBible("project-1", (character(),), (entry(), omitted))
    updated = WorldEntry("world-1", "rule", "새 규칙", "새 설명")
    added = WorldEntry("world-3", "place", "정원", "재회의 장소")

    result = current.apply_world_entry_changes(updates=(updated,), additions=(added,))

    assert result.characters is current.characters
    assert result.world_entries == (updated, omitted, added)
    assert current.world_entries == (entry(), omitted)


@pytest.mark.parametrize(
    ("updates", "additions", "reason"),
    [
        ((entry(), entry()), (), "duplicate_update"),
        ((WorldEntry("missing", "place", "제목", "설명"),), (), "unknown_update"),
        ((), (entry(),), "addition_id_conflict"),
    ],
)
def test_apply_changes_rejects_invalid_identifiers(
    updates: tuple[WorldEntry, ...],
    additions: tuple[WorldEntry, ...],
    reason: str,
) -> None:
    current = StoryBible("project-1", (character(),), (entry(),))

    with pytest.raises(WorldEntryChangeError) as raised:
        current.apply_world_entry_changes(updates=updates, additions=additions)

    assert raised.value.reason == reason
    assert current.world_entries == (entry(),)
