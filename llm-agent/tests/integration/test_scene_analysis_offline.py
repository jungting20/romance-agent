import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from narrative_analysis_agent import (
    KnowledgeGraphOutput,
    NarrativeAnalysisAgent,
    SceneAnalysisRequest,
)
from narrative_analysis_agent.models import (
    Character,
    CharacterMemory,
    Document,
    Entities,
    MemoryTarget,
)


@dataclass
class OfflineResult:
    output: KnowledgeGraphOutput


class OfflineRunner:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, user_prompt: str, *, instructions: str) -> OfflineResult:
        self.calls += 1
        return OfflineResult(
            KnowledgeGraphOutput(
                document=Document(
                    chapter_id="scene-01",
                    summary=f"요약 {self.calls}",
                    narrative_time="present",
                ),
                entities=Entities(
                    characters=(
                        Character(
                            id=f"character_{self.calls:03d}",
                            canonical_name="한서윤",
                            description="",
                            gender="unknown",
                            age=None,
                            occupation=None,
                            affiliation=None,
                            status="unknown",
                            first_mention="가",
                            confidence=0.8,
                        ),
                    )
                ),
                character_memories=(
                    CharacterMemory(
                        id=f"memory_{self.calls:03d}",
                        character_id=f"character_{self.calls:03d}",
                        target=MemoryTarget(
                            kind="character",
                            reference_id=f"character_{self.calls:03d}",
                            description="한서윤",
                        ),
                        content="한서윤은 자신을 기억한다.",
                        state="remembered",
                        time_expression=None,
                        scene_sequence=7,
                        evidence="가",
                        confidence=0.8,
                    ),
                ),
            )
        )


def _initialize_graph_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE project_snapshots (
                project_id TEXT NOT NULL,
                snapshot_version INTEGER NOT NULL,
                schema_version TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                payload BLOB NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, snapshot_version)
            );
            CREATE TABLE current_project_snapshots (
                project_id TEXT PRIMARY KEY,
                snapshot_version INTEGER NOT NULL
            );
            """
        )


def test_public_offline_flow_preserves_chunk_order_and_structured_output(tmp_path: Path) -> None:
    graph_path = tmp_path / "narrative-memory.sqlite3"
    _initialize_graph_database(graph_path)
    runner = OfflineRunner()
    agent = NarrativeAnalysisAgent("offline", project_graph_path=graph_path, runner=runner)
    request = SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=7,
        text="가" * 551,
    )

    analysis = asyncio.run(agent.analyze_scene(request))

    assert runner.calls == 3
    assert analysis.source_snapshot_version == 0
    assert [chunk.ordinal for chunk in analysis.chunks] == [0, 1, 2]
    assert [chunk.extraction.document.summary for chunk in analysis.chunks] == [
        "요약 1",
        "요약 2",
        "요약 3",
    ]
    assert [
        chunk.extraction.entities.characters[0].canonical_name for chunk in analysis.chunks
    ] == ["한서윤", "한서윤", "한서윤"]
    assert [chunk.extraction.character_memories[0].id for chunk in analysis.chunks] == [
        "memory_001",
        "memory_002",
        "memory_003",
    ]
