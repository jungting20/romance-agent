import math
import re
from collections.abc import Callable, Iterable
from dataclasses import replace

from apps.narrative_memory.service.models import (
    CHUNK_ANALYSIS_SCHEMA_VERSION,
    PROJECT_SNAPSHOT_SCHEMA_VERSION,
    SCENE_SNAPSHOT_SCHEMA_VERSION,
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


def evidence_key(evidence: Evidence) -> tuple[str, int, int, int, str]:
    return (
        evidence.scene_id,
        evidence.scene_revision,
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
    ordered_analyses = tuple(sorted(analyses, key=lambda analysis: analysis.chunk_ordinal))
    if len({analysis.chunk_ordinal for analysis in ordered_analyses}) != len(ordered_analyses):
        raise MergeInvariantError("chunk ordinals must be unique")
    if len({analysis.chunk_id for analysis in ordered_analyses}) != len(ordered_analyses):
        raise MergeInvariantError("chunk IDs must be unique")
    for analysis in ordered_analyses:
        _validate_analysis(analysis, scene_id, scene_revision, scene_sequence)

    return SceneRelationshipSnapshot(
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


def merge_scene_into_project(
    project: ProjectRelationshipSnapshot,
    scene: SceneRelationshipSnapshot,
) -> ProjectRelationshipSnapshot:
    _validate_project_snapshot(project)
    _validate_scene_snapshot(scene)
    active_revisions = dict(project.active_scene_revisions)
    previous_revision = active_revisions.get(scene.scene_id)
    if previous_revision is not None and scene.scene_revision <= previous_revision:
        raise MergeInvariantError("scene revision must advance")

    relationships = _replace_scene_relationships(project.relationship_events, scene)
    locations = _replace_scene_locations(project.location_events, scene)
    entities = _merge_project_identities(project.entities, scene.entities, scene)
    places = _merge_project_identities(project.places, scene.places, scene)
    active_revisions[scene.scene_id] = scene.scene_revision

    result = ProjectRelationshipSnapshot(
        project_id=project.project_id,
        snapshot_version=project.snapshot_version + 1,
        schema_version=project.schema_version,
        active_scene_revisions=tuple(sorted(active_revisions.items())),
        entities=entities,
        places=places,
        relationship_events=relationships,
        location_events=locations,
    )
    _validate_project_snapshot(result)
    _validate_reference_integrity(result)
    return result


def _replace_scene_relationships(
    previous: Iterable[RelationshipEventCandidate],
    scene: SceneRelationshipSnapshot,
) -> tuple[RelationshipEventCandidate, ...]:
    return _replace_scene_candidates(
        previous,
        scene.relationship_events,
        scene.scene_id,
        scene.scene_revision,
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
        scene.scene_revision,
        _location_replacement_key,
        _location_output_key,
    )


type ProjectCandidate = (
    EntityCandidate | PlaceCandidate | RelationshipEventCandidate | LocationEventCandidate
)
type CandidateKey = tuple[str, ...]
type CandidateOrderKey = tuple[object, ...]


def _merge_project_identities[
    Candidate: EntityCandidate | PlaceCandidate,
](
    previous: Iterable[Candidate],
    replacement_candidates: Iterable[Candidate],
    scene: SceneRelationshipSnapshot,
) -> tuple[Candidate, ...]:
    prior_records: list[tuple[Candidate, tuple[Evidence, ...], bool]] = []
    for candidate in previous:
        changed_evidence = tuple(
            evidence for evidence in candidate.evidence if evidence.scene_id == scene.scene_id
        )
        retained_evidence = tuple(
            evidence for evidence in candidate.evidence if evidence.scene_id != scene.scene_id
        )
        belongs_to_changed_scene = candidate.scene_id == scene.scene_id or bool(changed_evidence)
        if (
            belongs_to_changed_scene
            and candidate.status in (CandidateStatus.PENDING, CandidateStatus.REJECTED)
            and not retained_evidence
        ):
            continue
        prior_records.append(
            (
                replace(candidate, evidence=retained_evidence),
                changed_evidence,
                belongs_to_changed_scene,
            )
        )

    replacements = tuple(replacement_candidates)
    candidates = tuple(record[0] for record in prior_records) + replacements
    clusters = _identity_clusters(candidates)
    merged: list[Candidate] = []
    prior_count = len(prior_records)
    for cluster in clusters:
        stable = [
            candidates[index]
            for index in cluster
            if index < prior_count
            and candidates[index].status in (CandidateStatus.APPROVED, CandidateStatus.NEEDS_REVIEW)
        ]
        stable_ids = {candidate.candidate_id for candidate in stable}
        if len(stable_ids) > 1:
            raise MergeInvariantError("conflicting stable identities would collapse")

        cluster_replacements = [candidates[index] for index in cluster if index >= prior_count]
        cluster_priors = [candidates[index] for index in cluster if index < prior_count]
        stable_candidate = stable[0] if stable else None
        base = cluster_replacements[0] if cluster_replacements else candidates[cluster[0]]
        evidence_values = [evidence for index in cluster for evidence in candidates[index].evidence]
        status = CandidateStatus.PENDING
        if stable_candidate is not None:
            stable_index = next(
                index
                for index in cluster
                if index < prior_count
                and candidates[index].candidate_id == stable_candidate.candidate_id
            )
            old_changed_evidence = prior_records[stable_index][1]
            belongs_to_changed_scene = prior_records[stable_index][2]
            supported = any(
                _has_materially_equivalent_evidence(
                    old_changed_evidence,
                    candidate.evidence,
                )
                for candidate in cluster_replacements
            )
            if belongs_to_changed_scene and not supported:
                status = CandidateStatus.NEEDS_REVIEW
                if not cluster_replacements:
                    evidence_values.extend(old_changed_evidence)
            else:
                status = stable_candidate.status
            base = replace(base, candidate_id=stable_candidate.candidate_id)
        elif cluster_priors and cluster_replacements:
            base = replace(base, candidate_id=cluster_priors[0].candidate_id)

        if not cluster_replacements and base.scene_id == scene.scene_id:
            base = replace(base, scene_revision=scene.scene_revision)
        merged.append(
            replace(
                base,
                aliases=_merge_aliases(
                    alias for index in cluster for alias in candidates[index].aliases
                ),
                status=status,
                evidence=_merge_evidence(evidence_values),
            )
        )

    return tuple(sorted(merged, key=lambda candidate: candidate.candidate_id))


def _identity_clusters[
    Candidate: EntityCandidate | PlaceCandidate,
](candidates: tuple[Candidate, ...]) -> tuple[tuple[int, ...], ...]:
    parents = list(range(len(candidates)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    token_sets = tuple(_identity_tokens(candidate) for candidate in candidates)
    for right_index, right_tokens in enumerate(token_sets):
        for left_index in range(right_index):
            if token_sets[left_index] & right_tokens:
                left_root = find(left_index)
                right_root = find(right_index)
                if left_root != right_root:
                    parents[right_root] = left_root
    by_root: dict[int, list[int]] = {}
    for index in range(len(candidates)):
        by_root.setdefault(find(index), []).append(index)
    return tuple(tuple(by_root[root]) for root in sorted(by_root))


def _identity_tokens(candidate: EntityCandidate | PlaceCandidate) -> set[str]:
    return {
        normalized
        for value in (candidate.normalized_name, *candidate.aliases)
        if (normalized := normalize_text(value))
    }


def _replace_scene_candidates[
    Candidate: ProjectCandidate,
](
    previous: Iterable[Candidate],
    replacement_candidates: Iterable[Candidate],
    scene_id: str,
    scene_revision: int,
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
            identity_match_index = _identity_replacement_index(
                prior,
                replacements,
                consumed,
                identity_key,
            )
            if identity_match_index is not None:
                consumed.add(identity_match_index)
                merged.append(
                    _retain_stable_id(
                        replace(
                            replacements[identity_match_index],
                            status=CandidateStatus.NEEDS_REVIEW,
                        ),
                        prior,
                    )
                )
                continue
            merged.append(
                replace(
                    prior,
                    status=CandidateStatus.NEEDS_REVIEW,
                    scene_revision=scene_revision,
                )
            )
            continue

        consumed.add(match_index)
        replacement = replacements[match_index]
        retained_status = (
            CandidateStatus.APPROVED
            if prior.status is CandidateStatus.APPROVED
            else CandidateStatus.NEEDS_REVIEW
        )
        merged.append(_retain_stable_id(replace(replacement, status=retained_status), prior))

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


def _identity_replacement_index[
    Candidate: ProjectCandidate,
](
    prior: Candidate,
    replacements: tuple[Candidate, ...],
    consumed: set[int],
    identity_key: Callable[[Candidate], CandidateKey],
) -> int | None:
    prior_identity = identity_key(prior)
    return next(
        (
            index
            for index, candidate in enumerate(replacements)
            if index not in consumed and identity_key(candidate) == prior_identity
        ),
        None,
    )


def _has_materially_equivalent_evidence(
    left: Iterable[Evidence],
    right: Iterable[Evidence],
) -> bool:
    left_key = {_material_evidence_key(value) for value in left}
    right_key = {_material_evidence_key(value) for value in right}
    return bool(left_key) and left_key <= right_key


def _material_evidence_key(evidence: Evidence) -> tuple[int, int, str]:
    return (evidence.start_offset, evidence.end_offset, normalize_text(evidence.text))


def _retain_stable_id(
    replacement: ProjectCandidate,
    prior: ProjectCandidate,
) -> ProjectCandidate:
    if isinstance(replacement, (EntityCandidate, PlaceCandidate)):
        return replace(replacement, candidate_id=prior.candidate_id)
    return replace(replacement, event_id=prior.event_id)


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


def _validate_analysis(
    analysis: ChunkAnalysis,
    scene_id: str,
    scene_revision: int,
    scene_sequence: int,
) -> None:
    if analysis.schema_version != CHUNK_ANALYSIS_SCHEMA_VERSION:
        raise MergeInvariantError("unsupported chunk analysis schema")
    if analysis.chunk_ordinal < 0:
        raise MergeInvariantError("chunk ordinal must be non-negative")
    if not 0 <= analysis.chunk_start <= analysis.chunk_end:
        raise MergeInvariantError("chunk bounds are invalid")
    if len(analysis.source_text) != analysis.chunk_end - analysis.chunk_start:
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
        if candidate.scene_id != scene_id:
            raise MergeInvariantError("candidate scene does not match requested scene")
        if candidate.scene_revision != scene_revision:
            raise MergeInvariantError("candidate revision does not match requested revision")
        if isinstance(candidate, (RelationshipEventCandidate, LocationEventCandidate)):
            if candidate.scene_sequence != scene_sequence:
                raise MergeInvariantError("event sequence does not match containing scene")
            _validate_confidence(candidate.confidence)
        for evidence in candidate.evidence:
            if evidence.chunk_id != analysis.chunk_id:
                raise MergeInvariantError("evidence chunk does not match analysis source chunk")
            if evidence.scene_id != scene_id or evidence.scene_revision != scene_revision:
                raise MergeInvariantError("evidence provenance does not match analysis scene")
            if not 0 <= evidence.start_offset < evidence.end_offset:
                raise MergeInvariantError("evidence range must satisfy 0 <= start < end")
            if not (
                analysis.chunk_start
                <= evidence.start_offset
                < evidence.end_offset
                <= analysis.chunk_end
            ):
                raise MergeInvariantError("evidence range is outside source chunk bounds")
            relative_start = evidence.start_offset - analysis.chunk_start
            relative_end = evidence.end_offset - analysis.chunk_start
            if analysis.source_text[relative_start:relative_end] != evidence.text:
                raise MergeInvariantError("evidence text does not match source chunk text")


def _validate_scene_snapshot(scene: SceneRelationshipSnapshot) -> None:
    if scene.schema_version != SCENE_SNAPSHOT_SCHEMA_VERSION:
        raise MergeInvariantError("unsupported scene snapshot schema")
    for candidate in _all_candidates(scene):
        if candidate.scene_id != scene.scene_id or candidate.scene_revision != scene.scene_revision:
            raise MergeInvariantError("candidate provenance does not match scene snapshot")
        if isinstance(candidate, (RelationshipEventCandidate, LocationEventCandidate)):
            if candidate.scene_sequence != scene.scene_sequence:
                raise MergeInvariantError("event sequence does not match containing scene")
            _validate_confidence(candidate.confidence)
        _validate_candidate_evidence(candidate)


def _validate_project_snapshot(project: ProjectRelationshipSnapshot) -> None:
    if project.schema_version != PROJECT_SNAPSHOT_SCHEMA_VERSION:
        raise MergeInvariantError("unsupported project snapshot schema")
    active_revisions: dict[str, int] = {}
    for scene_id, revision in project.active_scene_revisions:
        if scene_id in active_revisions:
            raise MergeInvariantError("active scene revisions must contain unique scene IDs")
        active_revisions[scene_id] = revision

    scene_sequences: dict[str, int] = {}
    for candidate in _all_candidates(project):
        active_revision = active_revisions.get(candidate.scene_id)
        if active_revision is None or candidate.scene_revision != active_revision:
            raise MergeInvariantError("candidate provenance does not match active scene revision")
        if isinstance(candidate, (RelationshipEventCandidate, LocationEventCandidate)):
            existing_sequence = scene_sequences.setdefault(
                candidate.scene_id, candidate.scene_sequence
            )
            if existing_sequence != candidate.scene_sequence:
                raise MergeInvariantError("event sequences conflict within containing scene")
            _validate_confidence(candidate.confidence)
        _validate_candidate_evidence(candidate, active_revisions)


def _all_candidates(
    snapshot: SceneRelationshipSnapshot | ProjectRelationshipSnapshot,
) -> tuple[ProjectCandidate, ...]:
    return (
        *snapshot.entities,
        *snapshot.places,
        *snapshot.relationship_events,
        *snapshot.location_events,
    )


def _validate_candidate_evidence(
    candidate: ProjectCandidate,
    active_revisions: dict[str, int] | None = None,
) -> None:
    for evidence in candidate.evidence:
        if not 0 <= evidence.start_offset < evidence.end_offset:
            raise MergeInvariantError("evidence range must satisfy 0 <= start < end")
        if active_revisions is None:
            if (
                evidence.scene_id != candidate.scene_id
                or evidence.scene_revision != candidate.scene_revision
            ):
                raise MergeInvariantError("evidence provenance does not match candidate")
        else:
            active_revision = active_revisions.get(evidence.scene_id)
            if active_revision is None or evidence.scene_revision > active_revision:
                raise MergeInvariantError("evidence provenance is outside active project scenes")


def _validate_confidence(confidence: float) -> None:
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise MergeInvariantError("confidence must be finite and between 0.0 and 1.0")


def _validate_reference_integrity(project: ProjectRelationshipSnapshot) -> None:
    entity_references = {
        normalize_text(value)
        for candidate in project.entities
        for value in (candidate.candidate_id, candidate.normalized_name, *candidate.aliases)
    }
    place_references = {
        normalize_text(value)
        for candidate in project.places
        for value in (candidate.candidate_id, candidate.normalized_name, *candidate.aliases)
    }
    for event in project.relationship_events:
        if (
            normalize_text(event.subject_key) not in entity_references
            or normalize_text(event.object_key) not in entity_references
        ):
            raise MergeInvariantError("relationship reference is absent from entity catalog")
    for event in project.location_events:
        if normalize_text(event.character_key) not in entity_references:
            raise MergeInvariantError("location character reference is absent from entity catalog")
        if normalize_text(event.place_key) not in place_references:
            raise MergeInvariantError("location place reference is absent from place catalog")


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
