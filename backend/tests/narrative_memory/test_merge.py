from dataclasses import replace

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
    ProjectKnowledgeGraphSnapshot,
    Relation,
    SceneAnalysis,
    UnresolvedReference,
)

from apps.narrative_memory.service.merge import (
    assemble_scene_graph,
    rebuild_project_graph,
)
from apps.narrative_memory.service.models import SceneGraphRecord


def test_scene_merge_combines_clear_character_identity_across_chunks() -> None:
    analysis = _analysis(
        chunks=(
            _chunk(
                ordinal=1,
                text="한서윤은 문을 닫았다.",
                characters=(
                    _character(
                        "character_001",
                        "한서윤",
                        aliases=("서윤",),
                        first_mention="한서윤",
                    ),
                ),
            ),
            _chunk(
                ordinal=0,
                text="서윤은 온실에 들어왔다.",
                characters=(
                    _character(
                        "character_001",
                        "서윤",
                        aliases=("한서윤",),
                        first_mention="서윤",
                    ),
                ),
            ),
        )
    )

    scene = assemble_scene_graph(analysis, _empty_project())

    assert len(scene.graph.entities.characters) == 1
    character = scene.graph.entities.characters[0]
    assert character.id == "character_001"
    assert character.canonical_name == "서윤"
    assert character.aliases == ("한서윤",)


def test_scene_merge_reuses_existing_ids_and_rewrites_every_reference() -> None:
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=7,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        entities=Entities(
            characters=(
                _character(
                    "character_007",
                    "서윤",
                    aliases=("한서윤",),
                    first_mention="서윤",
                ),
            ),
            locations=(_location("location_009", "정원", first_mention="정원"),),
            events=(
                _event(
                    "event_009",
                    participant_ids=("character_007",),
                    location_ids=("location_009",),
                ),
            ),
        ),
    )
    unresolved = UnresolvedReference(
        expression="그곳",
        possible_entity_ids=("location_002", "character_002", "event_001"),
        reason="표현이 모호함",
    )
    chunk = _chunk(
        ordinal=0,
        text="한서윤과 민준은 온실 안쪽 방에 도착했다. 그녀는 그곳과 그 일을 둘러봤다.",
        characters=(
            _character("character_001", "한서윤", first_mention="한서윤"),
            _character("character_002", "민준", first_mention="민준"),
        ),
        locations=(
            _location("location_001", "온실", first_mention="온실"),
            _location(
                "location_002",
                "방",
                first_mention="방",
                parent_location_id="location_001",
            ),
        ),
        events=(
            _event(
                "event_001",
                participant_ids=("character_001", "character_002"),
                location_ids=("location_001",),
            ),
        ),
        relations=(
            _relation(
                "relation_001",
                source_id="character_001",
                target_id="character_002",
                start_event_id="event_001",
                end_event_id="event_009",
            ),
        ),
        movements=(
            Movement(
                character_id="character_001",
                from_location_id="location_001",
                to_location_id="location_002",
                movement_type="ARRIVAL",
                event_id="event_001",
                time_expression=None,
                sequence=0,
                evidence="도착했다",
                confidence=0.9,
            ),
        ),
        coreferences=(
            Coreference(
                expression="그녀",
                resolved_entity_id="character_001",
                evidence="그녀",
                confidence=0.9,
            ),
            Coreference(
                expression="그곳",
                resolved_entity_id="location_002",
                evidence="그곳",
                confidence=0.9,
            ),
            Coreference(
                expression="그 일",
                resolved_entity_id="event_001",
                evidence="그 일",
                confidence=0.9,
            ),
        ),
        unresolved_references=(unresolved, unresolved),
        contradictions=(
            Contradiction(
                subject_id="character_001",
                field_or_relation="status",
                existing_value="missing",
                new_value="alive",
                evidence="한서윤",
                possible_explanation="",
            ),
        ),
    )

    graph = assemble_scene_graph(_analysis(chunks=(chunk,)), existing).graph

    assert [item.id for item in graph.entities.characters] == [
        "character_007",
        "character_008",
    ]
    events = {item.id: item for item in graph.entities.events}
    assert tuple(events) == ("event_009", "event_010")
    assert events["event_009"] == existing.entities.events[0]
    assert events["event_010"].participant_ids == ("character_007", "character_008")
    assert [item.id for item in graph.entities.locations] == [
        "location_009",
        "location_010",
        "location_011",
    ]
    assert graph.entities.locations[0] == existing.entities.locations[0]
    assert graph.entities.locations[2].parent_location_id == "location_010"
    assert events["event_010"].location_ids == ("location_010",)
    assert graph.relations[0].source_id == "character_007"
    assert graph.relations[0].target_id == "character_008"
    assert graph.relations[0].start_event_id == "event_010"
    assert graph.relations[0].end_event_id == "event_009"
    assert graph.movements[0].character_id == "character_007"
    assert graph.movements[0].from_location_id == "location_010"
    assert graph.movements[0].to_location_id == "location_011"
    assert graph.movements[0].event_id == "event_010"
    assert [item.resolved_entity_id for item in graph.coreferences] == [
        "character_007",
        "location_011",
        "event_010",
    ]
    assert graph.unresolved_references == (
        UnresolvedReference(
            expression="그곳",
            possible_entity_ids=("character_008", "event_010", "location_011"),
            reason="표현이 모호함",
        ),
    )
    assert graph.contradictions[0].subject_id == "character_007"


