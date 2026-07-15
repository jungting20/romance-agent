from collections.abc import Callable
from dataclasses import replace
from itertools import permutations

import pytest

from apps.narrative_memory.service.merge import (
    MergeInvariantError,
    merge_chunk_analyses,
    merge_scene_into_project,
)
from apps.narrative_memory.service.models import (
    CHUNK_ANALYSIS_SCHEMA_VERSION,
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
        event_id="relationship-01",
        subject_key="entity-서연",
        object_key="entity-민준",
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
        "relationship-prior",
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
        evidence=(_evidence("scene-01:r2:0000", 0, 2, "서연"),),
    )

    result = merge_scene_into_project(
        _project(entities=(pending, approved)),
        _scene(scene_revision=2, entities=(replacement,)),
    )

    assert result.entities == (
        replace(replacement, candidate_id="entity-01", status=CandidateStatus.APPROVED),
    )


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
    entity = replace(_entity(), scene_id="scene-02", scene_revision=4)
    minjun = replace(
        _entity(candidate_id="entity-minjun", normalized_name="민준"),
        scene_id="scene-02",
        scene_revision=4,
    )
    place = replace(_place(), scene_id="scene-02", scene_revision=4)
    relationship = replace(_relationship(), scene_id="scene-02", scene_revision=4)
    location = replace(_location(evidence=()), scene_id="scene-02", scene_revision=4)
    current = _project(
        active_scene_revisions=(("scene-01", 1), ("scene-02", 4)),
        entities=(entity, minjun),
        places=(place,),
        relationship_events=(relationship,),
        location_events=(location,),
    )

    result = merge_scene_into_project(
        current,
        scene_snapshot_for_scene_one_revision_two_without_events(),
    )

    assert set(result.entities) == {entity, minjun}
    assert result.places == (place,)
    assert result.relationship_events == (
        replace(relationship, subject_key="entity-01", object_key="entity-minjun"),
    )
    assert result.location_events == (
        replace(location, character_key="entity-01", place_key="place-01"),
    )
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
        replace(
            replacement,
            event_id="relationship-01",
            subject_key="entity-서연",
            object_key="entity-민준",
            status=CandidateStatus.NEEDS_REVIEW,
        ),
    )


def test_project_merge_consolidates_cross_scene_entity_identity_and_evidence() -> None:
    prior = replace(
        _entity(candidate_id="entity-stable", aliases=("연이",)),
        status=CandidateStatus.APPROVED,
        scene_id="scene-02",
        scene_revision=4,
        evidence=(
            _evidence("scene-02:r4:0000", 0, 2, "서연", scene_id="scene-02", scene_revision=4),
        ),
    )
    replacement = replace(
        _entity(candidate_id="entity-new", aliases=("Seo-yeon",)),
        scene_revision=2,
        evidence=(_evidence("scene-01:r2:0000", 0, 2, "서연", scene_revision=2),),
    )

    result = merge_scene_into_project(
        _project(active_scene_revisions=(("scene-01", 1), ("scene-02", 4)), entities=(prior,)),
        _scene(scene_revision=2, entities=(replacement,)),
    )

    assert len(result.entities) == 1
    assert result.entities[0].candidate_id == "entity-stable"
    assert result.entities[0].status is CandidateStatus.APPROVED
    assert result.entities[0].aliases == ("Seo-yeon", "연이")
    assert {item.scene_id for item in result.entities[0].evidence} == {"scene-01", "scene-02"}


def test_project_merge_rejects_conflicting_stable_entity_identities() -> None:
    approved = replace(_entity(candidate_id="entity-approved"), status=CandidateStatus.APPROVED)
    needs_review = replace(
        _entity(candidate_id="entity-review"),
        status=CandidateStatus.NEEDS_REVIEW,
        scene_id="scene-02",
        scene_revision=3,
    )

    with pytest.raises(MergeInvariantError, match="conflicting.*identit|identities.*consolidated"):
        merge_scene_into_project(
            _project(
                active_scene_revisions=(("scene-01", 1), ("scene-02", 3)),
                entities=(approved, needs_review),
            ),
            _scene(scene_revision=2),
        )


