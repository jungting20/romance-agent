import json
from dataclasses import FrozenInstanceError, asdict, replace

import pytest

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
from apps.narrative_memory.service.snapshot_codec import (
    SnapshotDecodeError,
    decode_project_snapshot,
    encode_project_snapshot,
)


def test_empty_project_snapshot_is_version_zero() -> None:
    snapshot = ProjectRelationshipSnapshot.empty("project-01")

    assert snapshot.project_id == "project-01"
    assert snapshot.snapshot_version == 0
    assert snapshot.relationship_events == ()
    assert snapshot.location_events == ()


def test_evidence_is_immutable() -> None:
    evidence = Evidence(
        chunk_id="scene-01:r1:0000",
        scene_id="scene-01",
        scene_revision=1,
        start_offset=0,
        end_offset=3,
        text="서연은",
    )

    with pytest.raises(FrozenInstanceError):
        evidence.text = "민준은"  # type: ignore[misc]


def test_project_snapshot_codec_is_stable_and_round_trips() -> None:
    snapshot = ProjectRelationshipSnapshot.empty("project-01")

    payload = encode_project_snapshot(snapshot)

    assert (
        payload == b'{\n  "active_scene_revisions": [],\n  "entities": [],\n'
        b'  "location_events": [],\n  "places": [],\n  "project_id": "project-01",\n'
        b'  "relationship_events": [],\n'
        b'  "schema_version": "project-relationship-snapshot-v1",\n'
        b'  "snapshot_version": 0\n}\n'
    )
    assert decode_project_snapshot(payload) == snapshot
    assert encode_project_snapshot(decode_project_snapshot(payload)) == payload


def test_project_snapshot_decoder_rejects_unknown_fields() -> None:
    data = _encoded_snapshot_data()
    data["unexpected"] = True

    with pytest.raises(SnapshotDecodeError, match="unexpected"):
        decode_project_snapshot(json.dumps(data).encode())


def test_project_snapshot_decoder_rejects_missing_fields() -> None:
    data = _encoded_snapshot_data()
    del data["places"]

    with pytest.raises(SnapshotDecodeError, match="missing fields: places"):
        decode_project_snapshot(json.dumps(data).encode())


def test_project_snapshot_decoder_rejects_invalid_enum_values() -> None:
    data = _encoded_snapshot_data()
    data["relationship_events"][0]["status"] = "published"

    with pytest.raises(SnapshotDecodeError, match="published"):
        decode_project_snapshot(json.dumps(data).encode())


@pytest.mark.parametrize("root", [[], "snapshot", 7, None])
def test_project_snapshot_decoder_rejects_non_object_root(root: object) -> None:
    with pytest.raises(SnapshotDecodeError, match="root must be an object"):
        decode_project_snapshot(json.dumps(root).encode())


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_project_snapshot_decoder_rejects_non_utf8_json(encoding: str) -> None:
    canonical_json = encode_project_snapshot(_semantic_project_snapshot()).decode("utf-8")

    with pytest.raises(SnapshotDecodeError, match="snapshot is not valid UTF-8 JSON"):
        decode_project_snapshot(canonical_json.encode(encoding))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", 7),
        ("active_scene_revisions", {}),
        ("relationship_events", {}),
    ],
)
def test_project_snapshot_decoder_rejects_wrong_project_field_types(
    field: str, value: object
) -> None:
    data = _encoded_snapshot_data()
    data[field] = value

    with pytest.raises(SnapshotDecodeError, match=field):
        decode_project_snapshot(json.dumps(data).encode())


def test_project_snapshot_decoder_rejects_bool_for_integer_field() -> None:
    data = _encoded_snapshot_data()
    data["snapshot_version"] = True

    with pytest.raises(SnapshotDecodeError, match="snapshot_version"):
        decode_project_snapshot(json.dumps(data).encode())


