from collections.abc import Callable
from dataclasses import replace

import pytest

from narrative_analysis_agent import (
    CandidateStatus,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    LocationEventType,
    PlaceCandidate,
    RelationshipEventCandidate,
)
from narrative_analysis_agent.assembly.merge import MergeInvariantError, merge_chunk_analyses
from narrative_analysis_agent.assembly.models import (
    CHUNK_ANALYSIS_SCHEMA_VERSION,
    ChunkAnalysis,
)


def test_merge_deduplicates_relationship_overlap_and_retains_distinct_evidence() -> None:
    first = _analysis(
        "scene-01:r1:0000",
        relationship_events=(
            _relationship(
                event_id="relationship-01",
                evidence=(
                    _evidence("scene-01:r1:0000", 240, 268, "서연은 민준을 믿는다고 말했다."),
                ),
            ),
        ),
    )
    second = _analysis(
        "scene-01:r1:0001",
        relationship_events=(
            _relationship(
                event_id="relationship-02",
                category="  TRUST  ",
                description="서연은  민준을 믿는다고 말했다. ",
                evidence=(
                    _evidence("scene-01:r1:0001", 250, 268, first.source_text[250:268]),
                    _evidence("scene-01:r1:0001", 268, 280, first.source_text[268:280]),
                ),
            ),
        ),
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (second, first))

    assert len(snapshot.relationship_events) == 1
    event = snapshot.relationship_events[0]
    assert event.event_id == "relationship-01"
    assert [(item.start_offset, item.end_offset) for item in event.evidence] == [
        (240, 268),
        (250, 268),
        (268, 280),
    ]


def test_merge_keeps_disjoint_identical_relationship_occurrences_distinct() -> None:
    analysis = _analysis(
        "scene-01:r1:0000",
        relationship_events=(
            _relationship(
                event_id="relationship-later",
                evidence=(_evidence("scene-01:r1:0000", 30, 50, "믿는다고 말했다."),),
            ),
            _relationship(
                event_id="relationship-earlier",
                evidence=(_evidence("scene-01:r1:0000", 10, 30, "믿는다고 말했다."),),
            ),
        ),
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (analysis,))

    assert [event.event_id for event in snapshot.relationship_events] == [
        "relationship-earlier",
        "relationship-later",
    ]


def test_merge_clusters_relationship_overlap_transitively() -> None:
    analysis = _analysis(
        "scene-01:r1:0000",
        relationship_events=(
            _relationship(
                event_id="relationship-later",
                evidence=(_evidence("scene-01:r1:0000", 20, 30, "믿는다고 말했다."),),
            ),
            _relationship(
                event_id="relationship-bridge",
                evidence=(_evidence("scene-01:r1:0000", 8, 22, "믿는다고 말했다."),),
            ),
            _relationship(
                event_id="relationship-earliest",
                evidence=(_evidence("scene-01:r1:0000", 0, 10, "믿는다고 말했다."),),
            ),
        ),
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (analysis,))

    assert len(snapshot.relationship_events) == 1
    assert snapshot.relationship_events[0].event_id == "relationship-earliest"
    assert [
        (evidence.start_offset, evidence.end_offset)
        for evidence in snapshot.relationship_events[0].evidence
    ] == [(0, 10), (8, 22), (20, 30)]


def test_merge_keeps_relationship_events_with_different_descriptions_distinct() -> None:
    analysis = _analysis(
        "scene-01:r1:0000",
        relationship_events=(
            _relationship(event_id="relationship-02", description="민준은 서연을 의심했다."),
            _relationship(event_id="relationship-01"),
        ),
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (analysis,))

    assert [event.description for event in snapshot.relationship_events] == [
        "민준은 서연을 의심했다.",
        "서연은 민준을 믿는다고 말했다.",
    ]


def test_merge_deduplicates_location_overlap_and_sorts_by_identity() -> None:
    first = _analysis(
        "scene-01:r1:0000",
        location_events=(
            _location(
                event_id="location-02",
                character_key="서연",
                place_key="정원",
                event_type=LocationEventType.PRESENT,
                description="서연은 정원에 머물렀다.",
            ),
            _location(event_id="location-01"),
        ),
    )
    second = _analysis(
        "scene-01:r1:0001",
        location_events=(
            _location(
                event_id="location-overlap",
                description=" 서연은  카페에 도착했다. ",
                evidence=(_evidence("scene-01:r1:0001", 250, 270, first.source_text[250:270]),),
            ),
        ),
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (second, first))

    assert [event.place_key for event in snapshot.location_events] == [
        "정원",
        "카페",
    ]
    assert [
        (item.start_offset, item.end_offset) for item in snapshot.location_events[1].evidence
    ] == [
        (250, 265),
        (250, 270),
    ]


