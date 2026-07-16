from collections import deque
from collections.abc import Mapping, Sequence

from apps.narrative_memory.service.scene_analysis_ports import SceneAnalysisCall
from apps.narrative_memory.service.scene_analysis_types import (
    AgentInvocationResult,
    AgentUsage,
    SceneChunkExtraction,
)

type ScriptedResult = SceneChunkExtraction | Exception


class ScriptedSceneAnalysisAgent:
    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedResult]] | None = None,
    ) -> None:
        self._scripts = {
            chunk_id: deque(sequence) for chunk_id, sequence in (scripts or {}).items()
        }
        self.calls: list[SceneAnalysisCall] = []

    async def analyze(self, call: SceneAnalysisCall) -> AgentInvocationResult:
        self.calls.append(call)
        script = self._scripts.get(call.chunk_id)
        scripted = script.popleft() if script else SceneChunkExtraction(summary="")
        if isinstance(scripted, Exception):
            raise scripted
        return AgentInvocationResult(
            extraction=scripted,
            response_messages_json=b"[]",
            usage=AgentUsage(),
            provider_name="mock",
            model_name="mock",
        )
