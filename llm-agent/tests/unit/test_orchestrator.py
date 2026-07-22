import asyncio
import json
import sqlite3
import traceback
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_ai.exceptions import UnexpectedModelBehavior

from narrative_analysis_agent import (
    AnalysisAuditError,
    InvalidExtractionError,
    NarrativeAnalysisError,
    PromptLoadError,
    ProviderUnavailableError,
    SceneAnalysisRequest,
)
from narrative_analysis_agent.assembly.models import (
    ExtractedEntity,
    RelativeEvidence,
    SceneChunkExtraction,
)
from narrative_analysis_agent.audit.ports import (
    AgentAuditPort,
    AttemptEvent,
    AttemptFailed,
    AttemptStarted,
    AttemptSucceeded,
    RunEvent,
    RunFailed,
    RunStarted,
    RunSucceeded,
)
from narrative_analysis_agent.audit.sqlite import SQLiteAgentAudit
from narrative_analysis_agent.extraction.agent import (
    AgentUsage,
    ChunkAnalysisCall,
    ChunkAnalyzerPort,
    ChunkInvocationResult,
    PydanticAIChunkAnalyzer,
    _ProviderCallError,
)
from narrative_analysis_agent.extraction.prompts import PromptDefinition
from narrative_analysis_agent.extraction.schemas import ChunkExtractionOutput
from narrative_analysis_agent.orchestrator import SceneAnalysisOrchestrator

NOW = datetime(2026, 7, 16, 9, 30, tzinfo=UTC)


class RecordingAudit(AgentAuditPort):
    def __init__(self) -> None:
        self.prompts: list[PromptDefinition] = []
        self.events: list[RunEvent | AttemptEvent] = []

    def register_prompt(self, prompt: PromptDefinition) -> None:
        self.prompts.append(prompt)

    def append_run_event(self, event: RunEvent) -> None:
        self.events.append(event)

    def append_attempt_event(self, event: AttemptEvent) -> None:
        self.events.append(event)

    @property
    def event_types(self) -> list[str]:
        names = {
            RunStarted: "run_started",
            RunFailed: "run_failed",
            RunSucceeded: "run_succeeded",
            AttemptStarted: "attempt_started",
            AttemptFailed: "attempt_failed",
            AttemptSucceeded: "attempt_succeeded",
        }
        return [names[type(event)] for event in self.events]


class StubPromptRegistry:
    def __init__(self) -> None:
        self.prompt = PromptDefinition(
            prompt_id="scene-analysis",
            version=1,
            result_schema="chunk-analysis-extraction-v1",
            content_hash="sha256:prompt-v1",
            raw_bytes=b"---\nprompt body",
            body="Extract only asserted facts.\n",
        )
        self.loads: list[str] = []

    def load(self, prompt_id: str) -> PromptDefinition:
        self.loads.append(prompt_id)
        return self.prompt


class ScriptedAnalyzer:
    model_name = "configured-model"

    def __init__(self, results: list[ChunkInvocationResult | BaseException]) -> None:
        self._results = iter(results)
        self.calls: list[ChunkAnalysisCall] = []

    async def analyze(self, call: ChunkAnalysisCall) -> ChunkInvocationResult:
        self.calls.append(call)
        result = next(self._results)
        if isinstance(result, BaseException):
            raise result
        return result


def _result(
    extraction: SceneChunkExtraction,
    response: bytes = b"[]",
) -> ChunkInvocationResult:
    return ChunkInvocationResult(
        extraction=extraction,
        response_messages_json=response,
        usage=AgentUsage(requests=1, input_tokens=10, output_tokens=5),
        provider_name="resolved-provider",
        model_name="resolved-model",
    )


def _orchestrator(
    analyzer: ChunkAnalyzerPort,
    audit: RecordingAudit,
    registry: StubPromptRegistry | None = None,
) -> tuple[SceneAnalysisOrchestrator, StubPromptRegistry]:
    prompt_registry = registry or StubPromptRegistry()
    ticks = iter(index / 8 for index in range(100))
    return (
        SceneAnalysisOrchestrator(
            analyzer=analyzer,
            prompt_registry=prompt_registry,
            audit=audit,
            run_id_factory=lambda: "run-01",
            clock=lambda: NOW,
            monotonic=lambda: next(ticks),
        ),
        prompt_registry,
    )