def test_merge_keeps_disjoint_identical_location_occurrences_distinct() -> None:
    analysis = _analysis(
        "scene-01:r1:0000",
        location_events=(
            _location(
                event_id="location-later",
                evidence=(_evidence("scene-01:r1:0000", 90, 110, "카페에 도착했다."),),
            ),
            _location(
                event_id="location-earlier",
                evidence=(_evidence("scene-01:r1:0000", 40, 60, "카페에 도착했다."),),
            ),
        ),
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (analysis,))

    assert [event.event_id for event in snapshot.location_events] == [
        "location-earlier",
        "location-later",
    ]


def test_merge_clusters_location_overlap_transitively() -> None:
    analysis = _analysis(
        "scene-01:r1:0000",
        location_events=(
            _location(
                event_id="location-later",
                evidence=(_evidence("scene-01:r1:0000", 70, 90, "카페에 도착했다."),),
            ),
            _location(
                event_id="location-earliest",
                evidence=(_evidence("scene-01:r1:0000", 50, 72, "카페에 도착했다."),),
            ),
            _location(
                event_id="location-bridge",
                evidence=(_evidence("scene-01:r1:0000", 68, 75, "카페에 도착했다."),),
            ),
        ),
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (analysis,))

    assert len(snapshot.location_events) == 1
    assert snapshot.location_events[0].event_id == "location-earliest"
    assert [
        (evidence.start_offset, evidence.end_offset)
        for evidence in snapshot.location_events[0].evidence
    ] == [(50, 72), (68, 75), (70, 90)]


def test_merge_combines_entity_and_place_aliases_and_evidence_deterministically() -> None:
    first = _analysis(
        "scene-01:r1:0000",
        entities=(
            _entity(
                candidate_id="entity-01",
                aliases=("연이", "서연"),
                evidence=(_evidence("scene-01:r1:0000", 10, 12, "서연"),),
            ),
        ),
        places=(
            _place(
                candidate_id="place-01",
                aliases=("카페",),
                evidence=(_evidence("scene-01:r1:0000", 30, 35, "카페에서"),),
            ),
        ),
    )
    second = _analysis(
        "scene-01:r1:0001",
        entities=(
            _entity(
                candidate_id="entity-02",
                aliases=(" 주인공 ", "연이"),
                evidence=(_evidence("scene-01:r1:0001", 260, 262, "그녀"),),
            ),
        ),
        places=(
            _place(
                candidate_id="place-02",
                aliases=("단골집", "카페"),
                evidence=(_evidence("scene-01:r1:0001", 275, 278, "그곳"),),
            ),
        ),
    )
    first = replace(
        first,
        source_text=first.source_text[:250] + second.source_text[:50],
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (second, first))

    assert len(snapshot.entities) == 1
    assert snapshot.entities[0].candidate_id == "entity-01"
    assert snapshot.entities[0].aliases == ("서연", "연이", "주인공")
    assert [(item.start_offset, item.end_offset) for item in snapshot.entities[0].evidence] == [
        (10, 12),
        (260, 262),
    ]
    assert len(snapshot.places) == 1
    assert snapshot.places[0].candidate_id == "place-01"
    assert snapshot.places[0].aliases == ("단골집", "카페")
    assert [(item.start_offset, item.end_offset) for item in snapshot.places[0].evidence] == [
        (30, 35),
        (275, 278),
    ]


