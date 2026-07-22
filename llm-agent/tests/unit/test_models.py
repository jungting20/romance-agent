import json
import math

import pytest
from pydantic import ValidationError

from narrative_analysis_agent.models import (
    KnowledgeGraphOutput,
    ProjectKnowledgeGraphSnapshot,
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


def test_knowledge_graph_accepts_exact_json_structure() -> None:
    output = validate_graph(graph_payload())

    assert output.document.chapter_id == "scene-01"
    assert output.entities.characters == ()


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
