import asyncio

import pytest

from narrative_analysis_agent import AnalyzedChunk, Evidence, SceneAnalysisRequest

pytestmark = pytest.mark.live

REQUIRED_RELATIONSHIPS = {
    ("character:han-seoyun", "character:cha-mina", "family"),
    ("character:han-seoyun", "character:kang-dohyeon", "romance"),
    ("character:han-seoyun", "character:yun-taegyeong", "friendship"),
    ("character:kang-dohyeon", "character:cha-mina", "professional"),
    ("character:kang-dohyeon", "character:yun-taegyeong", "antagonistic"),
}


def _assert_evidence_matches_chunk(evidence: Evidence, chunk: AnalyzedChunk) -> None:
    assert 0 <= evidence.start_offset < evidence.end_offset <= len(chunk.text)
    assert chunk.text[evidence.start_offset : evidence.end_offset] == evidence.text


def test_live_scene_analysis_matches_required_relationships(
    live_agent,
    scene_request: SceneAnalysisRequest,
) -> None:
    analysis = asyncio.run(live_agent.analyze_scene(scene_request))
    relationships = {
        (event.subject_ref, event.object_ref, event.category)
        for chunk in analysis.chunks
        for event in chunk.extraction.relationship_events
    }

    assert relationships >= REQUIRED_RELATIONSHIPS
    for chunk in analysis.chunks:
        extraction = chunk.extraction
        for record in (
            *extraction.entities,
            *extraction.places,
            *extraction.relationship_events,
            *extraction.location_events,
        ):
            for evidence in record.evidence:
                _assert_evidence_matches_chunk(evidence, chunk)