def _request(text: str = "text") -> SceneAnalysisRequest:
    return SceneAnalysisRequest("project-01", "scene-01", 1, 4, text)


def test_empty_scene_is_audited_success_without_analyzer_calls() -> None:
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer([])
    orchestrator, registry = _orchestrator(analyzer, audit)

    result = asyncio.run(orchestrator.analyze_scene(_request("")))

    assert result.run_id == "run-01"
    assert result.snapshot.scene_id == "scene-01"
    assert result.snapshot.summary == ""
    assert result.snapshot.entities == ()
    assert registry.loads == ["scene-analysis"]
    assert audit.prompts == [registry.prompt]
    assert analyzer.calls == []
    assert audit.event_types == ["run_started", "run_succeeded"]
    succeeded = audit.events[-1]
    assert isinstance(succeeded, RunSucceeded)
    assert json.loads(succeeded.scene_snapshot_json) == {
        "entities": [],
        "location_events": [],
        "places": [],
        "relationship_events": [],
        "scene_id": "scene-01",
        "scene_revision": 1,
        "scene_sequence": 4,
        "schema_version": "scene-relationship-snapshot-v1",
        "summary": "",
    }


def test_scene_chunks_are_analyzed_serially_and_audited_canonically() -> None:
    text = "Alex " * 70
    extraction = SceneChunkExtraction(
        summary="Alex appears.",
        entities=(
            ExtractedEntity(
                local_ref="alex",
                normalized_name="alex",
                display_name="Alex",
                aliases=(),
                evidence=(RelativeEvidence(0, 4, "Alex"),),
            ),
        ),
    )
    analyzer = ScriptedAnalyzer(
        [_result(extraction, b'[{"chunk":0}]'), _result(extraction, b'[{"chunk":1}]')]
    )
    audit = RecordingAudit()
    orchestrator, registry = _orchestrator(analyzer, audit)

    result = asyncio.run(orchestrator.analyze_scene(_request(text)))

    assert [call.chunk_id for call in analyzer.calls] == [
        "scene-01:r1:0000",
        "scene-01:r1:0001",
    ]
    assert len(result.snapshot.entities) == 1
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_succeeded",
        "attempt_started",
        "attempt_succeeded",
        "run_succeeded",
    ]
    starts = [event for event in audit.events if isinstance(event, AttemptStarted)]
    assert [event.system_message for event in starts] == [registry.prompt.body] * 2
    successes = [event for event in audit.events if isinstance(event, AttemptSucceeded)]
    assert [event.response_messages_json for event in successes] == [
        b'[{"chunk":0}]',
        b'[{"chunk":1}]',
    ]
    assert [json.loads(event.validated_extraction_json) for event in successes] == [
        {
            "entities": [
                {
                    "aliases": [],
                    "display_name": "Alex",
                    "evidence": [{"end_offset": 4, "start_offset": 0, "text": "Alex"}],
                    "local_ref": "alex",
                    "normalized_name": "alex",
                }
            ],
            "location_events": [],
            "places": [],
            "relationship_events": [],
            "summary": "Alex appears.",
        }
    ] * 2
    assert [event.latency_ms for event in successes] == [125.0, 125.0]


def test_provider_failure_is_retried_once_then_succeeds() -> None:
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer(
        [_ProviderCallError("secret provider detail"), _result(SceneChunkExtraction("ok"))]
    )
    orchestrator, _ = _orchestrator(analyzer, audit)

    result = asyncio.run(orchestrator.analyze_scene(_request()))

    assert result.snapshot.summary == "ok"
    assert len(analyzer.calls) == 2
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "attempt_started",
        "attempt_succeeded",
        "run_succeeded",
    ]
    failed = next(event for event in audit.events if isinstance(event, AttemptFailed))
    assert failed.error_message == "scene analysis provider call failed"
    assert "secret" not in failed.error_message