def test_project_snapshot_decoder_rejects_non_object_nested_entry() -> None:
    data = _encoded_snapshot_data()
    data["relationship_events"] = ["not-an-object"]

    with pytest.raises(SnapshotDecodeError, match="relationship event must be an object"):
        decode_project_snapshot(json.dumps(data).encode())


@pytest.mark.parametrize("schema_version", ["project-relationship-snapshot-v2", "unknown"])
def test_project_snapshot_decoder_rejects_unsupported_schema(schema_version: str) -> None:
    data = _encoded_snapshot_data()
    data["schema_version"] = schema_version

    with pytest.raises(SnapshotDecodeError, match="schema"):
        decode_project_snapshot(json.dumps(data).encode())


@pytest.mark.parametrize("value", [1.0001, -0.0001])
def test_project_snapshot_decoder_rejects_non_finite_or_out_of_range_confidence(
    value: float,
) -> None:
    data = _encoded_snapshot_data()
    data["relationship_events"][0]["confidence"] = value

    with pytest.raises(SnapshotDecodeError, match="confidence"):
        decode_project_snapshot(json.dumps(data).encode())


@pytest.mark.parametrize("overflow", ["1e400", "-1e400"])
def test_project_snapshot_decoder_rejects_confidence_overflow(overflow: str) -> None:
    payload = encode_project_snapshot(_semantic_project_snapshot()).replace(
        b'"confidence": 0.75',
        f'"confidence": {overflow}'.encode(),
    )

    with pytest.raises(SnapshotDecodeError, match="confidence"):
        decode_project_snapshot(payload)


@pytest.mark.parametrize("event_field", ["relationship_events", "location_events"])
@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_project_snapshot_decoder_accepts_closed_confidence_boundaries(
    event_field: str,
    confidence: float,
) -> None:
    data = _encoded_snapshot_data()
    if event_field == "location_events":
        _move_relationship_to_location(data)
    data[event_field][0]["confidence"] = confidence

    snapshot = decode_project_snapshot(json.dumps(data).encode())

    assert getattr(snapshot, event_field)[0].confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_project_snapshot_decoder_rejects_location_confidence_range(
    confidence: float,
) -> None:
    data = _encoded_snapshot_data()
    _move_relationship_to_location(data)
    data["location_events"][0]["confidence"] = confidence

    with pytest.raises(SnapshotDecodeError, match="confidence"):
        decode_project_snapshot(json.dumps(data).encode())


@pytest.mark.parametrize("overflow", ["1e400", "-1e400"])
def test_project_snapshot_decoder_rejects_location_confidence_overflow(
    overflow: str,
) -> None:
    data = _encoded_snapshot_data()
    _move_relationship_to_location(data)
    payload = json.dumps(data).replace("0.75", overflow).encode()

    with pytest.raises(SnapshotDecodeError, match="confidence"):
        decode_project_snapshot(payload)


@pytest.mark.parametrize("boundary", ["encode", "decode"])
def test_snapshot_codec_rejects_approved_event_with_pending_dependencies(
    boundary: str,
) -> None:
    snapshot = _semantic_project_snapshot()
    invalid = replace(
        snapshot,
        relationship_events=(
            replace(
                snapshot.relationship_events[0],
                status=CandidateStatus.APPROVED,
            ),
        ),
    )

    with pytest.raises((ValueError, SnapshotDecodeError), match="approved|dependency"):
        if boundary == "encode":
            encode_project_snapshot(invalid)
        else:
            decode_project_snapshot(json.dumps(asdict(invalid)).encode())


@pytest.mark.parametrize("identifier_kind", ["candidate", "event"])
def test_snapshot_codec_rejects_duplicate_project_identifiers(
    identifier_kind: str,
) -> None:
    snapshot = _semantic_project_snapshot()
    if identifier_kind == "candidate":
        invalid = replace(
            snapshot,
            places=(replace(snapshot.places[0], candidate_id="entity-seoyeon"),),
        )
    else:
        invalid = replace(
            snapshot,
            location_events=(replace(snapshot.location_events[0], event_id="relationship-01"),),
        )

    with pytest.raises(ValueError, match="unique"):
        encode_project_snapshot(invalid)


