import sqlite3
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from narrative_analysis_agent.models import ProjectKnowledgeGraphSnapshot


class ProjectGraphReadError(RuntimeError):
    pass


class ProjectGraphReader:
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self, project_id: str) -> ProjectKnowledgeGraphSnapshot:
        try:
            uri = f"{self._path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(uri, uri=True) as connection:
                pointer = connection.execute(
                    "SELECT snapshot_version FROM current_project_snapshots WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
                if pointer is None:
                    return ProjectKnowledgeGraphSnapshot.empty(project_id)
                if type(pointer[0]) is not int or pointer[0] < 1:
                    raise ValueError("stored snapshot version is invalid")
                row = connection.execute(
                    """
                    SELECT schema_version, content_hash, payload
                    FROM project_snapshots
                    WHERE project_id = ? AND snapshot_version = ?
                    """,
                    (project_id, pointer[0]),
                ).fetchone()
            if row is None:
                raise ValueError("current snapshot is missing")
            schema_version, content_hash, raw_payload = row
            if not isinstance(raw_payload, bytes):
                raise ValueError("snapshot payload is not binary")
            payload = raw_payload
            calculated = f"sha256:{sha256(payload).hexdigest()}"
            if content_hash != calculated:
                raise ValueError("snapshot hash mismatch")
            snapshot = ProjectKnowledgeGraphSnapshot.model_validate_json(payload)
            if (
                snapshot.project_id != project_id
                or snapshot.snapshot_version != pointer[0]
                or snapshot.schema_version != schema_version
            ):
                raise ValueError("snapshot metadata mismatch")
            return snapshot
        except (OSError, sqlite3.Error, ValidationError, ValueError):
            raise ProjectGraphReadError("unable to read project graph") from None