def test_merge_sorts_candidates_and_joins_unique_non_empty_summaries_in_chunk_order() -> None:
    later = _analysis(
        "scene-01:r1:0001",
        summary=" 두 사람은 대화했다. ",
        entities=(_entity(candidate_id="entity-minjun", normalized_name="민준"),),
        places=(_place(candidate_id="place-garden", normalized_name="정원"),),
    )
    first = _analysis(
        "scene-01:r1:0000",
        summary="두 사람은 만났다.",
        entities=(_entity(candidate_id="entity-seoyeon", normalized_name="서연"),),
        places=(_place(candidate_id="place-cafe", normalized_name="카페"),),
    )
    duplicate_summary = _analysis("scene-01:r1:0002", summary="두 사람은 만났다.")
    empty_summary = _analysis("scene-01:r1:0003", summary="   ")

    snapshot = merge_chunk_analyses(
        "scene-01", 1, 7, (empty_summary, later, duplicate_summary, first)
    )

    assert snapshot.schema_version == "scene-relationship-snapshot-v1"
    assert snapshot.scene_sequence == 7
    assert snapshot.summary == "두 사람은 만났다.\n두 사람은 대화했다."
    assert [candidate.normalized_name for candidate in snapshot.entities] == ["민준", "서연"]
    assert [candidate.normalized_name for candidate in snapshot.places] == ["정원", "카페"]


@pytest.fixture
def chunk_analysis_for_revision_one() -> ChunkAnalysis:
    return _analysis("scene-01:r1:0000")


def test_merge_rejects_an_analysis_from_another_revision(
    chunk_analysis_for_revision_one: ChunkAnalysis,
) -> None:
    with pytest.raises(MergeInvariantError, match="revision"):
        merge_chunk_analyses(
            scene_id="scene-01",
            scene_revision=2,
            scene_sequence=1,
            analyses=(chunk_analysis_for_revision_one,),
        )


def test_merge_rejects_an_analysis_from_another_scene(
    chunk_analysis_for_revision_one: ChunkAnalysis,
) -> None:
    with pytest.raises(MergeInvariantError, match="scene"):
        merge_chunk_analyses(
            scene_id="scene-02",
            scene_revision=1,
            scene_sequence=1,
            analyses=(chunk_analysis_for_revision_one,),
        )


@pytest.mark.parametrize("start_offset,end_offset", [(-1, 2), (2, 2), (3, 2)])
def test_merge_rejects_invalid_evidence_ranges(start_offset: int, end_offset: int) -> None:
    analysis = _analysis(
        "scene-01:r1:0000",
        relationship_events=(
            _relationship(
                evidence=(
                    _evidence(
                        "scene-01:r1:0000",
                        start_offset,
                        end_offset,
                        "invalid",
                    ),
                )
            ),
        ),
    )

    with pytest.raises(MergeInvariantError, match="evidence"):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


@pytest.mark.parametrize("field", ["entities", "places", "relationship_events", "location_events"])
@pytest.mark.parametrize("mismatch", ["scene", "revision"])
def test_merge_rejects_candidate_source_mismatch(field: str, mismatch: str) -> None:
    candidate = {
        "entities": _entity(),
        "places": _place(),
        "relationship_events": _relationship(),
        "location_events": _location(),
    }[field]
    changes = {"scene_id": "scene-02"} if mismatch == "scene" else {"scene_revision": 2}
    invalid_candidate = replace(candidate, **changes)
    analysis = _analysis("scene-01:r1:0000", **{field: (invalid_candidate,)})

    with pytest.raises(MergeInvariantError, match=mismatch):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


@pytest.mark.parametrize("field", ["entities", "places", "location_events"])
def test_merge_validates_evidence_for_every_candidate_type(field: str) -> None:
    candidate = {
        "entities": _entity(),
        "places": _place(),
        "location_events": _location(),
    }[field]
    invalid_candidate = replace(
        candidate,
        evidence=(_evidence("scene-01:r1:0000", 4, 4, "invalid"),),
    )
    analysis = _analysis("scene-01:r1:0000", **{field: (invalid_candidate,)})

    with pytest.raises(MergeInvariantError, match="evidence"):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


@pytest.mark.parametrize("field", ["entities", "places", "relationship_events", "location_events"])
def test_merge_rejects_evidence_from_another_chunk_source(field: str) -> None:
    candidate = {
        "entities": _entity(),
        "places": _place(),
        "relationship_events": _relationship(),
        "location_events": _location(),
    }[field]
    mismatched_source = replace(
        candidate,
        evidence=(_evidence("scene-01:r1:0001", 4, 8, "wrong source"),),
    )
    analysis = _analysis("scene-01:r1:0000", **{field: (mismatched_source,)})

    with pytest.raises(MergeInvariantError, match="chunk.*source"):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


