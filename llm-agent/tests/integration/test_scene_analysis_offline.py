import asyncio
from dataclasses import dataclass

from narrative_analysis_agent import (
    ChunkExtraction,
    Entity,
    NarrativeAnalysisAgent,
    SceneAnalysisRequest,
)


@dataclass
class OfflineResult:
    output: ChunkExtraction


class OfflineRunner:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, user_prompt: str, *, instructions: str) -> OfflineResult:
        self.calls += 1
        return OfflineResult(
            ChunkExtraction(
                summary=f"요약 {self.calls}",
                entities=(
                    Entity(
                        local_ref=f"character-{self.calls}",
                        normalized_name="한서윤",
                        display_name="한서윤",
                    ),
                ),
            )
        )


def test_public_offline_flow_preserves_chunk_order_and_structured_output() -> None:
    runner = OfflineRunner()
    agent = NarrativeAnalysisAgent("offline", runner=runner)
    request = SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=7,
        text="가" * 551,
    )

    analysis = asyncio.run(agent.analyze_scene(request))

    assert runner.calls == 3
    assert [chunk.ordinal for chunk in analysis.chunks] == [0, 1, 2]
    assert [chunk.extraction.summary for chunk in analysis.chunks] == ["요약 1", "요약 2", "요약 3"]
    assert [chunk.extraction.entities[0].local_ref for chunk in analysis.chunks] == [
        "character-1",
        "character-2",
        "character-3",
    ]
