from typing import Protocol, cast

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage

from apps.narrative_memory.service.scene_analysis_ports import (
    ProviderCallError,
    SceneAnalysisCall,
)
from apps.narrative_memory.service.scene_analysis_types import AgentInvocationResult, AgentUsage
from infrastructure.llm.scene_analysis_schemas import ChunkExtractionOutput


class _AgentResult(Protocol):
    output: ChunkExtractionOutput
    usage: RunUsage
    response: ModelResponse

    def all_messages_json(self) -> bytes: ...


class _AgentRunner(Protocol):
    async def run(
        self,
        user_prompt: str,
        *,
        instructions: str,
    ) -> _AgentResult: ...


class PydanticAISceneAnalysisAgent:
    output_type = ChunkExtractionOutput

    def __init__(self, model: Model | str, *, agent: _AgentRunner | None = None) -> None:
        self._agent = agent or cast(
            _AgentRunner,
            Agent(
                model,
                output_type=self.output_type,
                retries=0,
                defer_model_check=True,
            ),
        )

    async def analyze(self, call: SceneAnalysisCall) -> AgentInvocationResult:
        try:
            result = await self._agent.run(
                call.user_prompt,
                instructions=call.system_prompt,
            )
        except AgentRunError as error:
            raise ProviderCallError("scene analysis provider call failed") from error

        return AgentInvocationResult(
            extraction=result.output.to_domain(),
            response_messages_json=result.all_messages_json(),
            usage=AgentUsage(
                requests=result.usage.requests,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
            ),
            provider_name=result.response.provider_name,
            model_name=result.response.model_name,
        )