def test_project_merge_rejects_dangling_relationship_and_location_references() -> None:
    scene = _scene(
        scene_revision=2,
        entities=(
            replace(
                _entity(candidate_id="entity-seoyeon", normalized_name="서연"),
                scene_revision=2,
            ),
        ),
        places=(
            replace(_place(candidate_id="place-cafe", normalized_name="카페"), scene_revision=2),
        ),
        relationship_events=(replace(_relationship(), scene_revision=2),),
        location_events=(replace(_location(character_key="민준", evidence=()), scene_revision=2),),
    )

    with pytest.raises(MergeInvariantError, match="reference"):
        merge_scene_into_project(_project(), scene)


def test_chunk_merge_rejects_wrong_schema_sequence_and_confidence() -> None:
    invalid = replace(
        _analysis("scene-01:r1:0000"),
        schema_version="chunk-analysis-v2",
        relationship_events=(replace(_relationship(), scene_sequence=8, confidence=1.1),),
    )

    with pytest.raises(MergeInvariantError):
        merge_chunk_analyses("scene-01", 1, 7, (invalid,))


def test_project_merge_rejects_unknown_scene_schema_and_candidate_provenance() -> None:
    invalid_entity = replace(_entity(), scene_revision=1)
    scene = replace(
        _scene(scene_revision=2, entities=(invalid_entity,)),
        schema_version="scene-relationship-snapshot-v2",
    )

    with pytest.raises(MergeInvariantError):
        merge_scene_into_project(_project(), scene)


@pytest.mark.parametrize("field", ["entities", "places", "relationship_events", "location_events"])
def test_project_merge_preserves_stable_id_for_evidence_superset(field: str) -> None:
    prior = {
        "entities": _entity(candidate_id="stable"),
        "places": _place(candidate_id="stable"),
        "relationship_events": _relationship(event_id="stable"),
        "location_events": _location(event_id="stable"),
    }[field]
    prior = replace(
        prior,
        status=CandidateStatus.APPROVED,
        evidence=(_evidence("scene-01:r1:0000", 0, 2, "서연"),),
    )
    replacement = replace(
        prior,
        scene_revision=2,
        status=CandidateStatus.PENDING,
        evidence=(
            _evidence("scene-01:r2:0000", 0, 2, "서연", scene_revision=2),
            _evidence("scene-01:r2:0000", 4, 6, "연이", scene_revision=2),
        ),
        **(
            {"candidate_id": "replacement"}
            if field in {"entities", "places"}
            else {"event_id": "replacement"}
        ),
    )

    result = merge_scene_into_project(
        _project(**{field: (prior,)}),
        _scene(scene_revision=2, **{field: (replacement,)}),
    )
    retained = getattr(result, field)

    assert len(retained) == 1
    stable_id = (
        retained[0].candidate_id if field in {"entities", "places"} else retained[0].event_id
    )
    assert stable_id == "stable"
    assert retained[0].status is CandidateStatus.APPROVED
    assert len(retained[0].evidence) == 2


@pytest.mark.parametrize(
    "field",
    ["entities", "places", "relationship_events", "location_events"],
)
def test_project_merge_reviews_one_stable_candidate_when_replacement_loses_evidence(
    field: str,
) -> None:
    prior = {
        "entities": _entity(candidate_id="stable"),
        "places": _place(candidate_id="stable"),
        "relationship_events": _relationship(event_id="stable"),
        "location_events": _location(event_id="stable"),
    }[field]
    prior = replace(
        prior,
        status=CandidateStatus.APPROVED,
        evidence=(
            _evidence("scene-01:r1:0000", 0, 2, "서연"),
            _evidence("scene-01:r1:0000", 4, 6, "연이"),
        ),
    )
    replacement = replace(
        prior,
        scene_revision=2,
        status=CandidateStatus.PENDING,
        evidence=(_evidence("scene-01:r2:0000", 0, 2, "서연", scene_revision=2),),
        **(
            {"candidate_id": "replacement"}
            if field in {"entities", "places"}
            else {"event_id": "replacement"}
        ),
    )

    result = merge_scene_into_project(
        _project(**{field: (prior,)}),
        _scene(scene_revision=2, **{field: (replacement,)}),
    )
    retained = getattr(result, field)

    assert len(retained) == 1
    stable_id = (
        retained[0].candidate_id if field in {"entities", "places"} else retained[0].event_id
    )
    assert stable_id == "stable"
    assert retained[0].status is CandidateStatus.NEEDS_REVIEW
    assert retained[0].evidence == replacement.evidence


