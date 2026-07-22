import pytest
from pydantic import ValidationError

from narrative_analysis_agent.models import ChunkExtraction, Evidence, SceneAnalysisRequest


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


def test_chunk_extraction_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ChunkExtraction.model_validate({"summary": "요약", "unknown": True})


def test_evidence_requires_an_increasing_range() -> None:
    with pytest.raises(ValidationError):
        Evidence(start_offset=2, end_offset=2, text="")