def test_two_provider_failures_are_sanitized_and_return_no_snapshot() -> None:
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer(
        [_ProviderCallError("secret one"), _ProviderCallError("secret two")]
    )
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(ProviderUnavailableError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert captured.value.run_id == "run-01"
    assert captured.value.args == ("scene analysis provider call failed",)
    assert captured.value.__cause__ is None
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert "secret one" not in formatted
    assert "secret two" not in formatted
    assert len(analyzer.calls) == 2
    assert audit.event_types[-1] == "run_failed"
    assert not any(isinstance(event, RunSucceeded) for event in audit.events)


def test_invalid_evidence_is_not_retried_and_is_sanitized() -> None:
    secret_reference = "SECRET_MODEL_REFERENCE"
    extraction = SceneChunkExtraction(
        summary="invalid",
        entities=(
            ExtractedEntity(
                local_ref=secret_reference,
                normalized_name="entity",
                display_name="Entity",
                aliases=(),
                evidence=(RelativeEvidence(0, 1, "wrong"),),
            ),
        ),
    )
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer([_result(extraction)])
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(InvalidExtractionError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert captured.value.run_id == "run-01"
    assert captured.value.args == ("scene analysis extraction is invalid",)
    assert captured.value.__cause__ is None
    assert len(analyzer.calls) == 1
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_succeeded",
        "run_failed",
    ]
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert secret_reference not in formatted


class UnexpectedAnalyzerError(RuntimeError):
    pass


def test_unexpected_analyzer_error_is_not_retried_or_exposed() -> None:
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer([UnexpectedAnalyzerError("secret provider body")])
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(NarrativeAnalysisError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request("x" * 350)))

    assert captured.value.run_id == "run-01"
    assert captured.value.args == ("scene analysis agent call failed",)
    assert len(analyzer.calls) == 1
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "run_failed",
    ]
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert "secret provider body" not in formatted


class StructuredOutputFailingRunner:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        try:
            ChunkExtractionOutput.model_validate(
                {
                    "summary": "SECRET_MANUSCRIPT_BODY",
                    "relationship_events": [
                        {
                            "subject_ref": "subject",
                            "object_ref": "object",
                            "category": "invalid-secret-category",
                            "description": "SECRET_RESPONSE_BODY",
                            "confidence": 0.5,
                            "evidence": [],
                        }
                    ],
                }
            )
        except ValidationError as error:
            raise UnexpectedModelBehavior(
                "Exceeded maximum output retries (0)",
                body="SECRET_PROVIDER_BODY",
            ) from error
        raise AssertionError("invalid payload unexpectedly validated")


def test_structured_output_validation_failure_is_not_retried_and_is_audited() -> None:
    audit = RecordingAudit()
    runner = StructuredOutputFailingRunner()
    analyzer = PydanticAIChunkAnalyzer("configured-model", agent=runner)
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(InvalidExtractionError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert runner.calls == 1
    assert captured.value.run_id == "run-01"
    assert captured.value.args == ("scene analysis extraction is invalid",)
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "run_failed",
    ]
    failed_attempt = audit.events[-2]
    failed_run = audit.events[-1]
    assert isinstance(failed_attempt, AttemptFailed)
    assert failed_attempt.attempt_number == 1
    assert failed_attempt.error_type == "InvalidExtractionError"
    assert failed_attempt.error_message == "scene analysis extraction is invalid"
    assert isinstance(failed_run, RunFailed)
    assert failed_run.error_type == "InvalidExtractionError"
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    for secret in (
        "SECRET_MANUSCRIPT_BODY",
        "SECRET_RESPONSE_BODY",
        "SECRET_PROVIDER_BODY",
        "invalid-secret-category",
    ):
        assert secret not in formatted


