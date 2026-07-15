import re
from collections.abc import Callable, Iterable
from dataclasses import replace

from apps.narrative_memory.service.models import (
    CandidateStatus,
    ChunkAnalysis,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    PlaceCandidate,
    ProjectRelationshipSnapshot,
    RelationshipEventCandidate,
    SceneRelationshipSnapshot,
)


class MergeInvariantError(ValueError):
    pass


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def evidence_key(evidence: Evidence) -> tuple[int, int, str]:
    return (
        evidence.start_offset,
        evidence.end_offset,
        normalize_text(evidence.text),
    )


def relationship_key(
    event: RelationshipEventCandidate,
) -> tuple[str, str, str, str, str]:
    return (
        event.subject_key,
        event.object_key,
        normalize_text(event.category),
        normalize_text(event.description),
        event.scene_id,
    )


def entity_key(candidate: EntityCandidate) -> tuple[str, str]:
    return (candidate.scene_id, candidate.normalized_name)


def place_key(candidate: PlaceCandidate) -> tuple[str, str]:
    return (candidate.scene_id, candidate.normalized_name)


def location_key(
    event: LocationEventCandidate,
) -> tuple[str, str, str, str, str]:
    return (
        event.character_key,
        event.place_key,
        event.event_type.value,
        normalize_text(event.description),
        event.scene_id,
    )


def _merge_evidence(values: Iterable[Evidence]) -> tuple[Evidence, ...]:
    by_key = {evidence_key(value): value for value in values}
    return tuple(by_key[key] for key in sorted(by_key))


def merge_chunk_analyses(
    scene_id: str,
    scene_revision: int,
    scene_sequence: int,
    analyses: Iterable[ChunkAnalysis],
) -> SceneRelationshipSnapshot:
    ordered_analyses = tuple(sorted(analyses, key=lambda analysis: analysis.chunk_id))
    for analysis in ordered_analyses:
        _validate_analysis(analysis, scene_id, scene_revision)

    return SceneRelationshipSnapshot(
        scene_id=scene_id,
        scene_revision=scene_revision,
        scene_sequence=scene_sequence,
        schema_version="scene-relationship-snapshot-v1",
        summary=_merge_summaries(ordered_analyses),
        entities=_merge_entities(
            candidate for analysis in ordered_analyses for candidate in analysis.entities
        ),
        places=_merge_places(
            candidate for analysis in ordered_analyses for candidate in analysis.places
        ),
        relationship_events=_merge_relationship_events(
            event for analysis in ordered_analyses for event in analysis.relationship_events
        ),
        location_events=_merge_location_events(
            event for analysis in ordered_analyses for event in analysis.location_events
        ),
    )


def merge_scene_into_project(
    project: ProjectRelationshipSnapshot,
    scene: SceneRelationshipSnapshot,
) -> ProjectRelationshipSnapshot:
    active_revisions = dict(project.active_scene_revisions)
    previous_revision = active_revisions.get(scene.scene_id)
    if previous_revision is not None and scene.scene_revision <= previous_revision:
        raise MergeInvariantError("scene revision must advance")

    relationships = _replace_scene_relationships(project.relationship_events, scene)
    locations = _replace_scene_locations(project.location_events, scene)
    entities = _merge_entities_after_scene_replacement(project.entities, scene.entities, scene)
    places = _merge_places_after_scene_replacement(project.places, scene.places, scene)
    active_revisions[scene.scene_id] = scene.scene_revision

    return ProjectRelationshipSnapshot(
        project_id=project.project_id,
        snapshot_version=project.snapshot_version + 1,
        schema_version=project.schema_version,
        active_scene_revisions=tuple(sorted(active_revisions.items())),
        entities=entities,
        places=places,
        relationship_events=relationships,
        location_events=locations,
    )


def _replace_scene_relationships(
    previous: Iterable[RelationshipEventCandidate],
    scene: SceneRelationshipSnapshot,
) -> tuple[RelationshipEventCandidate, ...]:
    return _replace_scene_candidates(
        previous,
        scene.relationship_events,
        scene.scene_id,
        _relationship_replacement_key,
        _relationship_output_key,
    )


