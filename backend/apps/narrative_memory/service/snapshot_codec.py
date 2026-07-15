import json
from dataclasses import asdict
from typing import Any

from apps.narrative_memory.service.models import (
    CandidateStatus,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    LocationEventType,
    PlaceCandidate,
    ProjectRelationshipSnapshot,
    RelationshipEventCandidate,
)


class SnapshotDecodeError(ValueError):
    pass


def encode_project_snapshot(snapshot: ProjectRelationshipSnapshot) -> bytes:
    data = asdict(snapshot)
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


def decode_project_snapshot(payload: bytes) -> ProjectRelationshipSnapshot:
    try:
        text = payload.decode("utf-8")
        data = json.loads(text, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise SnapshotDecodeError("snapshot is not valid UTF-8 JSON") from error
    if not isinstance(data, dict):
        raise SnapshotDecodeError("snapshot root must be an object")
    return _project_from_dict(data)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _project_from_dict(data: dict[str, Any]) -> ProjectRelationshipSnapshot:
    keys = {
        "project_id",
        "snapshot_version",
        "schema_version",
        "active_scene_revisions",
        "entities",
        "places",
        "relationship_events",
        "location_events",
    }
    try:
        _require_keys(data, keys, keys, "project snapshot")
        return _decode_nested_project_fields(data)
    except (TypeError, ValueError) as error:
        raise SnapshotDecodeError(f"invalid project snapshot: {error}") from error


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _require_keys(
    data: dict[str, Any],
    allowed: set[str],
    required: set[str],
    label: str,
) -> None:
    unknown = sorted(set(data) - allowed)
    missing = sorted(required - set(data))
    if unknown:
        raise ValueError(f"{label} has unexpected fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(missing)}")


def _require_array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    return value


def _require_integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    return value


def _require_number(value: Any, label: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{label} must be a number")
    return float(value)


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    return tuple(_require_string(item, f"{label} item") for item in _require_array(value, label))


def _evidence(value: Any) -> Evidence:
    data = _require_object(value, "evidence")
    keys = {"chunk_id", "start_offset", "end_offset", "text"}
    _require_keys(data, keys, keys, "evidence")
    return Evidence(
        chunk_id=_require_string(data["chunk_id"], "evidence.chunk_id"),
        start_offset=_require_integer(data["start_offset"], "evidence.start_offset"),
        end_offset=_require_integer(data["end_offset"], "evidence.end_offset"),
        text=_require_string(data["text"], "evidence.text"),
    )


def _evidence_tuple(value: Any, label: str) -> tuple[Evidence, ...]:
    return tuple(_evidence(item) for item in _require_array(value, label))


def _entity(value: Any) -> EntityCandidate:
    data = _require_object(value, "entity")
    keys = {
        "candidate_id",
        "normalized_name",
        "display_name",
        "aliases",
        "status",
        "scene_id",
        "scene_revision",
        "evidence",
    }
    _require_keys(data, keys, keys, "entity")
    return EntityCandidate(
        candidate_id=_require_string(data["candidate_id"], "entity.candidate_id"),
        normalized_name=_require_string(data["normalized_name"], "entity.normalized_name"),
        display_name=_require_string(data["display_name"], "entity.display_name"),
        aliases=_string_tuple(data["aliases"], "entity.aliases"),
        status=CandidateStatus(_require_string(data["status"], "entity.status")),
        scene_id=_require_string(data["scene_id"], "entity.scene_id"),
        scene_revision=_require_integer(data["scene_revision"], "entity.scene_revision"),
        evidence=_evidence_tuple(data["evidence"], "entity.evidence"),
    )


def _place(value: Any) -> PlaceCandidate:
    data = _require_object(value, "place")
    keys = {
        "candidate_id",
        "normalized_name",
        "display_name",
        "aliases",
        "status",
        "scene_id",
        "scene_revision",
        "evidence",
    }
    _require_keys(data, keys, keys, "place")
    return PlaceCandidate(
        candidate_id=_require_string(data["candidate_id"], "place.candidate_id"),
        normalized_name=_require_string(data["normalized_name"], "place.normalized_name"),
        display_name=_require_string(data["display_name"], "place.display_name"),
        aliases=_string_tuple(data["aliases"], "place.aliases"),
        status=CandidateStatus(_require_string(data["status"], "place.status")),
        scene_id=_require_string(data["scene_id"], "place.scene_id"),
        scene_revision=_require_integer(data["scene_revision"], "place.scene_revision"),
        evidence=_evidence_tuple(data["evidence"], "place.evidence"),
    )


def _relationship(value: Any) -> RelationshipEventCandidate:
    data = _require_object(value, "relationship event")
    keys = {
        "event_id",
        "subject_key",
        "object_key",
        "category",
        "description",
        "status",
        "scene_id",
        "scene_revision",
        "scene_sequence",
        "confidence",
        "evidence",
    }
    _require_keys(data, keys, keys, "relationship event")
    return RelationshipEventCandidate(
        event_id=_require_string(data["event_id"], "relationship event.event_id"),
        subject_key=_require_string(data["subject_key"], "relationship event.subject_key"),
        object_key=_require_string(data["object_key"], "relationship event.object_key"),
        category=_require_string(data["category"], "relationship event.category"),
        description=_require_string(data["description"], "relationship event.description"),
        status=CandidateStatus(_require_string(data["status"], "relationship event.status")),
        scene_id=_require_string(data["scene_id"], "relationship event.scene_id"),
        scene_revision=_require_integer(
            data["scene_revision"], "relationship event.scene_revision"
        ),
        scene_sequence=_require_integer(
            data["scene_sequence"], "relationship event.scene_sequence"
        ),
        confidence=_require_number(data["confidence"], "relationship event.confidence"),
        evidence=_evidence_tuple(data["evidence"], "relationship event.evidence"),
    )


def _location(value: Any) -> LocationEventCandidate:
    data = _require_object(value, "location event")
    keys = {
        "event_id",
        "character_key",
        "place_key",
        "event_type",
        "description",
        "status",
        "scene_id",
        "scene_revision",
        "scene_sequence",
        "confidence",
        "evidence",
    }
    _require_keys(data, keys, keys, "location event")
    return LocationEventCandidate(
        event_id=_require_string(data["event_id"], "location event.event_id"),
        character_key=_require_string(data["character_key"], "location event.character_key"),
        place_key=_require_string(data["place_key"], "location event.place_key"),
        event_type=LocationEventType(
            _require_string(data["event_type"], "location event.event_type")
        ),
        description=_require_string(data["description"], "location event.description"),
        status=CandidateStatus(_require_string(data["status"], "location event.status")),
        scene_id=_require_string(data["scene_id"], "location event.scene_id"),
        scene_revision=_require_integer(data["scene_revision"], "location event.scene_revision"),
        scene_sequence=_require_integer(data["scene_sequence"], "location event.scene_sequence"),
        confidence=_require_number(data["confidence"], "location event.confidence"),
        evidence=_evidence_tuple(data["evidence"], "location event.evidence"),
    )


def _active_scene_revision(value: Any) -> tuple[str, int]:
    item = _require_array(value, "active_scene_revisions item")
    if len(item) != 2:
        raise ValueError("active_scene_revisions item must contain exactly two values")
    return (
        _require_string(item[0], "active_scene_revisions scene_id"),
        _require_integer(item[1], "active_scene_revisions scene_revision"),
    )


def _decode_nested_project_fields(data: dict[str, Any]) -> ProjectRelationshipSnapshot:
    return ProjectRelationshipSnapshot(
        project_id=_require_string(data["project_id"], "project_id"),
        snapshot_version=_require_integer(data["snapshot_version"], "snapshot_version"),
        schema_version=_require_string(data["schema_version"], "schema_version"),
        active_scene_revisions=tuple(
            _active_scene_revision(item)
            for item in _require_array(data["active_scene_revisions"], "active_scene_revisions")
        ),
        entities=tuple(_entity(item) for item in _require_array(data["entities"], "entities")),
        places=tuple(_place(item) for item in _require_array(data["places"], "places")),
        relationship_events=tuple(
            _relationship(item)
            for item in _require_array(data["relationship_events"], "relationship_events")
        ),
        location_events=tuple(
            _location(item) for item in _require_array(data["location_events"], "location_events")
        ),
    )
