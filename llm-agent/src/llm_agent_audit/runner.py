import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, TypeVar
from uuid import uuid4

from pydantic import BaseModel
from pydantic_ai.models import Model

from llm_agent_audit.events import (
    AuditAttemptFinished,
    AuditAttemptStarted,
    AuditEvent,
    AuditStatus,
    PromptIdentity,
    SanitizedAuditError,
    SensitiveAuditPayload,
)
from llm_agent_audit.inspection import (
    InspectedResult,
    inspect_result,
    sanitized_model_configuration,
)

OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentResult(Protocol[OutputT]):
    output: OutputT


class AgentRunner(Protocol[OutputT]):
    async def run(self, user_prompt: str, *, instructions: str) -> AgentResult[OutputT]: ...


class AgentAuditSink(Protocol):
    capture_sensitive_content: bool

    async def append(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None: ...


class NoopAgentAuditSink:
    capture_sensitive_content = False

    async def append(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None:
        return None


class AgentAuditWriteError(RuntimeError):
    pass


class AuditedAgentRunner[OutputT: BaseModel]:
    def __init__(
        self,
        runner: AgentRunner[OutputT],
        *,
        agent_name: str,
        model: Model | str,
        sink: AgentAuditSink | None = None,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._runner = runner
        self._agent_name = agent_name
        self._model = sanitized_model_configuration(model)
        self._sink = sink or NoopAgentAuditSink()
        self._id_factory = id_factory or _new_attempt_id
        self._clock = clock or _utc_now
        self._monotonic = monotonic or time.monotonic

    def new_run_id(self) -> str:
        return f"run-{uuid4()}"

    async def run(
        self,
        user_prompt: str,
        *,
        instructions: str,
        run_id: str,
        prompt: PromptIdentity,
        validate: Callable[[OutputT], None],
    ) -> AgentResult[OutputT]:
        attempt_id = self._id_factory()
        started_at = self._clock()
        started_monotonic = self._monotonic()
        await self._append_required(
            AuditAttemptStarted(
                schema_version="llm-agent-audit-v1",
                event_type="attempt_started",
                agent_name=self._agent_name,
                run_id=run_id,
                attempt_id=attempt_id,
                model=self._model,
                prompt=prompt,
                started_at=started_at,
            )
        )

        try:
            result = await self._runner.run(user_prompt, instructions=instructions)
        except asyncio.CancelledError:
            await self._append_cancellation(
                self._finished_event(
                    run_id=run_id,
                    attempt_id=attempt_id,
                    prompt=prompt,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    status="cancelled",
                    inspected=None,
                    error=SanitizedAuditError(code="cancelled", message="agent run cancelled"),
                )
            )
            raise
        except Exception:
            await self._append_required(
                self._finished_event(
                    run_id=run_id,
                    attempt_id=attempt_id,
                    prompt=prompt,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    status="failure",
                    inspected=None,
                    error=SanitizedAuditError(
                        code="model_call_failed",
                        message="model call failed",
                    ),
                )
            )
            raise

        inspected = inspect_result(result)
        try:
            validate(result.output)
        except asyncio.CancelledError:
            await self._append_cancellation(
                self._finished_event(
                    run_id=run_id,
                    attempt_id=attempt_id,
                    prompt=prompt,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    status="cancelled",
                    inspected=inspected,
                    error=SanitizedAuditError(code="cancelled", message="agent run cancelled"),
                )
            )
            raise
        except Exception:
            await self._append_required(
                self._finished_event(
                    run_id=run_id,
                    attempt_id=attempt_id,
                    prompt=prompt,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    status="failure",
                    inspected=inspected,
                    error=SanitizedAuditError(
                        code="output_validation_failed",
                        message="output validation failed",
                    ),
                ),
                sensitive=self._sensitive_payload(
                    instructions,
                    user_prompt,
                    inspected,
                    validated_output_json=None,
                ),
            )
            raise

        await self._append_required(
            self._finished_event(
                run_id=run_id,
                attempt_id=attempt_id,
                prompt=prompt,
                started_at=started_at,
                started_monotonic=started_monotonic,
                status="success",
                inspected=inspected,
                error=None,
            ),
            sensitive=self._sensitive_payload(
                instructions,
                user_prompt,
                inspected,
                validated_output_json=inspected.validated_output_json,
            ),
        )
        return result

    def _finished_event(
        self,
        *,
        run_id: str,
        attempt_id: str,
        prompt: PromptIdentity,
        started_at: datetime,
        started_monotonic: float,
        status: AuditStatus,
        inspected: InspectedResult | None,
        error: SanitizedAuditError | None,
    ) -> AuditAttemptFinished:
        ended_at = self._clock()
        duration_ms = (self._monotonic() - started_monotonic) * 1000
        return AuditAttemptFinished(
            schema_version="llm-agent-audit-v1",
            event_type="attempt_finished",
            agent_name=self._agent_name,
            run_id=run_id,
            attempt_id=attempt_id,
            model=self._model,
            prompt=prompt,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            status=status,
            actual_provider=inspected.actual_provider if inspected else None,
            actual_model=inspected.actual_model if inspected else None,
            usage=inspected.usage if inspected else None,
            error=error,
        )

    def _sensitive_payload(
        self,
        instructions: str,
        user_prompt: str,
        inspected: InspectedResult,
        *,
        validated_output_json: bytes | None,
    ) -> SensitiveAuditPayload | None:
        if not self._sink.capture_sensitive_content:
            return None
        return SensitiveAuditPayload(
            system_prompt=instructions,
            user_prompt=user_prompt,
            raw_response_json=inspected.raw_response_json,
            validated_output_json=validated_output_json,
        )

    async def _append_required(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None:
        try:
            await self._sink.append(event, sensitive)
        except Exception:
            raise AgentAuditWriteError("agent audit logging failed") from None

    async def _append_cancellation(self, event: AuditEvent) -> None:
        try:  # noqa: SIM105
            await self._sink.append(event)
        except Exception:
            pass


def _new_attempt_id() -> str:
    return f"attempt-{uuid4()}"


def _utc_now() -> datetime:
    return datetime.now(UTC)