def test_chunk_merge_orders_by_numeric_ordinal_not_chunk_id() -> None:
    later = _analysis("scene-01:r1:0001", summary="later")
    earlier = _analysis("scene-01:r1:0000", summary="earlier")

    result = merge_chunk_analyses("scene-01", 1, 7, (later, earlier))

    assert result.summary == "earlier\nlater"


def test_project_merge_consolidates_place_by_alias_across_scenes() -> None:
    prior = replace(
        _place(candidate_id="place-stable", normalized_name="카페", aliases=("단골집",)),
        scene_id="scene-02",
        scene_revision=3,
        evidence=(
            _evidence(
                "scene-02:r3:0000",
                10,
                13,
                "카페 ",
                scene_id="scene-02",
                scene_revision=3,
            ),
        ),
    )
    replacement = replace(
        _place(candidate_id="place-new", normalized_name="단골집"),
        scene_revision=2,
        evidence=(_evidence("scene-01:r2:0000", 20, 23, "그곳", scene_revision=2),),
    )

    result = merge_scene_into_project(
        _project(active_scene_revisions=(("scene-01", 1), ("scene-02", 3)), places=(prior,)),
        _scene(scene_revision=2, places=(replacement,)),
    )

    assert len(result.places) == 1
    assert result.places[0].candidate_id == "place-stable"
    assert {item.scene_id for item in result.places[0].evidence} == {"scene-01", "scene-02"}


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


def test_project_merge_rejects_duplicate_active_scene_revisions() -> None:
    project = _project(active_scene_revisions=(("scene-01", 1), ("scene-01", 1)))

    with pytest.raises(MergeInvariantError, match="unique"):
        merge_scene_into_project(project, _scene(scene_revision=2))


def test_project_merge_rejects_incompatible_project_schema() -> None:
    project = replace(_project(), schema_version="project-relationship-snapshot-v2")

    with pytest.raises(MergeInvariantError, match="schema"):
        merge_scene_into_project(project, _scene(scene_revision=2))


def test_project_merge_rewrites_local_entity_and_place_references_to_stable_ids() -> None:
    stable_seoyeon = replace(
        _entity(candidate_id="entity-stable-seoyeon", aliases=("연이",)),
        status=CandidateStatus.APPROVED,
    )
    stable_minjun = replace(
        _entity(candidate_id="entity-stable-minjun", normalized_name="민준"),
        status=CandidateStatus.APPROVED,
    )
    stable_cafe = replace(
        _place(candidate_id="place-stable-cafe", aliases=("단골집",)),
        status=CandidateStatus.APPROVED,
    )
    local_seoyeon = replace(
        _entity(candidate_id="entity-local-seoyeon", normalized_name="연이"),
        scene_revision=2,
    )
    local_minjun = replace(
        _entity(candidate_id="entity-local-minjun", normalized_name="민준"),
        scene_revision=2,
    )
    local_cafe = replace(
        _place(candidate_id="place-local-cafe", normalized_name="단골집"),
        scene_revision=2,
    )
    relationship = replace(
        _relationship(event_id="relationship-local"),
        subject_key="entity-local-seoyeon",
        object_key="entity-local-minjun",
        scene_revision=2,
    )
    location = replace(
        _location(event_id="location-local", evidence=()),
        character_key="entity-local-seoyeon",
        place_key="place-local-cafe",
        scene_revision=2,
    )

    result = merge_scene_into_project(
        _project(
            entities=(stable_seoyeon, stable_minjun),
            places=(stable_cafe,),
        ),
        _scene(
            scene_revision=2,
            entities=(local_seoyeon, local_minjun),
            places=(local_cafe,),
            relationship_events=(relationship,),
            location_events=(location,),
        ),
    )

    assert result.relationship_events[0].subject_key == "entity-stable-seoyeon"
    assert result.relationship_events[0].object_key == "entity-stable-minjun"
    assert result.location_events[0].character_key == "entity-stable-seoyeon"
    assert result.location_events[0].place_key == "place-stable-cafe"


