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
    merged: dict[tuple[str, str, str, str, str], RelationshipEventCandidate] = {}
    for event in values:
        key = relationship_key(event)
        existing = merged.get(key)
        if existing is None:
            merged[key] = replace(event, evidence=_merge_evidence(event.evidence))
        else:
            merged[key] = replace(
                existing,
                evidence=_merge_evidence((*existing.evidence, *event.evidence)),
            )
    return tuple(merged[key] for key in sorted(merged))


def _merge_location_events(
    values: Iterable[LocationEventCandidate],
) -> tuple[LocationEventCandidate, ...]:
    merged: dict[tuple[str, str, str, str, str], LocationEventCandidate] = {}
    for event in values:
        key = location_key(event)
        existing = merged.get(key)
        if existing is None:
            merged[key] = replace(event, evidence=_merge_evidence(event.evidence))
        else:
            merged[key] = replace(
                existing,
                evidence=_merge_evidence((*existing.evidence, *event.evidence)),
            )
    return tuple(merged[key] for key in sorted(merged))
