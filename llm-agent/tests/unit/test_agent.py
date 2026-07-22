import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic_ai.exceptions import AgentRunError

from narrative_analysis_agent import (
    ChunkExtraction,
    NarrativeAnalysisAgent,
    NarrativeAnalysisError,
    SceneAnalysisRequest,
    packaged_prompt_path,
)


@dataclass
class FakeResult:
    output: ChunkExtraction


class FakeRunner:
    def __init__(self, *, failure_call: int | None = None) -> None:
        self.failure_call = failure_call
        self.calls: list[tuple[str, str]] = []

    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        self.calls.append((user_prompt, instructions))
        if len(self.calls) == self.failure_call:
            raise AgentRunError("provider detail")
        ordinal = json.loads(user_prompt)["chunk"]["ordinal"]
        return FakeResult(ChunkExtraction(summary=f"chunk {ordinal}"))


class CancelledRunner:
    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        raise asyncio.CancelledError


def _request(text: str = "가" * 551) -> SceneAnalysisRequest:
    return SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=2,
        text=text,
    )


def test_analyze_scene_calls_each_chunk_once_in_order() -> None:
    runner = FakeRunner()
    agent = NarrativeAnalysisAgent("test", runner=runner)

    analysis = asyncio.run(agent.analyze_scene(_request()))

    assert len(runner.calls) == 3
    assert [chunk.ordinal for chunk in analysis.chunks] == [0, 1, 2]
    assert [chunk.extraction.summary for chunk in analysis.chunks] == [
        "chunk 0",
        "chunk 1",
        "chunk 2",
    ]


def test_analyze_scene_stops_at_first_agent_failure() -> None:
    runner = FakeRunner(failure_call=2)
    agent = NarrativeAnalysisAgent("test", runner=runner)

    with pytest.raises(NarrativeAnalysisError, match="scene analysis failed") as captured:
        asyncio.run(agent.analyze_scene(_request()))

    assert len(runner.calls) == 2
    assert captured.value.__cause__ is None
    assert "provider detail" not in str(captured.value)


def test_analyze_scene_loads_a_custom_prompt_for_each_request(tmp_path: Path) -> None:
    prompt_path = tmp_path / "system.md"
    prompt_path.write_text("사용자 지시", encoding="utf-8")
    runner = FakeRunner()
    agent = NarrativeAnalysisAgent("test", prompt_path=prompt_path, runner=runner)

    asyncio.run(agent.analyze_scene(_request("본문")))

    assert runner.calls[0][1] == "사용자 지시"


def test_analyze_scene_sanitizes_prompt_read_errors(tmp_path: Path) -> None:
    agent = NarrativeAnalysisAgent("test", prompt_path=tmp_path / "missing.md", runner=FakeRunner())

    with pytest.raises(NarrativeAnalysisError, match="unable to load scene analysis prompt"):
        asyncio.run(agent.analyze_scene(_request("")))


def test_analyze_scene_preserves_async_cancellation() -> None:
    agent = NarrativeAnalysisAgent("test", runner=CancelledRunner())

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent.analyze_scene(_request("본문")))


def test_packaged_prompt_is_plain_korean_markdown() -> None:
    content = packaged_prompt_path().read_text(encoding="utf-8")

    assert not content.startswith("---")
    assert "제공된 장면 청크" in content
    assert "chunk-analysis-extraction-v1" in content