@pytest.mark.parametrize("event_field", ["relationship_events", "location_events"])
def test_project_merge_forces_unmatched_approved_event_pending(
    event_field: str,
) -> None:
    entity = replace(_entity(candidate_id="entity-local"), scene_revision=2)
    second_entity = replace(
        _entity(candidate_id="entity-other", normalized_name="민준"),
        scene_revision=2,
    )
    place = replace(_place(candidate_id="place-local"), scene_revision=2)
    event = (
        replace(
            _relationship(event_id="event-stable"),
            subject_key="entity-local",
            object_key="entity-other",
            status=CandidateStatus.APPROVED,
            scene_revision=2,
        )
        if event_field == "relationship_events"
        else replace(
            _location(event_id="event-stable", evidence=()),
            character_key="entity-local",
            place_key="place-local",
            status=CandidateStatus.APPROVED,
            scene_revision=2,
        )
    )

    result = merge_scene_into_project(
        _project(),
        _scene(
            scene_revision=2,
            entities=(entity, second_entity),
            places=(place,),
            **{event_field: (event,)},
        ),
    )

    reviewed = getattr(result, event_field)
    assert len(reviewed) == 1
    assert reviewed[0].event_id == "event-stable"
    assert reviewed[0].status is CandidateStatus.PENDING


def test_unrelated_scene_merge_reviews_stale_approved_evidence_and_dependents() -> None:
    stale = replace(
        _entity(candidate_id="entity-stale"),
        status=CandidateStatus.APPROVED,
        scene_revision=2,
        evidence=(_evidence("scene-01:r1:0000", 0, 2, "서연"),),
    )
    fresh = replace(
        _entity(candidate_id="entity-fresh", normalized_name="민준"),
        status=CandidateStatus.APPROVED,
        scene_revision=2,
        evidence=(
            _evidence(
                "scene-01:r2:0000",
                4,
                6,
                "민준",
                scene_revision=2,
            ),
        ),
    )
    relationship = replace(
        _relationship(event_id="relationship-stable"),
        subject_key="entity-stale",
        object_key="entity-fresh",
        status=CandidateStatus.APPROVED,
        scene_revision=2,
    )
    current = _project(
        active_scene_revisions=(("scene-01", 2),),
        entities=(stale, fresh),
        relationship_events=(relationship,),
    )
    unrelated_scene = replace(
        _scene(scene_revision=1),
        scene_id="scene-02",
        scene_sequence=8,
    )

    result = merge_scene_into_project(current, unrelated_scene)

    assert {candidate.candidate_id: candidate.status for candidate in result.entities}[
        "entity-stale"
    ] is CandidateStatus.NEEDS_REVIEW
    assert result.relationship_events[0].event_id == "relationship-stable"
    assert result.relationship_events[0].status is CandidateStatus.NEEDS_REVIEW


def test_project_identity_representative_is_input_order_independent() -> None:
    candidates = (
        _entity(candidate_id="entity-z", normalized_name="서연", aliases=("연이",)),
        _entity(candidate_id="entity-a", normalized_name="연이", aliases=("서연",)),
    )
    results = {
        merge_scene_into_project(
            ProjectRelationshipSnapshot.empty("project-01"),
            _scene(scene_revision=1, entities=tuple(order)),
        ).entities
        for order in permutations(candidates)
    }

    assert len(results) == 1
    assert next(iter(results))[0].candidate_id == "entity-a"


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