def test_non_json_extraction_fails_before_attempt_success_without_retry() -> None:
    extraction = SceneChunkExtraction(summary="invalid \ud800")
    response = b'[{"content":"SECRET_RESPONSE_BODY"}]'
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer([_result(extraction, response)])
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(InvalidExtractionError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert len(analyzer.calls) == 1
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "run_failed",
    ]
    failed_attempt = audit.events[-2]
    assert isinstance(failed_attempt, AttemptFailed)
    assert failed_attempt.error_message == "scene analysis extraction result is invalid"
    assert failed_attempt.response_messages_json == response
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert "SECRET_RESPONSE_BODY" not in formatted


@pytest.mark.parametrize(
    "scene_request",
    [
        SceneAnalysisRequest("", "scene", 0, 0, "text"),
        SceneAnalysisRequest("project", " ", 0, 0, "text"),
        SceneAnalysisRequest("project", "scene", -1, 0, "text"),
        SceneAnalysisRequest("project", "scene", 0, -1, "text"),
    ],
)
def test_invalid_request_is_rejected_before_prompt_load(
    scene_request: SceneAnalysisRequest,
) -> None:
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer([])
    orchestrator, registry = _orchestrator(analyzer, audit)

    with pytest.raises(NarrativeAnalysisError):
        asyncio.run(orchestrator.analyze_scene(scene_request))

    assert registry.loads == []
    assert audit.events == []
    assert analyzer.calls == []


def test_duplicate_or_blank_known_identity_keys_are_rejected_before_prompt_load() -> None:
    from narrative_analysis_agent import KnownIdentity

    requests = (
        SceneAnalysisRequest(
            "project",
            "scene",
            0,
            0,
            "text",
            known_entities=(KnownIdentity(" ", "one", "One"),),
        ),
        SceneAnalysisRequest(
            "project",
            "scene",
            0,
            0,
            "text",
            known_entities=(KnownIdentity("same", "one", "One"),),
            known_places=(KnownIdentity("same", "place", "Place"),),
        ),
    )
    for request in requests:
        audit = RecordingAudit()
        analyzer = ScriptedAnalyzer([])
        orchestrator, registry = _orchestrator(analyzer, audit)

        with pytest.raises(NarrativeAnalysisError):
            asyncio.run(orchestrator.analyze_scene(request))

        assert registry.loads == []
        assert audit.events == []
        assert analyzer.calls == []


class FailingPromptRegistry(StubPromptRegistry):
    def load(self, prompt_id: str) -> PromptDefinition:
        self.loads.append(prompt_id)
        raise RuntimeError("secret prompt failure")


class FailingAudit(RecordingAudit):
    def __init__(self, failure: str | type[RunEvent | AttemptEvent]) -> None:
        super().__init__()
        self.failure = failure

    def register_prompt(self, prompt: PromptDefinition) -> None:
        if self.failure == "register_prompt":
            raise RuntimeError("secret prompt conflict")
        super().register_prompt(prompt)

    def append_run_event(self, event: RunEvent) -> None:
        if type(event) is self.failure:
            raise RuntimeError("secret audit failure")
        super().append_run_event(event)

    def append_attempt_event(self, event: AttemptEvent) -> None:
        if type(event) is self.failure:
            raise RuntimeError("secret audit failure")
        super().append_attempt_event(event)


