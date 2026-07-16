import json
import math
import re
from collections.abc import Callable
from hashlib import sha256

from apps.narrative_memory.service.chunking import SceneChunk
from apps.narrative_memory.service.models import (
    CHUNK_ANALYSIS_SCHEMA_VERSION,
    CandidateStatus,
    ChunkAnalysis,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    PlaceCandidate,
    RelationshipEventCandidate,
)
from apps.narrative_memory.service.scene_analysis_types import (
    ExtractedEntity,
    ExtractedLocationEvent,
    ExtractedPlace,
    ExtractedRelationshipEvent,
    KnownIdentity,
    RelativeEvidence,
    SceneChunkExtraction,
)


class ExtractionTranslationError(ValueError):
    pass


def translate_chunk_extraction(
    chunk: SceneChunk,
    scene_sequence: int,
    extraction: SceneChunkExtraction,
    known_entities: tuple[KnownIdentity, ...],
    known_places: tuple[KnownIdentity, ...],
) -> ChunkAnalysis:
    entity_refs = _build_local_ids(
        chunk,
        "entity",
        extraction.entities,
        lambda entity: (
            entity.normalized_name,
            entity.display_name,
            *sorted(entity.aliases, key=_normalize_text),
        ),
    )
    place_refs = _build_local_ids(
        chunk,
        "place",
        extraction.places,
        lambda place: (
            place.normalized_name,
            place.display_name,
            *sorted(place.aliases, key=_normalize_text),
        ),
    )
    known_entity_keys = {identity.identity_key for identity in known_entities}
    known_place_keys = {identity.identity_key for identity in known_places}
    known_keys = known_entity_keys | known_place_keys
    local_refs = set(entity_refs) | set(place_refs)
    if local_refs & known_keys:
        raise ExtractionTranslationError("ambiguous local reference collides with known key")

    entities = tuple(
        EntityCandidate(
            candidate_id=entity_refs[entity.local_ref],
            normalized_name=entity.normalized_name,
            display_name=entity.display_name,
            aliases=entity.aliases,
            status=CandidateStatus.PENDING,
            scene_id=chunk.scene_id,
            scene_revision=chunk.manuscript_revision,
            evidence=_translate_evidence(chunk, entity.evidence),
        )
        for entity in extraction.entities
    )
    places = tuple(
        PlaceCandidate(
            candidate_id=place_refs[place.local_ref],
            normalized_name=place.normalized_name,
            display_name=place.display_name,
            aliases=place.aliases,
            status=CandidateStatus.PENDING,
            scene_id=chunk.scene_id,
            scene_revision=chunk.manuscript_revision,
            evidence=_translate_evidence(chunk, place.evidence),
        )
        for place in extraction.places
    )

    relationship_events = tuple(
        _translate_relationship_event(
            chunk,
            scene_sequence,
            event,
            entity_refs,
            place_refs,
            known_entity_keys,
            known_place_keys,
        )
        for event in extraction.relationship_events
    )
    location_events = tuple(
        _translate_location_event(
            chunk,
            scene_sequence,
            event,
            entity_refs,
            place_refs,
            known_entity_keys,
            known_place_keys,
        )
        for event in extraction.location_events
    )

    return ChunkAnalysis(
        schema_version=CHUNK_ANALYSIS_SCHEMA_VERSION,
        chunk_id=chunk.chunk_id,
        chunk_ordinal=chunk.ordinal,
        chunk_start=chunk.start_offset,
        chunk_end=chunk.end_offset,
        source_text=chunk.text,
        scene_id=chunk.scene_id,
        scene_revision=chunk.manuscript_revision,
        summary=_normalize_whitespace(extraction.summary),
        entities=entities,
        places=places,
        relationship_events=relationship_events,
        location_events=location_events,
    )


