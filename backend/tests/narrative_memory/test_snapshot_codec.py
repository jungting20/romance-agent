import json
import math

import pytest
from narrative_analysis_agent import ProjectKnowledgeGraphSnapshot

from apps.narrative_memory.service.snapshot_codec import (
    SnapshotDecodeError,
    decode_project_snapshot,
    encode_project_snapshot,
)


def test_v2_empty_project_snapshot_codec_is_canonical_and_round_trips() -> None:
    snapshot = ProjectKnowledgeGraphSnapshot.empty("project-01")

    payload = encode_project_snapshot(snapshot)

    assert payload == (
        b'{\n  "contradictions": [],\n  "coreferences": [],\n  "documents": [],\n'
        b'  "entities": {\n    "characters": [],\n    "events": [],\n'
        b'    "locations": []\n  },\n  "movements": [],\n'
        b'  "project_id": "project-01",\n  "relations": [],\n'
        b'  "schema_version": "project-knowledge-graph-snapshot-v2",\n'
        b'  "snapshot_version": 0,\n  "unresolved_references": []\n}\n'
    )
    assert decode_project_snapshot(payload) == snapshot
    assert encode_project_snapshot(decode_project_snapshot(payload)) == payload


def test_v2_semantic_project_snapshot_codec_is_canonical_and_round_trips() -> None:
    snapshot = _semantic_snapshot()

    payload = encode_project_snapshot(snapshot)

    assert payload.endswith(b"\n")
    assert decode_project_snapshot(payload) == snapshot
    assert encode_project_snapshot(decode_project_snapshot(payload)) == payload


def test_decoder_rejects_v1_snapshot() -> None:
    payload = b'{"schema_version":"project-relationship-snapshot-v1"}'

    with pytest.raises(SnapshotDecodeError):
        decode_project_snapshot(payload)


def test_decoder_rejects_unknown_field() -> None:
    data = _snapshot_data()
    data["unexpected"] = True

    with pytest.raises(SnapshotDecodeError, match="invalid project knowledge graph snapshot"):
        decode_project_snapshot(json.dumps(data).encode())


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("project_id", ""),
        ("snapshot_version", -1),
        ("schema_version", "project-relationship-snapshot-v1"),
    ],
)
def test_encoder_rejects_invalid_snapshot_identity_or_version(
    field: str,
    invalid_value: object,
) -> None:
    snapshot = _semantic_snapshot().model_copy(update={field: invalid_value})

    with pytest.raises(ValueError):
        encode_project_snapshot(snapshot)


def test_snapshot_codec_rejects_duplicate_document_chapter_id() -> None:
    snapshot = _semantic_snapshot()
    invalid = snapshot.model_copy(update={"documents": snapshot.documents * 2})

    with pytest.raises(ValueError, match="chapter IDs must be unique"):
        encode_project_snapshot(invalid)


@pytest.mark.parametrize("collection", ["characters", "locations", "events", "relations"])
def test_snapshot_codec_rejects_duplicate_graph_ids(collection: str) -> None:
    snapshot = _semantic_snapshot()
    if collection == "relations":
        invalid = snapshot.model_copy(update={"relations": snapshot.relations * 2})
    else:
        entities = snapshot.entities.model_copy(
            update={collection: getattr(snapshot.entities, collection) * 2}
        )
        invalid = snapshot.model_copy(update={"entities": entities})

    with pytest.raises(ValueError, match="IDs must be unique"):
        encode_project_snapshot(invalid)


@pytest.mark.parametrize(
    ("path", "reference"),
    [
        ("location.parent_location_id", "character_001"),
        ("event.participant_ids", ("location_001",)),
        ("event.location_ids", ("character_001",)),
        ("relation.source_id", "relation_001"),
        ("relation.target_id", "character_999"),
        ("relation.start_event_id", "character_001"),
        ("relation.end_event_id", "event_999"),
        ("movement.character_id", "location_001"),
        ("movement.from_location_id", "character_001"),
        ("movement.to_location_id", "location_999"),
        ("movement.event_id", "location_001"),
        ("coreference.resolved_entity_id", "relation_001"),
        ("unresolved.possible_entity_ids", ("relation_001",)),
        ("contradiction.subject_id", "relation_001"),
    ],
)
def test_snapshot_codec_rejects_dangling_or_wrong_kind_reference(
    path: str,
    reference: object,
) -> None:
    snapshot = _snapshot_with_reference(path, reference)

    with pytest.raises(ValueError, match="unknown|reference"):
        encode_project_snapshot(snapshot)


@pytest.mark.parametrize(
    "path",
    ["character", "location", "event", "relation", "movement", "coreference"],
)
@pytest.mark.parametrize("confidence", [math.nan, math.inf, -math.inf])
def test_snapshot_codec_rejects_non_finite_confidence(
    path: str,
    confidence: float,
) -> None:
    snapshot = _snapshot_with_confidence(path, confidence)

    with pytest.raises(ValueError, match="confidence"):
        encode_project_snapshot(snapshot)


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    [
        pytest.param("character.status", "departed", id="invalid-enum"),
        pytest.param("character.id", "person_001", id="invalid-id"),
        pytest.param("event.sequence", -1, id="negative-sequence"),
    ],
)
def test_encoder_revalidates_model_copy_against_exact_public_model(
    path: str,
    invalid_value: object,
) -> None:
    snapshot = _snapshot_with_field(path, invalid_value)

    with pytest.raises(ValueError):
        encode_project_snapshot(snapshot)


