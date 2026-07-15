from dataclasses import replace

import pytest

from apps.narrative_memory.service.merge import (
    MergeInvariantError,
    merge_chunk_analyses,
    merge_scene_into_project,
)
from apps.narrative_memory.service.models import (
    CandidateStatus,
    ChunkAnalysis,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    LocationEventType,
    PlaceCandidate,
    ProjectRelationshipSnapshot,
    RelationshipEventCandidate,
    SceneRelationshipSnapshot,
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
                    _evidence("scene-01:r1:0001", 240, 268, "서연은  민준을 믿는다고 말했다."),
                    _evidence("scene-01:r1:0001", 268, 280, "민준은 웃었다."),
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
                evidence=(_evidence("scene-01:r1:0001", 255, 270, "서연은 카페에 도착했다."),),
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
        (255, 270),
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
                evidence=(
                    _evidence("scene-01:r1:0001", 10, 12, " 서연 "),
                    _evidence("scene-01:r1:0001", 260, 262, "그녀"),
                ),
            ),
        ),
        places=(
            _place(
                candidate_id="place-02",
                aliases=("단골집", "카페"),
                evidence=(
                    _evidence("scene-01:r1:0001", 30, 35, "카페에서"),
                    _evidence("scene-01:r1:0001", 275, 278, "그곳"),
                ),
            ),
        ),
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


def test_project_merge_replaces_pending_candidates_from_same_scene() -> None:
    current = project_snapshot_with_pending_scene_one_revision_one()
    replacement = scene_snapshot_for_scene_one_revision_two_without_events()

    result = merge_scene_into_project(current, replacement)

    assert result.snapshot_version == current.snapshot_version + 1
    assert result.relationship_events == ()
    assert dict(result.active_scene_revisions) == {"scene-01": 2}


def test_project_merge_marks_unsupported_approved_event_needs_review() -> None:
    current = project_snapshot_with_approved_scene_one_event()
    replacement = scene_snapshot_for_scene_one_revision_two_without_events()

    result = merge_scene_into_project(current, replacement)

    assert result.relationship_events[0].status is CandidateStatus.NEEDS_REVIEW


def test_project_merge_preserves_events_from_other_scenes() -> None:
    current = project_snapshot_with_scene_one_and_scene_two_events()
    replacement = scene_snapshot_for_scene_one_revision_two_without_events()

    result = merge_scene_into_project(current, replacement)

    assert [event.scene_id for event in result.relationship_events] == ["scene-02"]


def test_project_merge_preserves_approved_event_with_equivalent_replacement_evidence() -> None:
    prior = replace(
        _relationship(),
        status=CandidateStatus.APPROVED,
        evidence=(_evidence("scene-01:r1:0000", 10, 30, "서연은 민준을 믿었다."),),
    )
    replacement_event = replace(
        prior,
        event_id="relationship-reanalyzed",
        status=CandidateStatus.PENDING,
        scene_revision=2,
        evidence=(_evidence("scene-01:r2:0003", 10, 30, "  서연은  민준을 믿었다. "),),
    )
    current = _project(relationship_events=(prior,))
    replacement = _scene(scene_revision=2, relationship_events=(replacement_event,))

    result = merge_scene_into_project(current, replacement)

    assert len(result.relationship_events) == 1
    assert result.relationship_events[0] == replace(
        replacement_event,
        status=CandidateStatus.APPROVED,
    )


def test_project_merge_preserves_disjoint_repeated_relationship_events() -> None:
    prior = replace(
        _relationship(event_id="relationship-prior"),
        status=CandidateStatus.APPROVED,
        evidence=(_evidence("scene-01:r1:0000", 10, 20, "믿는다고 말했다."),),
    )
    supported = replace(
        prior,
        event_id="relationship-supported",
        status=CandidateStatus.PENDING,
        scene_revision=2,
        evidence=(_evidence("scene-01:r2:0000", 10, 20, "믿는다고 말했다."),),
    )
    repeated = replace(
        supported,
        event_id="relationship-repeated",
        evidence=(_evidence("scene-01:r2:0000", 30, 40, "믿는다고 말했다."),),
    )

    result = merge_scene_into_project(
        _project(relationship_events=(prior,)),
        _scene(scene_revision=2, relationship_events=(repeated, supported)),
    )

    assert [event.event_id for event in result.relationship_events] == [
        "relationship-supported",
        "relationship-repeated",
    ]
    assert [event.status for event in result.relationship_events] == [
        CandidateStatus.APPROVED,
        CandidateStatus.PENDING,
    ]