def _replace_scene_locations(
    previous: Iterable[LocationEventCandidate],
    scene: SceneRelationshipSnapshot,
) -> tuple[LocationEventCandidate, ...]:
    return _replace_scene_candidates(
        previous,
        scene.location_events,
        scene.scene_id,
        _location_replacement_key,
        _location_output_key,
    )


def _merge_entities_after_scene_replacement(
    previous: Iterable[EntityCandidate],
    replacement: Iterable[EntityCandidate],
    scene: SceneRelationshipSnapshot,
) -> tuple[EntityCandidate, ...]:
    return _replace_scene_candidates(
        previous,
        replacement,
        scene.scene_id,
        _entity_replacement_key,
        _entity_output_key,
    )


def _merge_places_after_scene_replacement(
    previous: Iterable[PlaceCandidate],
    replacement: Iterable[PlaceCandidate],
    scene: SceneRelationshipSnapshot,
) -> tuple[PlaceCandidate, ...]:
    return _replace_scene_candidates(
        previous,
        replacement,
        scene.scene_id,
        _place_replacement_key,
        _place_output_key,
    )


type ProjectCandidate = (
    EntityCandidate | PlaceCandidate | RelationshipEventCandidate | LocationEventCandidate
)
type CandidateKey = tuple[str, ...]
type CandidateOrderKey = tuple[object, ...]


def _replace_scene_candidates[
    Candidate: ProjectCandidate,
](
    previous: Iterable[Candidate],
    replacement_candidates: Iterable[Candidate],
    scene_id: str,
    identity_key: Callable[[Candidate], CandidateKey],
    output_key: Callable[[Candidate], CandidateOrderKey],
) -> tuple[Candidate, ...]:
    replacements = tuple(sorted(replacement_candidates, key=output_key))
    consumed: set[int] = set()
    merged: list[Candidate] = []

    for prior in sorted(previous, key=output_key):
        if prior.scene_id != scene_id:
            merged.append(prior)
            continue
        if prior.status in (CandidateStatus.PENDING, CandidateStatus.REJECTED):
            continue

        match_index = _matching_replacement_index(
            prior,
            replacements,
            consumed,
            identity_key,
        )
        if match_index is None:
            merged.append(replace(prior, status=CandidateStatus.NEEDS_REVIEW))
            continue

        consumed.add(match_index)
        replacement = replacements[match_index]
        retained_status = (
            CandidateStatus.APPROVED
            if prior.status is CandidateStatus.APPROVED
            else CandidateStatus.NEEDS_REVIEW
        )
        merged.append(replace(replacement, status=retained_status))

    merged.extend(
        replace(candidate, status=CandidateStatus.PENDING)
        for index, candidate in enumerate(replacements)
        if index not in consumed
    )
    return tuple(sorted(merged, key=output_key))


def _matching_replacement_index[
    Candidate: ProjectCandidate,
](
    prior: Candidate,
    replacements: tuple[Candidate, ...],
    consumed: set[int],
    identity_key: Callable[[Candidate], CandidateKey],
) -> int | None:
    prior_identity = identity_key(prior)
    for index, candidate in enumerate(replacements):
        if index in consumed:
            continue
        if identity_key(candidate) != prior_identity:
            continue
        if _has_materially_equivalent_evidence(prior.evidence, candidate.evidence):
            return index
    return None


def _has_materially_equivalent_evidence(
    left: Iterable[Evidence],
    right: Iterable[Evidence],
) -> bool:
    left_key = tuple(sorted(evidence_key(value) for value in left))
    right_key = tuple(sorted(evidence_key(value) for value in right))
    return bool(left_key) and left_key == right_key


def _entity_replacement_key(candidate: EntityCandidate) -> CandidateKey:
    return (normalize_text(candidate.normalized_name),)


def _place_replacement_key(candidate: PlaceCandidate) -> CandidateKey:
    return (normalize_text(candidate.normalized_name),)


def _relationship_replacement_key(
    event: RelationshipEventCandidate,
) -> CandidateKey:
    return (
        normalize_text(event.subject_key),
        normalize_text(event.object_key),
        normalize_text(event.category),
        normalize_text(event.description),
    )


