import math
import re
from collections.abc import Callable, Iterable
from dataclasses import replace

from apps.narrative_memory.service.models import (
    SCENE_SNAPSHOT_SCHEMA_VERSION,
    CandidateStatus,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    PlaceCandidate,
    ProjectRelationshipSnapshot,
    RelationshipEventCandidate,
    SceneRelationshipSnapshot,
)
from apps.narrative_memory.service.validation import (
    ProjectInvariantError,
    build_canonical_reference_map,
    downgrade_invalid_approvals,
    normalize_reference,
    validate_project_snapshot,
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


def merge_scene_into_project(
    project: ProjectRelationshipSnapshot,
    scene: SceneRelationshipSnapshot,
) -> ProjectRelationshipSnapshot:
    try:
        project = downgrade_invalid_approvals(project)
    except ProjectInvariantError as error:
        raise MergeInvariantError(str(error)) from error
    _require_valid_project(project)
    _validate_scene_snapshot(scene)
    active_revisions = dict(project.active_scene_revisions)
    previous_revision = active_revisions.get(scene.scene_id)
    if previous_revision is not None and scene.scene_revision <= previous_revision:
        raise MergeInvariantError("scene revision must advance")
    scene = _force_pending_scene_candidates(scene)

    entities, entity_id_map = _merge_project_identities(project.entities, scene.entities, scene)
    places, place_id_map = _merge_project_identities(project.places, scene.places, scene)
    entity_references = build_canonical_reference_map(entities, entity_id_map)
    place_references = build_canonical_reference_map(places, place_id_map)
    previous_relationships = _rewrite_relationship_references(
        project.relationship_events, entity_references
    )
    replacement_relationships = _rewrite_relationship_references(
        scene.relationship_events, entity_references
    )
    previous_relationships = _merge_relationship_events(
        previous_relationships, reject_conflicting_stable_ids=True
    )
    replacement_relationships = _merge_relationship_events(replacement_relationships)
    previous_locations = _rewrite_location_references(
        project.location_events, entity_references, place_references
    )
    replacement_locations = _rewrite_location_references(
        scene.location_events, entity_references, place_references
    )
    previous_locations = _merge_location_events(
        previous_locations, reject_conflicting_stable_ids=True
    )
    replacement_locations = _merge_location_events(replacement_locations)
    relationships = _replace_scene_candidates(
        previous_relationships,
        replacement_relationships,
        scene.scene_id,
        scene.scene_revision,
        _relationship_replacement_key,
        _relationship_output_key,
    )
    locations = _replace_scene_candidates(
        previous_locations,
        replacement_locations,
        scene.scene_id,
        scene.scene_revision,
        _location_replacement_key,
        _location_output_key,
    )
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
    result = downgrade_invalid_approvals(result)
    _require_valid_project(result)
    return result


def _require_valid_project(project: ProjectRelationshipSnapshot) -> None:
    try:
        validate_project_snapshot(project)
    except ProjectInvariantError as error:
        raise MergeInvariantError(str(error)) from error


def _force_pending_scene_candidates(
    scene: SceneRelationshipSnapshot,
) -> SceneRelationshipSnapshot:
    return replace(
        scene,
        entities=tuple(
            replace(candidate, status=CandidateStatus.PENDING) for candidate in scene.entities
        ),
        places=tuple(
            replace(candidate, status=CandidateStatus.PENDING) for candidate in scene.places
        ),
        relationship_events=tuple(
            replace(event, status=CandidateStatus.PENDING) for event in scene.relationship_events
        ),
        location_events=tuple(
            replace(event, status=CandidateStatus.PENDING) for event in scene.location_events
        ),
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
) -> tuple[tuple[Candidate, ...], dict[str, str]]:
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
    candidate_id_map: dict[str, str] = {}
    prior_count = len(prior_records)
    for cluster in clusters:
        stable = sorted(
            (
                candidates[index]
                for index in cluster
                if candidates[index].status
                in (CandidateStatus.APPROVED, CandidateStatus.NEEDS_REVIEW)
            ),
            key=_identity_representative_key,
        )
        stable_ids = {candidate.candidate_id for candidate in stable}
        if len(stable_ids) > 1:
            raise MergeInvariantError("conflicting stable identities would collapse")

        cluster_replacements = sorted(
            (candidates[index] for index in cluster if index >= prior_count),
            key=_identity_representative_key,
        )
        cluster_priors = sorted(
            (candidates[index] for index in cluster if index < prior_count),
            key=_identity_representative_key,
        )
        stable_candidate = stable[0] if stable else None
        base = cluster_replacements[0] if cluster_replacements else cluster_priors[0]
        evidence_values = [evidence for index in cluster for evidence in candidates[index].evidence]
        status = base.status
        if stable_candidate is not None:
            stable_prior_index = next(
                (
                    index
                    for index in cluster
                    if index < prior_count
                    and candidates[index].candidate_id == stable_candidate.candidate_id
                ),
                None,
            )
            old_changed_evidence = (
                prior_records[stable_prior_index][1] if stable_prior_index is not None else ()
            )
            belongs_to_changed_scene = (
                prior_records[stable_prior_index][2] if stable_prior_index is not None else False
            )
            supported = any(
                (not old_changed_evidence and not candidate.evidence)
                or _has_materially_equivalent_evidence(old_changed_evidence, candidate.evidence)
                for candidate in cluster_replacements
            )
            if belongs_to_changed_scene and not supported:
                status = CandidateStatus.NEEDS_REVIEW
                if not cluster_replacements:
                    evidence_values.extend(old_changed_evidence)
            else:
                status = stable_candidate.status
            base = replace(base, candidate_id=stable_candidate.candidate_id)
        elif cluster_priors:
            base = replace(base, candidate_id=cluster_priors[0].candidate_id)
        else:
            base = replace(base, candidate_id=cluster_replacements[0].candidate_id)

        representative_id = base.candidate_id
        candidate_id_map.update(
            {candidates[index].candidate_id: representative_id for index in cluster}
        )

        if not cluster_replacements and base.scene_id == scene.scene_id:
            base = replace(base, scene_revision=scene.scene_revision)
        merged.append(
            replace(
                base,
                aliases=_merge_aliases(
                    value
                    for index in cluster
                    for value in (
                        candidates[index].normalized_name,
                        *candidates[index].aliases,
                    )
                    if normalize_text(value) != normalize_text(base.normalized_name)
                ),
                status=status,
                evidence=_merge_evidence(evidence_values),
            )
        )

    return (
        tuple(sorted(merged, key=lambda candidate: candidate.candidate_id)),
        candidate_id_map,
    )


def _identity_representative_key(
    candidate: EntityCandidate | PlaceCandidate,
) -> tuple[int, str, str, str]:
    status_rank = {
        CandidateStatus.APPROVED: 0,
        CandidateStatus.NEEDS_REVIEW: 1,
        CandidateStatus.PENDING: 2,
        CandidateStatus.REJECTED: 3,
    }
    return (
        status_rank[candidate.status],
        candidate.candidate_id,
        normalize_text(candidate.normalized_name),
        candidate.display_name,
    )


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
        candidate for index, candidate in enumerate(replacements) if index not in consumed
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


def _rewrite_relationship_references(
    events: Iterable[RelationshipEventCandidate],
    entity_references: dict[str, str],
) -> tuple[RelationshipEventCandidate, ...]:
    return tuple(
        replace(
            event,
            subject_key=entity_references.get(
                normalize_reference(event.subject_key), event.subject_key
            ),
            object_key=entity_references.get(
                normalize_reference(event.object_key), event.object_key
            ),
        )
        for event in events
    )


def _rewrite_location_references(
    events: Iterable[LocationEventCandidate],
    entity_references: dict[str, str],
    place_references: dict[str, str],
) -> tuple[LocationEventCandidate, ...]:
    return tuple(
        replace(
            event,
            character_key=entity_references.get(
                normalize_reference(event.character_key), event.character_key
            ),
            place_key=place_references.get(normalize_reference(event.place_key), event.place_key),
        )
        for event in events
    )


def _validate_scene_snapshot(scene: SceneRelationshipSnapshot) -> None:
    if scene.schema_version != SCENE_SNAPSHOT_SCHEMA_VERSION:
        raise MergeInvariantError("unsupported scene snapshot schema")
    candidates = _all_candidates(scene)
    candidate_ids = tuple(candidate.candidate_id for candidate in (*scene.entities, *scene.places))
    event_ids = tuple(
        event.event_id for event in (*scene.relationship_events, *scene.location_events)
    )
    if len(candidate_ids) != len(set(candidate_ids)):
        raise MergeInvariantError("scene candidate IDs must be unique")
    if len(event_ids) != len(set(event_ids)):
        raise MergeInvariantError("scene event IDs must be unique")
    for candidate in candidates:
        if candidate.scene_id != scene.scene_id or candidate.scene_revision != scene.scene_revision:
            raise MergeInvariantError("candidate provenance does not match scene snapshot")
        if isinstance(candidate, (RelationshipEventCandidate, LocationEventCandidate)):
            if candidate.scene_sequence != scene.scene_sequence:
                raise MergeInvariantError("event sequence does not match containing scene")
            _validate_confidence(candidate.confidence)
        _validate_candidate_evidence(candidate)


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
) -> None:
    for evidence in candidate.evidence:
        if not 0 <= evidence.start_offset < evidence.end_offset:
            raise MergeInvariantError("evidence range must satisfy 0 <= start < end")
        if (
            evidence.scene_id != candidate.scene_id
            or evidence.scene_revision != candidate.scene_revision
        ):
            raise MergeInvariantError("evidence provenance does not match candidate")


