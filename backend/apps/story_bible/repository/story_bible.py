import fcntl
import json
import os
import tempfile
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from apps.story_bible.service.story_bible import (
    Character,
    StoryBible,
    StoryBibleNotFoundError,
    StoryBiblePersistenceError,
    StoryBibleRevisionConflictError,
    StoryBibleSnapshot,
    WorldEntry,
)

_SCHEMA_VERSION = 1


class FileStoryBibleRepository:
    def __init__(self, data_root: Path) -> None:
        self._data_root = data_root.resolve()

    def get(self, project_id: str) -> StoryBibleSnapshot:
        return self._read(self._story_bible_path(project_id), project_id)

    def replace(
        self,
        project_id: str,
        expected_revision: int,
        story_bible: StoryBible,
    ) -> StoryBibleSnapshot:
        path = self._story_bible_path(project_id)
        if story_bible.project_id != project_id:
            raise StoryBiblePersistenceError("Story Bible project does not match its path")
        if not path.parent.is_dir():
            raise StoryBibleNotFoundError

        with self._project_lock(path):
            current = self._read(path, project_id)
            if current.revision != expected_revision:
                raise StoryBibleRevisionConflictError
            replacement = StoryBibleSnapshot(
                story_bible=story_bible,
                revision=current.revision + 1,
            )
            self._atomic_write(path, replacement)
            return replacement

    def _story_bible_path(self, project_id: str) -> Path:
        projects_root = (self._data_root / "projects").resolve()
        candidate = (projects_root / project_id / "story-bible.json").resolve()
        if (
            not project_id
            or Path(project_id).name != project_id
            or not projects_root.is_relative_to(self._data_root)
            or not candidate.is_relative_to(self._data_root)
            or not candidate.is_relative_to(projects_root)
        ):
            raise StoryBiblePersistenceError("Project path escapes the configured data root")
        return candidate

    @contextmanager
    def _project_lock(self, story_bible_path: Path):
        lock_path = story_bible_path.with_suffix(".lock")
        try:
            with lock_path.open("a+b") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except (StoryBibleNotFoundError, StoryBibleRevisionConflictError):
            raise
        except OSError as error:
            raise StoryBiblePersistenceError("Could not lock Story Bible") from error

    @staticmethod
    def _read(path: Path, project_id: str) -> StoryBibleSnapshot:
        try:
            with path.open(encoding="utf-8") as source:
                document = json.load(source)
            return _decode_snapshot(document, project_id)
        except FileNotFoundError as error:
            raise StoryBibleNotFoundError from error
        except StoryBiblePersistenceError:
            raise
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            KeyError,
        ) as error:
            raise StoryBiblePersistenceError("Could not read Story Bible") from error

    @staticmethod
    def _atomic_write(path: Path, snapshot: StoryBibleSnapshot) -> None:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=".story-bible.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temp_path = Path(temporary.name)
                json.dump(
                    _encode_snapshot(snapshot),
                    temporary,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temp_path, path)
            temp_path = None
        except (OSError, TypeError, ValueError) as error:
            raise StoryBiblePersistenceError("Could not persist Story Bible") from error
        finally:
            if temp_path is not None:
                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)


def _encode_snapshot(snapshot: StoryBibleSnapshot) -> dict[str, Any]:
    return {
        "schemaVersion": _SCHEMA_VERSION,
        "storyBibleRevision": snapshot.revision,
        "storyBible": {
            "projectId": snapshot.story_bible.project_id,
            "characters": [
                {
                    "id": character.id,
                    "name": character.name,
                    "role": character.role,
                    "desire": character.desire,
                    "hiddenFeeling": character.hidden_feeling,
                }
                for character in snapshot.story_bible.characters
            ],
            "worldEntries": [
                {
                    "id": entry.id,
                    "kind": entry.kind,
                    "title": entry.title,
                    "description": entry.description,
                }
                for entry in snapshot.story_bible.world_entries
            ],
        },
    }


def _decode_snapshot(document: object, project_id: str) -> StoryBibleSnapshot:
    envelope = _object_with_keys(document, {"schemaVersion", "storyBibleRevision", "storyBible"})
    if _integer(envelope["schemaVersion"]) != _SCHEMA_VERSION:
        raise StoryBiblePersistenceError("Unsupported Story Bible schema version")
    revision = _integer(envelope["storyBibleRevision"])
    if revision < 1:
        raise StoryBiblePersistenceError("Story Bible revision must be positive")

    payload = _object_with_keys(envelope["storyBible"], {"projectId", "characters", "worldEntries"})
    stored_project_id = _nonempty_string(payload["projectId"])
    if stored_project_id != project_id:
        raise StoryBiblePersistenceError("Story Bible project does not match its path")

    characters_value = _list(payload["characters"])
    entries_value = _list(payload["worldEntries"])
    characters = tuple(_decode_character(value) for value in characters_value)
    entries = tuple(_decode_world_entry(value) for value in entries_value)
    return StoryBibleSnapshot(
        story_bible=StoryBible(
            project_id=stored_project_id,
            characters=characters,
            world_entries=entries,
        ),
        revision=revision,
    )


def _decode_character(value: object) -> Character:
    item = _object_with_keys(value, {"id", "name", "role", "desire", "hiddenFeeling"})
    role = _string(item["role"])
    if role != "protagonist":
        raise StoryBiblePersistenceError("Invalid character role")
    return Character(
        id=_nonempty_string(item["id"]),
        name=_nonempty_string(item["name"]),
        role="protagonist",
        desire=_string(item["desire"]),
        hidden_feeling=_string(item["hiddenFeeling"]),
    )


def _decode_world_entry(value: object) -> WorldEntry:
    item = _object_with_keys(value, {"id", "kind", "title", "description"})
    kind = _string(item["kind"])
    if kind not in {"place", "object", "rule"}:
        raise StoryBiblePersistenceError("Invalid world entry kind")
    title = _nonempty_string(item["title"], strip=True)
    description = _nonempty_string(item["description"], strip=True)
    return WorldEntry(
        id=_nonempty_string(item["id"]),
        kind=kind,
        title=title,
        description=description,
    )


def _object_with_keys(value: object, keys: set[str]) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or not all(isinstance(key, str) for key in value)
    ):
        raise StoryBiblePersistenceError("Invalid Story Bible object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise StoryBiblePersistenceError("Invalid Story Bible list")
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise StoryBiblePersistenceError("Invalid Story Bible string")
    return value


def _nonempty_string(value: object, *, strip: bool = False) -> str:
    result = _string(value)
    normalized = result.strip() if strip else result
    if not normalized:
        raise StoryBiblePersistenceError("Story Bible string must not be empty")
    return normalized


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StoryBiblePersistenceError("Invalid Story Bible integer")
    return value
