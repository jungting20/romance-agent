from dataclasses import replace

import pytest

from narrative_analysis_agent import CandidateStatus, Evidence, KnownIdentity, LocationEventType
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
    text = "0123456789Alex met Bea at the pier." + "x" * 65
    return SceneChunk(
        chunk_id="scene-01:r7:0001",
        scene_id="scene-01",
        manuscript_revision=7,
        ordinal=1,
        start_offset=250,
        end_offset=350,
        content_hash="unused-by-translation",
        text=text,
    )


@pytest.fixture
def extraction(chunk: SceneChunk) -> SceneChunkExtraction:
    evidence = (RelativeEvidence(10, 14, chunk.text[10:14]),)
    return SceneChunkExtraction(
        summary="  Alex   meets Bea.  ",
        entities=(
            ExtractedEntity("alex", "alex", "Alex", (), evidence),
            ExtractedEntity("bea", "bea", "Bea", ("B",), evidence),
        ),
        places=(ExtractedPlace("pier", "pier", "Pier", (), evidence),),
        relationship_events=(
            ExtractedRelationshipEvent(
                "alex",
                "bea",
                "romance",
                "They meet.",
                0.75,
                evidence,
            ),
        ),
        location_events=(
            ExtractedLocationEvent(
                "alex",
                "pier",
                LocationEventType.ARRIVED,
                "Alex arrives.",
                1.0,
                evidence,
            ),
        ),
    )


def _translate(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
    known_entities: tuple[KnownIdentity, ...] = (),
    known_places: tuple[KnownIdentity, ...] = (),
):
    return translate_chunk_extraction(chunk, 3, extraction, known_entities, known_places)


def test_translate_chunk_extraction_builds_pending_candidates_with_absolute_evidence(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
) -> None:
    analysis = _translate(chunk, extraction)

    assert analysis.schema_version == "chunk-analysis-v1"
    assert analysis.chunk_id == "scene-01:r7:0001"
    assert analysis.chunk_ordinal == 1
    assert analysis.chunk_start == 250
    assert analysis.chunk_end == 350
    assert analysis.source_text == chunk.text
    assert analysis.scene_id == "scene-01"
    assert analysis.scene_revision == 7
    assert analysis.summary == "Alex meets Bea."
    assert analysis.entities[0].status is CandidateStatus.PENDING
    assert analysis.places[0].status is CandidateStatus.PENDING
    assert analysis.relationship_events[0].status is CandidateStatus.PENDING
    assert analysis.location_events[0].status is CandidateStatus.PENDING
    assert analysis.entities[0].evidence[0] == Evidence(
        chunk_id="scene-01:r7:0001",
        scene_id="scene-01",
        scene_revision=7,
        start_offset=260,
        end_offset=264,
        text=chunk.text[10:14],
    )
    assert analysis.relationship_events[0].subject_key == analysis.entities[0].candidate_id
    assert analysis.relationship_events[0].object_key == analysis.entities[1].candidate_id
    assert analysis.location_events[0].character_key == analysis.entities[0].candidate_id
    assert analysis.location_events[0].place_key == analysis.places[0].candidate_id


def test_translation_is_deterministic_and_ids_are_separated_by_kind(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
) -> None:
    first = _translate(chunk, extraction)
    second = _translate(chunk, extraction)

    assert first == second
    assert first.entities[0].candidate_id.startswith("sha256:")
    assert first.entities[0].candidate_id != first.places[0].candidate_id
    assert first.relationship_events[0].event_id != first.location_events[0].event_id


def test_translation_rejects_evidence_text_mismatch(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
) -> None:
    bad_entity = replace(
        extraction.entities[0],
        evidence=(RelativeEvidence(10, 14, "wrong"),),
    )

    with pytest.raises(ExtractionTranslationError, match="evidence text"):
        _translate(chunk, replace(extraction, entities=(bad_entity, *extraction.entities[1:])))


@pytest.mark.parametrize("start,end", [(-1, 2), (2, 2), (4, 3), (0, 1_000)])
def test_translation_rejects_relative_evidence_outside_chunk(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
    start: int,
    end: int,
) -> None:
    bad = replace(
        extraction.entities[0],
        evidence=(RelativeEvidence(start, end, "invalid"),),
    )

    with pytest.raises(ExtractionTranslationError, match="evidence bounds"):
        _translate(chunk, replace(extraction, entities=(bad, *extraction.entities[1:])))


def test_translation_rejects_unknown_entity_reference(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
) -> None:
    bad_relationship = replace(extraction.relationship_events[0], subject_ref="missing")

    with pytest.raises(ExtractionTranslationError, match="unknown entity reference"):
        _translate(
            chunk,
            replace(extraction, relationship_events=(bad_relationship,)),
        )


def test_translation_rejects_ambiguous_duplicate_local_reference(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
) -> None:
    duplicate = replace(extraction.entities[0], display_name="Duplicate")

    with pytest.raises(ExtractionTranslationError, match="ambiguous local reference"):
        _translate(chunk, replace(extraction, entities=(*extraction.entities, duplicate)))