def test_project_merge_replaces_location_events_and_reviews_unsupported_approval() -> None:
    unsupported = replace(
        _location(event_id="location-approved"),
        status=CandidateStatus.APPROVED,
    )
    rejected = replace(
        _location(event_id="location-rejected", place_key="정원"),
        status=CandidateStatus.REJECTED,
    )
    replacement_event = replace(
        _location(event_id="location-new", place_key="역"),
        scene_revision=2,
        evidence=(_evidence("scene-01:r2:0000", 300, 310, "역에 도착했다."),),
    )

    result = merge_scene_into_project(
        _project(location_events=(rejected, unsupported)),
        _scene(scene_revision=2, location_events=(replacement_event,)),
    )

    assert {event.event_id: event.status for event in result.location_events} == {
        "location-approved": CandidateStatus.NEEDS_REVIEW,
        "location-new": CandidateStatus.PENDING,
    }


def test_project_merge_replaces_entities_and_preserves_supported_approval() -> None:
    approved = replace(
        _entity(evidence=(_evidence("scene-01:r1:0000", 0, 2, "서연"),)),
        status=CandidateStatus.APPROVED,
    )
    pending = _entity(candidate_id="entity-pending", normalized_name="민준")
    replacement = replace(
        approved,
        candidate_id="entity-reanalyzed",
        status=CandidateStatus.PENDING,
        scene_revision=2,
        evidence=(_evidence("scene-01:r2:0000", 0, 2, " 서연 "),),
    )

    result = merge_scene_into_project(
        _project(entities=(pending, approved)),
        _scene(scene_revision=2, entities=(replacement,)),
    )

    assert result.entities == (replace(replacement, status=CandidateStatus.APPROVED),)


def test_project_merge_replaces_places_and_reviews_unsupported_approval() -> None:
    approved = replace(
        _place(evidence=(_evidence("scene-01:r1:0000", 30, 32, "카페"),)),
        status=CandidateStatus.APPROVED,
    )
    replacement = replace(
        _place(candidate_id="place-station", normalized_name="역"),
        scene_revision=2,
        evidence=(_evidence("scene-01:r2:0000", 50, 51, "역"),),
    )

    result = merge_scene_into_project(
        _project(places=(approved,)),
        _scene(scene_revision=2, places=(replacement,)),
    )

    assert {place.candidate_id: place.status for place in result.places} == {
        "place-01": CandidateStatus.NEEDS_REVIEW,
        "place-station": CandidateStatus.PENDING,
    }


def test_project_merge_preserves_candidates_from_other_scenes() -> None:
    entity = replace(_entity(), scene_id="scene-02")
    place = replace(_place(), scene_id="scene-02")
    relationship = replace(_relationship(), scene_id="scene-02")
    location = replace(_location(), scene_id="scene-02")
    current = _project(
        active_scene_revisions=(("scene-01", 1), ("scene-02", 4)),
        entities=(entity,),
        places=(place,),
        relationship_events=(relationship,),
        location_events=(location,),
    )

    result = merge_scene_into_project(
        current,
        scene_snapshot_for_scene_one_revision_two_without_events(),
    )

    assert result.entities == (entity,)
    assert result.places == (place,)
    assert result.relationship_events == (relationship,)
    assert result.location_events == (location,)
    assert result.active_scene_revisions == (("scene-01", 2), ("scene-02", 4))


