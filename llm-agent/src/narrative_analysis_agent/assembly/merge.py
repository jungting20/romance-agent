import re
from collections.abc import Iterable
from dataclasses import replace

from narrative_analysis_agent.contracts import (
    CandidateStatus,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    PlaceCandidate,
    RelationshipEventCandidate,
    SceneRelationshipSnapshot,
)

from .models import CHUNK_ANALYSIS_SCHEMA_VERSION, SCENE_SNAPSHOT_SCHEMA_VERSION, ChunkAnalysis
from .validation import (
    MergeInvariantError,
    validate_confidence,
    validate_scene_snapshot,
)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def evidence_key(evidence: Evidence) -> tuple[str, int, int, int, str]:
    return (
        evidence.scene_id,
        evidence.scene_revision,
        evidence.start_offset,
        evidence.end_offset,
        normalize_text(evidence.text),
    )


def relationship_key(event: RelationshipEventCandidate) -> tuple[str, str, str, str, str]:
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


def location_key(event: LocationEventCandidate) -> tuple[str, str, str, str, str]:
    return (
        event.character_key,
        event.place_key,
        event.event_type.value,
        normalize_text(event.description),
        event.scene_id,
    )


def merge_chunk_analyses(
    scene_id: str,
    scene_revision: int,
    scene_sequence: int,
    analyses: Iterable[ChunkAnalysis],
) -> SceneRelationshipSnapshot:
    ordered_analyses = tuple(sorted(analyses, key=lambda analysis: analysis.chunk_ordinal))
    if len({analysis.chunk_ordinal for analysis in ordered_analyses}) != len(ordered_analyses):
        raise MergeInvariantError("chunk ordinals must be unique")
    if len({analysis.chunk_id for analysis in ordered_analyses}) != len(ordered_analyses):
        raise MergeInvariantError("chunk IDs must be unique")
    _validate_chunk_set(ordered_analyses)
    for analysis in ordered_analyses:
        _validate_analysis(analysis, scene_id, scene_revision, scene_sequence)
    snapshot = SceneRelationshipSnapshot(
        scene_id=scene_id,
        scene_revision=scene_revision,
        scene_sequence=scene_sequence,
        schema_version=SCENE_SNAPSHOT_SCHEMA_VERSION,
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
    validate_scene_snapshot(snapshot)
    return snapshot


def _validate_chunk_set(analyses: tuple[ChunkAnalysis, ...]) -> None:
    ordinals = tuple(analysis.chunk_ordinal for analysis in analyses)
    if ordinals != tuple(range(len(analyses))):
        raise MergeInvariantError("chunk ordinals must be contiguous and start at zero")
    for analysis in analyses[:-1]:
        if analysis.chunk_end - analysis.chunk_start != 300:
            raise MergeInvariantError("nonfinal chunk width must be 300")
    if len(analyses) > 1 and analyses[-1].chunk_end - analyses[-1].chunk_start <= 50:
        raise MergeInvariantError("final chunk must contain text beyond the overlap")
    for previous, current in zip(analyses, analyses[1:], strict=False):
        if previous.source_text[-50:] != current.source_text[:50]:
            raise MergeInvariantError("adjacent chunk overlap text must match")


def _validate_analysis(
    analysis: ChunkAnalysis, scene_id: str, scene_revision: int, scene_sequence: int
) -> None:
    if analysis.schema_version != CHUNK_ANALYSIS_SCHEMA_VERSION:
        raise MergeInvariantError("unsupported chunk analysis schema")
    if analysis.chunk_ordinal < 0:
        raise MergeInvariantError("chunk ordinal must be non-negative")
    if analysis.chunk_id != f"{scene_id}:r{scene_revision}:{analysis.chunk_ordinal:04d}":
        raise MergeInvariantError("chunk ID does not match scene, revision, and ordinal")
    if analysis.chunk_start != analysis.chunk_ordinal * 250:
        raise MergeInvariantError("chunk start does not match numeric ordinal stride")
    chunk_width = analysis.chunk_end - analysis.chunk_start
    if not 1 <= chunk_width <= 300:
        raise MergeInvariantError("chunk width must be between 1 and 300")
    if len(analysis.source_text) != chunk_width:
        raise MergeInvariantError("source chunk text does not match chunk bounds")
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
        if candidate.status is not CandidateStatus.PENDING:
            raise MergeInvariantError("extraction candidates must be pending")
        if candidate.scene_id != scene_id:
            raise MergeInvariantError("candidate scene does not match requested scene")
        if candidate.scene_revision != scene_revision:
            raise MergeInvariantError("candidate revision does not match requested revision")
        if isinstance(candidate, (RelationshipEventCandidate, LocationEventCandidate)):
            if candidate.scene_sequence != scene_sequence:
                raise MergeInvariantError("event sequence does not match containing scene")
            validate_confidence(candidate.confidence)
        for evidence in candidate.evidence:
            if evidence.chunk_id != analysis.chunk_id:
                raise MergeInvariantError("evidence chunk does not match analysis source chunk")
            if evidence.scene_id != scene_id or evidence.scene_revision != scene_revision:
                raise MergeInvariantError("evidence provenance does not match analysis scene")
            if not 0 <= evidence.start_offset < evidence.end_offset:
                raise MergeInvariantError("evidence range must satisfy 0 <= start < end")
            if (
                not analysis.chunk_start
                <= evidence.start_offset
                < evidence.end_offset
                <= analysis.chunk_end
            ):
                raise MergeInvariantError("evidence range is outside source chunk bounds")
            relative_start = evidence.start_offset - analysis.chunk_start
            relative_end = evidence.end_offset - analysis.chunk_start
            if analysis.source_text[relative_start:relative_end] != evidence.text:
                raise MergeInvariantError("evidence text does not match source chunk text")


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


def _merge_evidence(values: Iterable[Evidence]) -> tuple[Evidence, ...]:
    by_key = {evidence_key(value): value for value in values}
    return tuple(by_key[key] for key in sorted(by_key))


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
        merged[key] = (
            replace(
                candidate,
                aliases=_merge_aliases(candidate.aliases),
                evidence=_merge_evidence(candidate.evidence),
            )
            if existing is None
            else replace(
                existing,
                aliases=_merge_aliases((*existing.aliases, *candidate.aliases)),
                evidence=_merge_evidence((*existing.evidence, *candidate.evidence)),
            )
        )
    return tuple(merged[key] for key in sorted(merged))


def _merge_places(values: Iterable[PlaceCandidate]) -> tuple[PlaceCandidate, ...]:
    merged: dict[tuple[str, str], PlaceCandidate] = {}
    for candidate in values:
        key = place_key(candidate)
        existing = merged.get(key)
        merged[key] = (
            replace(
                candidate,
                aliases=_merge_aliases(candidate.aliases),
                evidence=_merge_evidence(candidate.evidence),
            )
            if existing is None
            else replace(
                existing,
                aliases=_merge_aliases((*existing.aliases, *candidate.aliases)),
                evidence=_merge_evidence((*existing.evidence, *candidate.evidence)),
            )
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
            representative = cluster[0]
            merged.append(
                replace(
                    representative,
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
            representative = cluster[0]
            merged.append(
                replace(
                    representative,
                    evidence=_merge_evidence(
                        evidence for event in cluster for evidence in event.evidence
                    ),
                )
            )
    return tuple(sorted(merged, key=_location_output_key))


type TemporalEvent = RelationshipEventCandidate | LocationEventCandidate


def _overlap_clusters(events: tuple[TemporalEvent, ...]) -> tuple[tuple[TemporalEvent, ...], ...]:
    parents = list(range(len(events)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for right_index, right in enumerate(events):
        for left_index in range(right_index):
            if _evidence_overlaps(events[left_index].evidence, right.evidence):
                left_root, right_root = find(left_index), find(right_index)
                if left_root != right_root:
                    parents[right_root] = left_root
    by_root: dict[int, list[TemporalEvent]] = {}
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


def _evidence_order_key(values: Iterable[Evidence]) -> tuple[tuple[int, int, str, str], ...]:
    return tuple(
        sorted(
            (value.start_offset, value.end_offset, normalize_text(value.text), value.chunk_id)
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
) -> tuple[tuple[str, str, str, str, str], tuple[tuple[int, int, str, str], ...], str]:
    return (relationship_key(event), _evidence_order_key(event.evidence), event.event_id)


def _location_output_key(
    event: LocationEventCandidate,
) -> tuple[tuple[str, str, str, str, str], tuple[tuple[int, int, str, str], ...], str]:
    return (location_key(event), _evidence_order_key(event.evidence), event.event_id)
