from dataclasses import FrozenInstanceError

import pytest

from narrative_analysis_agent import (
    KnownIdentity,
    SceneAnalysisRequest,
    SceneAnalysisResult,
    SceneRelationshipSnapshot,
)


def test_public_contract_is_immutable_and_provider_independent() -> None:
    request = SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=7,
        text="서윤이 도착했다.",
        known_entities=(KnownIdentity("character:seoyun", "서윤", "서윤"),),
    )
    snapshot = SceneRelationshipSnapshot.empty("scene-01", 1, 7)
    result = SceneAnalysisResult(run_id="run-01", snapshot=snapshot)

    assert result.snapshot.schema_version == "scene-relationship-snapshot-v1"
    with pytest.raises(FrozenInstanceError):
        request.text = "changed"  # type: ignore[misc]
