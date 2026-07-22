import asyncio

import pytest

from narrative_analysis_agent import Evidence, SceneAnalysisRequest, SceneRelationshipSnapshot

pytestmark = pytest.mark.live

REQUIRED_RELATIONSHIPS = {
    ("character:han-seoyun", "character:cha-mina", "family"),
    ("character:han-seoyun", "character:kang-dohyeon", "romance"),
    ("character:han-seoyun", "character:yun-taegyeong", "friendship"),
    ("character:kang-dohyeon", "character:cha-mina", "professional"),
    ("character:kang-dohyeon", "character:yun-taegyeong", "antagonistic"),
}
ALLOWED_LOCATION_EVENTS = {
    ("character:cha-mina", "place:haedam-bookstore", "departed"),
    ("character:han-seoyun", "place:haedam-bookstore", "arrived"),
    ("character:han-seoyun", "place:haedam-bookstore", "present"),
    ("character:kang-dohyeon", "place:haedam-bookstore", "arrived"),
    ("character:kang-dohyeon", "place:haedam-bookstore", "present"),
    ("character:yun-taegyeong", "place:haedam-bookstore", "arrived"),
    ("character:yun-taegyeong", "place:haedam-bookstore", "departed"),
}


def _assert_evidence_matches_source(snapshot: SceneRelationshipSnapshot, source: str) -> None:
    for candidate in (
        *snapshot.entities,
        *snapshot.places,
        *snapshot.relationship_events,
        *snapshot.location_events,
    ):
        for evidence in candidate.evidence:
            _assert_evidence_matches_candidate_source(evidence, snapshot, source)


def _assert_evidence_matches_candidate_source(
    evidence: Evidence,
    snapshot: SceneRelationshipSnapshot,
    source: str,
) -> None:
    assert evidence.scene_id == snapshot.scene_id
    assert evidence.scene_revision == snapshot.scene_revision
    prefix = f"{snapshot.scene_id}:r{snapshot.scene_revision}:"
    assert evidence.chunk_id.startswith(prefix)
    ordinal_text = evidence.chunk_id.removeprefix(prefix)
    assert ordinal_text.isdigit()
    assert evidence.chunk_id == f"{prefix}{int(ordinal_text):04d}"

    chunk_start = int(ordinal_text) * 250
    chunk_end = min(chunk_start + 300, len(source))
    assert chunk_start <= evidence.start_offset < evidence.end_offset <= chunk_end
    assert source[evidence.start_offset : evidence.end_offset] == evidence.text


def test_live_scene_analysis_matches_required_relationships(
    live_agent,
    scene_request: SceneAnalysisRequest,
) -> None:
    request = scene_request
    result = asyncio.run(live_agent.analyze_scene(request))
    relationships = {
        (event.subject_key, event.object_key, event.category)
        for event in result.snapshot.relationship_events
    }
    location_events = {
        (event.character_key, event.place_key, event.event_type.value)
        for event in result.snapshot.location_events
    }

    assert relationships >= REQUIRED_RELATIONSHIPS
    assert relationships <= REQUIRED_RELATIONSHIPS
    assert location_events <= ALLOWED_LOCATION_EVENTS
    _assert_evidence_matches_source(result.snapshot, request.text)
