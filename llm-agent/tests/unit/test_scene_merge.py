from dataclasses import replace

import pytest

from narrative_analysis_agent import (
    CandidateStatus,
    EntityCandidate,
    Evidence,
    RelationshipEventCandidate,
)
from narrative_analysis_agent.assembly.merge import MergeInvariantError, merge_chunk_analyses
from narrative_analysis_agent.assembly.models import CHUNK_ANALYSIS_SCHEMA_VERSION, ChunkAnalysis


def _analysis(
    ordinal: int,
    *,
    summary: str = "",
    entities: tuple[EntityCandidate, ...] = (),
    relationship_events: tuple[RelationshipEventCandidate, ...] = (),
) -> ChunkAnalysis:
    start = ordinal * 250
    return ChunkAnalysis(
        schema_version=CHUNK_ANALYSIS_SCHEMA_VERSION,
        chunk_id=f"scene-01:r1:{ordinal:04d}",
        chunk_ordinal=ordinal,
        chunk_start=start,
        chunk_end=start + 300,
        source_text=" " * 300,
        scene_id="scene-01",
        scene_revision=1,
        summary=summary,
        entities=entities,
        places=(),
        relationship_events=relationship_events,
        location_events=(),
    )


def _entity(candidate_id: str, start: int, end: int) -> EntityCandidate:
    return EntityCandidate(
        candidate_id=candidate_id,
        normalized_name="서연",
        display_name="서연",
        aliases=("연이",),
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=1,
        evidence=(Evidence("scene-01:r1:0000", "scene-01", 1, start, end, "  "),),
    )


def test_scene_merge_orders_numeric_chunks_and_merges_candidates() -> None:
    first = _analysis(0, summary="첫 요약", entities=(_entity("entity-01", 10, 12),))
    second = _analysis(
        1,
        summary="둘째 요약",
        entities=(
            replace(
                _entity("entity-02", 260, 262),
                evidence=(Evidence("scene-01:r1:0001", "scene-01", 1, 260, 262, "  "),),
            ),
        ),
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (second, first))

    assert snapshot.summary == "첫 요약\n둘째 요약"
    assert len(snapshot.entities) == 1
    assert snapshot.entities[0].candidate_id == "entity-01"
    assert snapshot.entities[0].status is CandidateStatus.PENDING


def test_scene_merge_rejects_non_pending_candidates() -> None:
    analysis = _analysis(
        0, entities=(replace(_entity("entity-01", 10, 12), status=CandidateStatus.APPROVED),)
    )

    with pytest.raises(MergeInvariantError, match="pending"):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))