def _location_replacement_key(event: LocationEventCandidate) -> CandidateKey:
    return (
        normalize_text(event.character_key),
        normalize_text(event.place_key),
        event.event_type.value,
        normalize_text(event.description),
    )


def _entity_output_key(candidate: EntityCandidate) -> CandidateOrderKey:
    return (
        candidate.scene_id,
        normalize_text(candidate.normalized_name),
        _evidence_order_key(candidate.evidence),
        candidate.candidate_id,
    )


def _place_output_key(candidate: PlaceCandidate) -> CandidateOrderKey:
    return (
        candidate.scene_id,
        normalize_text(candidate.normalized_name),
        _evidence_order_key(candidate.evidence),
        candidate.candidate_id,
    )


def _validate_analysis(
    analysis: ChunkAnalysis,
    scene_id: str,
    scene_revision: int,
) -> None:
    if analysis.scene_id != scene_id:
        raise MergeInvariantError("analysis scene does not match requested scene")
    if analysis.scene_revision != scene_revision:
        raise MergeInvariantError("analysis revision does not match requested revision")

    candidates = (
        *analysis.entities,
        *analysis.places,
        *analysis.relationship_events,
        *analysis.location_events,
    )
    for candidate in candidates:
        if candidate.scene_id != scene_id:
            raise MergeInvariantError("candidate scene does not match requested scene")
        if candidate.scene_revision != scene_revision:
            raise MergeInvariantError("candidate revision does not match requested revision")
        for evidence in candidate.evidence:
            if evidence.chunk_id != analysis.chunk_id:
                raise MergeInvariantError("evidence chunk does not match analysis source chunk")
            if not 0 <= evidence.start_offset < evidence.end_offset:
                raise MergeInvariantError("evidence range must satisfy 0 <= start < end")


def _merge_summaries(analyses: Iterable[ChunkAnalysis]) -> str:
    summaries: list[str] = []
    seen: set[str] = set()
    for analysis in analyses:
        summary = re.sub(r"\s+", " ", analysis.summary.strip())
        key = normalize_text(summary)
        if summary and key not in seen:
            seen.add(key)
            summaries.append(summary)
    return "\n".join(summaries)


def _merge_aliases(values: Iterable[str]) -> tuple[str, ...]:
    by_key: dict[str, str] = {}
    for value in values:
        alias = re.sub(r"\s+", " ", value.strip())
        if alias:
            by_key.setdefault(normalize_text(alias), alias)
    return tuple(by_key[key] for key in sorted(by_key))


def _merge_entities(values: Iterable[EntityCandidate]) -> tuple[EntityCandidate, ...]:
    merged: dict[tuple[str, str], EntityCandidate] = {}
    for candidate in values:
        key = entity_key(candidate)
        existing = merged.get(key)
        if existing is None:
            merged[key] = replace(
                candidate,
                aliases=_merge_aliases(candidate.aliases),
                evidence=_merge_evidence(candidate.evidence),
            )
        else:
            merged[key] = replace(
                existing,
                aliases=_merge_aliases((*existing.aliases, *candidate.aliases)),
                evidence=_merge_evidence((*existing.evidence, *candidate.evidence)),
            )
    return tuple(merged[key] for key in sorted(merged))


def _merge_places(values: Iterable[PlaceCandidate]) -> tuple[PlaceCandidate, ...]:
    merged: dict[tuple[str, str], PlaceCandidate] = {}
    for candidate in values:
        key = place_key(candidate)
        existing = merged.get(key)
        if existing is None:
            merged[key] = replace(
                candidate,
                aliases=_merge_aliases(candidate.aliases),
                evidence=_merge_evidence(candidate.evidence),
            )
        else:
            merged[key] = replace(
                existing,
                aliases=_merge_aliases((*existing.aliases, *candidate.aliases)),
                evidence=_merge_evidence((*existing.evidence, *candidate.evidence)),
            )
    return tuple(merged[key] for key in sorted(merged))