def test_snapshot_codec_rejects_approved_candidate_with_stale_evidence() -> None:
    snapshot = _semantic_project_snapshot()
    stale = replace(
        snapshot.entities[0],
        status=CandidateStatus.APPROVED,
        evidence=(Evidence("scene-01:r1:0000", "scene-01", 1, 0, 2, "서연"),),
    )
    invalid = replace(snapshot, entities=(stale, snapshot.entities[1]))

    with pytest.raises(ValueError, match="stale|revision"):
        encode_project_snapshot(invalid)


def _project_snapshot_with_relationship_event() -> ProjectRelationshipSnapshot:
    evidence = Evidence(
        chunk_id="scene-01:r1:0000",
        scene_id="scene-01",
        scene_revision=1,
        start_offset=0,
        end_offset=11,
        text="서연은 민준을 만났다.",
    )
    relationship = RelationshipEventCandidate(
        event_id="relationship-01",
        subject_key="서연",
        object_key="민준",
        category="first_meeting",
        description="서연은 민준을 만났다.",
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=3,
        confidence=0.75,
        evidence=(evidence,),
    )
    return ProjectRelationshipSnapshot(
        project_id="project-01",
        snapshot_version=2,
        schema_version="project-relationship-snapshot-v1",
        active_scene_revisions=(("scene-01", 1),),
        entities=(),
        places=(),
        relationship_events=(relationship,),
        location_events=(),
    )


def _semantic_project_snapshot() -> ProjectRelationshipSnapshot:
    evidence = Evidence("scene-01:r2:0000", "scene-01", 2, 0, 2, "서연")
    seoyeon = EntityCandidate(
        candidate_id="entity-seoyeon",
        normalized_name="서연",
        display_name="서연",
        aliases=(),
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=2,
        evidence=(evidence,),
    )
    minjun = replace(
        seoyeon,
        candidate_id="entity-minjun",
        normalized_name="민준",
        display_name="민준",
        evidence=(),
    )
    place = PlaceCandidate(
        candidate_id="place-cafe",
        normalized_name="카페",
        display_name="카페",
        aliases=(),
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=2,
        evidence=(),
    )
    relationship = RelationshipEventCandidate(
        event_id="relationship-01",
        subject_key="entity-seoyeon",
        object_key="entity-minjun",
        category="trust",
        description="서연은 민준을 믿었다.",
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=2,
        scene_sequence=3,
        confidence=0.75,
        evidence=(),
    )
    location = LocationEventCandidate(
        event_id="location-01",
        character_key="entity-seoyeon",
        place_key="place-cafe",
        event_type=LocationEventType.ARRIVED,
        description="서연은 카페에 도착했다.",
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=2,
        scene_sequence=3,
        confidence=0.75,
        evidence=(),
    )
    return ProjectRelationshipSnapshot(
        project_id="project-01",
        snapshot_version=2,
        schema_version="project-relationship-snapshot-v1",
        active_scene_revisions=(("scene-01", 2),),
        entities=(seoyeon, minjun),
        places=(place,),
        relationship_events=(relationship,),
        location_events=(location,),
    )


def _encoded_snapshot_data() -> dict[str, object]:
    snapshot = replace(_semantic_project_snapshot(), location_events=())
    return json.loads(encode_project_snapshot(snapshot))


def _move_relationship_to_location(data: dict[str, object]) -> None:
    relationship = data["relationship_events"].pop()
    data["location_events"] = [
        {
            "event_id": "location-01",
            "character_key": relationship["subject_key"],
            "place_key": "카페",
            "event_type": "arrived",
            "description": "서연은 카페에 도착했다.",
            "status": relationship["status"],
            "scene_id": relationship["scene_id"],
            "scene_revision": relationship["scene_revision"],
            "scene_sequence": relationship["scene_sequence"],
            "confidence": relationship["confidence"],
            "evidence": relationship["evidence"],
        }
    ]
