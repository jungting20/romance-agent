import json
import math
from typing import get_args

import pytest
from pydantic import ValidationError

from narrative_analysis_agent import (
    CharacterMemory as PublicCharacterMemory,
)
from narrative_analysis_agent import (
    MemoryState as PublicMemoryState,
)
from narrative_analysis_agent import (
    MemoryTarget as PublicMemoryTarget,
)
from narrative_analysis_agent.models import (
    Character,
    CharacterMemory,
    Contradiction,
    Coreference,
    Event,
    KnowledgeGraphOutput,
    Location,
    MemoryTarget,
    Movement,
    ProjectKnowledgeGraphSnapshot,
    Relation,
    SceneAnalysisRequest,
)


def graph_payload() -> dict[str, object]:
    return {
        "document": {
            "chapter_id": "scene-01",
            "summary": "서윤은 온실에 도착한다.",
            "narrative_time": "present",
        },
        "entities": {"characters": [], "locations": [], "events": []},
        "relations": [],
        "movements": [],
        "coreferences": [],
        "unresolved_references": [],
        "contradictions": [],
    }


def validate_graph(payload: dict[str, object]) -> KnowledgeGraphOutput:
    return KnowledgeGraphOutput.model_validate_json(json.dumps(payload))


def character_memory() -> CharacterMemory:
    return CharacterMemory(
        id="memory_001",
        character_id="character_001",
        target=MemoryTarget(
            kind="event",
            reference_id="event_001",
            description="비 내리던 날의 약속",
        ),
        content="서윤은 비 내리던 날의 약속을 기억한다.",
        state="remembered",
        time_expression="10년 전",
        scene_sequence=4,
        evidence="그녀는 10년 전 비 내리던 날의 약속을 기억했다",
        confidence=0.94,
    )


def character_memory_payload(**updates: object) -> dict[str, object]:
    payload = character_memory().model_dump(mode="json")
    payload.update(updates)
    return payload


def test_knowledge_graph_accepts_exact_json_structure() -> None:
    output = validate_graph(graph_payload())

    assert output.document.chapter_id == "scene-01"
    assert output.entities.characters == ()


def test_character_memory_round_trips_through_json_validation() -> None:
    memory = character_memory()

    restored = CharacterMemory.model_validate_json(memory.model_dump_json())

    assert restored == memory


def test_memory_contract_types_are_exported_from_package() -> None:
    assert PublicCharacterMemory is CharacterMemory
    assert PublicMemoryTarget is MemoryTarget
    assert set(get_args(PublicMemoryState)) == {
        "remembered",
        "forgotten",
        "repressed",
        "uncertain",
        "false_memory",
    }


@pytest.mark.parametrize(
    "state",
    ["remembered", "forgotten", "repressed", "uncertain", "false_memory"],
)
def test_character_memory_accepts_each_public_state(state: str) -> None:
    updates: dict[str, object] = {"state": state}
    if state == "false_memory":
        updates["target"] = {
            "kind": "described_event",
            "reference_id": None,
            "description": "실제로는 없었던 약속",
        }
    memory = CharacterMemory.model_validate(character_memory_payload(**updates))

    assert memory.state == state


def test_character_memory_rejects_unknown_state() -> None:
    with pytest.raises(ValidationError):
        CharacterMemory.model_validate(character_memory_payload(state="unknown"))


def test_false_memory_rejects_linked_target() -> None:
    with pytest.raises(ValidationError):
        CharacterMemory.model_validate(character_memory_payload(state="false_memory"))


@pytest.mark.parametrize("kind", ["described_event", "described_relation", "other"])
def test_false_memory_accepts_description_only_target(kind: str) -> None:
    memory = CharacterMemory.model_validate(
        character_memory_payload(
            state="false_memory",
            target={
                "kind": kind,
                "reference_id": None,
                "description": "실제로는 없었던 기억",
            },
        )
    )

    assert memory.target.kind == kind


@pytest.mark.parametrize(
    ("kind", "reference_id"),
    [
        ("character", "character_002"),
        ("location", "location_001"),
        ("event", "event_002"),
        ("relation", "relation_001"),
    ],
)
def test_memory_target_accepts_linked_target_kinds(kind: str, reference_id: str) -> None:
    target = MemoryTarget(
        kind=kind,
        reference_id=reference_id,
        description="연결된 대상",
    )

    assert target.reference_id == reference_id