def _merge_relationship_events(
    values: Iterable[RelationshipEventCandidate],
) -> tuple[RelationshipEventCandidate, ...]:
    grouped: dict[tuple[str, str, str, str, str], list[RelationshipEventCandidate]] = {}
    for event in values:
        grouped.setdefault(relationship_key(event), []).append(event)

    merged: list[RelationshipEventCandidate] = []
    for key in sorted(grouped):
        ordered = tuple(sorted(grouped[key], key=_relationship_event_order_key))
        for cluster in _overlap_clusters(ordered):
            merged.append(
                replace(
                    cluster[0],
                    evidence=_merge_evidence(
                        evidence for event in cluster for evidence in event.evidence
                    ),
                )
            )
    return tuple(sorted(merged, key=_relationship_output_key))


def _merge_location_events(
    values: Iterable[LocationEventCandidate],
) -> tuple[LocationEventCandidate, ...]:
    grouped: dict[tuple[str, str, str, str, str], list[LocationEventCandidate]] = {}
    for event in values:
        grouped.setdefault(location_key(event), []).append(event)

    merged: list[LocationEventCandidate] = []
    for key in sorted(grouped):
        ordered = tuple(sorted(grouped[key], key=_location_event_order_key))
        for cluster in _overlap_clusters(ordered):
            merged.append(
                replace(
                    cluster[0],
                    evidence=_merge_evidence(
                        evidence for event in cluster for evidence in event.evidence
                    ),
                )
            )
    return tuple(sorted(merged, key=_location_output_key))


type TemporalEventCandidate = RelationshipEventCandidate | LocationEventCandidate


def _overlap_clusters(
    events: tuple[TemporalEventCandidate, ...],
) -> tuple[tuple[TemporalEventCandidate, ...], ...]:
    parents = list(range(len(events)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for right_index, right in enumerate(events):
        for left_index in range(right_index):
            if _evidence_overlaps(events[left_index].evidence, right.evidence):
                left_root = find(left_index)
                right_root = find(right_index)
                if left_root != right_root:
                    parents[right_root] = left_root

    by_root: dict[int, list[TemporalEventCandidate]] = {}
    for index, event in enumerate(events):
        by_root.setdefault(find(index), []).append(event)
    return tuple(tuple(by_root[root]) for root in sorted(by_root))


def _evidence_overlaps(left: Iterable[Evidence], right: Iterable[Evidence]) -> bool:
    right_values = tuple(right)
    return any(
        left_value.start_offset < right_value.end_offset
        and right_value.start_offset < left_value.end_offset
        for left_value in left
        for right_value in right_values
    )


def _evidence_order_key(
    values: Iterable[Evidence],
) -> tuple[tuple[int, int, str, str], ...]:
    return tuple(
        sorted(
            (
                value.start_offset,
                value.end_offset,
                normalize_text(value.text),
                value.chunk_id,
            )
            for value in values
        )
    )


def _relationship_event_order_key(
    event: RelationshipEventCandidate,
) -> tuple[tuple[tuple[int, int, str, str], ...], str, str, str, str, int, float]:
    return (
        _evidence_order_key(event.evidence),
        event.event_id,
        event.category,
        event.description,
        event.status.value,
        event.scene_sequence,
        event.confidence,
    )


def _location_event_order_key(
    event: LocationEventCandidate,
) -> tuple[tuple[tuple[int, int, str, str], ...], str, str, str, int, float]:
    return (
        _evidence_order_key(event.evidence),
        event.event_id,
        event.description,
        event.status.value,
        event.scene_sequence,
        event.confidence,
    )


def _relationship_output_key(
    event: RelationshipEventCandidate,
) -> tuple[
    tuple[str, str, str, str, str],
    tuple[tuple[int, int, str, str], ...],
    str,
]:
    return (relationship_key(event), _evidence_order_key(event.evidence), event.event_id)


def _location_output_key(
    event: LocationEventCandidate,
) -> tuple[
    tuple[str, str, str, str, str],
    tuple[tuple[int, int, str, str], ...],
    str,
]:
    return (location_key(event), _evidence_order_key(event.evidence), event.event_id)
