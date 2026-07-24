import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from llm_agent_audit import (
    AgentAuditWriteError,
    AuditAttemptFinished,
    AuditAttemptStarted,
    AuditedAgentRunner,
    AuditEvent,
    PromptIdentity,
    SensitiveAuditPayload,
    TokenUsage,
    sanitized_model_configuration,
)


class FakeOutput(BaseModel):
    value: str


@dataclass
class FakeResult:
    output: FakeOutput
    response: ModelResponse
    usage: RunUsage


class RecordingRunner:
    def __init__(self, result: FakeResult | BaseException) -> None:
        self._result = result
        self.calls = 0

    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        self.calls += 1
        if isinstance(self._result, BaseException):
            raise self._result
        return self._result


class RecordingSink:
    def __init__(self, *, capture_sensitive_content: bool = False) -> None:
        self.capture_sensitive_content = capture_sensitive_content
        self.records: list[tuple[AuditEvent, SensitiveAuditPayload | None]] = []

    async def append(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None:
        self.records.append((event, sensitive))


class FailingSink(RecordingSink):
    def __init__(self, *, fail_on_append: int) -> None:
        super().__init__()
        self._fail_on_append = fail_on_append
        self.append_calls = 0

    async def append(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None:
        self.append_calls += 1
        if self.append_calls == self._fail_on_append:
            raise OSError("audit storage unavailable")
        await super().append(event, sensitive)


def _result() -> FakeResult:
    return FakeResult(
        output=FakeOutput(value="validated"),
        response=ModelResponse(
            parts=[],
            model_name="actual-model",
            provider_name="actual-provider",
        ),
        usage=RunUsage(input_tokens=11, output_tokens=7),
    )


def _audited_runner(
    *,
    sink: RecordingSink,
    result: FakeResult | BaseException,
) -> AuditedAgentRunner[FakeOutput]:
    times = iter(
        (
            datetime(2026, 7, 24, 9, 0, tzinfo=UTC),
            datetime(2026, 7, 24, 9, 0, 1, tzinfo=UTC),
        )
    )
    monotonic_times = iter((100.0, 100.25))
    return AuditedAgentRunner(
        RecordingRunner(result),
        agent_name="dialogue-generation",
        model=TestModel(),
        sink=sink,
        id_factory=lambda: "attempt-1",
        clock=lambda: next(times),
        monotonic=lambda: next(monotonic_times),
    )


def _run(
    runner: AuditedAgentRunner[FakeOutput],
    validate: Callable[[FakeOutput], None] = lambda output: None,
) -> FakeResult:
    return asyncio.run(
        runner.run(
            "user secret",
            instructions="system secret",
            run_id="run-1",
            prompt=PromptIdentity.from_text("dialogue-generation.system", 1, "system secret"),
            validate=validate,
        )
    )


def test_audited_runner_records_success_without_sensitive_content_by_default() -> None:
    sink = RecordingSink()
    runner = _audited_runner(sink=sink, result=_result())

    result = _run(runner)

    assert result.output.value == "validated"
    assert [type(record[0]) for record in sink.records] == [
        AuditAttemptStarted,
        AuditAttemptFinished,
    ]
    assert sink.records[0][1] is None
    assert sink.records[1][1] is None
    terminal = cast(AuditAttemptFinished, sink.records[1][0])
    assert terminal.status == "success"
    assert terminal.usage == TokenUsage(input_tokens=11, output_tokens=7)
    assert terminal.duration_ms == 250.0


def test_audited_runner_passes_sensitive_payload_only_when_sink_requests_it() -> None:
    sink = RecordingSink(capture_sensitive_content=True)
    runner = _audited_runner(sink=sink, result=_result())

    _run(runner)

    sensitive = sink.records[-1][1]
    assert sensitive is not None
    assert sensitive.system_prompt == "system secret"
    assert sensitive.user_prompt == "user secret"
    assert sensitive.raw_response_json is not None
    assert sensitive.validated_output_json == b'{"value":"validated"}'


def test_audited_runner_records_provider_failure_and_reraises_original_exception() -> None:
    provider_error = RuntimeError("private provider detail")
    sink = RecordingSink()

    with pytest.raises(RuntimeError, match="private provider detail"):
        _run(_audited_runner(sink=sink, result=provider_error))

    terminal = cast(AuditAttemptFinished, sink.records[-1][0])
    assert terminal.status == "failure"
    assert terminal.error is not None
    assert terminal.error.code == "model_call_failed"
    assert "private" not in terminal.error.message


def test_audited_runner_records_validation_failure_without_validated_output() -> None:
    sink = RecordingSink(capture_sensitive_content=True)

    with pytest.raises(ValueError, match="invalid output"):
        _run(
            _audited_runner(sink=sink, result=_result()),
            validate=lambda output: (_ for _ in ()).throw(ValueError("invalid output")),
        )

    terminal = cast(AuditAttemptFinished, sink.records[-1][0])
    sensitive = sink.records[-1][1]
    assert terminal.status == "failure"
    assert terminal.error is not None
    assert terminal.error.code == "output_validation_failed"
    assert sensitive is not None
    assert sensitive.validated_output_json is None


def test_audited_runner_records_cancellation_and_reraises_it() -> None:
    sink = RecordingSink()

    with pytest.raises(asyncio.CancelledError):
        _run(_audited_runner(sink=sink, result=asyncio.CancelledError()))

    terminal = cast(AuditAttemptFinished, sink.records[-1][0])
    assert terminal.status == "cancelled"
    assert terminal.error is not None
    assert terminal.error.code == "cancelled"


def test_audited_runner_fails_closed_when_start_append_fails() -> None:
    sink = FailingSink(fail_on_append=1)
    wrapped = RecordingRunner(_result())
    runner = AuditedAgentRunner(
        wrapped,
        agent_name="dialogue-generation",
        model=TestModel(),
        sink=sink,
        id_factory=lambda: "attempt-1",
    )

    with pytest.raises(AgentAuditWriteError, match="agent audit logging failed") as captured:
        _run(runner)

    assert captured.value.__cause__ is None
    assert wrapped.calls == 0


def test_audited_runner_fails_closed_when_success_terminal_append_fails() -> None:
    sink = FailingSink(fail_on_append=2)

    with pytest.raises(AgentAuditWriteError, match="agent audit logging failed"):
        _run(_audited_runner(sink=sink, result=_result()))


def test_audited_runner_does_not_mask_cancellation_when_terminal_append_fails() -> None:
    sink = FailingSink(fail_on_append=2)

    with pytest.raises(asyncio.CancelledError):
        _run(_audited_runner(sink=sink, result=asyncio.CancelledError()))

    assert sink.append_calls == 2


def test_prompt_identity_hashes_exact_utf8_bytes() -> None:
    prompt = PromptIdentity.from_text("id", 2, "한글\ntext")

    assert prompt.content_hash == (
        "sha256:9bf9e1e0043e50c61bfd69d911b6d2718f3127b3bf570e4549288496205d8c57"
    )


def test_sanitized_model_configuration_excludes_sensitive_and_non_scalar_settings() -> None:
    model = TestModel(
        settings={
            "api_key": "secret",
            "headers": {"authorization": "secret"},
            "base_url": "https://private.example",
            "temperature": 0.4,
            "max_tokens": 80,
            "top_p": 0.9,
            "seed": 3,
            "timeout": None,
            "metadata": ["not allowed"],
        }
    )

    configuration = sanitized_model_configuration(model)

    assert configuration.requested_model == "test"
    assert configuration.requested_provider == "test"
    assert configuration.settings == (
        ("max_tokens", 80),
        ("seed", 3),
        ("temperature", 0.4),
        ("timeout", None),
        ("top_p", 0.9),
    )