@pytest.mark.parametrize(
    ("field", "candidate"),
    [
        ("entities", lambda: _entity(candidate_id="replacement-entity")),
        ("places", lambda: _place(candidate_id="replacement-place")),
        ("relationship_events", lambda: _relationship(event_id="replacement-relationship")),
        ("location_events", lambda: _location(event_id="replacement-location", evidence=())),
    ],
)
def test_project_merge_forces_unmatched_replacement_candidates_pending(
    field: str,
    candidate: Callable[[], object],
) -> None:
    replacement = replace(  # type: ignore[type-var]
        candidate(), status=CandidateStatus.APPROVED, scene_revision=1
    )

    result = merge_scene_into_project(
        ProjectRelationshipSnapshot.empty("project-01"),
        _scene(scene_revision=1, **{field: (replacement,)}),
    )

    assert getattr(result, field)[0].status is CandidateStatus.PENDING


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


def test_project_merge_deduplicates_relationships_after_reference_rewriting() -> None:
    evidence = (_evidence("scene-01:r1:0000", 10, 30, "서연은 민준을 믿었다."),)
    scene = _scene(
        scene_revision=1,
        entities=(
            _entity(candidate_id="entity-seoyeon-a", aliases=("연이",)),
            _entity(candidate_id="entity-seoyeon-b", normalized_name="연이", aliases=("서연",)),
            _entity(candidate_id="entity-minjun", normalized_name="민준"),
        ),
        relationship_events=(
            replace(
                _relationship(event_id="relationship-z", evidence=evidence),
                subject_key="entity-seoyeon-a",
                object_key="entity-minjun",
            ),
            replace(
                _relationship(event_id="relationship-a", evidence=evidence),
                subject_key="entity-seoyeon-b",
                object_key="entity-minjun",
            ),
        ),
    )

    result = merge_scene_into_project(ProjectRelationshipSnapshot.empty("project-01"), scene)

    assert [event.event_id for event in result.relationship_events] == ["relationship-a"]
    assert result.relationship_events[0].status is CandidateStatus.PENDING


def test_project_merge_deduplicates_locations_after_reference_rewriting() -> None:
    evidence = (_evidence("scene-01:r1:0000", 40, 60, "서연은 카페에 왔다."),)
    scene = _scene(
        scene_revision=1,
        entities=(
            _entity(candidate_id="entity-seoyeon-a", aliases=("연이",)),
            _entity(candidate_id="entity-seoyeon-b", normalized_name="연이", aliases=("서연",)),
        ),
        places=(
            _place(candidate_id="place-cafe-a", aliases=("단골집",)),
            _place(candidate_id="place-cafe-b", normalized_name="단골집", aliases=("카페",)),
        ),
        location_events=(
            replace(
                _location(event_id="location-z", evidence=evidence),
                character_key="entity-seoyeon-a",
                place_key="place-cafe-a",
            ),
            replace(
                _location(event_id="location-a", evidence=evidence),
                character_key="entity-seoyeon-b",
                place_key="place-cafe-b",
            ),
        ),
    )

    result = merge_scene_into_project(ProjectRelationshipSnapshot.empty("project-01"), scene)

    assert [event.event_id for event in result.location_events] == ["location-a"]
    assert result.location_events[0].status is CandidateStatus.PENDING


