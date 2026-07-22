import asyncio
import json
from pathlib import Path
from typing import Protocol, cast

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from narrative_analysis_agent.chunking import SceneChunk, chunk_scene
from narrative_analysis_agent.models import (
    AnalyzedChunk,
    ChunkExtraction,
    SceneAnalysis,
    SceneAnalysisRequest,
)


class NarrativeAnalysisError(RuntimeError):
    pass


class AgentResult(Protocol):
    output: ChunkExtraction


class AgentRunner(Protocol):
    async def run(self, user_prompt: str, *, instructions: str) -> AgentResult: ...


def packaged_prompt_path() -> Path:
    return Path(__file__).parent / "prompts" / "scene-analysis" / "system.md"


class NarrativeAnalysisAgent:
    def __init__(
        self,
        model: Model | str,
        *,
        prompt_path: Path | None = None,
        runner: AgentRunner | None = None,
    ) -> None:
        self.prompt_path = prompt_path or packaged_prompt_path()
        self._runner = runner or cast(
            AgentRunner,
            Agent(
                model,
                output_type=ChunkExtraction,
                retries=0,
                defer_model_check=True,
            ),
        )

    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis:
        try:
            instructions = self.prompt_path.read_text(encoding="utf-8")
        except OSError:
            raise NarrativeAnalysisError("unable to load scene analysis prompt") from None

        analyzed: list[AnalyzedChunk] = []
        for chunk in chunk_scene(request.scene_id, request.scene_revision, request.text):
            try:
                result = await self._runner.run(
                    _render_user_prompt(request, chunk),
                    instructions=instructions,
                )
            except asyncio.CancelledError:
                raise
            except AgentRunError:
                raise NarrativeAnalysisError("scene analysis failed") from None
            analyzed.append(
                AnalyzedChunk(
                    chunk_id=chunk.chunk_id,
                    ordinal=chunk.ordinal,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    text=chunk.text,
                    extraction=result.output,
                )
            )

        return SceneAnalysis(
            project_id=request.project_id,
            scene_id=request.scene_id,
            scene_revision=request.scene_revision,
            scene_sequence=request.scene_sequence,
            chunks=tuple(analyzed),
        )


def _render_user_prompt(request: SceneAnalysisRequest, chunk: SceneChunk) -> str:
    envelope = {
        "project_id": request.project_id,
        "scene_id": request.scene_id,
        "scene_revision": request.scene_revision,
        "scene_sequence": request.scene_sequence,
        "known_entities": [identity.model_dump(mode="json") for identity in request.known_entities],
        "known_places": [identity.model_dump(mode="json") for identity in request.known_places],
        "chunk": {
            "chunk_id": chunk.chunk_id,
            "ordinal": chunk.ordinal,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            "text": chunk.text,
        },
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
