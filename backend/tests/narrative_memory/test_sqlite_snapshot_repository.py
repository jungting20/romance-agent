import hashlib
import sqlite3
import stat
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from apps.narrative_memory.repository.snapshot_repository import (
    SnapshotCorruptionError,
    SnapshotVersionConflict,
)
from apps.narrative_memory.repository.sqlite_snapshot_repository import (
    SQLiteSnapshotRepository,
)
from apps.narrative_memory.service.models import ProjectRelationshipSnapshot
from apps.narrative_memory.service.snapshot_codec import encode_project_snapshot


def test_repository_starts_without_a_current_snapshot(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "audit.sqlite3")
    repository.initialize()

    assert repository.get_current("missing-project") is None
    assert repository.get_version("missing-project", 0) is None


def test_repository_commits_and_reads_exact_snapshot_bytes(tmp_path) -> None:
    path = tmp_path / "agent-audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    snapshot = ProjectRelationshipSnapshot.empty("project-01")
    payload = encode_project_snapshot(snapshot)

    committed = repository.commit(expected_version=None, snapshot=snapshot)

    stored = repository.get_version("project-01", 0)
    assert stored is not None
    assert stored.snapshot == snapshot
    assert stored.payload == payload
    assert stored.content_hash == f"sha256:{hashlib.sha256(payload).hexdigest()}"
    assert committed == stored
    assert repository.get_current("project-01") == stored


def test_repository_preserves_old_versions_when_current_advances(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "audit.sqlite3")
    repository.initialize()
    initial = ProjectRelationshipSnapshot.empty("project-01")
    current = replace(initial, snapshot_version=1)

    repository.commit(None, initial)
    repository.commit(0, current)

    assert repository.get_version("project-01", 0).snapshot == initial  # type: ignore[union-attr]
    assert repository.get_version("project-01", 1).snapshot == current  # type: ignore[union-attr]
    assert repository.get_current("project-01").snapshot == current  # type: ignore[union-attr]


def test_repository_stores_schema_hash_and_utc_creation_timestamp(tmp_path) -> None:
    path = tmp_path / "audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    snapshot = ProjectRelationshipSnapshot.empty("project-01")
    payload = encode_project_snapshot(snapshot)

    repository.commit(None, snapshot)

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT schema_version, content_hash, payload, created_at
            FROM project_snapshots
            WHERE project_id = ? AND snapshot_version = ?
            """,
            ("project-01", 0),
        ).fetchone()
    assert row is not None
    schema_version, content_hash, stored_payload, created_at = row
    assert schema_version == snapshot.schema_version
    assert content_hash == f"sha256:{hashlib.sha256(payload).hexdigest()}"
    assert stored_payload == payload
    assert datetime.fromisoformat(created_at).tzinfo == UTC


def test_repository_rejects_stale_expected_version(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "audit.sqlite3")
    repository.initialize()
    repository.commit(None, ProjectRelationshipSnapshot.empty("project-01"))

    with pytest.raises(SnapshotVersionConflict, match="expected.*current"):
        repository.commit(None, ProjectRelationshipSnapshot.empty("project-01"))


def test_repository_rejects_invalid_next_version_and_preserves_current_pointer(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "audit.sqlite3")
    repository.initialize()
    initial = ProjectRelationshipSnapshot.empty("project-01")
    repository.commit(None, initial)

    with pytest.raises(ValueError, match="snapshot version"):
        repository.commit(0, replace(initial, snapshot_version=2))

    current = repository.get_current("project-01")
    assert current is not None
    assert current.snapshot == initial
    assert repository.get_version("project-01", 2) is None


def test_repository_never_overwrites_an_immutable_duplicate_version(tmp_path) -> None:
    path = tmp_path / "audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    initial = ProjectRelationshipSnapshot.empty("project-01")
    repository.commit(None, initial)
    original_payload = repository.get_version("project-01", 0).payload  # type: ignore[union-attr]
    with sqlite3.connect(path) as connection:
        connection.execute(
            "DELETE FROM current_project_snapshots WHERE project_id = ?", ("project-01",)
        )

    with pytest.raises(sqlite3.IntegrityError):
        repository.commit(None, initial)

    stored = repository.get_version("project-01", 0)
    assert stored is not None
    assert stored.payload == original_payload
    assert repository.get_current("project-01") is None


def test_repository_rolls_back_insert_when_advancing_pointer_fails(tmp_path) -> None:
    path = tmp_path / "audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    initial = ProjectRelationshipSnapshot.empty("project-01")
    repository.commit(None, initial)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_pointer_advance
            BEFORE UPDATE ON current_project_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'pointer update rejected');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="pointer update rejected"):
        repository.commit(0, replace(initial, snapshot_version=1))

    assert repository.get_version("project-01", 1) is None
    current = repository.get_current("project-01")
    assert current is not None
    assert current.snapshot == initial


def test_repository_file_is_owner_read_write_only(tmp_path) -> None:
    path = tmp_path / "private" / "audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)

    repository.initialize()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_repository_rejects_payload_corruption(tmp_path) -> None:
    path = tmp_path / "audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    repository.commit(None, ProjectRelationshipSnapshot.empty("project-01"))
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE project_snapshots
            SET payload = ?
            WHERE project_id = ? AND snapshot_version = ?
            """,
            (b"{}\n", "project-01", 0),
        )

    with pytest.raises(SnapshotCorruptionError, match="content hash"):
        repository.get_version("project-01", 0)


def test_repository_rejects_stored_hash_corruption(tmp_path) -> None:
    path = tmp_path / "audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    repository.commit(None, ProjectRelationshipSnapshot.empty("project-01"))
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE project_snapshots
            SET content_hash = ?
            WHERE project_id = ? AND snapshot_version = ?
            """,
            ("sha256:" + "0" * 64, "project-01", 0),
        )

    with pytest.raises(SnapshotCorruptionError, match="content hash"):
        repository.get_current("project-01")