def test_scene_merge_does_not_reuse_ambiguous_existing_name() -> None:
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=4,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        entities=Entities(
            characters=(
                _character("character_004", "김민준", aliases=("민준",), first_mention="김민준"),
                _character("character_009", "이민준", aliases=("민준",), first_mention="이민준"),
            )
        ),
    )
    analysis = _analysis(
        chunks=(
            _chunk(
                ordinal=0,
                text="민준이 들어왔다.",
                characters=(_character("character_001", "민준", first_mention="민준"),),
            ),
        )
    )

    graph = assemble_scene_graph(analysis, existing).graph

    assert [item.id for item in graph.entities.characters] == ["character_010"]


def test_scene_merge_treats_colliding_character_id_as_local_declaration() -> None:
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=1,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        entities=Entities(
            characters=(_character("character_001", "기존 인물", first_mention="기존 인물"),)
        ),
    )
    chunk = _chunk(
        ordinal=0,
        text="새 인물이 등장했다.",
        characters=(_character("character_001", "새 인물", first_mention="새 인물"),),
        coreferences=(
            Coreference(
                expression="그",
                resolved_entity_id="character_001",
                evidence="새 인물",
                confidence=0.9,
            ),
        ),
    )

    graph = assemble_scene_graph(_analysis(chunks=(chunk,)), existing).graph

    assert [item.id for item in graph.entities.characters] == ["character_002"]
    assert graph.coreferences[0].resolved_entity_id == "character_002"


def test_scene_merge_treats_colliding_location_id_as_local_declaration() -> None:
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=1,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        entities=Entities(
            locations=(_location("location_001", "기존 장소", first_mention="기존 장소"),)
        ),
    )
    chunk = _chunk(
        ordinal=0,
        text="새 장소가 드러났다.",
        locations=(_location("location_001", "새 장소", first_mention="새 장소"),),
    )

    graph = assemble_scene_graph(_analysis(chunks=(chunk,)), existing).graph

    assert [item.id for item in graph.entities.locations] == ["location_002"]


def test_scene_merge_treats_colliding_event_id_as_local_declaration() -> None:
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=1,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        entities=Entities(events=(_event("event_001"),)),
    )
    chunk = _chunk(
        ordinal=0,
        text="다시 도착했다.",
        events=(_event("event_001"),),
    )

    graph = assemble_scene_graph(_analysis(chunks=(chunk,)), existing).graph

    assert [item.id for item in graph.entities.events] == ["event_002"]


def test_scene_merge_treats_colliding_relation_id_as_local_declaration() -> None:
    first = _character("character_010", "서윤", first_mention="서윤")
    second = _character("character_011", "민준", first_mention="민준")
    existing_relation = _relation(
        "relation_001",
        source_id=first.id,
        target_id=second.id,
    )
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=1,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        entities=Entities(characters=(first, second)),
        relations=(existing_relation,),
    )
    chunk = _chunk(
        ordinal=0,
        text="두 사람의 관계가 드러났다.",
        relations=(
            _relation(
                "relation_001",
                source_id=first.id,
                target_id=second.id,
                evidence="관계",
            ),
        ),
    )

    graph = assemble_scene_graph(_analysis(chunks=(chunk,)), existing).graph

    assert [item.id for item in graph.relations] == ["relation_002"]


