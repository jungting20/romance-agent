from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage

from narrative_analysis_agent.assembly.models import SceneChunkExtraction
from narrative_analysis_agent.assembly.translation import map_chunk_extraction_output
from narrative_analysis_agent.extraction.schemas import ChunkExtractionOutput

_OUTPUT_VALIDATION_EXHAUSTED = "Exceeded maximum output retries (0)"


@dataclass(frozen=True, slots=True)
class ChunkAnalysisCall:
    chunk_id: str
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True, slots=True)
class AgentUsage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ChunkInvocationResult:
    extraction: SceneChunkExtraction
    response_messages_json: bytes
    usage: AgentUsage
    provider_name: str
    model_name: str


class _ProviderCallError(RuntimeError):
    pass


class _InvalidExtractionOutputError(RuntimeError):
    pass


class ChunkAnalyzerPort(Protocol):
    @property
    def model_name(self) -> str:
        raise NotImplementedError

    async def analyze(self, call: ChunkAnalysisCall) -> ChunkInvocationResult:
        raise NotImplementedError


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


class PydanticAIChunkAnalyzer:
    output_type = ChunkExtractionOutput

    def __init__(self, model: Model | str, *, agent: _AgentRunner | None = None) -> None:
        self._model_name = model if isinstance(model, str) else model.model_name
        self._agent = agent or cast(
            _AgentRunner,
            Agent(
                model,
                output_type=self.output_type,
                retries=0,
                defer_model_check=True,
            ),
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    async def analyze(self, call: ChunkAnalysisCall) -> ChunkInvocationResult:
        try:
            result = await self._agent.run(
                call.user_prompt,
                instructions=call.system_prompt,
            )
        except UnexpectedModelBehavior as error:
            if _is_structured_output_validation_exhaustion(error):
                raise _InvalidExtractionOutputError(
                    "scene analysis extraction is invalid"
                ) from None
            raise _ProviderCallError("scene analysis provider call failed") from None
        except AgentRunError:
            raise _ProviderCallError("scene analysis provider call failed") from None

        return ChunkInvocationResult(
            extraction=map_chunk_extraction_output(result.output),
            response_messages_json=result.all_messages_json(),
            usage=AgentUsage(
                requests=result.usage.requests,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
            ),
            provider_name=result.response.provider_name,
            model_name=result.response.model_name,
        )


def _is_structured_output_validation_exhaustion(error: UnexpectedModelBehavior) -> bool:
    if error.message != _OUTPUT_VALIDATION_EXHAUSTED:
        return False
    cause = error.__cause__
    while cause is not None:
        if isinstance(cause, ValidationError):
            return True
        cause = cause.__cause__
    return False


type ScriptedResult = SceneChunkExtraction | Exception


class ScriptedChunkAnalyzer:
    model_name = "mock"

    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedResult]] | None = None,
    ) -> None:
        self._scripts = {
            chunk_id: deque(sequence) for chunk_id, sequence in (scripts or {}).items()
        }
        self.calls: list[ChunkAnalysisCall] = []

    async def analyze(self, call: ChunkAnalysisCall) -> ChunkInvocationResult:
        self.calls.append(call)
        script = self._scripts.get(call.chunk_id)
        scripted = script.popleft() if script else SceneChunkExtraction(summary="")
        if isinstance(scripted, Exception):
            raise scripted
        return ChunkInvocationResult(
            extraction=scripted,
            response_messages_json=b"[]",
            usage=AgentUsage(),
            provider_name="mock",
            model_name="mock",
        )