def test_prompt_load_failure_prevents_analyzer_calls_and_hides_details() -> None:
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer([])
    orchestrator, _ = _orchestrator(analyzer, audit, FailingPromptRegistry())

    with pytest.raises(PromptLoadError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert captured.value.run_id is None
    assert captured.value.args == ("unable to load scene analysis prompt",)
    assert captured.value.__cause__ is None
    assert "secret" not in "".join(
        traceback.format_exception(captured.type, captured.value, captured.tb)
    )
    assert analyzer.calls == []
    assert audit.events == []


@pytest.mark.parametrize(
    ("failure", "expected_events"),
    [
        ("register_prompt", []),
        (RunStarted, []),
        (AttemptStarted, ["run_started", "run_failed"]),
    ],
)
def test_pre_call_audit_failure_blocks_analyzer(
    failure: str | type[RunEvent | AttemptEvent],
    expected_events: list[str],
) -> None:
    audit = FailingAudit(failure)
    analyzer = ScriptedAnalyzer([_result(SceneChunkExtraction("unused"))])
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(AnalysisAuditError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert captured.value.run_id == "run-01"
    assert "secret" not in str(captured.value)
    assert analyzer.calls == []
    assert audit.event_types == expected_events


@pytest.mark.parametrize("failure", [AttemptSucceeded, RunSucceeded])
def test_terminal_audit_failure_is_surfaced_without_returning_snapshot(
    failure: type[RunEvent | AttemptEvent],
) -> None:
    audit = FailingAudit(failure)
    analyzer = ScriptedAnalyzer([_result(SceneChunkExtraction("result"))])
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(AnalysisAuditError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert captured.value.run_id == "run-01"
    assert not any(isinstance(event, RunSucceeded) for event in audit.events)
    assert isinstance(audit.events[-1], RunFailed)


def test_attempt_failure_audit_error_is_surfaced_and_run_failure_is_recorded() -> None:
    audit = FailingAudit(AttemptFailed)
    analyzer = ScriptedAnalyzer([UnexpectedAnalyzerError("secret provider body")])
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(AnalysisAuditError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert captured.value.run_id == "run-01"
    assert analyzer.calls[0].chunk_id == "scene-01:r1:0000"
    assert audit.event_types == ["run_started", "attempt_started", "run_failed"]
    assert "secret provider body" not in "".join(
        traceback.format_exception(captured.type, captured.value, captured.tb)
    )


def test_run_failure_audit_error_replaces_analysis_error_without_secret_leak() -> None:
    audit = FailingAudit(RunFailed)
    analyzer = ScriptedAnalyzer(
        [_ProviderCallError("secret one"), _ProviderCallError("secret two")]
    )
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(AnalysisAuditError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert captured.value.run_id == "run-01"
    assert captured.value.args == ("unable to record scene analysis failure",)
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert "secret one" not in formatted
    assert "secret two" not in formatted
    assert not any(isinstance(event, RunSucceeded) for event in audit.events)


class AttemptSuccessTerminalAudit(RecordingAudit):
    def __init__(self, *, fail_fallback: bool) -> None:
        super().__init__()
        self.fail_fallback = fail_fallback
        self.terminal_append_calls: list[type[AttemptEvent]] = []

    def append_attempt_event(self, event: AttemptEvent) -> None:
        if isinstance(event, (AttemptSucceeded, AttemptFailed)):
            self.terminal_append_calls.append(type(event))
        if isinstance(event, AttemptSucceeded):
            raise RuntimeError("SECRET_SYSTEM_PROMPT SECRET_RESPONSE_BODY")
        if self.fail_fallback and isinstance(event, AttemptFailed):
            raise RuntimeError("SECRET_SYSTEM_PROMPT SECRET_RESPONSE_BODY")
        super().append_attempt_event(event)


class PersistThenRaiseAudit:
    def __init__(self, delegate: SQLiteAgentAudit) -> None:
        self.delegate = delegate
        self.terminal_append_calls: list[type[AttemptEvent]] = []

    def register_prompt(self, prompt: PromptDefinition) -> None:
        self.delegate.register_prompt(prompt)

    def append_run_event(self, event: RunEvent) -> None:
        self.delegate.append_run_event(event)

    def append_attempt_event(self, event: AttemptEvent) -> None:
        if isinstance(event, (AttemptSucceeded, AttemptFailed)):
            self.terminal_append_calls.append(type(event))
        self.delegate.append_attempt_event(event)
        if isinstance(event, AttemptSucceeded):
            raise RuntimeError("SECRET_SYSTEM_PROMPT SECRET_RESPONSE_BODY")


@pytest.mark.parametrize("fail_fallback", [False, True])
def test_attempt_success_audit_failure_uses_one_best_effort_failure_fallback(
    fail_fallback: bool,
) -> None:
    response = b'[{"content":"SECRET_RESPONSE_BODY"}]'
    audit = AttemptSuccessTerminalAudit(fail_fallback=fail_fallback)
    analyzer = ScriptedAnalyzer([_result(SceneChunkExtraction("result"), response)])
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(AnalysisAuditError) as captured:
        asyncio.run(orchestrator.analyze_scene(_request()))

    assert audit.terminal_append_calls == [AttemptSucceeded, AttemptFailed]
    assert isinstance(audit.events[-1], RunFailed)
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert "SECRET_SYSTEM_PROMPT" not in formatted
    assert "SECRET_RESPONSE_BODY" not in formatted


def test_persisted_attempt_success_rejects_fallback_terminal_event(tmp_path: Path) -> None:
    path = tmp_path / "agent-audit.sqlite3"
    stored_audit = SQLiteAgentAudit(path)
    stored_audit.initialize()
    audit = PersistThenRaiseAudit(stored_audit)
    analyzer = ScriptedAnalyzer(
        [_result(SceneChunkExtraction("result"), b'[{"content":"SECRET_RESPONSE_BODY"}]')]
    )
    registry = StubPromptRegistry()
    ticks = iter((1.0, 1.125))
    orchestrator = SceneAnalysisOrchestrator(
        analyzer=analyzer,
        prompt_registry=registry,
        audit=audit,
        run_id_factory=lambda: "run-persisted-terminal",
        clock=lambda: NOW,
        monotonic=lambda: next(ticks),
    )

    with pytest.raises(AnalysisAuditError) as captured:
        asyncio.run(
            orchestrator.analyze_scene(SceneAnalysisRequest("project", "scene", 0, 0, "text"))
        )

    assert audit.terminal_append_calls == [AttemptSucceeded, AttemptFailed]
    with sqlite3.connect(path) as connection:
        attempt_types = connection.execute(
            "SELECT event_type FROM attempt_events ORDER BY event_sequence"
        ).fetchall()
        run_types = connection.execute(
            "SELECT event_type FROM run_events ORDER BY event_sequence"
        ).fetchall()
        terminal_count = connection.execute(
            """
            SELECT COUNT(*) FROM attempt_events
            WHERE run_id = 'run-persisted-terminal'
              AND chunk_id = 'scene:r0:0000'
              AND attempt_number = 1
              AND event_type IN ('attempt_succeeded', 'attempt_failed')
            """
        ).fetchone()
    assert attempt_types == [("attempt_started",), ("attempt_succeeded",)]
    assert terminal_count == (1,)
    assert run_types == [("run_started",), ("run_failed",)]
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert captured.value.__cause__ is None
    assert captured.value.args == ("unable to record scene analysis attempt failure",)
    assert captured.value.run_id == "run-persisted-terminal"
    assert "SECRET_SYSTEM_PROMPT" not in formatted
    assert "SECRET_RESPONSE_BODY" not in formatted


def test_terminal_chunk_failure_stops_later_chunks() -> None:
    audit = RecordingAudit()
    analyzer = ScriptedAnalyzer([_ProviderCallError("one"), _ProviderCallError("two")])
    orchestrator, _ = _orchestrator(analyzer, audit)

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(orchestrator.analyze_scene(_request("x" * 350)))

    assert [call.chunk_id for call in analyzer.calls] == [
        "scene-01:r1:0000",
        "scene-01:r1:0000",
    ]


def test_cancellation_is_best_effort_audited_and_reraised() -> None:
    for audit in (RecordingAudit(), FailingAudit(RunFailed)):
        analyzer = ScriptedAnalyzer([asyncio.CancelledError()])
        orchestrator, _ = _orchestrator(analyzer, audit)

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(orchestrator.analyze_scene(_request()))

        assert audit.event_types[:2] == ["run_started", "attempt_started"]
        if type(audit) is RecordingAudit:
            assert audit.event_types == [
                "run_started",
                "attempt_started",
                "attempt_failed",
                "run_failed",
            ]
