import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from apps.story_bible.repository import story_bible as repository_module
from apps.story_bible.repository.story_bible import FileStoryBibleRepository
from apps.story_bible.service.story_bible import (
    Character,
    StoryBible,
    StoryBibleNotFoundError,
    StoryBiblePersistenceError,
    StoryBibleRevisionConflictError,
    WorldEntry,
)


def story_bible(*, title: str = "비가 그친 온실") -> StoryBible:
    return StoryBible(
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
                title=title,
                description="마지막 만남의 장소",
            ),
        ),
    )


def story_bible_path(root: Path, project_id: str = "silver-garden") -> Path:
    return root / "projects" / project_id / "story-bible.json"


def write_story_bible(root: Path, *, revision: int = 1) -> Path:
    path = story_bible_path(root)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "storyBibleRevision": revision,
                "storyBible": {
                    "projectId": "silver-garden",
                    "characters": [
                        {
                            "id": "silver-garden-character-1",
                            "name": "서윤",
                            "role": "protagonist",
                            "desire": "선택을 지키고 싶다.",
                            "hiddenFeeling": "진심을 확인하고 싶다.",
                        }
                    ],
                    "worldEntries": [
                        {
                            "id": "silver-garden-world-1",
                            "kind": "place",
                            "title": "비가 그친 온실",
                            "description": "마지막 만남의 장소",
                        }
                    ],
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def test_get_reloads_durable_envelope_in_a_new_repository(tmp_path: Path) -> None:
    write_story_bible(tmp_path)

    first = FileStoryBibleRepository(tmp_path).get("silver-garden")
    second = FileStoryBibleRepository(tmp_path).get("silver-garden")

    assert first == second
    assert first.revision == 1
    assert first.story_bible == story_bible()


def test_missing_story_bible_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(StoryBibleNotFoundError):
        FileStoryBibleRepository(tmp_path).get("silver-garden")


@pytest.mark.parametrize(
    "document",
    [
        "not-json",
        json.dumps({"schemaVersion": 2, "storyBibleRevision": 1, "storyBible": {}}),
        json.dumps({"schemaVersion": 1, "storyBibleRevision": 0, "storyBible": {}}),
        json.dumps(
            {
                "schemaVersion": 1,
                "storyBibleRevision": 1,
                "storyBible": {
                    "projectId": "other",
                    "characters": [],
                    "worldEntries": [],
                },
            }
        ),
    ],
)
def test_malformed_or_unsupported_envelope_is_a_persistence_error(
    tmp_path: Path, document: str
) -> None:
    path = story_bible_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(document, encoding="utf-8")

    with pytest.raises(StoryBiblePersistenceError):
        FileStoryBibleRepository(tmp_path).get("silver-garden")


@pytest.mark.parametrize("project_id", ["../outside", "../../escape", "/tmp/absolute"])
def test_project_id_cannot_escape_data_root(tmp_path: Path, project_id: str) -> None:
    with pytest.raises(StoryBiblePersistenceError):
        FileStoryBibleRepository(tmp_path).get(project_id)


@pytest.mark.parametrize("expected_revision", [0, 2])
def test_replace_requires_exact_revision_and_preserves_bytes(
    tmp_path: Path, expected_revision: int
) -> None:
    path = write_story_bible(tmp_path)
    original = path.read_bytes()

    with pytest.raises(StoryBibleRevisionConflictError):
        FileStoryBibleRepository(tmp_path).replace(
            "silver-garden", expected_revision, story_bible(title="변경")
        )

    assert path.read_bytes() == original


def test_replace_writes_expected_envelope_and_reloads(tmp_path: Path) -> None:
    write_story_bible(tmp_path)
    repository = FileStoryBibleRepository(tmp_path)

    saved = repository.replace("silver-garden", 1, story_bible(title="유리 온실"))

    assert saved.revision == 2
    assert FileStoryBibleRepository(tmp_path).get("silver-garden") == saved
    document = json.loads(story_bible_path(tmp_path).read_text(encoding="utf-8"))
    assert document == {
        "schemaVersion": 1,
        "storyBibleRevision": 2,
        "storyBible": {
            "projectId": "silver-garden",
            "characters": [
                {
                    "id": "silver-garden-character-1",
                    "name": "서윤",
                    "role": "protagonist",
                    "desire": "선택을 지키고 싶다.",
                    "hiddenFeeling": "진심을 확인하고 싶다.",
                }
            ],
            "worldEntries": [
                {
                    "id": "silver-garden-world-1",
                    "kind": "place",
                    "title": "유리 온실",
                    "description": "마지막 만남의 장소",
                }
            ],
        },
    }


def test_replace_uses_same_directory_temp_flush_fsync_and_atomic_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = write_story_bible(tmp_path)
    calls: list[tuple[str, object]] = []
    real_named_temporary_file = repository_module.tempfile.NamedTemporaryFile
    real_fsync = repository_module.os.fsync
    real_replace = repository_module.os.replace

    def recording_temp(*args: object, **kwargs: object):
        calls.append(("temp_dir", kwargs.get("dir")))
        return real_named_temporary_file(*args, **kwargs)

    def recording_fsync(file_descriptor: int) -> None:
        calls.append(("fsync", file_descriptor))
        real_fsync(file_descriptor)

    def recording_replace(source: str | Path, destination: str | Path) -> None:
        calls.append(("replace", (Path(source).parent, Path(destination))))
        real_replace(source, destination)

    monkeypatch.setattr(repository_module.tempfile, "NamedTemporaryFile", recording_temp)
    monkeypatch.setattr(repository_module.os, "fsync", recording_fsync)
    monkeypatch.setattr(repository_module.os, "replace", recording_replace)

    FileStoryBibleRepository(tmp_path).replace("silver-garden", 1, story_bible(title="변경"))

    assert ("temp_dir", canonical.parent) in calls
    assert any(name == "fsync" for name, _value in calls)
    assert ("replace", (canonical.parent, canonical)) in calls


@pytest.mark.parametrize("failure_point", ["serialize", "replace"])
def test_failed_write_cleans_owned_temp_and_preserves_canonical_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    canonical = write_story_bible(tmp_path)
    original = canonical.read_bytes()

    if failure_point == "serialize":

        def fail_dump(*_args: object, **_kwargs: object) -> None:
            raise TypeError("serialization failed")

        monkeypatch.setattr(repository_module.json, "dump", fail_dump)
    else:

        def fail_replace(*_args: object, **_kwargs: object) -> None:
            raise OSError("replace failed")

        monkeypatch.setattr(repository_module.os, "replace", fail_replace)

    with pytest.raises(StoryBiblePersistenceError):
        FileStoryBibleRepository(tmp_path).replace("silver-garden", 1, story_bible(title="변경"))

    assert canonical.read_bytes() == original
    assert list(canonical.parent.glob(".story-bible.*.tmp")) == []


def test_project_lock_allows_only_one_concurrent_replace(tmp_path: Path) -> None:
    write_story_bible(tmp_path)
    barrier = threading.Barrier(2)

    def replace(title: str) -> str:
        barrier.wait()
        try:
            FileStoryBibleRepository(tmp_path).replace("silver-garden", 1, story_bible(title=title))
        except StoryBibleRevisionConflictError:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(replace, ["첫째", "둘째"]))

    assert sorted(outcomes) == ["conflict", "saved"]
    assert FileStoryBibleRepository(tmp_path).get("silver-garden").revision == 2
