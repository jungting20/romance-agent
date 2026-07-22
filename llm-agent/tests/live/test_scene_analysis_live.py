import asyncio

import pytest

from narrative_analysis_agent import SceneAnalysisRequest
from narrative_analysis_agent.models import KnowledgeGraphOutput

pytestmark = pytest.mark.live


def _assert_confidence_and_evidence(output: KnowledgeGraphOutput, chunk_text: str) -> None:
    for character in output.entities.characters:
        assert character.confidence >= 0.8
        assert not character.first_mention or character.first_mention in chunk_text
    for location in output.entities.locations:
        assert location.confidence >= 0.8
        assert not location.first_mention or location.first_mention in chunk_text
    for record in (
        *output.entities.events,
        *output.relations,
        *output.movements,
        *output.coreferences,
    ):
        assert record.confidence >= 0.8
        assert not record.evidence or record.evidence in chunk_text
    for contradiction in output.contradictions:
        assert not contradiction.evidence or contradiction.evidence in chunk_text


def _assert_references_are_known(output: KnowledgeGraphOutput) -> None:
    characters = {item.id for item in output.entities.characters}
    locations = {item.id for item in output.entities.locations}
    events = {item.id for item in output.entities.events}
    entities = characters | locations | events

    for event in output.entities.events:
        assert set(event.participant_ids) <= characters
        assert set(event.location_ids) <= locations
    for relation in output.relations:
        assert relation.source_id in entities
        assert relation.target_id in entities
        assert relation.start_event_id is None or relation.start_event_id in events
        assert relation.end_event_id is None or relation.end_event_id in events
    for movement in output.movements:
        assert movement.character_id in characters
        assert movement.from_location_id is None or movement.from_location_id in locations
        assert movement.to_location_id is None or movement.to_location_id in locations
        assert movement.event_id is None or movement.event_id in events
    for coreference in output.coreferences:
        assert coreference.resolved_entity_id in entities
    for unresolved in output.unresolved_references:
        assert set(unresolved.possible_entity_ids) <= entities
    for contradiction in output.contradictions:
        assert contradiction.subject_id in entities


def test_live_scene_analysis_has_grounded_graph_collections(
    live_agent,
    scene_request: SceneAnalysisRequest,
) -> None:
    analysis = asyncio.run(live_agent.analyze_scene(scene_request))

    assert analysis.chunks
    for chunk in analysis.chunks:
        output = chunk.extraction
        assert isinstance(output.entities.characters, tuple)
        assert isinstance(output.entities.locations, tuple)
        assert isinstance(output.entities.events, tuple)
        assert isinstance(output.relations, tuple)
        assert isinstance(output.movements, tuple)
        assert isinstance(output.coreferences, tuple)
        assert isinstance(output.unresolved_references, tuple)
        assert isinstance(output.contradictions, tuple)
        _assert_confidence_and_evidence(output, chunk.text)
        _assert_references_are_known(output)
