import re
from collections.abc import Callable, Iterable

from narrative_analysis_agent.models import (
    PROJECT_GRAPH_SCHEMA_VERSION,
    AnalyzedChunk,
    Character,
    Contradiction,
    Coreference,
    Document,
    Entities,
    Event,
    KnowledgeGraphOutput,
    Location,
    Movement,
    NarrativeTime,
    ProjectKnowledgeGraphSnapshot,
    Relation,
    SceneAnalysis,
    UnresolvedReference,
)
from pydantic import ValidationError

from apps.narrative_memory.service.models import SceneGraphRecord
from apps.narrative_memory.service.validation import (
    ProjectInvariantError,
    validate_project_snapshot,
)

type LocalId = tuple[int, str]
type IdMap = dict[LocalId, str]
type Entity = Character | Location | Event
type EntityMap = dict[LocalId, str]


class MergeInvariantError(ValueError):
    pass


def assemble_scene_graph(
    analysis: SceneAnalysis,
    existing: ProjectKnowledgeGraphSnapshot,
) -> SceneGraphRecord:
    if analysis.project_id != existing.project_id:
        raise MergeInvariantError("analysis and existing graph project IDs must match")

    character_map = _character_id_map(analysis.chunks, existing)
    location_map = _location_id_map(analysis.chunks, existing)
    event_map = _event_id_map(
        analysis.chunks,
        existing,
        character_map,
        location_map,
    )
    entity_map = character_map | location_map | event_map
    graph = KnowledgeGraphOutput(
        document=_merge_documents(analysis.scene_id, analysis.chunks),
        entities=Entities(
            characters=_merge_characters(analysis.chunks, existing, character_map),
            locations=_merge_locations(analysis.chunks, existing, location_map),
            events=_merge_events(
                analysis.chunks,
                event_map,
                character_map,
                location_map,
            ),
        ),
        relations=_merge_relations(
            analysis.chunks,
            existing,
            entity_map,
            event_map,
        ),
        movements=_merge_movements(
            analysis.chunks,
            character_map,
            location_map,
            event_map,
        ),
        coreferences=_merge_coreferences(analysis.chunks, entity_map),
        unresolved_references=_merge_unresolved(analysis.chunks, entity_map),
        contradictions=_merge_contradictions(analysis.chunks, entity_map),
    )
    graph = _with_existing_dependency_closure(graph, existing)
    return SceneGraphRecord(
        project_id=analysis.project_id,
        scene_id=analysis.scene_id,
        scene_revision=analysis.scene_revision,
        scene_sequence=analysis.scene_sequence,
        graph=graph,
    )


def rebuild_project_graph(
    project_id: str,
    snapshot_version: int,
    scenes: tuple[SceneGraphRecord, ...],
) -> ProjectKnowledgeGraphSnapshot:
    current_scenes = _current_scene_records(project_id, scenes)
    ordered = tuple(sorted(current_scenes, key=lambda item: (item.scene_sequence, item.scene_id)))
    try:
        snapshot = ProjectKnowledgeGraphSnapshot(
            project_id=project_id,
            snapshot_version=snapshot_version,
            schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
            documents=tuple(item.graph.document for item in ordered),
            entities=_aggregate_entities(ordered),
            relations=_aggregate(ordered, lambda graph: graph.relations),
            movements=_aggregate(ordered, lambda graph: graph.movements),
            coreferences=_aggregate(ordered, lambda graph: graph.coreferences),
            unresolved_references=_aggregate(
                ordered,
                lambda graph: graph.unresolved_references,
            ),
            contradictions=_aggregate(ordered, lambda graph: graph.contradictions),
        )
        snapshot = ProjectKnowledgeGraphSnapshot.model_validate(
            snapshot.model_dump(mode="python"),
            strict=True,
        )
        validate_project_snapshot(snapshot)
        return snapshot
    except (ProjectInvariantError, ValidationError) as error:
        raise MergeInvariantError("project graph invariants are invalid") from error


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _ordered_chunks(chunks: Iterable[AnalyzedChunk]) -> tuple[AnalyzedChunk, ...]:
    return tuple(sorted(chunks, key=lambda chunk: chunk.ordinal))


