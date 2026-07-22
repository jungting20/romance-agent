import json

from narrative_analysis_agent import ProjectKnowledgeGraphSnapshot
from pydantic import ValidationError

from apps.narrative_memory.service.validation import validate_project_snapshot


class SnapshotDecodeError(ValueError):
    pass


def encode_project_snapshot(snapshot: ProjectKnowledgeGraphSnapshot) -> bytes:
    validate_project_snapshot(snapshot)
    data = snapshot.model_dump(mode="json")
    return (
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def decode_project_snapshot(payload: bytes) -> ProjectKnowledgeGraphSnapshot:
    try:
        snapshot = ProjectKnowledgeGraphSnapshot.model_validate_json(payload, strict=True)
        validate_project_snapshot(snapshot)
        return snapshot
    except (UnicodeDecodeError, ValidationError, ValueError) as error:
        raise SnapshotDecodeError("invalid project knowledge graph snapshot") from error
