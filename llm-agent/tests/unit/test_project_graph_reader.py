import json
import sqlite3
from hashlib import sha256
from pathlib import Path

import pytest

from narrative_analysis_agent.models import ProjectKnowledgeGraphSnapshot
from narrative_analysis_agent.project_graph_reader import ProjectGraphReader, ProjectGraphReadError


def initialize_v2_tables(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE project_snapshots (
                project_id TEXT NOT NULL,
                snapshot_version INTEGER NOT NULL,
                schema_version TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                payload BLOB NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, snapshot_version)
            );
            CREATE TABLE current_project_snapshots (
                project_id TEXT PRIMARY KEY,
                snapshot_version INTEGER NOT NULL
            );
            """
        )


def canonical_payload(project_id: str = "project-01", snapshot_version: int = 3) -> bytes:
    return json.dumps(
        {
            "project_id": project_id,
            "snapshot_version": snapshot_version,
            "schema_version": "project-knowledge-graph-snapshot-v2",
            "documents": [],
            "entities": {"characters": [], "locations": [], "events": []},
            "relations": [],
            "movements": [],
            "coreferences": [],
            "unresolved_references": [],
            "contradictions": [],
        },
        separators=(",", ":"),
    ).encode()


def insert_current_snapshot(
    path: Path,
    *,
    project_id: str = "project-01",
    snapshot_version: int = 3,
    schema_version: str = "project-knowledge-graph-snapshot-v2",
    payload: bytes | None = None,
    content_hash: str | None = None,
) -> None:
    snapshot_payload = payload or canonical_payload(project_id, snapshot_version)
    snapshot_hash = content_hash or f"sha256:{sha256(snapshot_payload).hexdigest()}"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO project_snapshots (
                project_id, snapshot_version, schema_version, content_hash, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                snapshot_version,
                schema_version,
                snapshot_hash,
                snapshot_payload,
                "2026-07-22T00:00:00+00:00",
            ),
        )
        connection.execute(
            "INSERT INTO current_project_snapshots (project_id, snapshot_version) VALUES (?, ?)",
            (project_id, snapshot_version),
        )


def test_reader_returns_current_v2_graph(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    initialize_v2_tables(path)
    insert_current_snapshot(path)

    result = ProjectGraphReader(path).read("project-01")

    assert result == ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=3,
        schema_version="project-knowledge-graph-snapshot-v2",
    )


def test_reader_returns_empty_v2_graph_when_project_has_no_current_record(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    initialize_v2_tables(path)

    result = ProjectGraphReader(path).read("project-01")

    assert result == ProjectKnowledgeGraphSnapshot.empty("project-01")


def test_reader_rejects_stored_current_snapshot_version_zero(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    initialize_v2_tables(path)
    insert_current_snapshot(path, snapshot_version=0)

    with pytest.raises(ProjectGraphReadError, match="unable to read project graph"):
        ProjectGraphReader(path).read("project-01")


def test_reader_does_not_create_a_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"

    with pytest.raises(ProjectGraphReadError, match="unable to read project graph"):
        ProjectGraphReader(path).read("project-01")

    assert not path.exists()


def test_reader_rejects_snapshot_with_mismatched_hash(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    initialize_v2_tables(path)
    insert_current_snapshot(path, content_hash="sha256:not-the-payload-hash")

    with pytest.raises(ProjectGraphReadError, match="unable to read project graph"):
        ProjectGraphReader(path).read("project-01")


def test_reader_rejects_v1_snapshot_schema(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    initialize_v2_tables(path)
    v1_payload = canonical_payload().replace(
        b"project-knowledge-graph-snapshot-v2", b"project-knowledge-graph-snapshot-v1"
    )
    insert_current_snapshot(
        path,
        schema_version="project-knowledge-graph-snapshot-v1",
        payload=v1_payload,
    )

    with pytest.raises(ProjectGraphReadError, match="unable to read project graph"):
        ProjectGraphReader(path).read("project-01")


def test_reader_rejects_malformed_snapshot_json(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    initialize_v2_tables(path)
    insert_current_snapshot(path, payload=b"not-json")

    with pytest.raises(ProjectGraphReadError, match="unable to read project graph"):
        ProjectGraphReader(path).read("project-01")


def test_reader_rejects_text_payload_even_when_text_contains_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    initialize_v2_tables(path)
    payload = canonical_payload().decode("utf-8")
    insert_current_snapshot(
        path,
        payload=payload,  # type: ignore[arg-type]
        content_hash=f"sha256:{sha256(payload.encode()).hexdigest()}",
    )

    with pytest.raises(ProjectGraphReadError, match="unable to read project graph"):
        ProjectGraphReader(path).read("project-01")
