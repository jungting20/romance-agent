from dataclasses import replace

import pytest

from narrative_analysis_agent import CandidateStatus, KnownIdentity, LocationEventType
from narrative_analysis_agent.assembly.models import (
    ExtractedEntity,
    ExtractedLocationEvent,
    ExtractedPlace,
    ExtractedRelationshipEvent,
    RelativeEvidence,
    SceneChunkExtraction,
)
from narrative_analysis_agent.assembly.translation import (
    ExtractionTranslationError,
    translate_chunk_extraction,
)
from narrative_analysis_agent.chunking import SceneChunk


@pytest.fixture
def chunk() -> SceneChunk:
    return SceneChunk(
        chunk_id="scene-01:r2:0001",
        scene_id="scene-01",
        manuscript_revision=2,
        ordinal=1,
        start_offset=250,
        end_offset=270,
        content_hash="sha256:unused",
        text="서연은 민준과 카페에 갔다.",
    )


@pytest.fixture
def extraction() -> SceneChunkExtraction:
    return SceneChunkExtraction(
        summary="  서연과 민준은 카페에 갔다. ",
        entities=(
            ExtractedEntity("seoyeon", "서연", "서연", (), (RelativeEvidence(0, 2, "서연"),)),
            ExtractedEntity("minjun", "민준", "민준", (), (RelativeEvidence(4, 6, "민준"),)),
        ),
        places=(ExtractedPlace("cafe", "카페", "카페", (), (RelativeEvidence(8, 10, "카페"),)),),
        relationship_events=(
            ExtractedRelationshipEvent(
                "seoyeon",
                "minjun",
                "friendship",
                "함께 갔다.",
                0.8,
                (RelativeEvidence(0, 6, "서연은 민준"),),
            ),
        ),
        location_events=(
            ExtractedLocationEvent(
                "seoyeon",
                "cafe",
                LocationEventType.ARRIVED,
                "카페에 갔다.",
                0.9,
                (RelativeEvidence(8, 14, "카페에 갔다"),),
            ),
        ),
    )


def test_translation_assigns_pending_stable_ids_and_absolute_evidence(
    chunk: SceneChunk, extraction: SceneChunkExtraction
) -> None:
    analysis = translate_chunk_extraction(chunk, 7, extraction, (), ())

    assert analysis.summary == "서연과 민준은 카페에 갔다."
    assert analysis.entities[0].status is CandidateStatus.PENDING
    assert analysis.entities[0].candidate_id.startswith("sha256:")
    assert analysis.entities[0].evidence[0].start_offset == 250
    assert analysis.relationship_events[0].status is CandidateStatus.PENDING
    assert analysis.relationship_events[0].evidence[0].end_offset == 256
    assert analysis.location_events[0].event_type is LocationEventType.ARRIVED


def test_translation_rejects_evidence_that_does_not_match_immutable_chunk(
    chunk: SceneChunk, extraction: SceneChunkExtraction
) -> None:
    invalid = replace(
        extraction,
        entities=(replace(extraction.entities[0], evidence=(RelativeEvidence(0, 2, "민준"),)),),
        relationship_events=(),
        location_events=(),
    )

    with pytest.raises(ExtractionTranslationError, match="evidence text"):
        translate_chunk_extraction(chunk, 7, invalid, (), ())


def test_translation_resolves_known_identity_without_creating_a_candidate(
    chunk: SceneChunk, extraction: SceneChunkExtraction
) -> None:
    event = replace(extraction.relationship_events[0], subject_ref="entity:known-seoyeon")

    analysis = translate_chunk_extraction(
        chunk,
        7,
        replace(extraction, relationship_events=(event,)),
        (KnownIdentity("entity:known-seoyeon", "서연", "서연"),),
        (),
    )

    assert analysis.relationship_events[0].subject_key == "entity:known-seoyeon"