def test_reused_character_and_location_remain_exact_canonical_objects_across_scenes() -> None:
    existing_character = _character(
        "character_007",
        "서윤",
        aliases=("한서윤",),
        first_mention="서윤",
    )
    existing_location = _location(
        "location_010",
        "홀",
        aliases=("대홀",),
        first_mention="홀",
    )
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=4,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        entities=Entities(
            characters=(existing_character,),
            locations=(existing_location,),
        ),
    )
    chunk = _chunk(
        ordinal=0,
        text="한서윤은 대홀에서 임시 부모 장소를 언급했다.",
        characters=(
            _character(
                "character_001",
                "한서윤",
                aliases=("새 별칭",),
                first_mention="한서윤",
            ),
        ),
        locations=(
            _location(
                "location_001",
                "대홀",
                aliases=("새 장소 별칭",),
                first_mention="대홀",
                parent_location_id="location_002",
            ),
            _location(
                "location_002",
                "임시 부모 장소",
                first_mention="임시 부모 장소",
            ),
        ),
    )
    first_scene = assemble_scene_graph(_analysis(chunks=(chunk,)), existing)
    second_analysis = _analysis(chunks=(chunk,)).model_copy(
        update={"scene_id": "scene-02", "scene_sequence": 5}
    )
    second_scene = assemble_scene_graph(second_analysis, existing)

    assert existing_character in first_scene.graph.entities.characters
    assert existing_character in second_scene.graph.entities.characters
    assert existing_location in first_scene.graph.entities.locations
    assert existing_location in second_scene.graph.entities.locations

    snapshot = rebuild_project_graph("project-01", 5, (second_scene, first_scene))

    assert snapshot.entities.characters == (existing_character,)
    assert snapshot.entities.locations.count(existing_location) == 1


def test_scene_merge_includes_only_referenced_existing_dependency_closure() -> None:
    character = _character("character_007", "서윤", first_mention="서윤")
    old_character = _character("character_099", "이전 인물", first_mention="이전 인물")
    parent = _location("location_006", "건물", first_mention="건물")
    location = _location(
        "location_007",
        "방",
        first_mention="방",
        parent_location_id=parent.id,
    )
    event = _event(
        "event_007",
        participant_ids=(character.id,),
        location_ids=(location.id,),
    )
    existing = ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=7,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        entities=Entities(
            characters=(character, old_character),
            locations=(parent, location),
            events=(event,),
        ),
    )
    chunk = _chunk(
        ordinal=0,
        text="관계와 이동, 그 일에 대한 변화가 드러났다.",
        relations=(
            _relation(
                "relation_001",
                source_id=character.id,
                target_id=location.id,
                start_event_id=event.id,
                end_event_id=event.id,
                evidence="관계",
            ),
        ),
        movements=(
            Movement(
                character_id=character.id,
                from_location_id=location.id,
                to_location_id=location.id,
                movement_type="MOVE",
                event_id=event.id,
                time_expression=None,
                sequence=0,
                evidence="이동",
                confidence=0.9,
            ),
        ),
        coreferences=(
            Coreference(
                expression="그 일",
                resolved_entity_id=event.id,
                evidence="그 일",
                confidence=0.9,
            ),
        ),
        unresolved_references=(
            UnresolvedReference(
                expression="그들",
                possible_entity_ids=(character.id, location.id, event.id),
                reason="복수 가능성",
            ),
        ),
        contradictions=(
            Contradiction(
                subject_id=location.id,
                field_or_relation="description",
                existing_value="이전",
                new_value="변화",
                evidence="변화",
                possible_explanation="",
            ),
        ),
    )

    scene = assemble_scene_graph(_analysis(chunks=(chunk,)), existing)

    assert scene.graph.entities.characters == (character,)
    assert scene.graph.entities.locations == (parent, location)
    assert scene.graph.entities.events == (event,)
    assert old_character not in scene.graph.entities.characters
    assert scene.graph.relations[0].start_event_id == event.id
    assert scene.graph.relations[0].end_event_id == event.id
    assert scene.graph.movements[0].event_id == event.id
    assert scene.graph.coreferences[0].resolved_entity_id == event.id
    assert scene.graph.unresolved_references[0].possible_entity_ids == (
        character.id,
        event.id,
        location.id,
    )
    assert scene.graph.contradictions[0].subject_id == location.id

    snapshot = rebuild_project_graph("project-01", 8, (scene,))

    assert snapshot.entities == scene.graph.entities


