from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage

from llm_agent_audit.events import ModelConfiguration, TokenUsage


@dataclass(frozen=True, slots=True)
class InspectedResult:
    actual_provider: str | None
    actual_model: str | None
    usage: TokenUsage | None
    raw_response_json: bytes | None
    validated_output_json: bytes


def sanitized_model_configuration(model: Model | str) -> ModelConfiguration:
    if isinstance(model, str):
        provider, separator, requested_model = model.partition(":")
        return ModelConfiguration(
            requested_model=requested_model if separator else model,
            requested_provider=provider if separator else None,
        )
    settings = tuple(
        sorted(
            (key, value)
            for key, value in (model.settings or {}).items()
            if key in {"temperature", "max_tokens", "top_p", "seed", "timeout"}
            and (value is None or isinstance(value, str | int | float | bool))
        )
    )
    return ModelConfiguration(model.model_name, model.system, settings)


def inspect_result(result: Any) -> InspectedResult:
    response = getattr(result, "response", None)
    usage = _token_usage(getattr(result, "usage", None))
    output = getattr(result, "output", None)
    if not isinstance(output, BaseModel):
        raise TypeError("agent output must be a Pydantic model")
    if not isinstance(response, ModelResponse):
        return InspectedResult(
            actual_provider=None,
            actual_model=None,
            usage=usage,
            raw_response_json=None,
            validated_output_json=output.model_dump_json().encode(),
        )
    return InspectedResult(
        actual_provider=response.provider_name,
        actual_model=response.model_name,
        usage=usage,
        raw_response_json=ModelMessagesTypeAdapter.dump_json([response]),
        validated_output_json=output.model_dump_json().encode(),
    )


def _token_usage(usage: object) -> TokenUsage | None:
    if not isinstance(usage, RunUsage):
        return None
    details = tuple(
        sorted((key, value) for key, value in usage.details.items() if _is_nonnegative_int(value))
    )
    return TokenUsage(
        input_tokens=_nonnegative_int(usage.input_tokens),
        output_tokens=_nonnegative_int(usage.output_tokens),
        cache_read_tokens=_nonnegative_int(usage.cache_read_tokens),
        cache_write_tokens=_nonnegative_int(usage.cache_write_tokens),
        details=details,
    )


def _nonnegative_int(value: object) -> int:
    return value if _is_nonnegative_int(value) else 0


def _is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0
