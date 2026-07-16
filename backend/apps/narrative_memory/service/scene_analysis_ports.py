from dataclasses import dataclass
from typing import Protocol

from apps.narrative_memory.service.scene_analysis_types import AgentInvocationResult


class ProviderCallError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SceneAnalysisCall:
    chunk_id: str
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    prompt_id: str
    version: int
    result_schema: str
    content_hash: str
    raw_bytes: bytes
    body: str


class PromptRegistryPort(Protocol):
    def load(self, prompt_id: str) -> PromptDefinition: ...


class SceneAnalysisAgentPort(Protocol):
    async def analyze(self, call: SceneAnalysisCall) -> AgentInvocationResult: ...
