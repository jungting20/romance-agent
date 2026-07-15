import json
from dataclasses import FrozenInstanceError

import pytest

from apps.narrative_memory.service.models import (
    CandidateStatus,
    Evidence,
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
        start_offset=0,
        end_offset=3,
        text="서연은",
    )

    with pytest.raises(FrozenInstanceError):
        evidence.text = "민준은"  # type: ignore[misc]


def test_project_snapshot_codec_is_stable_and_round_trips() -> None:
    snapshot = _project_snapshot_with_relationship_event()

    payload = encode_project_snapshot(snapshot)

    assert (
        payload
        == (
            "{\n"
            '  "active_scene_revisions": [\n'
            "    [\n"
            '      "scene-01",\n'
            "      1\n"
            "    ]\n"
            "  ],\n"
            '  "entities": [],\n'
            '  "location_events": [],\n'
            '  "places": [],\n'
            '  "project_id": "project-01",\n'
            '  "relationship_events": [\n'
            "    {\n"
            '      "category": "first_meeting",\n'
            '      "confidence": 0.75,\n'
            '      "description": "서연은 민준을 만났다.",\n'
            '      "event_id": "relationship-01",\n'
            '      "evidence": [\n'
            "        {\n"
            '          "chunk_id": "scene-01:r1:0000",\n'
            '          "end_offset": 11,\n'
            '          "start_offset": 0,\n'
            '          "text": "서연은 민준을 만났다."\n'
            "        }\n"
            "      ],\n"
            '      "object_key": "민준",\n'
            '      "scene_id": "scene-01",\n'
            '      "scene_revision": 1,\n'
            '      "scene_sequence": 3,\n'
            '      "status": "pending",\n'
            '      "subject_key": "서연"\n'
            "    }\n"
            "  ],\n"
            '  "schema_version": "project-relationship-snapshot-v1",\n'
            '  "snapshot_version": 2\n'
            "}\n"
        ).encode()
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
    canonical_json = encode_project_snapshot(_project_snapshot_with_relationship_event()).decode(
        "utf-8"
    )

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


def _project_snapshot_with_relationship_event() -> ProjectRelationshipSnapshot:
    evidence = Evidence(
        chunk_id="scene-01:r1:0000",
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


def _encoded_snapshot_data() -> dict[str, object]:
    return json.loads(encode_project_snapshot(_project_snapshot_with_relationship_event()))