def test_scene_merge_separates_ambiguous_same_name_and_preserves_possible_same_as() -> None:
    chunk = _chunk(
        ordinal=0,
        text="첫 번째 민준이 웃었다. 두 번째 민준은 고개를 돌렸다.",
        characters=(
            _character("character_010", "민준", first_mention="첫 번째 민준"),
            _character("character_020", "민준", first_mention="두 번째 민준"),
        ),
        relations=(
            _relation(
                "relation_009",
                source_id="character_010",
                target_id="character_020",
                relation_type="POSSIBLE_SAME_AS",
                state="uncertain",
                evidence="민준",
            ),
        ),
    )

    graph = assemble_scene_graph(_analysis(chunks=(chunk,)), _empty_project()).graph

    assert [item.id for item in graph.entities.characters] == [
        "character_001",
        "character_002",
    ]
    assert graph.relations[0].relation_type == "POSSIBLE_SAME_AS"
    assert graph.relations[0].source_id == "character_001"
    assert graph.relations[0].target_id == "character_002"


def test_scene_merge_separates_ambiguous_same_name_locations() -> None:
    chunk = _chunk(
        ordinal=0,
        text="첫 번째 중앙역을 지나 두 번째 중앙역에 도착했다.",
        locations=(
            _location("location_010", "중앙역", first_mention="첫 번째 중앙역"),
            _location("location_020", "중앙역", first_mention="두 번째 중앙역"),
        ),
        relations=(
            _relation(
                "relation_001",
                source_id="location_010",
                target_id="location_020",
                relation_type="POSSIBLE_SAME_AS",
                state="uncertain",
                evidence="중앙역",
            ),
        ),
    )

    graph = assemble_scene_graph(_analysis(chunks=(chunk,)), _empty_project()).graph

    assert [item.id for item in graph.entities.locations] == ["location_001", "location_002"]
    assert graph.relations[0].relation_type == "POSSIBLE_SAME_AS"
    assert graph.relations[0].source_id == "location_001"
    assert graph.relations[0].target_id == "location_002"


def test_scene_merge_keys_local_ids_by_chunk_ordinal() -> None:
    chunks = (
        _chunk(
            ordinal=0,
            text="서윤이 말했다.",
            characters=(_character("character_001", "서윤", first_mention="서윤"),),
            coreferences=(
                Coreference(
                    expression="그녀",
                    resolved_entity_id="character_001",
                    evidence="서윤",
                    confidence=0.9,
                ),
            ),
        ),
        _chunk(
            ordinal=1,
            text="민준이 답했다.",
            characters=(_character("character_001", "민준", first_mention="민준"),),
            coreferences=(
                Coreference(
                    expression="그",
                    resolved_entity_id="character_001",
                    evidence="민준",
                    confidence=0.9,
                ),
            ),
        ),
    )

    graph = assemble_scene_graph(_analysis(chunks=chunks), _empty_project()).graph

    assert [item.id for item in graph.entities.characters] == [
        "character_001",
        "character_002",
    ]
    assert [item.resolved_entity_id for item in graph.coreferences] == [
        "character_001",
        "character_002",
    ]


def test_scene_merge_combines_document_sentences_and_narrative_time() -> None:
    analysis = _analysis(
        chunks=(
            _chunk(
                ordinal=2,
                text="셋",
                summary="셋째다. 넷째다. 다섯째다.",
                narrative_time="present",
            ),
            _chunk(ordinal=0, text="하나", summary="첫째다. 둘째다.", narrative_time="present"),
            _chunk(ordinal=1, text="둘", summary="둘째다. 셋째다.", narrative_time="flashback"),
        )
    )

    document = assemble_scene_graph(analysis, _empty_project()).graph.document

    assert document.summary == "첫째다. 둘째다. 셋째다. 넷째다."
    assert document.narrative_time == "mixed"


def test_scene_merge_is_deterministic_for_chunk_and_collection_order() -> None:
    first = _chunk(
        ordinal=0,
        text="서윤과 민준이 만났다.",
        characters=(
            _character("character_002", "민준", first_mention="민준"),
            _character("character_001", "서윤", first_mention="서윤"),
        ),
        relations=(
            _relation(
                "relation_002",
                source_id="character_002",
                target_id="character_001",
                state="ended",
                evidence="만났다",
            ),
            _relation(
                "relation_001",
                source_id="character_001",
                target_id="character_002",
                state="active",
                evidence="만났다",
            ),
        ),
    )
    second = _chunk(
        ordinal=1,
        text="온실에 도착했다.",
        locations=(_location("location_001", "온실", first_mention="온실"),),
    )
    reversed_first = first.model_copy(
        update={
            "extraction": first.extraction.model_copy(
                update={
                    "entities": first.extraction.entities.model_copy(
                        update={"characters": tuple(reversed(first.extraction.entities.characters))}
                    ),
                    "relations": tuple(reversed(first.extraction.relations)),
                }
            )
        }
    )

    forward = assemble_scene_graph(_analysis(chunks=(first, second)), _empty_project())
    reversed_input = assemble_scene_graph(
        _analysis(chunks=(second, reversed_first)),
        _empty_project(),
    )

    assert reversed_input == forward