@pytest.mark.parametrize("scene_revision", [1, 0])
def test_project_merge_requires_scene_revision_to_strictly_advance(
    scene_revision: int,
) -> None:
    with pytest.raises(MergeInvariantError, match="scene revision must advance"):
        merge_scene_into_project(_project(), _scene(scene_revision=scene_revision))


def test_project_merge_keeps_existing_needs_review_candidate_non_approved() -> None:
    prior = replace(
        _relationship(),
        status=CandidateStatus.NEEDS_REVIEW,
        evidence=(_evidence("scene-01:r1:0000", 10, 20, "의심했다."),),
    )
    replacement = replace(
        prior,
        event_id="relationship-reanalyzed",
        status=CandidateStatus.PENDING,
        scene_revision=2,
        evidence=(_evidence("scene-01:r2:0000", 10, 20, "의심했다."),),
    )

    result = merge_scene_into_project(
        _project(relationship_events=(prior,)),
        _scene(scene_revision=2, relationship_events=(replacement,)),
    )

    assert result.relationship_events == (
        replace(replacement, status=CandidateStatus.NEEDS_REVIEW),
    )


def project_snapshot_with_pending_scene_one_revision_one() -> ProjectRelationshipSnapshot:
    return _project(relationship_events=(_relationship(),))


def project_snapshot_with_approved_scene_one_event() -> ProjectRelationshipSnapshot:
    return _project(
        relationship_events=(replace(_relationship(), status=CandidateStatus.APPROVED),)
    )


def project_snapshot_with_scene_one_and_scene_two_events() -> ProjectRelationshipSnapshot:
    return _project(
        active_scene_revisions=(("scene-01", 1), ("scene-02", 1)),
        relationship_events=(
            _relationship(event_id="relationship-scene-one"),
            replace(
                _relationship(event_id="relationship-scene-two"),
                scene_id="scene-02",
            ),
        ),
    )


def scene_snapshot_for_scene_one_revision_two_without_events() -> SceneRelationshipSnapshot:
    return _scene(scene_revision=2)


def _project(
    *,
    active_scene_revisions: tuple[tuple[str, int], ...] = (("scene-01", 1),),
    entities: tuple[EntityCandidate, ...] = (),
    places: tuple[PlaceCandidate, ...] = (),
    relationship_events: tuple[RelationshipEventCandidate, ...] = (),
    location_events: tuple[LocationEventCandidate, ...] = (),
) -> ProjectRelationshipSnapshot:
    return ProjectRelationshipSnapshot(
        project_id="project-01",
        snapshot_version=3,
        schema_version="project-relationship-snapshot-v1",
        active_scene_revisions=active_scene_revisions,
        entities=entities,
        places=places,
        relationship_events=relationship_events,
        location_events=location_events,
    )


def _scene(
    *,
    scene_revision: int,
    entities: tuple[EntityCandidate, ...] = (),
    places: tuple[PlaceCandidate, ...] = (),
    relationship_events: tuple[RelationshipEventCandidate, ...] = (),
    location_events: tuple[LocationEventCandidate, ...] = (),
) -> SceneRelationshipSnapshot:
    return SceneRelationshipSnapshot(
        scene_id="scene-01",
        scene_revision=scene_revision,
        scene_sequence=7,
        schema_version="scene-relationship-snapshot-v1",
        summary="replacement",
        entities=entities,
        places=places,
        relationship_events=relationship_events,
        location_events=location_events,
    )


def _evidence(
    chunk_id: str = "scene-01:r1:0000",
    start_offset: int = 0,
    end_offset: int = 2,
    text: str = "서연",
) -> Evidence:
    return Evidence(chunk_id, start_offset, end_offset, text)


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
        Evidence("scene-01:r1:0000", 250, 265, "서연은 카페에 도착했다."),
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
    return ChunkAnalysis(
        chunk_id=chunk_id,
        scene_id="scene-01",
        scene_revision=1,
        summary=summary,
        entities=entities,
        places=places,
        relationship_events=relationship_events,
        location_events=location_events,
    )