@pytest.mark.parametrize(
    "path",
    [
        "character.first_mention",
        "location.first_mention",
        "event.evidence",
        "relation.evidence",
        "movement.evidence",
        "coreference.evidence",
        "contradiction.evidence",
    ],
)
def test_encoder_defensively_rejects_empty_evidence_from_model_copy(path: str) -> None:
    snapshot = _snapshot_with_field(path, "")

    with pytest.raises(ValueError):
        encode_project_snapshot(snapshot)


def _semantic_snapshot() -> ProjectKnowledgeGraphSnapshot:
    return ProjectKnowledgeGraphSnapshot.model_validate_json(
        json.dumps(
            {
                "project_id": "project-01",
                "snapshot_version": 2,
                "schema_version": "project-knowledge-graph-snapshot-v2",
                "documents": [
                    {
                        "chapter_id": "scene-01",
                        "summary": "서윤은 온실에 도착한다.",
                        "narrative_time": "present",
                    }
                ],
                "entities": {
                    "characters": [
                        {
                            "id": "character_001",
                            "canonical_name": "서윤",
                            "aliases": [],
                            "description": "",
                            "gender": "unknown",
                            "age": None,
                            "occupation": None,
                            "affiliation": None,
                            "status": "alive",
                            "first_mention": "서윤",
                            "confidence": 0.9,
                        }
                    ],
                    "locations": [
                        {
                            "id": "location_001",
                            "canonical_name": "온실",
                            "aliases": [],
                            "location_type": "building",
                            "parent_location_id": None,
                            "description": "",
                            "first_mention": "온실",
                            "confidence": 0.9,
                        }
                    ],
                    "events": [
                        {
                            "id": "event_001",
                            "event_type": "ARRIVAL",
                            "name": "도착",
                            "summary": "서윤이 온실에 도착한다.",
                            "participant_ids": ["character_001"],
                            "location_ids": ["location_001"],
                            "time_expression": None,
                            "narrative_time": "present",
                            "sequence": 0,
                            "evidence": "도착한다",
                            "confidence": 0.9,
                        }
                    ],
                },
                "relations": [
                    {
                        "id": "relation_001",
                        "source_id": "character_001",
                        "relation_type": "LOCATED_IN",
                        "target_id": "location_001",
                        "state": "active",
                        "directed": True,
                        "start_event_id": "event_001",
                        "end_event_id": None,
                        "time_expression": None,
                        "scene_sequence": 0,
                        "evidence": "온실에",
                        "inference": False,
                        "confidence": 0.9,
                    }
                ],
                "movements": [
                    {
                        "character_id": "character_001",
                        "from_location_id": None,
                        "to_location_id": "location_001",
                        "movement_type": "ARRIVAL",
                        "event_id": "event_001",
                        "time_expression": None,
                        "sequence": 0,
                        "evidence": "도착한다",
                        "confidence": 0.9,
                    }
                ],
                "coreferences": [
                    {
                        "expression": "그녀",
                        "resolved_entity_id": "character_001",
                        "evidence": "그녀",
                        "confidence": 0.9,
                    }
                ],
                "unresolved_references": [
                    {
                        "expression": "그곳",
                        "possible_entity_ids": ["location_001"],
                        "reason": "모호함",
                    }
                ],
                "contradictions": [
                    {
                        "subject_id": "character_001",
                        "field_or_relation": "status",
                        "existing_value": "missing",
                        "new_value": "alive",
                        "evidence": "서윤이 등장함",
                        "possible_explanation": "",
                    }
                ],
            }
        )
    )


def _snapshot_data() -> dict[str, object]:
    return json.loads(encode_project_snapshot(_semantic_snapshot()))


def _snapshot_with_reference(path: str, reference: object) -> ProjectKnowledgeGraphSnapshot:
    snapshot = _semantic_snapshot()
    section, field = path.split(".")
    if section == "location":
        item = snapshot.entities.locations[0].model_copy(update={field: reference})
        entities = snapshot.entities.model_copy(update={"locations": (item,)})
        return snapshot.model_copy(update={"entities": entities})
    if section == "event":
        item = snapshot.entities.events[0].model_copy(update={field: reference})
        entities = snapshot.entities.model_copy(update={"events": (item,)})
        return snapshot.model_copy(update={"entities": entities})
    collection_by_section = {
        "relation": "relations",
        "movement": "movements",
        "coreference": "coreferences",
        "unresolved": "unresolved_references",
        "contradiction": "contradictions",
    }
    collection = collection_by_section[section]
    item = getattr(snapshot, collection)[0].model_copy(update={field: reference})
    return snapshot.model_copy(update={collection: (item,)})


def _snapshot_with_field(path: str, value: object) -> ProjectKnowledgeGraphSnapshot:
    snapshot = _semantic_snapshot()
    section, field = path.split(".")
    if section in {"character", "location", "event"}:
        collection = f"{section}s"
        item = getattr(snapshot.entities, collection)[0].model_copy(update={field: value})
        entities = snapshot.entities.model_copy(update={collection: (item,)})
        return snapshot.model_copy(update={"entities": entities})
    collection = f"{section}s"
    item = getattr(snapshot, collection)[0].model_copy(update={field: value})
    return snapshot.model_copy(update={collection: (item,)})


def _snapshot_with_confidence(
    path: str,
    confidence: float,
) -> ProjectKnowledgeGraphSnapshot:
    snapshot = _semantic_snapshot()
    if path in {"character", "location", "event"}:
        collection = f"{path}s"
        item = getattr(snapshot.entities, collection)[0].model_copy(
            update={"confidence": confidence}
        )
        entities = snapshot.entities.model_copy(update={collection: (item,)})
        return snapshot.model_copy(update={"entities": entities})
    collection = f"{path}s"
    item = getattr(snapshot, collection)[0].model_copy(update={"confidence": confidence})
    return snapshot.model_copy(update={collection: (item,)})