@pytest.mark.parametrize("kind", ["described_event", "described_relation", "other"])
def test_memory_target_accepts_description_only_target_kinds(kind: str) -> None:
    target = MemoryTarget(kind=kind, reference_id=None, description="설명만 있는 대상")

    assert target.reference_id is None


def test_knowledge_graph_accepts_character_memories() -> None:
    payload = graph_payload()
    payload["character_memories"] = [character_memory().model_dump(mode="json")]

    output = validate_graph(payload)

    assert output.character_memories == (character_memory(),)


def test_character_memory_rejects_unknown_fields() -> None:
    payload = character_memory().model_dump(mode="json")
    payload["unknown"] = True

    with pytest.raises(ValidationError):
        CharacterMemory.model_validate(payload)


def test_memory_target_rejects_unknown_fields() -> None:
    payload = character_memory().target.model_dump(mode="json")
    payload["unknown"] = True

    with pytest.raises(ValidationError):
        MemoryTarget.model_validate(payload)


@pytest.mark.parametrize(
    ("memory_id", "target_kind", "reference_id"),
    [
        ("invalid_001", "event", "event_001"),
        ("memory_001", "character", "event_001"),
        ("memory_001", "location", "character_001"),
        ("memory_001", "event", "location_001"),
        ("memory_001", "relation", "event_001"),
    ],
)
def test_character_memory_rejects_invalid_id_prefixes(
    memory_id: str, target_kind: str, reference_id: str
) -> None:
    with pytest.raises(ValidationError):
        CharacterMemory.model_validate(
            character_memory_payload(
                id=memory_id,
                target={
                    "kind": target_kind,
                    "reference_id": reference_id,
                    "description": "잘못된 참조",
                },
            ),
        )


@pytest.mark.parametrize("kind", ["described_event", "described_relation", "other"])
def test_memory_target_rejects_reference_for_description_only_target(kind: str) -> None:
    with pytest.raises(ValidationError):
        MemoryTarget(kind=kind, reference_id="event_001", description="설명만 있는 대상")


@pytest.mark.parametrize("kind", ["character", "location", "event", "relation"])
def test_memory_target_requires_reference_for_linked_target(kind: str) -> None:
    with pytest.raises(ValidationError):
        MemoryTarget(kind=kind, reference_id=None, description="연결된 대상")


@pytest.mark.parametrize(
    ("target_description", "content", "evidence"),
    [
        ("", "기억", "근거"),
        ("대상", "", "근거"),
        ("대상", "기억", ""),
    ],
)
def test_character_memory_rejects_empty_required_text(
    target_description: str, content: str, evidence: str
) -> None:
    with pytest.raises(ValidationError):
        CharacterMemory.model_validate(
            character_memory_payload(
                target={
                    "kind": "event",
                    "reference_id": "event_001",
                    "description": target_description,
                },
                content=content,
                evidence=evidence,
            )
        )


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -math.inf, 0.79, 1.01])
def test_character_memory_rejects_invalid_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        CharacterMemory.model_validate(character_memory_payload(confidence=confidence))


def test_character_memory_rejects_negative_scene_sequence() -> None:
    with pytest.raises(ValidationError):
        CharacterMemory.model_validate(character_memory_payload(scene_sequence=-1))


def test_character_memory_and_target_are_frozen() -> None:
    memory = character_memory()

    with pytest.raises(ValidationError):
        memory.content = "변경됨"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        memory.target.description = "변경됨"  # type: ignore[misc]


def test_legacy_v2_snapshot_defaults_character_memories_to_empty() -> None:
    snapshot = ProjectKnowledgeGraphSnapshot.model_validate(
        {
            "project_id": "project-01",
            "snapshot_version": 1,
            "schema_version": "project-knowledge-graph-snapshot-v2",
        }
    )

    assert snapshot.character_memories == ()


def test_knowledge_graph_rejects_unknown_fields() -> None:
    payload = graph_payload()
    payload["unknown"] = True

    with pytest.raises(ValidationError):
        validate_graph(payload)


def test_knowledge_graph_rejects_invalid_enum() -> None:
    payload = graph_payload()
    payload["document"] = {
        "chapter_id": "scene-01",
        "summary": "서윤은 온실에 도착한다.",
        "narrative_time": "future",
    }

    with pytest.raises(ValidationError):
        validate_graph(payload)


def test_knowledge_graph_rejects_general_confidence_below_point_eight() -> None:
    payload = graph_payload()
    payload["entities"] = {
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
                "status": "unknown",
                "first_mention": "서윤",
                "confidence": 0.79,
            }
        ],
        "locations": [],
        "events": [],
    }

    with pytest.raises(ValidationError):
        validate_graph(payload)


