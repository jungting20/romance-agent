import hashlib
import json
import sqlite3
import stat
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from narrative_analysis_agent import ProjectKnowledgeGraphSnapshot
from narrative_analysis_agent.models import (
    Character,
    Contradiction,
    Coreference,
    Document,
    Entities,
    Event,
    KnowledgeGraphOutput,
    Location,
    Movement,
    Relation,
    UnresolvedReference,
)

from apps.narrative_memory.repository.snapshot_repository import (
    SnapshotCorruptionError,
    SnapshotVersionConflict,
)
from apps.narrative_memory.repository.sqlite_snapshot_repository import (
    SQLiteSnapshotRepository,
)
from apps.narrative_memory.service.models import SceneGraphRecord
from apps.narrative_memory.service.snapshot_codec import encode_project_snapshot


def test_initialize_creates_v2_snapshot_tables(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)

    repository.initialize()

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        scene_columns = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(scene_knowledge_graphs)")
        )
    assert {
        "scene_knowledge_graphs",
        "project_snapshots",
        "current_project_snapshots",
    } <= tables
    assert scene_columns == (
        "project_id",
        "scene_id",
        "scene_revision",
        "scene_sequence",
        "content_hash",
        "payload",
        "updated_at",
    )


def test_repository_starts_without_scene_or_current_snapshot(tmp_path: Path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()

    assert repository.get_scene_graphs("missing-project") == ()
    assert repository.get_current("missing-project") is None


def test_commit_scene_writes_scene_and_project_atomically(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    scene = scene_record("project-01", "scene-01", revision=1)
    snapshot = project_snapshot("project-01", version=0, scenes=(scene,))
    payload = encode_project_snapshot(snapshot)

    stored = repository.commit_scene(None, scene, snapshot)

    assert stored.snapshot == snapshot
    assert stored.payload == payload
    assert stored.content_hash == content_hash(payload)
    assert repository.get_scene_graphs("project-01") == (scene,)
    assert repository.get_current("project-01") == stored
    with sqlite3.connect(path) as connection:
        scene_row = connection.execute(
            """
            SELECT scene_revision, scene_sequence, content_hash, payload, updated_at
            FROM scene_knowledge_graphs
            WHERE project_id = ? AND scene_id = ?
            """,
            ("project-01", "scene-01"),
        ).fetchone()
        project_row = connection.execute(
            """
            SELECT schema_version, content_hash, payload, created_at
            FROM project_snapshots
            WHERE project_id = ? AND snapshot_version = ?
            """,
            ("project-01", 0),
        ).fetchone()
    assert scene_row is not None
    assert scene_row[:2] == (1, 0)
    assert scene_row[2] == content_hash(bytes(scene_row[3]))
    assert datetime.fromisoformat(scene_row[4]).tzinfo == UTC
    assert project_row is not None
    assert project_row[:3] == (snapshot.schema_version, content_hash(payload), payload)
    assert datetime.fromisoformat(project_row[3]).tzinfo == UTC


def test_commit_scene_replaces_scene_and_preserves_project_history(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    original = scene_record("project-01", "scene-01", revision=1, summary="초고")
    revised = scene_record("project-01", "scene-01", revision=2, summary="개정고")
    initial = project_snapshot("project-01", version=0, scenes=(original,))
    current = project_snapshot("project-01", version=1, scenes=(revised,))

    repository.commit_scene(None, original, initial)
    repository.commit_scene(0, revised, current)

    assert repository.get_scene_graphs("project-01") == (revised,)
    assert repository.get_current("project-01").snapshot == current  # type: ignore[union-attr]
    with sqlite3.connect(path) as connection:
        versions = connection.execute(
            """
            SELECT snapshot_version, payload
            FROM project_snapshots
            WHERE project_id = ?
            ORDER BY snapshot_version
            """,
            ("project-01",),
        ).fetchall()
    assert versions == [
        (0, encode_project_snapshot(initial)),
        (1, encode_project_snapshot(current)),
    ]


def test_get_scene_graphs_orders_by_scene_sequence_then_id(tmp_path: Path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    later = scene_record("project-01", "scene-02", revision=1, sequence=2)
    earlier_b = scene_record("project-01", "scene-03", revision=1, sequence=1)
    earlier_a = scene_record("project-01", "scene-01", revision=1, sequence=1)

    repository.commit_scene(
        None,
        later,
        project_snapshot("project-01", version=0, scenes=(later,)),
    )
    repository.commit_scene(
        0,
        earlier_b,
        project_snapshot("project-01", version=1, scenes=(earlier_b, later)),
    )
    repository.commit_scene(
        1,
        earlier_a,
        project_snapshot("project-01", version=2, scenes=(earlier_a, earlier_b, later)),
    )

    assert repository.get_scene_graphs("project-01") == (earlier_a, earlier_b, later)


@pytest.mark.parametrize("expected_version", [None, 1])
def test_commit_scene_rejects_any_expected_version_mismatch(
    tmp_path: Path,
    expected_version: int | None,
) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    original = scene_record("project-01", "scene-01", revision=1)
    repository.commit_scene(
        None,
        original,
        project_snapshot("project-01", version=0, scenes=(original,)),
    )
    added = scene_record("project-01", "scene-02", revision=1, sequence=1)

    with pytest.raises(SnapshotVersionConflict, match="expected.*current"):
        repository.commit_scene(
            expected_version,
            added,
            project_snapshot("project-01", version=1, scenes=(original, added)),
        )

    assert repository.get_scene_graphs("project-01") == (original,)
    assert repository.get_current("project-01").snapshot.snapshot_version == 0  # type: ignore[union-attr]


@pytest.mark.parametrize("revision", [0, 1])
def test_commit_scene_rejects_non_increasing_scene_revision_and_rolls_back(
    tmp_path: Path,
    revision: int,
) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    original = scene_record("project-01", "scene-01", revision=1, summary="원본")
    initial = project_snapshot("project-01", version=0, scenes=(original,))
    repository.commit_scene(None, original, initial)
    stale = scene_record("project-01", "scene-01", revision=revision, summary="오래된 결과")

    with pytest.raises(SnapshotVersionConflict, match="scene revision"):
        repository.commit_scene(
            0,
            stale,
            project_snapshot("project-01", version=1, scenes=(stale,)),
        )

    assert repository.get_scene_graphs("project-01") == (original,)
    assert repository.get_current("project-01").snapshot == initial  # type: ignore[union-attr]
    with sqlite3.connect(path) as connection:
        project_count = connection.execute("SELECT COUNT(*) FROM project_snapshots").fetchone()
    assert project_count == (1,)


def test_commit_scene_rejects_invalid_next_snapshot_version_without_partial_write(
    tmp_path: Path,
) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    original = scene_record("project-01", "scene-01", revision=1)
    initial = project_snapshot("project-01", version=0, scenes=(original,))
    repository.commit_scene(None, original, initial)
    revised = scene_record("project-01", "scene-01", revision=2)

    with pytest.raises(ValueError, match="snapshot version"):
        repository.commit_scene(
            0,
            revised,
            project_snapshot("project-01", version=2, scenes=(revised,)),
        )

    assert repository.get_scene_graphs("project-01") == (original,)
    assert repository.get_current("project-01").snapshot == initial  # type: ignore[union-attr]


def test_commit_scene_rejects_cross_project_input_without_partial_write(tmp_path: Path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    scene = scene_record("project-01", "scene-01", revision=1)

    with pytest.raises(ValueError, match="project IDs"):
        repository.commit_scene(
            None,
            scene,
            project_snapshot("project-02", version=0, scenes=()),
        )

    assert repository.get_scene_graphs("project-01") == ()
    assert repository.get_current("project-01") is None
    assert repository.get_current("project-02") is None


@pytest.mark.parametrize("column", ["payload", "content_hash"])
def test_get_scene_graphs_rejects_scene_content_hash_corruption(
    tmp_path: Path,
    column: str,
) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    scene = scene_record("project-01", "scene-01", revision=1)
    repository.commit_scene(
        None,
        scene,
        project_snapshot("project-01", version=0, scenes=(scene,)),
    )
    with sqlite3.connect(path) as connection:
        value: bytes | str = b"{}\n" if column == "payload" else "sha256:" + "0" * 64
        connection.execute(
            f"UPDATE scene_knowledge_graphs SET {column} = ?",  # noqa: S608 - fixed parameters
            (value,),
        )

    with pytest.raises(SnapshotCorruptionError, match="scene.*content hash"):
        repository.get_scene_graphs("project-01")


def test_get_scene_graphs_rejects_scene_payload_that_matches_its_hash(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    scene = scene_record("project-01", "scene-01", revision=1)
    repository.commit_scene(
        None,
        scene,
        project_snapshot("project-01", version=0, scenes=(scene,)),
    )
    invalid_payload = b"{}\n"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE scene_knowledge_graphs SET payload = ?, content_hash = ?",
            (invalid_payload, content_hash(invalid_payload)),
        )

    with pytest.raises(SnapshotCorruptionError, match="scene.*payload"):
        repository.get_scene_graphs("project-01")


@pytest.mark.parametrize("collection", ["characters", "locations", "events", "relations"])
def test_commit_scene_rejects_duplicate_scene_graph_ids(
    tmp_path: Path,
    collection: str,
) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    scene = semantic_scene_record()
    invalid = scene_with_duplicate(scene, collection)

    with pytest.raises(ValueError, match="IDs must be unique"):
        repository.commit_scene(
            None,
            invalid,
            project_snapshot("project-01", version=0, scenes=(invalid,)),
        )

    assert repository.get_scene_graphs("project-01") == ()
    assert repository.get_current("project-01") is None


@pytest.mark.parametrize(
    ("path", "reference"),
    [
        ("location.parent_location_id", "character_001"),
        ("event.participant_ids", ("location_001",)),
        ("event.location_ids", ("character_001",)),
        ("relation.source_id", "relation_001"),
        ("relation.target_id", "character_999"),
        ("relation.start_event_id", "character_001"),
        ("relation.end_event_id", "event_999"),
        ("movement.character_id", "location_001"),
        ("movement.from_location_id", "character_001"),
        ("movement.to_location_id", "location_999"),
        ("movement.event_id", "location_001"),
        ("coreference.resolved_entity_id", "relation_001"),
        ("unresolved.possible_entity_ids", ("relation_001",)),
        ("contradiction.subject_id", "relation_001"),
    ],
)
def test_commit_scene_rejects_dangling_or_wrong_kind_scene_reference(
    tmp_path: Path,
    path: str,
    reference: object,
) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    scene = scene_with_reference(semantic_scene_record(), path, reference)

    with pytest.raises(ValueError, match="unknown|reference"):
        repository.commit_scene(
            None,
            scene,
            project_snapshot("project-01", version=0, scenes=(scene,)),
        )

    assert repository.get_scene_graphs("project-01") == ()
    assert repository.get_current("project-01") is None


@pytest.mark.parametrize(
    "corruption",
    [
        "duplicate",
        "wrong-kind",
        "dangling",
    ],
)
def test_get_scene_graphs_rejects_hash_valid_semantic_corruption(
    tmp_path: Path,
    corruption: str,
) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    scene = semantic_scene_record()
    repository.commit_scene(
        None,
        scene,
        project_snapshot("project-01", version=0, scenes=(scene,)),
    )
    if corruption == "duplicate":
        invalid = scene_with_duplicate(scene, "characters")
    elif corruption == "wrong-kind":
        invalid = scene_with_reference(scene, "relation.source_id", "relation_001")
    else:
        invalid = scene_with_reference(scene, "relation.target_id", "character_999")
    payload = scene_graph_payload(invalid.graph)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE scene_knowledge_graphs SET payload = ?, content_hash = ?",
            (payload, content_hash(payload)),
        )

    with pytest.raises(SnapshotCorruptionError, match="scene.*semantic"):
        repository.get_scene_graphs("project-01")


@pytest.mark.parametrize("column", ["payload", "content_hash"])
def test_get_current_rejects_project_content_hash_corruption(
    tmp_path: Path,
    column: str,
) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    scene = scene_record("project-01", "scene-01", revision=1)
    repository.commit_scene(
        None,
        scene,
        project_snapshot("project-01", version=0, scenes=(scene,)),
    )
    with sqlite3.connect(path) as connection:
        value: bytes | str = b"{}\n" if column == "payload" else "sha256:" + "0" * 64
        connection.execute(
            f"UPDATE project_snapshots SET {column} = ?",  # noqa: S608 - fixed parameters
            (value,),
        )

    with pytest.raises(SnapshotCorruptionError, match="snapshot content hash"):
        repository.get_current("project-01")


def test_get_current_rejects_v1_payload_even_when_hash_matches(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    payload = b'{"schema_version":"project-relationship-snapshot-v1"}\n'
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO project_snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (
                "project-01",
                0,
                "project-relationship-snapshot-v1",
                content_hash(payload),
                payload,
                datetime.now(UTC).isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO current_project_snapshots VALUES (?, ?)",
            ("project-01", 0),
        )

    with pytest.raises(SnapshotCorruptionError, match="snapshot payload"):
        repository.get_current("project-01")


def test_commit_scene_rolls_back_scene_upsert_when_project_insert_fails(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    original = scene_record("project-01", "scene-01", revision=1, summary="원본")
    initial = project_snapshot("project-01", version=0, scenes=(original,))
    repository.commit_scene(None, original, initial)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_project_snapshot_insert
            BEFORE INSERT ON project_snapshots
            WHEN NEW.snapshot_version = 1
            BEGIN
                SELECT RAISE(ABORT, 'project insert rejected');
            END
            """
        )
    revised = scene_record("project-01", "scene-01", revision=2, summary="개정고")

    with pytest.raises(sqlite3.IntegrityError, match="project insert rejected"):
        repository.commit_scene(
            0,
            revised,
            project_snapshot("project-01", version=1, scenes=(revised,)),
        )

    assert repository.get_scene_graphs("project-01") == (original,)
    assert repository.get_current("project-01").snapshot == initial  # type: ignore[union-attr]
    with sqlite3.connect(path) as connection:
        versions = connection.execute(
            "SELECT snapshot_version FROM project_snapshots ORDER BY snapshot_version"
        ).fetchall()
    assert versions == [(0,)]


def test_commit_scene_rolls_back_scene_and_project_when_pointer_write_fails(
    tmp_path: Path,
) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    original = scene_record("project-01", "scene-01", revision=1, summary="원본")
    initial = project_snapshot("project-01", version=0, scenes=(original,))
    repository.commit_scene(None, original, initial)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_current_pointer_update
            BEFORE UPDATE ON current_project_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'pointer write rejected');
            END
            """
        )
    revised = scene_record("project-01", "scene-01", revision=2, summary="개정고")

    with pytest.raises(sqlite3.IntegrityError, match="pointer write rejected"):
        repository.commit_scene(
            0,
            revised,
            project_snapshot("project-01", version=1, scenes=(revised,)),
        )

    assert repository.get_scene_graphs("project-01") == (original,)
    assert repository.get_current("project-01").snapshot == initial  # type: ignore[union-attr]
    with sqlite3.connect(path) as connection:
        versions = connection.execute(
            "SELECT snapshot_version FROM project_snapshots ORDER BY snapshot_version"
        ).fetchall()
    assert versions == [(0,)]


def test_repository_rejects_dangling_current_pointer(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO current_project_snapshots VALUES (?, ?)",
            ("project-01", 9),
        )

    with pytest.raises(SnapshotCorruptionError, match="current.*missing"):
        repository.get_current("project-01")


def test_repository_file_is_owner_read_write_only(tmp_path: Path) -> None:
    path = tmp_path / "private" / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(path)

    repository.initialize()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def scene_record(
    project_id: str,
    scene_id: str,
    *,
    revision: int,
    sequence: int = 0,
    summary: str = "장면 요약",
) -> SceneGraphRecord:
    return SceneGraphRecord(
        project_id=project_id,
        scene_id=scene_id,
        scene_revision=revision,
        scene_sequence=sequence,
        graph=KnowledgeGraphOutput(
            document=Document(
                chapter_id=scene_id,
                summary=summary,
                narrative_time="present",
            ),
            entities=Entities(),
        ),
    )


def project_snapshot(
    project_id: str,
    *,
    version: int,
    scenes: tuple[SceneGraphRecord, ...],
) -> ProjectKnowledgeGraphSnapshot:
    return ProjectKnowledgeGraphSnapshot(
        project_id=project_id,
        snapshot_version=version,
        schema_version="project-knowledge-graph-snapshot-v2",
        documents=tuple(scene.graph.document for scene in scenes),
    )


def semantic_scene_record() -> SceneGraphRecord:
    character = Character(
        id="character_001",
        canonical_name="서윤",
        aliases=(),
        description="",
        gender="unknown",
        age=None,
        occupation=None,
        affiliation=None,
        status="alive",
        first_mention="서윤",
        confidence=0.9,
    )
    location = Location(
        id="location_001",
        canonical_name="온실",
        aliases=(),
        location_type="building",
        parent_location_id=None,
        description="",
        first_mention="온실",
        confidence=0.9,
    )
    event = Event(
        id="event_001",
        event_type="ARRIVAL",
        name="도착",
        summary="서윤이 온실에 도착한다.",
        participant_ids=(character.id,),
        location_ids=(location.id,),
        time_expression=None,
        narrative_time="present",
        sequence=0,
        evidence="도착한다",
        confidence=0.9,
    )
    return SceneGraphRecord(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=0,
        graph=KnowledgeGraphOutput(
            document=Document(
                chapter_id="scene-01",
                summary="서윤은 온실에 도착한다.",
                narrative_time="present",
            ),
            entities=Entities(
                characters=(character,),
                locations=(location,),
                events=(event,),
            ),
            relations=(
                Relation(
                    id="relation_001",
                    source_id=character.id,
                    relation_type="LOCATED_IN",
                    target_id=location.id,
                    state="active",
                    directed=True,
                    start_event_id=event.id,
                    end_event_id=None,
                    time_expression=None,
                    scene_sequence=0,
                    evidence="온실에",
                    inference=False,
                    confidence=0.9,
                ),
            ),
            movements=(
                Movement(
                    character_id=character.id,
                    from_location_id=None,
                    to_location_id=location.id,
                    movement_type="ARRIVAL",
                    event_id=event.id,
                    time_expression=None,
                    sequence=0,
                    evidence="도착한다",
                    confidence=0.9,
                ),
            ),
            coreferences=(
                Coreference(
                    expression="그녀",
                    resolved_entity_id=character.id,
                    evidence="그녀",
                    confidence=0.9,
                ),
            ),
            unresolved_references=(
                UnresolvedReference(
                    expression="그곳",
                    possible_entity_ids=(location.id,),
                    reason="모호함",
                ),
            ),
            contradictions=(
                Contradiction(
                    subject_id=character.id,
                    field_or_relation="status",
                    existing_value="missing",
                    new_value="alive",
                    evidence="서윤",
                    possible_explanation="",
                ),
            ),
        ),
    )


def scene_with_duplicate(scene: SceneGraphRecord, collection: str) -> SceneGraphRecord:
    if collection == "relations":
        graph = scene.graph.model_copy(update={"relations": scene.graph.relations * 2})
    else:
        entities = scene.graph.entities.model_copy(
            update={collection: getattr(scene.graph.entities, collection) * 2}
        )
        graph = scene.graph.model_copy(update={"entities": entities})
    return replace(scene, graph=graph)


def scene_with_reference(
    scene: SceneGraphRecord,
    path: str,
    reference: object,
) -> SceneGraphRecord:
    section, field = path.split(".")
    if section in {"location", "event"}:
        collection = f"{section}s"
        item = getattr(scene.graph.entities, collection)[0].model_copy(update={field: reference})
        entities = scene.graph.entities.model_copy(update={collection: (item,)})
        return replace(scene, graph=scene.graph.model_copy(update={"entities": entities}))
    collection_by_section = {
        "relation": "relations",
        "movement": "movements",
        "coreference": "coreferences",
        "unresolved": "unresolved_references",
        "contradiction": "contradictions",
    }
    collection = collection_by_section[section]
    item = getattr(scene.graph, collection)[0].model_copy(update={field: reference})
    return replace(
        scene,
        graph=scene.graph.model_copy(update={collection: (item,)}),
    )


def scene_graph_payload(graph: KnowledgeGraphOutput) -> bytes:
    return (
        json.dumps(
            graph.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def content_hash(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