def test_scene_merge_canonicalizes_nested_reference_collection_order() -> None:
    chunk = _chunk(
        ordinal=0,
        text="서윤과 민준이 온실과 정원을 거쳐 도착했다.",
        characters=(
            _character("character_001", "서윤", first_mention="서윤"),
            _character("character_002", "민준", first_mention="민준"),
        ),
        locations=(
            _location("location_001", "온실", first_mention="온실"),
            _location("location_002", "정원", first_mention="정원"),
        ),
        events=(
            _event(
                "event_001",
                participant_ids=("character_002", "character_001"),
                location_ids=("location_002", "location_001"),
            ),
        ),
        movements=(
            Movement(
                character_id="character_001",
                from_location_id=None,
                to_location_id="location_002",
                movement_type="ARRIVAL",
                event_id="event_001",
                time_expression=None,
                sequence=0,
                evidence="도착했다",
                confidence=0.9,
            ),
            Movement(
                character_id="character_001",
                from_location_id=None,
                to_location_id="location_001",
                movement_type="ARRIVAL",
                event_id="event_001",
                time_expression=None,
                sequence=0,
                evidence="도착했다",
                confidence=0.9,
            ),
        ),
        unresolved_references=(
            UnresolvedReference(
                expression="그들",
                possible_entity_ids=("location_002", "character_001"),
                reason="복수 대상",
            ),
        ),
    )
    extraction = chunk.extraction
    event = extraction.entities.events[0]
    unresolved = extraction.unresolved_references[0]
    reversed_chunk = chunk.model_copy(
        update={
            "extraction": extraction.model_copy(
                update={
                    "entities": extraction.entities.model_copy(
                        update={
                            "events": (
                                event.model_copy(
                                    update={
                                        "participant_ids": tuple(reversed(event.participant_ids)),
                                        "location_ids": tuple(reversed(event.location_ids)),
                                    }
                                ),
                            )
                        }
                    ),
                    "unresolved_references": (
                        unresolved.model_copy(
                            update={
                                "possible_entity_ids": tuple(
                                    reversed(unresolved.possible_entity_ids)
                                )
                            }
                        ),
                    ),
                    "movements": tuple(reversed(extraction.movements)),
                }
            )
        }
    )

    forward = assemble_scene_graph(_analysis(chunks=(chunk,)), _empty_project())
    reversed_input = assemble_scene_graph(
        _analysis(chunks=(reversed_chunk,)),
        _empty_project(),
    )

    assert reversed_input == forward


def test_rebuild_project_graph_replaces_reanalyzed_scene_and_preserves_other_scene() -> None:
    old_scene = _scene_record("scene-01", revision=1, sequence=0, character_name="이전 인물")
    replacement = _scene_record("scene-01", revision=2, sequence=1, character_name="새 인물")
    other = _scene_record("scene-02", revision=3, sequence=0, character_name="다른 인물")

    snapshot = rebuild_project_graph(
        "project-01",
        9,
        (replacement, old_scene, other),
    )

    assert snapshot.snapshot_version == 9
    assert [document.chapter_id for document in snapshot.documents] == ["scene-02", "scene-01"]
    assert [character.canonical_name for character in snapshot.entities.characters] == [
        "다른 인물",
        "새 인물",
    ]
    assert "이전 인물" not in {item.canonical_name for item in snapshot.entities.characters}
    assert snapshot == rebuild_project_graph(
        "project-01",
        9,
        (other, old_scene, replacement),
    )


def test_rebuild_project_graph_preserves_active_and_ended_relation_records() -> None:
    scene = _scene_record("scene-01", revision=2, sequence=0, character_name="서윤")
    character = scene.graph.entities.characters[0]
    other_character = _character("character_002", "민준", first_mention="민준")
    graph = scene.graph.model_copy(
        update={
            "entities": scene.graph.entities.model_copy(
                update={"characters": (character, other_character)}
            ),
            "relations": (
                _relation(
                    "relation_001",
                    source_id=character.id,
                    target_id=other_character.id,
                    state="active",
                ),
                _relation(
                    "relation_002",
                    source_id=character.id,
                    target_id=other_character.id,
                    state="ended",
                ),
            ),
        }
    )

    snapshot = rebuild_project_graph(
        "project-01",
        3,
        (replace(scene, graph=graph),),
    )

    assert [relation.state for relation in snapshot.relations] == ["active", "ended"]


