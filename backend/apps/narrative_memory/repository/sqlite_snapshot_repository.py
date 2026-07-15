import hashlib
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from apps.narrative_memory.repository.snapshot_repository import (
    SnapshotCorruptionError,
    SnapshotVersionConflict,
    StoredProjectSnapshot,
)
from apps.narrative_memory.service.models import ProjectRelationshipSnapshot
from apps.narrative_memory.service.snapshot_codec import (
    SnapshotDecodeError,
    decode_project_snapshot,
    encode_project_snapshot,
)


class SQLiteSnapshotRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        self._path.chmod(0o600)

        with sqlite3.connect(self._path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_snapshots (
                    project_id TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL,
                    schema_version TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, snapshot_version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS current_project_snapshots (
                    project_id TEXT PRIMARY KEY,
                    snapshot_version INTEGER NOT NULL
                )
                """
            )

    def get_current(self, project_id: str) -> StoredProjectSnapshot | None:
        with sqlite3.connect(self._path) as connection:
            row = connection.execute(
                """
                SELECT snapshot_version
                FROM current_project_snapshots
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return self.get_version(project_id, row[0])

    def get_version(self, project_id: str, version: int) -> StoredProjectSnapshot | None:
        with sqlite3.connect(self._path) as connection:
            row = connection.execute(
                """
                SELECT schema_version, content_hash, payload
                FROM project_snapshots
                WHERE project_id = ? AND snapshot_version = ?
                """,
                (project_id, version),
            ).fetchone()
        if row is None:
            return None

        schema_version, content_hash, raw_payload = row
        payload = bytes(raw_payload)
        calculated_hash = _content_hash(payload)
        if content_hash != calculated_hash:
            raise SnapshotCorruptionError("stored snapshot content hash does not match payload")
        try:
            snapshot = decode_project_snapshot(payload)
        except SnapshotDecodeError as error:
            raise SnapshotCorruptionError("stored snapshot payload cannot be decoded") from error
        if (
            snapshot.project_id != project_id
            or snapshot.snapshot_version != version
            or snapshot.schema_version != schema_version
        ):
            raise SnapshotCorruptionError("stored snapshot metadata does not match payload")
        return StoredProjectSnapshot(
            snapshot=snapshot,
            payload=payload,
            content_hash=content_hash,
        )

    def commit(
        self,
        expected_version: int | None,
        snapshot: ProjectRelationshipSnapshot,
    ) -> StoredProjectSnapshot:
        payload = encode_project_snapshot(snapshot)
        content_hash = _content_hash(payload)
        connection = sqlite3.connect(self._path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT snapshot_version
                FROM current_project_snapshots
                WHERE project_id = ?
                """,
                (snapshot.project_id,),
            ).fetchone()
            current_version = None if row is None else row[0]
            if current_version != expected_version:
                raise SnapshotVersionConflict(
                    f"expected version {expected_version!r}, current version is {current_version!r}"
                )

            next_version = 0 if expected_version is None else expected_version + 1
            if snapshot.snapshot_version != next_version:
                raise ValueError(
                    f"snapshot version must be {next_version}, got {snapshot.snapshot_version}"
                )

            connection.execute(
                """
                INSERT INTO project_snapshots (
                    project_id,
                    snapshot_version,
                    schema_version,
                    content_hash,
                    payload,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.project_id,
                    snapshot.snapshot_version,
                    snapshot.schema_version,
                    content_hash,
                    payload,
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO current_project_snapshots (project_id, snapshot_version)
                VALUES (?, ?)
                ON CONFLICT(project_id) DO UPDATE
                SET snapshot_version = excluded.snapshot_version
                """,
                (snapshot.project_id, snapshot.snapshot_version),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return StoredProjectSnapshot(
            snapshot=snapshot,
            payload=payload,
            content_hash=content_hash,
        )


def _content_hash(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
