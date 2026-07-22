import hashlib
import json
import os
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from narrative_analysis_agent import ProjectKnowledgeGraphSnapshot
from narrative_analysis_agent.models import KnowledgeGraphOutput
from pydantic import ValidationError

from apps.narrative_memory.repository.snapshot_repository import (
    SnapshotCorruptionError,
    SnapshotRepositoryError,
    SnapshotVersionConflict,
    StoredProjectSnapshot,
)
from apps.narrative_memory.service.models import SceneGraphRecord
from apps.narrative_memory.service.snapshot_codec import (
    SnapshotDecodeError,
    decode_project_snapshot,
    encode_project_snapshot,
)
from apps.narrative_memory.service.validation import (
    ProjectInvariantError,
    validate_scene_graph,
)


class SQLiteSnapshotRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(descriptor)
            self._path.chmod(0o600)

            with sqlite3.connect(self._path) as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scene_knowledge_graphs (
                        project_id TEXT NOT NULL,
                        scene_id TEXT NOT NULL,
                        scene_revision INTEGER NOT NULL,
                        scene_sequence INTEGER NOT NULL,
                        content_hash TEXT NOT NULL,
                        payload BLOB NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (project_id, scene_id)
                    )
                    """
                )
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
        except (OSError, sqlite3.Error):
            raise SnapshotRepositoryError("snapshot repository operation failed") from None

    def get_current(self, project_id: str) -> StoredProjectSnapshot | None:
        try:
            with sqlite3.connect(self._path) as connection:
                row = connection.execute(
                    """
                    SELECT snapshot_version
                    FROM current_project_snapshots
                    WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()
        except (OSError, sqlite3.Error):
            raise SnapshotRepositoryError("snapshot repository operation failed") from None
        if row is None:
            return None
        snapshot = self._get_version(project_id, row[0])
        if snapshot is None:
            raise SnapshotCorruptionError("current snapshot pointer references a missing snapshot")
        if type(row[0]) is not int or row[0] < 1:
            raise SnapshotCorruptionError("stored snapshot version must be positive")
        return snapshot

    def get_scene_graphs(self, project_id: str) -> tuple[SceneGraphRecord, ...]:
        try:
            with sqlite3.connect(self._path) as connection:
                rows = connection.execute(
                    """
                    SELECT scene_id, scene_revision, scene_sequence, content_hash, payload
                    FROM scene_knowledge_graphs
                    WHERE project_id = ?
                    ORDER BY scene_sequence, scene_id
                    """,
                    (project_id,),
                ).fetchall()
        except (OSError, sqlite3.Error):
            raise SnapshotRepositoryError("snapshot repository operation failed") from None

        records = []
        for scene_id, scene_revision, scene_sequence, content_hash, raw_payload in rows:
            payload = _stored_payload(raw_payload, "scene")
            if content_hash != _content_hash(payload):
                raise SnapshotCorruptionError("stored scene content hash does not match payload")
            graph = _decode_scene_graph(payload)
            if (
                not isinstance(scene_id, str)
                or not scene_id
                or type(scene_revision) is not int
                or scene_revision < 0
                or type(scene_sequence) is not int
                or scene_sequence < 0
                or graph.document.chapter_id != scene_id
            ):
                raise SnapshotCorruptionError("stored scene metadata does not match payload")
            records.append(
                SceneGraphRecord(
                    project_id=project_id,
                    scene_id=scene_id,
                    scene_revision=scene_revision,
                    scene_sequence=scene_sequence,
                    graph=graph,
                )
            )
        return tuple(records)

    def commit_scene(
        self,
        expected_version: int | None,
        scene: SceneGraphRecord,
        snapshot: ProjectKnowledgeGraphSnapshot,
    ) -> StoredProjectSnapshot:
        exact_graph = _validate_scene(scene)
        if scene.project_id != snapshot.project_id:
            raise ValueError("scene and snapshot project IDs must match")

        scene_payload = _encode_scene_graph(exact_graph)
        scene_content_hash = _content_hash(scene_payload)
        snapshot_payload = encode_project_snapshot(snapshot)
        snapshot_content_hash = _content_hash(snapshot_payload)
        try:
            connection = sqlite3.connect(self._path)
        except (OSError, sqlite3.Error):
            raise SnapshotRepositoryError("snapshot repository operation failed") from None
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

            next_version = 1 if expected_version is None else expected_version + 1
            if snapshot.snapshot_version != next_version:
                raise ValueError(
                    f"snapshot version must be {next_version}, got {snapshot.snapshot_version}"
                )

            row = connection.execute(
                """
                SELECT scene_revision
                FROM scene_knowledge_graphs
                WHERE project_id = ? AND scene_id = ?
                """,
                (scene.project_id, scene.scene_id),
            ).fetchone()
            current_scene_revision = None if row is None else row[0]
            if (
                current_scene_revision is not None
                and scene.scene_revision <= current_scene_revision
            ):
                raise SnapshotVersionConflict(
                    "scene revision must be greater than "
                    f"{current_scene_revision}, got {scene.scene_revision}"
                )

            now = datetime.now(UTC).isoformat()
            connection.execute(
                """
                INSERT INTO scene_knowledge_graphs (
                    project_id,
                    scene_id,
                    scene_revision,
                    scene_sequence,
                    content_hash,
                    payload,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, scene_id) DO UPDATE SET
                    scene_revision = excluded.scene_revision,
                    scene_sequence = excluded.scene_sequence,
                    content_hash = excluded.content_hash,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    scene.project_id,
                    scene.scene_id,
                    scene.scene_revision,
                    scene.scene_sequence,
                    scene_content_hash,
                    scene_payload,
                    now,
                ),
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
                    snapshot_content_hash,
                    snapshot_payload,
                    now,
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
        except (SnapshotVersionConflict, ValueError):
            try:
                connection.rollback()
                connection.close()
            except sqlite3.Error:
                _discard_connection(connection)
                raise SnapshotRepositoryError("snapshot repository operation failed") from None
            raise
        except (OSError, sqlite3.Error):
            _discard_connection(connection)
            raise SnapshotRepositoryError("snapshot repository operation failed") from None
        try:
            connection.close()
        except sqlite3.Error:
            raise SnapshotRepositoryError("snapshot repository operation failed") from None

        return StoredProjectSnapshot(
            snapshot=snapshot,
            payload=snapshot_payload,
            content_hash=snapshot_content_hash,
        )

    def _get_version(
        self,
        project_id: str,
        version: int,
    ) -> StoredProjectSnapshot | None:
        try:
            with sqlite3.connect(self._path) as connection:
                row = connection.execute(
                    """
                    SELECT schema_version, content_hash, payload
                    FROM project_snapshots
                    WHERE project_id = ? AND snapshot_version = ?
                    """,
                    (project_id, version),
                ).fetchone()
        except (OSError, sqlite3.Error):
            raise SnapshotRepositoryError("snapshot repository operation failed") from None
        if row is None:
            return None

        schema_version, content_hash, raw_payload = row
        payload = _stored_payload(raw_payload, "snapshot")
        if content_hash != _content_hash(payload):
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


def _validate_scene(scene: SceneGraphRecord) -> KnowledgeGraphOutput:
    if not scene.project_id or not scene.scene_id:
        raise ValueError("scene project and scene IDs must be non-empty")
    if type(scene.scene_revision) is not int or scene.scene_revision < 0:
        raise ValueError("scene revision must be a non-negative integer")
    if type(scene.scene_sequence) is not int or scene.scene_sequence < 0:
        raise ValueError("scene sequence must be a non-negative integer")
    try:
        exact_graph = KnowledgeGraphOutput.model_validate(
            scene.graph.model_dump(mode="python"),
            strict=True,
        )
    except ValidationError as error:
        raise ProjectInvariantError("scene graph violates the public model contract") from error
    if exact_graph.document.chapter_id != scene.scene_id:
        raise ValueError("scene ID must match the graph document chapter ID")
    validate_scene_graph(exact_graph)
    return exact_graph


def _encode_scene_graph(graph: KnowledgeGraphOutput) -> bytes:
    return (
        json.dumps(
            graph.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _decode_scene_graph(payload: bytes) -> KnowledgeGraphOutput:
    try:
        graph = KnowledgeGraphOutput.model_validate_json(payload, strict=True)
    except (UnicodeDecodeError, ValidationError, ValueError) as error:
        raise SnapshotCorruptionError("stored scene payload cannot be decoded") from error
    try:
        validate_scene_graph(graph)
    except ValueError as error:
        raise SnapshotCorruptionError("stored scene semantic invariants are invalid") from error
    return graph


def _stored_payload(raw_payload: object, label: str) -> bytes:
    if not isinstance(raw_payload, bytes):
        raise SnapshotCorruptionError(f"stored {label} payload is not binary")
    return raw_payload


def _content_hash(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _discard_connection(connection: sqlite3.Connection) -> None:
    with suppress(sqlite3.Error):
        connection.rollback()
    with suppress(sqlite3.Error):
        connection.close()