def _build_local_ids[
    Extracted: ExtractedEntity | ExtractedPlace,
](
    chunk: SceneChunk,
    kind: str,
    extracted_values: tuple[Extracted, ...],
    semantic_fields: Callable[[Extracted], tuple[str, ...]],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for extracted in extracted_values:
        if not extracted.local_ref.strip():
            raise ExtractionTranslationError(f"blank local reference for {kind}")
        if extracted.local_ref in result:
            raise ExtractionTranslationError(f"ambiguous local reference for {kind}")
        evidence = _translate_evidence(chunk, extracted.evidence)
        result[extracted.local_ref] = _stable_id(
            chunk,
            kind,
            semantic_fields(extracted),
            evidence,
        )
    return result


def _translate_relationship_event(
    chunk: SceneChunk,
    scene_sequence: int,
    event: ExtractedRelationshipEvent,
    entity_refs: dict[str, str],
    place_refs: dict[str, str],
    known_entity_keys: set[str],
    known_place_keys: set[str],
) -> RelationshipEventCandidate:
    _validate_confidence(event.confidence)
    subject_key = _resolve_reference(
        event.subject_ref,
        "entity",
        entity_refs,
        place_refs,
        known_entity_keys,
        known_place_keys,
    )
    object_key = _resolve_reference(
        event.object_ref,
        "entity",
        entity_refs,
        place_refs,
        known_entity_keys,
        known_place_keys,
    )
    evidence = _translate_evidence(chunk, event.evidence)
    return RelationshipEventCandidate(
        event_id=_stable_id(
            chunk,
            "relationship-event",
            (
                subject_key,
                object_key,
                event.category,
                event.description,
                _confidence_semantic_value(event.confidence),
            ),
            evidence,
        ),
        subject_key=subject_key,
        object_key=object_key,
        category=event.category,
        description=event.description,
        status=CandidateStatus.PENDING,
        scene_id=chunk.scene_id,
        scene_revision=chunk.manuscript_revision,
        scene_sequence=scene_sequence,
        confidence=event.confidence,
        evidence=evidence,
    )


def _translate_location_event(
    chunk: SceneChunk,
    scene_sequence: int,
    event: ExtractedLocationEvent,
    entity_refs: dict[str, str],
    place_refs: dict[str, str],
    known_entity_keys: set[str],
    known_place_keys: set[str],
) -> LocationEventCandidate:
    _validate_confidence(event.confidence)
    character_key = _resolve_reference(
        event.character_ref,
        "entity",
        entity_refs,
        place_refs,
        known_entity_keys,
        known_place_keys,
    )
    place_key = _resolve_reference(
        event.place_ref,
        "place",
        place_refs,
        entity_refs,
        known_place_keys,
        known_entity_keys,
    )
    evidence = _translate_evidence(chunk, event.evidence)
    return LocationEventCandidate(
        event_id=_stable_id(
            chunk,
            "location-event",
            (
                character_key,
                place_key,
                event.event_type.value,
                event.description,
                _confidence_semantic_value(event.confidence),
            ),
            evidence,
        ),
        character_key=character_key,
        place_key=place_key,
        event_type=event.event_type,
        description=event.description,
        status=CandidateStatus.PENDING,
        scene_id=chunk.scene_id,
        scene_revision=chunk.manuscript_revision,
        scene_sequence=scene_sequence,
        confidence=event.confidence,
        evidence=evidence,
    )


def _resolve_reference(
    reference: str,
    expected_kind: str,
    local_expected: dict[str, str],
    local_other: dict[str, str],
    known_expected: set[str],
    known_other: set[str],
) -> str:
    if reference in local_expected:
        return local_expected[reference]
    if reference in known_expected and reference in known_other:
        raise ExtractionTranslationError(f"ambiguous {expected_kind} reference: {reference}")
    if reference in known_expected:
        return reference
    if reference in local_other or reference in known_other:
        raise ExtractionTranslationError(f"wrong-kind {expected_kind} reference: {reference}")
    raise ExtractionTranslationError(f"unknown {expected_kind} reference: {reference}")


def _translate_evidence(
    chunk: SceneChunk,
    evidence_values: tuple[RelativeEvidence, ...],
) -> tuple[Evidence, ...]:
    translated: list[Evidence] = []
    for evidence in evidence_values:
        if not 0 <= evidence.start_offset < evidence.end_offset <= len(chunk.text):
            raise ExtractionTranslationError("evidence bounds must be within the chunk")
        if chunk.text[evidence.start_offset : evidence.end_offset] != evidence.text:
            raise ExtractionTranslationError("evidence text must match the chunk source")
        translated.append(
            Evidence(
                chunk_id=chunk.chunk_id,
                scene_id=chunk.scene_id,
                scene_revision=chunk.manuscript_revision,
                start_offset=chunk.start_offset + evidence.start_offset,
                end_offset=chunk.start_offset + evidence.end_offset,
                text=evidence.text,
            )
        )
    return tuple(translated)


def _validate_confidence(confidence: float) -> None:
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ExtractionTranslationError("confidence must be finite and between 0.0 and 1.0")


def _confidence_semantic_value(confidence: float) -> str:
    return str(0.0 if confidence == 0.0 else confidence)


def _stable_id(
    chunk: SceneChunk,
    kind: str,
    semantic_fields: tuple[str, ...],
    evidence: tuple[Evidence, ...],
) -> str:
    payload = [
        CHUNK_ANALYSIS_SCHEMA_VERSION,
        chunk.scene_id,
        chunk.manuscript_revision,
        kind,
        [_normalize_text(value) for value in semantic_fields],
        sorted([item.start_offset, item.end_offset] for item in evidence),
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _normalize_text(value: str) -> str:
    return _normalize_whitespace(value).casefold()