def test_knowledge_graph_rejects_non_finite_confidence() -> None:
    payload = graph_payload()
    payload["entities"] = {
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
                "status": "unknown",
                "first_mention": "서윤",
                "confidence": math.nan,
            }
        ],
        "locations": [],
        "events": [],
    }

    with pytest.raises(ValidationError):
        validate_graph(payload)


def test_knowledge_graph_rejects_lowercase_custom_type() -> None:
    payload = graph_payload()
    payload["entities"] = {
        "characters": [],
        "locations": [],
        "events": [
            {
                "id": "event_001",
                "event_type": "arrival",
                "name": "도착",
                "summary": "서윤이 온실에 도착한다.",
                "participant_ids": [],
                "location_ids": [],
                "time_expression": None,
                "narrative_time": "present",
                "sequence": 0,
                "evidence": "도착한다",
                "confidence": 0.8,
            }
        ],
    }

    with pytest.raises(ValidationError):
        validate_graph(payload)


def test_knowledge_graph_allows_nullable_fields() -> None:
    payload = graph_payload()
    payload["entities"] = {
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
                "status": "unknown",
                "first_mention": "서윤",
                "confidence": 0.8,
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
                "confidence": 0.8,
            }
        ],
        "events": [],
    }

    output = validate_graph(payload)

    assert output.entities.characters[0].age is None
    assert output.entities.locations[0].parent_location_id is None


@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        pytest.param(
            Character,
            {
                "id": "character_001",
                "canonical_name": "서윤",
                "aliases": (),
                "description": "",
                "gender": "unknown",
                "age": None,
                "occupation": None,
                "affiliation": None,
                "status": "unknown",
                "first_mention": "",
                "confidence": 0.8,
            },
            id="character-first-mention",
        ),
        pytest.param(
            Location,
            {
                "id": "location_001",
                "canonical_name": "온실",
                "aliases": (),
                "location_type": "building",
                "parent_location_id": None,
                "description": "",
                "first_mention": "",
                "confidence": 0.8,
            },
            id="location-first-mention",
        ),
        pytest.param(
            Event,
            {
                "id": "event_001",
                "event_type": "ARRIVAL",
                "name": "도착",
                "summary": "",
                "participant_ids": (),
                "location_ids": (),
                "time_expression": None,
                "narrative_time": "present",
                "sequence": 0,
                "evidence": "",
                "confidence": 0.8,
            },
            id="event-evidence",
        ),
        pytest.param(
            Relation,
            {
                "id": "relation_001",
                "source_id": "character_001",
                "relation_type": "KNOWS",
                "target_id": "character_002",
                "state": "active",
                "directed": True,
                "start_event_id": None,
                "end_event_id": None,
                "time_expression": None,
                "scene_sequence": 0,
                "evidence": "",
                "inference": False,
                "confidence": 0.8,
            },
            id="relation-evidence",
        ),
        pytest.param(
            Movement,
            {
                "character_id": "character_001",
                "from_location_id": None,
                "to_location_id": "location_001",
                "movement_type": "ARRIVAL",
                "event_id": None,
                "time_expression": None,
                "sequence": 0,
                "evidence": "",
                "confidence": 0.8,
            },
            id="movement-evidence",
        ),
        pytest.param(
            Coreference,
            {
                "expression": "그녀",
                "resolved_entity_id": "character_001",
                "evidence": "",
                "confidence": 0.8,
            },
            id="coreference-evidence",
        ),
        pytest.param(
            Contradiction,
            {
                "subject_id": "character_001",
                "field_or_relation": "status",
                "existing_value": "missing",
                "new_value": "alive",
                "evidence": "",
                "possible_explanation": "",
            },
            id="contradiction-evidence",
        ),
    ],
)
def test_public_models_reject_empty_evidence_strings(
    model_type: type[object],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)  # type: ignore[attr-defined]


def test_request_is_frozen_and_rejects_blank_identity() -> None:
    request = SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=2,
        text="본문",
    )

    with pytest.raises(ValidationError):
        request.scene_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SceneAnalysisRequest(
            project_id="project-01",
            scene_id="",
            scene_revision=1,
            scene_sequence=2,
            text="본문",
        )


def test_empty_project_snapshot_has_version_zero() -> None:
    snapshot = ProjectKnowledgeGraphSnapshot.empty("project-01")

    assert snapshot.snapshot_version == 0
    assert snapshot.documents == ()
