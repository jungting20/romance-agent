import re
from collections.abc import Iterable
from dataclasses import replace

from apps.narrative_memory.service.models import (
    ChunkAnalysis,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    PlaceCandidate,
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