def _validate_confidence(confidence: float) -> None:
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise MergeInvariantError("confidence must be finite and between 0.0 and 1.0")


def _merge_aliases(values: Iterable[str]) -> tuple[str, ...]:
    by_key: dict[str, str] = {}
    for value in values:
        alias = re.sub(r"\s+", " ", value.strip())
        if alias:
            by_key.setdefault(normalize_text(alias), alias)
    return tuple(by_key[key] for key in sorted(by_key))


def _merge_relationship_events(
    values: Iterable[RelationshipEventCandidate],
    *,
    reject_conflicting_stable_ids: bool = False,
) -> tuple[RelationshipEventCandidate, ...]:
    grouped: dict[tuple[str, str, str, str, str], list[RelationshipEventCandidate]] = {}
    for event in values:
        grouped.setdefault(relationship_key(event), []).append(event)

    merged: list[RelationshipEventCandidate] = []
    for key in sorted(grouped):
        ordered = tuple(sorted(grouped[key], key=_relationship_event_order_key))
        for cluster in _overlap_clusters(ordered):
            stable = tuple(
                event
                for event in cluster
                if event.status in (CandidateStatus.APPROVED, CandidateStatus.NEEDS_REVIEW)
            )
            if reject_conflicting_stable_ids and len({event.event_id for event in stable}) > 1:
                raise MergeInvariantError("conflicting stable event IDs would collapse")
            representative = stable[0] if stable else cluster[0]
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
    *,
    reject_conflicting_stable_ids: bool = False,
) -> tuple[LocationEventCandidate, ...]:
    grouped: dict[tuple[str, str, str, str, str], list[LocationEventCandidate]] = {}
    for event in values:
        grouped.setdefault(location_key(event), []).append(event)

    merged: list[LocationEventCandidate] = []
    for key in sorted(grouped):
        ordered = tuple(sorted(grouped[key], key=_location_event_order_key))
        for cluster in _overlap_clusters(ordered):
            stable = tuple(
                event
                for event in cluster
                if event.status in (CandidateStatus.APPROVED, CandidateStatus.NEEDS_REVIEW)
            )
            if reject_conflicting_stable_ids and len({event.event_id for event in stable}) > 1:
                raise MergeInvariantError("conflicting stable event IDs would collapse")
            representative = stable[0] if stable else cluster[0]
            merged.append(
                replace(
                    representative,
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