@pytest.mark.parametrize("kind", ["entity", "place"])
@pytest.mark.parametrize("local_ref", ["", "   "])
def test_translation_rejects_blank_local_references(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
    kind: str,
    local_ref: str,
) -> None:
    if kind == "entity":
        changed = replace(
            extraction,
            entities=(replace(extraction.entities[0], local_ref=local_ref),),
            relationship_events=(),
            location_events=(),
        )
    else:
        changed = replace(
            extraction,
            places=(replace(extraction.places[0], local_ref=local_ref),),
            location_events=(),
        )

    with pytest.raises(ExtractionTranslationError, match="blank local reference"):
        _translate(chunk, changed)


def test_translation_resolves_known_stable_entity_and_place_references(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
) -> None:
    relationship = replace(
        extraction.relationship_events[0],
        subject_ref="entity:known-alex",
    )
    location = replace(
        extraction.location_events[0],
        character_ref="entity:known-alex",
        place_ref="place:known-pier",
    )
    known_entity = KnownIdentity("entity:known-alex", "alex", "Alex")
    known_place = KnownIdentity("place:known-pier", "pier", "Pier")

    analysis = _translate(
        chunk,
        replace(
            extraction,
            relationship_events=(relationship,),
            location_events=(location,),
        ),
        (known_entity,),
        (known_place,),
    )

    assert analysis.relationship_events[0].subject_key == "entity:known-alex"
    assert analysis.location_events[0].character_key == "entity:known-alex"
    assert analysis.location_events[0].place_key == "place:known-pier"


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("relationship", {"subject_ref": "pier"}, "wrong-kind entity reference"),
        ("location", {"character_ref": "place:known-pier"}, "wrong-kind entity reference"),
        ("location", {"place_ref": "alex"}, "wrong-kind place reference"),
        ("location", {"place_ref": "entity:known-alex"}, "wrong-kind place reference"),
    ],
)
def test_translation_rejects_wrong_kind_references(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
    field: str,
    replacement: dict[str, str],
    message: str,
) -> None:
    known_entities = (KnownIdentity("entity:known-alex", "alex", "Alex"),)
    known_places = (KnownIdentity("place:known-pier", "pier", "Pier"),)
    if field == "relationship":
        changed = replace(
            extraction,
            relationship_events=(replace(extraction.relationship_events[0], **replacement),),
        )
    else:
        changed = replace(
            extraction,
            location_events=(replace(extraction.location_events[0], **replacement),),
        )

    with pytest.raises(ExtractionTranslationError, match=message):
        _translate(chunk, changed, known_entities, known_places)


def test_translation_rejects_local_reference_colliding_with_known_key(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
) -> None:
    known = KnownIdentity("alex", "alexander", "Alexander")

    with pytest.raises(ExtractionTranslationError, match="ambiguous local reference"):
        _translate(chunk, extraction, (known,), ())


@pytest.mark.parametrize(
    "category",
    ["romance", "family", "friendship", "professional", "antagonistic", "other"],
)
def test_translation_supports_every_relationship_category(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
    category: str,
) -> None:
    event = replace(extraction.relationship_events[0], category=category)

    analysis = _translate(chunk, replace(extraction, relationship_events=(event,)))

    assert analysis.relationship_events[0].category == category


@pytest.mark.parametrize("event_type", list(LocationEventType))
def test_translation_supports_every_location_event_type(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
    event_type: LocationEventType,
) -> None:
    event = replace(extraction.location_events[0], event_type=event_type)

    analysis = _translate(chunk, replace(extraction, location_events=(event,)))

    assert analysis.location_events[0].event_type is event_type


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), -0.01, 1.01])
@pytest.mark.parametrize("event_kind", ["relationship", "location"])
def test_translation_rejects_non_finite_or_out_of_range_confidence(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
    confidence: float,
    event_kind: str,
) -> None:
    if event_kind == "relationship":
        changed = replace(
            extraction,
            relationship_events=(
                replace(extraction.relationship_events[0], confidence=confidence),
            ),
        )
    else:
        changed = replace(
            extraction,
            location_events=(replace(extraction.location_events[0], confidence=confidence),),
        )

    with pytest.raises(ExtractionTranslationError, match="confidence"):
        _translate(chunk, changed)


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_translation_accepts_confidence_boundaries(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
    confidence: float,
) -> None:
    relationship = replace(extraction.relationship_events[0], confidence=confidence)
    location = replace(extraction.location_events[0], confidence=confidence)

    analysis = _translate(
        chunk,
        replace(
            extraction,
            relationship_events=(relationship,),
            location_events=(location,),
        ),
    )

    assert analysis.relationship_events[0].confidence == confidence
    assert analysis.location_events[0].confidence == confidence


def test_equal_numeric_zero_confidence_produces_the_same_event_ids(
    chunk: SceneChunk,
    extraction: SceneChunkExtraction,
) -> None:
    positive_zero = replace(
        extraction,
        relationship_events=(replace(extraction.relationship_events[0], confidence=0.0),),
        location_events=(replace(extraction.location_events[0], confidence=0.0),),
    )
    negative_zero = replace(
        extraction,
        relationship_events=(replace(extraction.relationship_events[0], confidence=-0.0),),
        location_events=(replace(extraction.location_events[0], confidence=-0.0),),
    )

    positive_analysis = _translate(chunk, positive_zero)
    negative_analysis = _translate(chunk, negative_zero)

    assert positive_analysis.relationship_events[0].event_id == (
        negative_analysis.relationship_events[0].event_id
    )
    assert positive_analysis.location_events[0].event_id == (
        negative_analysis.location_events[0].event_id
    )