@pytest.mark.parametrize("event_type", ["relationship", "location"])
def test_project_merge_preserves_disjoint_events_after_reference_rewriting(
    event_type: str,
) -> None:
    identities = (
        _entity(candidate_id="entity-seoyeon-a", aliases=("연이",)),
        _entity(candidate_id="entity-seoyeon-b", normalized_name="연이", aliases=("서연",)),
        _entity(candidate_id="entity-minjun", normalized_name="민준"),
    )
    if event_type == "relationship":
        first = replace(
            _relationship(
                event_id="event-a", evidence=(_evidence(start_offset=10, end_offset=20),)
            ),
            subject_key="entity-seoyeon-a",
            object_key="entity-minjun",
        )
        second = replace(
            first,
            event_id="event-b",
            subject_key="entity-seoyeon-b",
            evidence=(_evidence(start_offset=30, end_offset=40),),
        )
        scene = _scene(scene_revision=1, entities=identities, relationship_events=(first, second))
        field = "relationship_events"
    else:
        places = (
            _place(candidate_id="place-cafe-a", aliases=("단골집",)),
            _place(candidate_id="place-cafe-b", normalized_name="단골집", aliases=("카페",)),
        )
        first = replace(
            _location(event_id="event-a", evidence=(_evidence(start_offset=10, end_offset=20),)),
            character_key="entity-seoyeon-a",
            place_key="place-cafe-a",
        )
        second = replace(
            first,
            event_id="event-b",
            character_key="entity-seoyeon-b",
            place_key="place-cafe-b",
            evidence=(_evidence(start_offset=30, end_offset=40),),
        )
        scene = _scene(
            scene_revision=1,
            entities=identities[:2],
            places=places,
            location_events=(first, second),
        )
        field = "location_events"

    result = merge_scene_into_project(ProjectRelationshipSnapshot.empty("project-01"), scene)

    assert [event.event_id for event in getattr(result, field)] == ["event-a", "event-b"]


def test_project_merge_rejects_conflicting_stable_events_after_reference_rewriting() -> None:
    seoyeon = replace(_entity(candidate_id="entity-seoyeon"), status=CandidateStatus.APPROVED)
    minjun = replace(
        _entity(candidate_id="entity-minjun", normalized_name="민준"),
        status=CandidateStatus.APPROVED,
    )
    evidence = (_evidence(start_offset=10, end_offset=30),)
    first = replace(
        _relationship(event_id="stable-a", evidence=evidence),
        subject_key="서연",
        object_key="민준",
        status=CandidateStatus.APPROVED,
    )
    second = replace(
        first,
        event_id="stable-b",
        subject_key="entity-seoyeon",
        object_key="entity-minjun",
    )
    project = _project(
        entities=(seoyeon, minjun),
        relationship_events=(first, second),
    )

    with pytest.raises(MergeInvariantError, match="conflicting stable event"):
        merge_scene_into_project(
            project,
            replace(_scene(scene_revision=1), scene_id="scene-02"),
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
    if not entities and (relationship_events or location_events):
        references = {
            (event.scene_id, event.scene_revision, key)
            for event in relationship_events
            for key in (event.subject_key, event.object_key)
        } | {
            (event.scene_id, event.scene_revision, event.character_key) for event in location_events
        }
        references_by_name = {
            name: (source_scene_id, revision)
            for source_scene_id, revision, name in sorted(references)
        }
        entities = tuple(
            replace(
                _entity(candidate_id=f"entity-{name}", normalized_name=name),
                scene_id=source_scene_id,
                scene_revision=revision,
                status=CandidateStatus.APPROVED,
            )
            for name, (source_scene_id, revision) in sorted(references_by_name.items())
        )
    if not places and location_events:
        references = {
            (event.scene_id, event.scene_revision, event.place_key) for event in location_events
        }
        places = tuple(
            replace(
                _place(candidate_id=f"place-{name}", normalized_name=name),
                scene_id=source_scene_id,
                scene_revision=revision,
                status=CandidateStatus.APPROVED,
            )
            for source_scene_id, revision, name in sorted(references)
        )
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
    if not entities and (relationship_events or location_events):
        references = {
            key for event in relationship_events for key in (event.subject_key, event.object_key)
        } | {event.character_key for event in location_events}
        entities = tuple(
            replace(
                _entity(candidate_id=f"entity-{name}", normalized_name=name),
                scene_revision=scene_revision,
            )
            for name in sorted(references)
        )
    if not places and location_events:
        places = tuple(
            replace(
                _place(candidate_id=f"place-{name}", normalized_name=name),
                scene_revision=scene_revision,
            )
            for name in sorted({event.place_key for event in location_events})
        )
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