def test_chunk_merge_rejects_wrong_schema_sequence_and_confidence() -> None:
    invalid = replace(
        _analysis("scene-01:r1:0000"),
        schema_version="chunk-analysis-v2",
        relationship_events=(replace(_relationship(), scene_sequence=8, confidence=1.1),),
    )

    with pytest.raises(MergeInvariantError):
        merge_chunk_analyses("scene-01", 1, 7, (invalid,))


def test_chunk_merge_orders_by_numeric_ordinal_not_chunk_id() -> None:
    later = _analysis("scene-01:r1:0001", summary="later")
    earlier = _analysis("scene-01:r1:0000", summary="earlier")

    result = merge_chunk_analyses("scene-01", 1, 7, (later, earlier))

    assert result.summary == "earlier\nlater"


def test_chunk_merge_validates_first_overlap_and_final_short_chunk_metadata() -> None:
    first = _analysis(
        "scene-01:r1:0000",
        entities=(_entity(evidence=(_evidence("scene-01:r1:0000", 0, 2, "서연"),)),),
    )
    overlap = _analysis(
        "scene-01:r1:0001",
        entities=(_entity(evidence=(_evidence("scene-01:r1:0001", 250, 252, "서연"),)),),
    )
    first = replace(
        first,
        source_text=first.source_text[:250] + overlap.source_text[:50],
    )
    final = replace(
        _analysis("scene-01:r1:0002", summary="final"),
        chunk_start=500,
        chunk_end=551,
        source_text=overlap.source_text[-50:] + "끝",
    )

    snapshot = merge_chunk_analyses("scene-01", 1, 7, (final, overlap, first))

    assert snapshot.summary == "final"


@pytest.mark.parametrize("failure", ["bounds", "text"])
def test_chunk_merge_rejects_evidence_outside_authoritative_source(failure: str) -> None:
    analysis = _analysis(
        "scene-01:r1:0000",
        entities=(_entity(evidence=(_evidence("scene-01:r1:0000", 0, 2, "서연"),)),),
    )
    if failure == "bounds":
        analysis = replace(
            analysis,
            chunk_start=3,
            source_text=analysis.source_text[3:],
        )
    else:
        analysis = replace(analysis, source_text="민준" + analysis.source_text[2:])

    with pytest.raises(MergeInvariantError, match="start" if failure == "bounds" else "evidence"):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


def test_chunk_merge_rejects_mixed_chunk_schema_versions() -> None:
    supported = _analysis("scene-01:r1:0000")
    unknown = replace(
        _analysis("scene-01:r1:0001"),
        schema_version="chunk-analysis-v2",
    )

    with pytest.raises(MergeInvariantError, match="schema"):
        merge_chunk_analyses("scene-01", 1, 7, (supported, unknown))


@pytest.mark.parametrize("field", ["relationship_events", "location_events"])
@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("inf"), float("-inf")])
def test_chunk_merge_rejects_invalid_temporal_confidence(
    field: str,
    confidence: float,
) -> None:
    candidate = _relationship() if field == "relationship_events" else _location(evidence=())
    analysis = _analysis(
        "scene-01:r1:0000",
        **{field: (replace(candidate, confidence=confidence),)},
    )

    with pytest.raises(MergeInvariantError, match="confidence"):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_chunk_merge_accepts_closed_confidence_boundaries(confidence: float) -> None:
    snapshot = merge_chunk_analyses(
        "scene-01",
        1,
        7,
        (
            _analysis(
                "scene-01:r1:0000",
                relationship_events=(replace(_relationship(), confidence=confidence),),
                location_events=(replace(_location(evidence=()), confidence=confidence),),
            ),
        ),
    )

    assert snapshot.relationship_events[0].confidence == confidence
    assert snapshot.location_events[0].confidence == confidence


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"chunk_id": "scene-01:r1:0009"}, "chunk ID"),
        ({"chunk_start": 1, "chunk_end": 301}, "start"),
        ({"chunk_end": 301, "source_text": " " * 301}, "width"),
    ],
)
def test_chunk_merge_rejects_noncanonical_chunk_metadata(
    mutation: dict[str, object],
    message: str,
) -> None:
    analysis = replace(_analysis("scene-01:r1:0000"), **mutation)

    with pytest.raises(MergeInvariantError, match=message):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