def _character_id_map(
    chunks: tuple[AnalyzedChunk, ...],
    existing: ProjectKnowledgeGraphSnapshot,
) -> IdMap:
    entries = [
        (chunk, character)
        for chunk in _ordered_chunks(chunks)
        for character in chunk.extraction.entities.characters
    ]
    entries.sort(key=lambda entry: _identity_order(*entry))
    existing_items = {item.id: item for item in existing.entities.characters}
    result = _map_existing_identities(
        entries,
        existing_items,
        _has_explicit_alias_bridge,
    )
    remaining = [entry for entry in entries if _local_key(*entry) not in result]
    clusters = _clusters(
        remaining,
        lambda left, right: _identities_clearly_match(left, right),
    )
    _allocate_clusters(
        result,
        clusters,
        "character",
        existing_items,
        _identity_order,
    )
    return result


def _location_id_map(
    chunks: tuple[AnalyzedChunk, ...],
    existing: ProjectKnowledgeGraphSnapshot,
) -> IdMap:
    entries = [
        (chunk, location)
        for chunk in _ordered_chunks(chunks)
        for location in chunk.extraction.entities.locations
    ]
    entries.sort(key=lambda entry: _identity_order(*entry))
    existing_items = {item.id: item for item in existing.entities.locations}
    result = _map_existing_identities(
        entries,
        existing_items,
        _shares_name_or_alias,
    )
    remaining = [entry for entry in entries if _local_key(*entry) not in result]
    clusters = _clusters(
        remaining,
        lambda left, right: _identities_clearly_match(left, right),
    )
    _allocate_clusters(
        result,
        clusters,
        "location",
        existing_items,
        _identity_order,
    )
    return result


def _event_id_map(
    chunks: tuple[AnalyzedChunk, ...],
    existing: ProjectKnowledgeGraphSnapshot,
    character_map: IdMap,
    location_map: IdMap,
) -> IdMap:
    entries = [
        (chunk, event)
        for chunk in _ordered_chunks(chunks)
        for event in chunk.extraction.entities.events
    ]
    entries.sort(key=lambda entry: _event_order(*entry))
    existing_items = {item.id: item for item in existing.entities.events}
    result: IdMap = {}
    clusters = _clusters(
        entries,
        lambda left, right: _events_clearly_match(
            left,
            right,
            character_map,
            location_map,
        ),
    )
    _allocate_clusters(
        result,
        clusters,
        "event",
        existing_items,
        _event_order,
    )
    return result


def _map_existing_identities[Item: Character | Location](
    entries: list[tuple[AnalyzedChunk, Item]],
    existing_items: dict[str, Item],
    matches_identity: Callable[[Item, Item], bool],
) -> IdMap:
    result: IdMap = {}
    for chunk, item in entries:
        key = (chunk.ordinal, item.id)
        matches = {
            existing_id
            for existing_id, existing_item in existing_items.items()
            if matches_identity(item, existing_item)
        }
        if len(matches) == 1:
            result[key] = matches.pop()
    return result


def _has_explicit_alias_bridge(
    left: Character | Location,
    right: Character | Location,
) -> bool:
    left_name = normalize_text(left.canonical_name)
    right_name = normalize_text(right.canonical_name)
    left_aliases = {normalize_text(alias) for alias in left.aliases if normalize_text(alias)}
    right_aliases = {normalize_text(alias) for alias in right.aliases if normalize_text(alias)}
    return bool(left_aliases & ({right_name} | right_aliases)) or bool(
        right_aliases & ({left_name} | left_aliases)
    )


def _shares_name_or_alias(
    left: Character | Location,
    right: Character | Location,
) -> bool:
    return bool(_identity_tokens(left) & _identity_tokens(right))


