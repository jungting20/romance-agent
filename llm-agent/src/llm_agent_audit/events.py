from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Literal

type AuditStatus = Literal["success", "failure", "cancelled"]
type ModelSettingValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class PromptIdentity:
    prompt_id: str
    version: int
    content_hash: str

    @classmethod
    def from_text(cls, prompt_id: str, version: int, text: str) -> "PromptIdentity":
        digest = sha256(text.encode("utf-8")).hexdigest()
        return cls(prompt_id=prompt_id, version=version, content_hash=f"sha256:{digest}")


@dataclass(frozen=True, slots=True)
class ModelConfiguration:
    requested_model: str
    requested_provider: str | None
    settings: tuple[tuple[str, ModelSettingValue], ...] = ()


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    details: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class AuditAttemptStarted:
    schema_version: Literal["llm-agent-audit-v1"]
    event_type: Literal["attempt_started"]
    agent_name: str
    run_id: str
    attempt_id: str
    model: ModelConfiguration
    prompt: PromptIdentity
    started_at: datetime


@dataclass(frozen=True, slots=True)
class SanitizedAuditError:
    code: Literal["model_call_failed", "output_validation_failed", "cancelled"]
    message: str


@dataclass(frozen=True, slots=True)
class AuditAttemptFinished:
    schema_version: Literal["llm-agent-audit-v1"]
    event_type: Literal["attempt_finished"]
    agent_name: str
    run_id: str
    attempt_id: str
    model: ModelConfiguration
    prompt: PromptIdentity
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    status: AuditStatus
    actual_provider: str | None
    actual_model: str | None
    usage: TokenUsage | None
    error: SanitizedAuditError | None


@dataclass(frozen=True, slots=True)
class SensitiveAuditPayload:
    system_prompt: str
    user_prompt: str
    raw_response_json: bytes | None
    validated_output_json: bytes | None


type AuditEvent = AuditAttemptStarted | AuditAttemptFinished