def test_chunk_merge_rejects_gapped_ordinals_and_short_nonfinal_chunk() -> None:
    first = replace(
        _analysis("scene-01:r1:0000"),
        chunk_end=100,
        source_text=" " * 100,
    )
    gapped = _analysis("scene-01:r1:0002")

    with pytest.raises(MergeInvariantError, match="ordinal|nonfinal"):
        merge_chunk_analyses("scene-01", 1, 7, (first, gapped))


@pytest.mark.parametrize(
    ("field", "candidate"),
    [
        ("entities", lambda: _entity()),
        ("places", lambda: _place()),
        ("relationship_events", lambda: _relationship()),
        ("location_events", lambda: _location(evidence=())),
    ],
)
@pytest.mark.parametrize(
    "status",
    [CandidateStatus.APPROVED, CandidateStatus.NEEDS_REVIEW, CandidateStatus.REJECTED],
)
def test_chunk_merge_rejects_non_pending_extraction_candidates(
    field: str,
    candidate: Callable[[], object],
    status: CandidateStatus,
) -> None:
    analysis = _analysis(
        "scene-01:r1:0000",
        **{field: (replace(candidate(), status=status),)},  # type: ignore[type-var]
    )

    with pytest.raises(MergeInvariantError, match="extraction.*pending"):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


def test_chunk_merge_rejects_mismatched_adjacent_overlap_text() -> None:
    first = _analysis("scene-01:r1:0000")
    second = _analysis("scene-01:r1:0001")
    second = replace(second, source_text="x" + second.source_text[1:])

    with pytest.raises(MergeInvariantError, match="overlap.*text"):
        merge_chunk_analyses("scene-01", 1, 7, (first, second))


def test_chunk_merge_rejects_overlap_only_final_chunk() -> None:
    first = _analysis("scene-01:r1:0000")
    final = replace(
        _analysis("scene-01:r1:0001"),
        chunk_end=300,
        source_text=" " * 50,
    )

    with pytest.raises(MergeInvariantError, match="final.*overlap"):
        merge_chunk_analyses("scene-01", 1, 7, (first, final))


@pytest.mark.parametrize(
    ("field", "candidate_factory"),
    [
        (
            "entities",
            lambda: (
                _entity(candidate_id="duplicate", normalized_name="서연"),
                _entity(candidate_id="duplicate", normalized_name="민준"),
            ),
        ),
        (
            "places",
            lambda: (
                _place(candidate_id="duplicate", normalized_name="카페"),
                _place(candidate_id="duplicate", normalized_name="정원"),
            ),
        ),
        (
            "relationship_events",
            lambda: (
                _relationship(event_id="duplicate"),
                _relationship(event_id="duplicate", description="민준은 서연을 의심했다."),
            ),
        ),
        (
            "location_events",
            lambda: (
                _location(event_id="duplicate", evidence=()),
                _location(
                    event_id="duplicate",
                    place_key="정원",
                    description="서연은 정원에 머물렀다.",
                    evidence=(),
                ),
            ),
        ),
    ],
)
def test_chunk_merge_rejects_duplicate_scene_candidate_and_event_ids(
    field: str,
    candidate_factory: Callable[[], tuple[object, ...]],
) -> None:
    analysis = _analysis(  # type: ignore[arg-type]
        "scene-01:r1:0000", **{field: candidate_factory()}
    )

    with pytest.raises(MergeInvariantError, match="IDs must be unique"):
        merge_chunk_analyses("scene-01", 1, 7, (analysis,))


def _evidence(
    chunk_id: str = "scene-01:r1:0000",
    start_offset: int = 0,
    end_offset: int = 2,
    text: str = "서연",
    *,
    scene_id: str = "scene-01",
    scene_revision: int = 1,
) -> Evidence:
    chunk_scene_id, revision_text, _ = chunk_id.rsplit(":", 2)
    if scene_id == "scene-01":
        scene_id = chunk_scene_id
    if scene_revision == 1 and revision_text.startswith("r"):
        scene_revision = int(revision_text[1:])
    if 0 <= start_offset < end_offset:
        width = end_offset - start_offset
        text = text[:width].ljust(width)
    return Evidence(chunk_id, scene_id, scene_revision, start_offset, end_offset, text)