def _clusters[Item](
    entries: list[tuple[AnalyzedChunk, Item]],
    matches: Callable[[tuple[AnalyzedChunk, Item], tuple[AnalyzedChunk, Item]], bool],
) -> tuple[tuple[tuple[AnalyzedChunk, Item], ...], ...]:
    parents = list(range(len(entries)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for right_index, right in enumerate(entries):
        for left_index in range(right_index):
            if matches(entries[left_index], right):
                left_root = find(left_index)
                right_root = find(right_index)
                if left_root != right_root:
                    parents[right_root] = left_root

    grouped: dict[int, list[tuple[AnalyzedChunk, Item]]] = {}
    for index, entry in enumerate(entries):
        grouped.setdefault(find(index), []).append(entry)
    return tuple(tuple(grouped[root]) for root in sorted(grouped))


def _allocate_clusters[Item: Entity](
    result: IdMap,
    clusters: tuple[tuple[tuple[AnalyzedChunk, Item], ...], ...],
    prefix: str,
    existing_items: dict[str, Item],
    order: Callable[[AnalyzedChunk, Item], tuple[object, ...]],
) -> None:
    next_number = _next_id_number(prefix, existing_items)
    ordered_clusters = sorted(
        clusters,
        key=lambda cluster: min(order(chunk, item) for chunk, item in cluster),
    )
    for cluster in ordered_clusters:
        durable_id = f"{prefix}_{next_number:03d}"
        next_number += 1
        for chunk, item in cluster:
            result[(chunk.ordinal, item.id)] = durable_id


def _next_id_number(prefix: str, items: Iterable[str]) -> int:
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
    numbers = [
        int(match.group(1))
        for item_id in items
        if (match := pattern.fullmatch(item_id)) is not None
    ]
    return max(numbers, default=0) + 1


def _identities_clearly_match[Item: Character | Location](
    left: tuple[AnalyzedChunk, Item],
    right: tuple[AnalyzedChunk, Item],
) -> bool:
    left_chunk, left_item = left
    right_chunk, right_item = right
    left_name = normalize_text(left_item.canonical_name)
    right_name = normalize_text(right_item.canonical_name)
    left_aliases = {normalize_text(alias) for alias in left_item.aliases if normalize_text(alias)}
    right_aliases = {normalize_text(alias) for alias in right_item.aliases if normalize_text(alias)}
    alias_link = bool(left_aliases & ({right_name} | right_aliases)) or bool(
        right_aliases & ({left_name} | left_aliases)
    )
    same_evidence = _absolute_evidence_position(
        left_chunk,
        left_item.first_mention,
    ) == _absolute_evidence_position(right_chunk, right_item.first_mention)
    return bool(_identity_tokens(left_item) & _identity_tokens(right_item)) and (
        alias_link or same_evidence
    )


def _events_clearly_match(
    left: tuple[AnalyzedChunk, Event],
    right: tuple[AnalyzedChunk, Event],
    character_map: IdMap,
    location_map: IdMap,
) -> bool:
    left_chunk, left_event = left
    right_chunk, right_event = right
    if _absolute_evidence_position(
        left_chunk,
        left_event.evidence,
    ) != _absolute_evidence_position(right_chunk, right_event.evidence):
        return False
    return _event_semantic_key(
        left_chunk,
        left_event,
        character_map,
        location_map,
    ) == _event_semantic_key(
        right_chunk,
        right_event,
        character_map,
        location_map,
    )


def _event_semantic_key(
    chunk: AnalyzedChunk,
    event: Event,
    character_map: IdMap,
    location_map: IdMap,
) -> tuple[object, ...]:
    return (
        event.event_type,
        normalize_text(event.name),
        normalize_text(event.summary),
        _canonical_references(chunk.ordinal, event.participant_ids, character_map),
        _canonical_references(chunk.ordinal, event.location_ids, location_map),
        normalize_text(event.time_expression or ""),
        event.narrative_time,
        event.sequence,
        normalize_text(event.evidence),
        event.confidence,
    )


def _identity_tokens(item: Character | Location) -> set[str]:
    return {
        normalized
        for value in (item.canonical_name, *item.aliases)
        if (normalized := normalize_text(value))
    }


def _local_key(chunk: AnalyzedChunk, item: Entity) -> LocalId:
    return chunk.ordinal, item.id


def _identity_order(
    chunk: AnalyzedChunk,
    item: Character | Location,
) -> tuple[object, ...]:
    return (
        _absolute_evidence_position(chunk, item.first_mention),
        normalize_text(item.canonical_name),
        item.id,
        chunk.ordinal,
    )


def _event_order(chunk: AnalyzedChunk, item: Event) -> tuple[object, ...]:
    return (
        _absolute_evidence_position(chunk, item.evidence),
        normalize_text(item.name),
        item.id,
        chunk.ordinal,
    )


def _absolute_evidence_position(chunk: AnalyzedChunk, evidence: str) -> int:
    return chunk.start_offset + chunk.text.find(evidence)


def _merge_characters(
    chunks: tuple[AnalyzedChunk, ...],
    existing: ProjectKnowledgeGraphSnapshot,
    character_map: IdMap,
) -> tuple[Character, ...]:
    entries = [
        (chunk, item)
        for chunk in _ordered_chunks(chunks)
        for item in chunk.extraction.entities.characters
    ]
    existing_items = {item.id: item for item in existing.entities.characters}
    return _merge_identities(entries, existing_items, character_map)


def _merge_locations(
    chunks: tuple[AnalyzedChunk, ...],
    existing: ProjectKnowledgeGraphSnapshot,
    location_map: IdMap,
) -> tuple[Location, ...]:
    entries = [
        (chunk, item)
        for chunk in _ordered_chunks(chunks)
        for item in chunk.extraction.entities.locations
    ]
    existing_items = {item.id: item for item in existing.entities.locations}
    merged = _merge_identities(entries, existing_items, location_map)
    return tuple(
        item
        if item.id in existing_items
        else item.model_copy(
            update={
                "parent_location_id": _resolve_reference(
                    source_chunk.ordinal,
                    source_item.parent_location_id,
                    location_map,
                )
            }
        )
        for item in merged
        for source_chunk, source_item in (
            min(
                (
                    (chunk, candidate)
                    for chunk, candidate in entries
                    if location_map[(chunk.ordinal, candidate.id)] == item.id
                ),
                key=lambda entry: _identity_order(*entry),
            ),
        )
    )


def _merge_identities[Item: Character | Location](
    entries: list[tuple[AnalyzedChunk, Item]],
    existing_items: dict[str, Item],
    id_map: IdMap,
) -> tuple[Item, ...]:
    by_id: dict[str, list[tuple[AnalyzedChunk, Item]]] = {}
    for chunk, item in entries:
        by_id.setdefault(id_map[(chunk.ordinal, item.id)], []).append((chunk, item))

    merged: list[Item] = []
    for durable_id in sorted(by_id, key=_id_order):
        values = sorted(by_id[durable_id], key=lambda entry: _identity_order(*entry))
        if durable_id in existing_items:
            merged.append(existing_items[durable_id])
            continue
        base = values[0][1]
        aliases = _merged_aliases(base, (item for _, item in values))
        merged.append(base.model_copy(update={"id": durable_id, "aliases": aliases}))
    return tuple(merged)


def _merged_aliases[Item: Character | Location](
    base: Item,
    values: Iterable[Item],
) -> tuple[str, ...]:
    canonical = normalize_text(base.canonical_name)
    by_normalized: dict[str, str] = {}
    for value in (base, *values):
        for name in (value.canonical_name, *value.aliases):
            normalized = normalize_text(name)
            if normalized and normalized != canonical:
                by_normalized.setdefault(normalized, name)
    return tuple(by_normalized[key] for key in sorted(by_normalized))


def _merge_events(
    chunks: tuple[AnalyzedChunk, ...],
    event_map: IdMap,
    character_map: IdMap,
    location_map: IdMap,
) -> tuple[Event, ...]:
    by_id: dict[str, list[tuple[AnalyzedChunk, Event]]] = {}
    for chunk in _ordered_chunks(chunks):
        for event in chunk.extraction.entities.events:
            by_id.setdefault(event_map[(chunk.ordinal, event.id)], []).append((chunk, event))

    merged: list[Event] = []
    for durable_id in sorted(by_id, key=_id_order):
        chunk, event = min(by_id[durable_id], key=lambda entry: _event_order(*entry))
        merged.append(
            event.model_copy(
                update={
                    "id": durable_id,
                    "participant_ids": _canonical_references(
                        chunk.ordinal,
                        event.participant_ids,
                        character_map,
                    ),
                    "location_ids": _canonical_references(
                        chunk.ordinal,
                        event.location_ids,
                        location_map,
                    ),
                }
            )
        )
    return tuple(merged)


def _merge_relations(
    chunks: tuple[AnalyzedChunk, ...],
    existing: ProjectKnowledgeGraphSnapshot,
    entity_map: EntityMap,
    event_map: IdMap,
) -> tuple[Relation, ...]:
    entries = [
        (chunk, relation)
        for chunk in _ordered_chunks(chunks)
        for relation in chunk.extraction.relations
    ]
    rewritten = [
        (
            chunk,
            relation.model_copy(
                update={
                    "source_id": _resolve_reference(
                        chunk.ordinal,
                        relation.source_id,
                        entity_map,
                    ),
                    "target_id": _resolve_reference(
                        chunk.ordinal,
                        relation.target_id,
                        entity_map,
                    ),
                    "start_event_id": _resolve_reference(
                        chunk.ordinal,
                        relation.start_event_id,
                        event_map,
                    ),
                    "end_event_id": _resolve_reference(
                        chunk.ordinal,
                        relation.end_event_id,
                        event_map,
                    ),
                }
            ),
        )
        for chunk, relation in entries
    ]
    rewritten.sort(key=lambda entry: _relation_order(*entry))
    existing_ids = {item.id for item in existing.relations}
    next_number = _next_id_number("relation", existing_ids)
    by_duplicate: dict[tuple[object, ...], str] = {}
    merged: list[Relation] = []
    for chunk, relation in rewritten:
        duplicate_key = (
            _absolute_evidence_position(chunk, relation.evidence),
            *_relation_semantic_key(relation),
        )
        durable_id = by_duplicate.get(duplicate_key, "")
        if not durable_id:
            durable_id = f"relation_{next_number:03d}"
            next_number += 1
            by_duplicate[duplicate_key] = durable_id
        candidate = relation.model_copy(update={"id": durable_id})
        if candidate not in merged:
            merged.append(candidate)
    return tuple(sorted(merged, key=lambda item: _id_order(item.id)))


def _relation_order(chunk: AnalyzedChunk, relation: Relation) -> tuple[object, ...]:
    return (
        _absolute_evidence_position(chunk, relation.evidence),
        *_relation_semantic_key(relation),
        relation.id,
        chunk.ordinal,
    )


def _relation_semantic_key(relation: Relation) -> tuple[object, ...]:
    return (
        relation.source_id,
        relation.relation_type,
        relation.target_id,
        relation.state,
        relation.directed,
        relation.start_event_id or "",
        relation.end_event_id or "",
        normalize_text(relation.time_expression or ""),
        relation.scene_sequence,
        normalize_text(relation.evidence),
        relation.inference,
        relation.confidence,
    )


def _merge_movements(
    chunks: tuple[AnalyzedChunk, ...],
    character_map: IdMap,
    location_map: IdMap,
    event_map: IdMap,
) -> tuple[Movement, ...]:
    values = [
        (
            chunk,
            movement.model_copy(
                update={
                    "character_id": _resolve_reference(
                        chunk.ordinal,
                        movement.character_id,
                        character_map,
                    ),
                    "from_location_id": _resolve_reference(
                        chunk.ordinal,
                        movement.from_location_id,
                        location_map,
                    ),
                    "to_location_id": _resolve_reference(
                        chunk.ordinal,
                        movement.to_location_id,
                        location_map,
                    ),
                    "event_id": _resolve_reference(
                        chunk.ordinal,
                        movement.event_id,
                        event_map,
                    ),
                }
            ),
        )
        for chunk in _ordered_chunks(chunks)
        for movement in chunk.extraction.movements
    ]
    values.sort(
        key=lambda entry: (
            entry[0].ordinal,
            entry[0].text.find(entry[1].evidence),
            entry[1].character_id,
            entry[1].sequence,
            entry[1].movement_type,
            entry[1].model_dump_json(),
        )
    )
    return _dedupe(item for _, item in values)


def _merge_coreferences(
    chunks: tuple[AnalyzedChunk, ...],
    entity_map: EntityMap,
) -> tuple[Coreference, ...]:
    values = [
        (
            chunk,
            item.model_copy(
                update={
                    "resolved_entity_id": _resolve_reference(
                        chunk.ordinal,
                        item.resolved_entity_id,
                        entity_map,
                    )
                }
            ),
        )
        for chunk in _ordered_chunks(chunks)
        for item in chunk.extraction.coreferences
    ]
    values.sort(
        key=lambda entry: (
            entry[0].ordinal,
            entry[0].text.find(entry[1].evidence),
            normalize_text(entry[1].expression),
            entry[1].resolved_entity_id,
            entry[1].model_dump_json(),
        )
    )
    return _dedupe(item for _, item in values)


def _merge_unresolved(
    chunks: tuple[AnalyzedChunk, ...],
    entity_map: EntityMap,
) -> tuple[UnresolvedReference, ...]:
    values = [
        (
            chunk,
            item.model_copy(
                update={
                    "possible_entity_ids": _canonical_references(
                        chunk.ordinal,
                        item.possible_entity_ids,
                        entity_map,
                    )
                }
            ),
        )
        for chunk in _ordered_chunks(chunks)
        for item in chunk.extraction.unresolved_references
    ]
    values.sort(
        key=lambda entry: (
            entry[0].ordinal,
            normalize_text(entry[1].expression),
            normalize_text(entry[1].reason),
            entry[1].possible_entity_ids,
        )
    )
    return _dedupe(item for _, item in values)


def _merge_contradictions(
    chunks: tuple[AnalyzedChunk, ...],
    entity_map: EntityMap,
) -> tuple[Contradiction, ...]:
    values = [
        (
            chunk,
            item.model_copy(
                update={
                    "subject_id": _resolve_reference(
                        chunk.ordinal,
                        item.subject_id,
                        entity_map,
                    )
                }
            ),
        )
        for chunk in _ordered_chunks(chunks)
        for item in chunk.extraction.contradictions
    ]
    values.sort(
        key=lambda entry: (
            entry[0].ordinal,
            entry[0].text.find(entry[1].evidence),
            entry[1].subject_id,
            normalize_text(entry[1].field_or_relation),
            entry[1].model_dump_json(),
        )
    )
    return _dedupe(item for _, item in values)


def _resolve_reference(
    ordinal: int,
    reference: str | None,
    id_map: IdMap,
) -> str | None:
    if reference is None:
        return None
    return id_map.get((ordinal, reference), reference)


def _with_existing_dependency_closure(
    graph: KnowledgeGraphOutput,
    existing: ProjectKnowledgeGraphSnapshot,
) -> KnowledgeGraphOutput:
    characters = {item.id: item for item in graph.entities.characters}
    locations = {item.id: item for item in graph.entities.locations}
    events = {item.id: item for item in graph.entities.events}
    existing_characters = {item.id: item for item in existing.entities.characters}
    existing_locations = {item.id: item for item in existing.entities.locations}
    existing_events = {item.id: item for item in existing.entities.events}

    pending = _graph_reference_ids(graph)
    processed: set[str] = set()
    while pending:
        reference = min(pending, key=_id_order)
        pending.remove(reference)
        if reference in processed:
            continue
        processed.add(reference)
        if reference in characters or reference in locations or reference in events:
            continue
        if character := existing_characters.get(reference):
            characters[reference] = character
            continue
        if location := existing_locations.get(reference):
            locations[reference] = location
            if location.parent_location_id is not None:
                pending.add(location.parent_location_id)
            continue
        if event := existing_events.get(reference):
            events[reference] = event
            pending.update(event.participant_ids)
            pending.update(event.location_ids)

    return graph.model_copy(
        update={
            "entities": Entities(
                characters=tuple(characters[key] for key in sorted(characters, key=_id_order)),
                locations=tuple(locations[key] for key in sorted(locations, key=_id_order)),
                events=tuple(events[key] for key in sorted(events, key=_id_order)),
            )
        }
    )


def _graph_reference_ids(graph: KnowledgeGraphOutput) -> set[str]:
    references = {
        *(item.parent_location_id for item in graph.entities.locations),
        *(reference for item in graph.entities.events for reference in item.participant_ids),
        *(reference for item in graph.entities.events for reference in item.location_ids),
        *(item.source_id for item in graph.relations),
        *(item.target_id for item in graph.relations),
        *(item.start_event_id for item in graph.relations),
        *(item.end_event_id for item in graph.relations),
        *(item.character_id for item in graph.movements),
        *(item.from_location_id for item in graph.movements),
        *(item.to_location_id for item in graph.movements),
        *(item.event_id for item in graph.movements),
        *(item.resolved_entity_id for item in graph.coreferences),
        *(
            reference
            for item in graph.unresolved_references
            for reference in item.possible_entity_ids
        ),
        *(item.subject_id for item in graph.contradictions),
    }
    return {reference for reference in references if reference is not None}


def _canonical_references(
    ordinal: int,
    references: tuple[str, ...],
    id_map: IdMap,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            (id_map.get((ordinal, reference), reference) for reference in references),
            key=_id_order,
        )
    )


def _merge_documents(
    scene_id: str,
    chunks: tuple[AnalyzedChunk, ...],
) -> Document:
    ordered = _ordered_chunks(chunks)
    sentences: list[str] = []
    seen: set[str] = set()
    for chunk in ordered:
        for sentence in _summary_sentences(chunk.extraction.document.summary):
            key = normalize_text(sentence)
            if key and key not in seen:
                seen.add(key)
                sentences.append(sentence)
                if len(sentences) == 4:
                    break
        if len(sentences) == 4:
            break

    times = {chunk.extraction.document.narrative_time for chunk in ordered}
    narrative_time: NarrativeTime
    if not times:
        narrative_time = "unknown"
    elif len(times) == 1:
        narrative_time = times.pop()
    else:
        narrative_time = "mixed"
    return Document(
        chapter_id=scene_id,
        summary=" ".join(sentences),
        narrative_time=narrative_time,
    )


def _summary_sentences(summary: str) -> tuple[str, ...]:
    return tuple(
        match.group(0).strip()
        for match in re.finditer(r"[^.!?。！？]+[.!?。！？]*", summary)
        if match.group(0).strip()
    )


def _current_scene_records(
    project_id: str,
    scenes: tuple[SceneGraphRecord, ...],
) -> tuple[SceneGraphRecord, ...]:
    by_scene: dict[str, SceneGraphRecord] = {}
    for scene in scenes:
        if scene.project_id != project_id:
            raise MergeInvariantError("scene and snapshot project IDs must match")
        if scene.graph.document.chapter_id != scene.scene_id:
            raise MergeInvariantError("scene graph document must identify its scene")
        current = by_scene.get(scene.scene_id)
        if current is None or _scene_revision_key(scene) > _scene_revision_key(current):
            by_scene[scene.scene_id] = scene
    return tuple(by_scene.values())


def _scene_revision_key(scene: SceneGraphRecord) -> tuple[object, ...]:
    return (
        scene.scene_revision,
        scene.scene_sequence,
        scene.graph.model_dump_json(),
    )


def _aggregate_entities(scenes: tuple[SceneGraphRecord, ...]) -> Entities:
    return Entities(
        characters=_aggregate(scenes, lambda graph: graph.entities.characters),
        locations=_aggregate(scenes, lambda graph: graph.entities.locations),
        events=_aggregate(scenes, lambda graph: graph.entities.events),
    )


def _aggregate[Item](
    scenes: tuple[SceneGraphRecord, ...],
    values: Callable[[KnowledgeGraphOutput], tuple[Item, ...]],
) -> tuple[Item, ...]:
    return _dedupe(item for scene in scenes for item in values(scene.graph))


def _dedupe[Item](values: Iterable[Item]) -> tuple[Item, ...]:
    result: list[Item] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)


def _id_order(value: str) -> tuple[str, int, str]:
    prefix, separator, suffix = value.rpartition("_")
    if separator and suffix.isdigit():
        return prefix, int(suffix), value
    return value, -1, value