def _analysis(*, chunks: tuple[AnalyzedChunk, ...]) -> SceneAnalysis:
    return SceneAnalysis(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=2,
        scene_sequence=4,
        source_snapshot_version=0,
        chunks=chunks,
    )


def _chunk(
    *,
    ordinal: int,
    text: str,
    summary: str = "장면 요약.",
    narrative_time: str = "present",
    characters: tuple[Character, ...] = (),
    locations: tuple[Location, ...] = (),
    events: tuple[Event, ...] = (),
    relations: tuple[Relation, ...] = (),
    movements: tuple[Movement, ...] = (),
    coreferences: tuple[Coreference, ...] = (),
    unresolved_references: tuple[UnresolvedReference, ...] = (),
    contradictions: tuple[Contradiction, ...] = (),
) -> AnalyzedChunk:
    return AnalyzedChunk(
        chunk_id=f"scene-01:r2:{ordinal:04d}",
        ordinal=ordinal,
        start_offset=ordinal * 250,
        end_offset=ordinal * 250 + max(len(text), 1),
        text=text,
        extraction=KnowledgeGraphOutput(
            document=Document(
                chapter_id="scene-01",
                summary=summary,
                narrative_time=narrative_time,
            ),
            entities=Entities(characters=characters, locations=locations, events=events),
            relations=relations,
            movements=movements,
            coreferences=coreferences,
            unresolved_references=unresolved_references,
            contradictions=contradictions,
        ),
    )


def _character(
    character_id: str,
    canonical_name: str,
    *,
    aliases: tuple[str, ...] = (),
    first_mention: str,
) -> Character:
    return Character(
        id=character_id,
        canonical_name=canonical_name,
        aliases=aliases,
        description="",
        gender="unknown",
        age=None,
        occupation=None,
        affiliation=None,
        status="unknown",
        first_mention=first_mention,
        confidence=0.9,
    )


def _location(
    location_id: str,
    canonical_name: str,
    *,
    aliases: tuple[str, ...] = (),
    first_mention: str,
    parent_location_id: str | None = None,
) -> Location:
    return Location(
        id=location_id,
        canonical_name=canonical_name,
        aliases=aliases,
        location_type="building",
        parent_location_id=parent_location_id,
        description="",
        first_mention=first_mention,
        confidence=0.9,
    )


def _event(
    event_id: str,
    *,
    participant_ids: tuple[str, ...] = (),
    location_ids: tuple[str, ...] = (),
) -> Event:
    return Event(
        id=event_id,
        event_type="ARRIVAL",
        name="도착",
        summary="온실에 도착했다.",
        participant_ids=participant_ids,
        location_ids=location_ids,
        time_expression=None,
        narrative_time="present",
        sequence=0,
        evidence="도착했다",
        confidence=0.9,
    )


def _relation(
    relation_id: str,
    *,
    source_id: str,
    target_id: str,
    relation_type: str = "KNOWS",
    state: str = "active",
    start_event_id: str | None = None,
    end_event_id: str | None = None,
    evidence: str = "관계",
) -> Relation:
    return Relation(
        id=relation_id,
        source_id=source_id,
        relation_type=relation_type,
        target_id=target_id,
        state=state,
        directed=True,
        start_event_id=start_event_id,
        end_event_id=end_event_id,
        time_expression=None,
        scene_sequence=0,
        evidence=evidence,
        inference=False,
        confidence=0.9,
    )


def _empty_project() -> ProjectKnowledgeGraphSnapshot:
    return ProjectKnowledgeGraphSnapshot.empty("project-01")


def _scene_record(
    scene_id: str,
    *,
    revision: int,
    sequence: int,
    character_name: str,
) -> SceneGraphRecord:
    suffix = int(scene_id.rsplit("-", maxsplit=1)[-1])
    character = _character(
        f"character_{revision * 100 + suffix:03d}",
        character_name,
        first_mention=character_name,
    )
    graph = KnowledgeGraphOutput(
        document=Document(chapter_id=scene_id, summary=character_name, narrative_time="present"),
        entities=Entities(characters=(character,)),
    )
    return SceneGraphRecord(
        project_id="project-01",
        scene_id=scene_id,
        scene_revision=revision,
        scene_sequence=sequence,
        graph=graph,
    )
