from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from apps.narrative_memory.service.scene_analysis_ports import PromptDefinition
from apps.narrative_memory.service.scene_analysis_types import AgentUsage


class PromptVersionConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RunStarted:
    run_id: str
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    model_name: str
    prompt_id: str
    prompt_version: int
    occurred_at: datetime
    provider_name: str | None = None


@dataclass(frozen=True, slots=True)
class RunSucceeded:
    run_id: str
    occurred_at: datetime
    scene_snapshot_json: bytes


@dataclass(frozen=True, slots=True)
class RunFailed:
    run_id: str
    occurred_at: datetime
    error_type: str
    error_message: str


@dataclass(frozen=True, slots=True)
class AttemptStarted:
    run_id: str
    chunk_id: str
    attempt_number: int
    occurred_at: datetime
    system_message: str
    user_message: str


@dataclass(frozen=True, slots=True)
class AttemptSucceeded:
    run_id: str
    chunk_id: str
    attempt_number: int
    occurred_at: datetime
    latency_ms: float
    response_messages_json: bytes
    validated_extraction_json: bytes
    provider_name: str
    model_name: str
    usage: AgentUsage


@dataclass(frozen=True, slots=True)
class AttemptFailed:
    run_id: str
    chunk_id: str
    attempt_number: int
    occurred_at: datetime
    latency_ms: float
    error_type: str
    error_message: str
    response_messages_json: bytes | None = None


type RunEvent = RunStarted | RunSucceeded | RunFailed
type AttemptEvent = AttemptStarted | AttemptSucceeded | AttemptFailed


class AgentAuditPort(Protocol):
    def register_prompt(self, prompt: PromptDefinition) -> None: ...

    def append_run_event(self, event: RunEvent) -> None: ...

    def append_attempt_event(self, event: AttemptEvent) -> None: ...