def _entity(
    candidate_id: str = "entity-01",
    normalized_name: str = "서연",
    aliases: tuple[str, ...] = (),
    evidence: tuple[Evidence, ...] = (),
) -> EntityCandidate:
    return EntityCandidate(
        candidate_id=candidate_id,
        normalized_name=normalized_name,
        display_name=normalized_name,
        aliases=aliases,
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=1,
        evidence=evidence,
    )


def _place(
    candidate_id: str = "place-01",
    normalized_name: str = "카페",
    aliases: tuple[str, ...] = (),
    evidence: tuple[Evidence, ...] = (),
) -> PlaceCandidate:
    return PlaceCandidate(
        candidate_id=candidate_id,
        normalized_name=normalized_name,
        display_name=normalized_name,
        aliases=aliases,
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=1,
        evidence=evidence,
    )


def _relationship(
    event_id: str = "relationship-01",
    category: str = "trust",
    description: str = "서연은 민준을 믿는다고 말했다.",
    evidence: tuple[Evidence, ...] = (),
) -> RelationshipEventCandidate:
    return RelationshipEventCandidate(
        event_id=event_id,
        subject_key="서연",
        object_key="민준",
        category=category,
        description=description,
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=7,
        confidence=0.8,
        evidence=evidence,
    )


def _location(
    event_id: str = "location-01",
    character_key: str = "서연",
    place_key: str = "카페",
    event_type: LocationEventType = LocationEventType.ARRIVED,
    description: str = "서연은 카페에 도착했다.",
    evidence: tuple[Evidence, ...] = (
        Evidence(
            "scene-01:r1:0000",
            "scene-01",
            1,
            250,
            265,
            "서연은 카페에 도착했다.",
        ),
    ),
) -> LocationEventCandidate:
    return LocationEventCandidate(
        event_id=event_id,
        character_key=character_key,
        place_key=place_key,
        event_type=event_type,
        description=description,
        status=CandidateStatus.PENDING,
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=7,
        confidence=0.9,
        evidence=evidence,
    )


def _analysis(
    chunk_id: str,
    summary: str = "",
    entities: tuple[EntityCandidate, ...] = (),
    places: tuple[PlaceCandidate, ...] = (),
    relationship_events: tuple[RelationshipEventCandidate, ...] = (),
    location_events: tuple[LocationEventCandidate, ...] = (),
) -> ChunkAnalysis:
    ordinal = int(chunk_id.rsplit(":", 1)[1])
    default_chunk_start = ordinal * 250
    candidate_evidence = tuple(
        evidence
        for candidate in (*entities, *places, *relationship_events, *location_events)
        for evidence in candidate.evidence
    )
    chunk_start = default_chunk_start
    chunk_end = chunk_start + 300
    source = [" "] * (chunk_end - chunk_start)
    for evidence in candidate_evidence:
        relative_start = evidence.start_offset - chunk_start
        relative_end = evidence.end_offset - chunk_start
        if 0 <= relative_start < relative_end <= len(source):
            width = relative_end - relative_start
            source[relative_start:relative_end] = list(evidence.text[:width].ljust(width))
    source_text = "".join(source)

    def normalize_candidate(
        candidate: EntityCandidate
        | PlaceCandidate
        | RelationshipEventCandidate
        | LocationEventCandidate,
    ):
        normalized_evidence = tuple(
            replace(
                evidence,
                text=source_text[
                    evidence.start_offset - chunk_start : evidence.end_offset - chunk_start
                ],
            )
            if chunk_start <= evidence.start_offset < evidence.end_offset <= chunk_end
            else evidence
            for evidence in candidate.evidence
        )
        return replace(candidate, evidence=normalized_evidence)

    entities = tuple(normalize_candidate(candidate) for candidate in entities)
    places = tuple(normalize_candidate(candidate) for candidate in places)
    relationship_events = tuple(normalize_candidate(candidate) for candidate in relationship_events)
    location_events = tuple(normalize_candidate(candidate) for candidate in location_events)
    return ChunkAnalysis(
        schema_version=CHUNK_ANALYSIS_SCHEMA_VERSION,
        chunk_id=chunk_id,
        chunk_ordinal=ordinal,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        source_text=source_text,
        scene_id="scene-01",
        scene_revision=1,
        summary=summary,
        entities=entities,
        places=places,
        relationship_events=relationship_events,
        location_events=location_events,
    )
