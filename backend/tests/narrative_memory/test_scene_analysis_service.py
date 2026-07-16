import asyncio
import json
import traceback
from datetime import UTC, datetime

import pytest

from apps.narrative_memory.repository.analysis_audit import (
    AgentAuditPort,
    AttemptEvent,
    AttemptFailed,
    AttemptStarted,
    AttemptSucceeded,
    PromptVersionConflict,
    RunEvent,
    RunFailed,
    RunStarted,
    RunSucceeded,
)
from apps.narrative_memory.service.chunking import chunk_scene
from apps.narrative_memory.service.scene_analysis import (
    SceneAnalysisAuditError,
    SceneAnalysisError,
    SceneAnalysisProviderError,
    SceneAnalysisService,
)
from apps.narrative_memory.service.scene_analysis_ports import (
    PromptDefinition,
    ProviderCallError,
    SceneAnalysisCall,
)
from apps.narrative_memory.service.scene_analysis_types import (
    AgentInvocationResult,
    AgentUsage,
    AnalyzeSceneRequest,
    ExtractedEntity,
    ExtractedRelationshipEvent,
    KnownIdentity,
    RelativeEvidence,
    SceneChunkExtraction,
)
from infrastructure.llm.prompt_registry import render_scene_analysis_user_prompt

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
        return [
            {
                RunStarted: "run_started",
                RunFailed: "run_failed",
                RunSucceeded: "run_succeeded",
                AttemptStarted: "attempt_started",
                AttemptFailed: "attempt_failed",
                AttemptSucceeded: "attempt_succeeded",
            }[type(event)]
            for event in self.events
        ]


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


class ScriptedAgent:
    model_name = "configured-model"

    def __init__(self, results: list[AgentInvocationResult | BaseException]) -> None:
        self._results = iter(results)
        self.calls: list[SceneAnalysisCall] = []

    async def analyze(self, call: SceneAnalysisCall) -> AgentInvocationResult:
        self.calls.append(call)
        result = next(self._results)
        if isinstance(result, BaseException):
            raise result
        return result


def _result(extraction: SceneChunkExtraction, response: bytes = b"[]") -> AgentInvocationResult:
    return AgentInvocationResult(
        extraction=extraction,
        response_messages_json=response,
        usage=AgentUsage(requests=1, input_tokens=10, output_tokens=5),
        provider_name="resolved-provider",
        model_name="resolved-model",
    )


def _service(
    agent: ScriptedAgent, audit: RecordingAudit
) -> tuple[SceneAnalysisService, StubPromptRegistry]:
    registry = StubPromptRegistry()
    ticks = iter((1.0, 1.125, 2.0, 2.25))
    service = SceneAnalysisService(
        agent=agent,
        prompt_registry=registry,
        audit=audit,
        run_id_factory=lambda: "run-01",
        clock=lambda: NOW,
        monotonic=lambda: next(ticks),
    )
    return service, registry


def test_empty_scene_is_audited_success_without_agent_calls() -> None:
    audit = RecordingAudit()
    agent = ScriptedAgent([])
    service, registry = _service(agent, audit)

    snapshot = asyncio.run(
        service.analyze_scene(AnalyzeSceneRequest("project-01", "scene-01", 1, 4, ""))
    )

    assert registry.loads == ["scene-analysis"]
    assert audit.prompts == [registry.prompt]
    assert agent.calls == []
    assert audit.event_types == ["run_started", "run_succeeded"]
    started = audit.events[0]
    assert isinstance(started, RunStarted)
    assert started.model_name == "configured-model"
    assert started.provider_name is None
    assert snapshot.scene_id == "scene-01"
    assert snapshot.scene_revision == 1
    assert snapshot.scene_sequence == 4
    assert snapshot.summary == ""
    assert snapshot.entities == ()
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
    agent = ScriptedAgent(
        [_result(extraction, b'[{"chunk":0}]'), _result(extraction, b'[{"chunk":1}]')]
    )
    audit = RecordingAudit()
    service, registry = _service(agent, audit)
    request = AnalyzeSceneRequest("project-01", "scene-01", 1, 4, text)

    result = asyncio.run(service.analyze_scene(request))

    assert [call.chunk_id for call in agent.calls] == [
        "scene-01:r1:0000",
        "scene-01:r1:0001",
    ]
    assert result.scene_id == "scene-01"
    assert result.scene_revision == 1
    assert result.scene_sequence == 4
    assert len(result.entities) == 1
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
    assert [event.user_message for event in starts] == [
        render_scene_analysis_user_prompt(request, chunk)
        for chunk in chunk_scene("scene-01", 1, text)
    ]
    successes = [event for event in audit.events if isinstance(event, AttemptSucceeded)]
    assert [event.response_messages_json for event in successes] == [
        b'[{"chunk":0}]',
        b'[{"chunk":1}]',
    ]
    canonical_extraction = (
        b'{"entities":[{"aliases":[],"display_name":"Alex","evidence":'
        b'[{"end_offset":4,"start_offset":0,"text":"Alex"}],"local_ref":"alex",'
        b'"normalized_name":"alex"}],"location_events":[],"places":[],'
        b'"relationship_events":[],"summary":"Alex appears."}'
    )
    assert [event.validated_extraction_json for event in successes] == [
        canonical_extraction,
        canonical_extraction,
    ]
    assert [event.latency_ms for event in successes] == [125.0, 250.0]


def test_provider_failure_is_retried_once_then_succeeds() -> None:
    audit = RecordingAudit()
    agent = ScriptedAgent(
        [ProviderCallError("secret provider detail"), _result(SceneChunkExtraction("ok"))]
    )
    service, _ = _service(agent, audit)

    snapshot = asyncio.run(
        service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "text"))
    )

    assert snapshot.summary == "ok"
    assert len(agent.calls) == 2
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "attempt_started",
        "attempt_succeeded",
        "run_succeeded",
    ]
    failed = next(event for event in audit.events if isinstance(event, AttemptFailed))
    assert failed.attempt_number == 1
    assert failed.error_message == "scene analysis provider call failed"
    assert "secret" not in failed.error_message


def test_two_provider_failures_fail_the_run_without_a_snapshot() -> None:
    audit = RecordingAudit()
    agent = ScriptedAgent([ProviderCallError("secret one"), ProviderCallError("secret two")])
    service, _ = _service(agent, audit)

    with pytest.raises(SceneAnalysisProviderError) as captured:
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "text")))

    assert len(agent.calls) == 2
    assert "secret" not in str(captured.value)
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "attempt_started",
        "attempt_failed",
        "run_failed",
    ]
    assert not any(isinstance(event, RunSucceeded) for event in audit.events)
    failed_run = audit.events[-1]
    assert isinstance(failed_run, RunFailed)
    assert failed_run.error_type == "ProviderCallError"


def test_translation_failure_is_not_retried() -> None:
    extraction = SceneChunkExtraction(
        summary="invalid",
        entities=(
            ExtractedEntity(
                local_ref="entity",
                normalized_name="entity",
                display_name="Entity",
                aliases=(),
                evidence=(RelativeEvidence(0, 1, "wrong"),),
            ),
        ),
    )
    audit = RecordingAudit()
    agent = ScriptedAgent([_result(extraction)])
    service, _ = _service(agent, audit)

    with pytest.raises(SceneAnalysisError, match="extraction is invalid"):
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "text")))

    assert len(agent.calls) == 1
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_succeeded",
        "run_failed",
    ]
    failed_run = audit.events[-1]
    assert isinstance(failed_run, RunFailed)
    assert failed_run.error_type == "ExtractionTranslationError"


def test_terminal_chunk_failure_stops_later_chunks() -> None:
    audit = RecordingAudit()
    agent = ScriptedAgent([ProviderCallError("one"), ProviderCallError("two")])
    service, _ = _service(agent, audit)

    with pytest.raises(SceneAnalysisProviderError):
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "x" * 350)))

    assert [call.chunk_id for call in agent.calls] == ["scene:r0:0000", "scene:r0:0000"]


class UnexpectedAgentError(RuntimeError):
    pass


def test_unexpected_agent_error_fails_attempt_once_without_retry_or_secret_leak() -> None:
    audit = RecordingAudit()
    agent = ScriptedAgent([UnexpectedAgentError("secret provider body")])
    service, _ = _service(agent, audit)

    with pytest.raises(SceneAnalysisError) as captured:
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "x" * 350)))

    assert [call.chunk_id for call in agent.calls] == ["scene:r0:0000"]
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "run_failed",
    ]
    failed_attempt = audit.events[-2]
    failed_run = audit.events[-1]
    assert isinstance(failed_attempt, AttemptFailed)
    assert failed_attempt.error_type == "UnexpectedAgentError"
    assert failed_attempt.error_message == "scene analysis agent call failed"
    assert isinstance(failed_run, RunFailed)
    assert failed_run.error_type == "UnexpectedAgentError"
    assert failed_run.error_message == "scene analysis failed"
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert "secret provider body" not in str(captured.value)
    assert "secret provider body" not in formatted
    assert not any(isinstance(event, RunSucceeded) for event in audit.events)


def test_non_json_extraction_fails_deterministically_before_attempt_success() -> None:
    extraction = SceneChunkExtraction(
        summary="invalid result",
        relationship_events=(
            ExtractedRelationshipEvent(
                subject_ref="subject",
                object_ref="object",
                category="romance",
                description="invalid confidence",
                confidence=float("nan"),
                evidence=(),
            ),
        ),
    )
    response = b'[{"content":"secret response body"}]'
    audit = RecordingAudit()
    agent = ScriptedAgent([_result(extraction, response)])
    service, _ = _service(agent, audit)

    with pytest.raises(SceneAnalysisError) as captured:
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "x" * 350)))

    assert [call.chunk_id for call in agent.calls] == ["scene:r0:0000"]
    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "run_failed",
    ]
    failed_attempt = audit.events[-2]
    failed_run = audit.events[-1]
    assert isinstance(failed_attempt, AttemptFailed)
    assert failed_attempt.error_type == "ValueError"
    assert failed_attempt.error_message == "scene analysis extraction result is invalid"
    assert failed_attempt.response_messages_json == response
    assert isinstance(failed_run, RunFailed)
    assert failed_run.error_type == "ValueError"
    assert "secret" not in failed_run.error_message
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert "secret response body" not in str(captured.value)
    assert "secret response body" not in formatted
    assert not any(isinstance(event, AttemptSucceeded) for event in audit.events)
    assert not any(isinstance(event, RunSucceeded) for event in audit.events)


@pytest.mark.parametrize(
    "scene_request",
    [
        AnalyzeSceneRequest("", "scene", 0, 0, "text"),
        AnalyzeSceneRequest("project", " ", 0, 0, "text"),
        AnalyzeSceneRequest("project", "scene", -1, 0, "text"),
        AnalyzeSceneRequest("project", "scene", 0, -1, "text"),
        AnalyzeSceneRequest(
            "project",
            "scene",
            0,
            0,
            "text",
            known_entities=(KnownIdentity("same", "one", "One"),),
            known_places=(KnownIdentity("same", "place", "Place"),),
        ),
    ],
)
def test_invalid_request_is_rejected_before_prompt_load(
    scene_request: AnalyzeSceneRequest,
) -> None:
    audit = RecordingAudit()
    agent = ScriptedAgent([])
    service, registry = _service(agent, audit)

    with pytest.raises(SceneAnalysisError):
        asyncio.run(service.analyze_scene(scene_request))

    assert registry.loads == []
    assert audit.events == []
    assert agent.calls == []


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
            raise PromptVersionConflict("secret prompt conflict")
        super().register_prompt(prompt)

    def append_run_event(self, event: RunEvent) -> None:
        if type(event) is self.failure:
            raise RuntimeError("secret audit failure")
        super().append_run_event(event)

    def append_attempt_event(self, event: AttemptEvent) -> None:
        if type(event) is self.failure:
            raise RuntimeError("secret audit failure")
        super().append_attempt_event(event)


def test_prompt_load_failure_occurs_before_agent_calls() -> None:
    audit = RecordingAudit()
    agent = ScriptedAgent([])
    service = SceneAnalysisService(
        agent,
        FailingPromptRegistry(),
        audit,
        lambda: "run",
        lambda: NOW,
        lambda: 0.0,
    )

    with pytest.raises(SceneAnalysisError) as captured:
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "text")))

    assert "secret" not in str(captured.value)
    assert agent.calls == []
    assert audit.events == []


@pytest.mark.parametrize(
    ("failure", "expected_events"),
    [
        ("register_prompt", []),
        (RunStarted, []),
        (AttemptStarted, ["run_started", "run_failed"]),
    ],
)
def test_pre_call_audit_failure_prevents_model_call(
    failure: str | type[RunEvent | AttemptEvent], expected_events: list[str]
) -> None:
    audit = FailingAudit(failure)
    agent = ScriptedAgent([_result(SceneChunkExtraction("unused"))])
    service, _ = _service(agent, audit)

    with pytest.raises(SceneAnalysisAuditError) as captured:
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "text")))

    assert "secret" not in str(captured.value)
    assert agent.calls == []
    assert audit.event_types == expected_events


@pytest.mark.parametrize("failure", [AttemptSucceeded, RunSucceeded])
def test_terminal_audit_failure_is_surfaced_without_claiming_snapshot(
    failure: type[RunEvent | AttemptEvent],
) -> None:
    audit = FailingAudit(failure)
    agent = ScriptedAgent([_result(SceneChunkExtraction("result"))])
    service, _ = _service(agent, audit)

    with pytest.raises(SceneAnalysisAuditError):
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "text")))

    assert not any(isinstance(event, RunSucceeded) for event in audit.events)
    assert isinstance(audit.events[-1], RunFailed)


def test_attempt_failure_audit_error_surfaces_and_records_run_failure_once() -> None:
    audit = FailingAudit(AttemptFailed)
    agent = ScriptedAgent([UnexpectedAgentError("secret provider body")])
    service, _ = _service(agent, audit)

    with pytest.raises(SceneAnalysisAuditError) as captured:
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "x" * 350)))

    assert [call.chunk_id for call in agent.calls] == ["scene:r0:0000"]
    assert audit.event_types == ["run_started", "attempt_started", "run_failed"]
    assert sum(isinstance(event, AttemptStarted) for event in audit.events) == 1
    assert sum(isinstance(event, AttemptFailed) for event in audit.events) == 0
    failed_run = audit.events[-1]
    assert isinstance(failed_run, RunFailed)
    assert failed_run.error_type == "SceneAnalysisAuditError"
    assert "secret" not in str(captured.value)
    formatted = "".join(traceback.format_exception(captured.type, captured.value, captured.tb))
    assert "secret provider body" not in formatted
    assert not any(isinstance(event, RunSucceeded) for event in audit.events)


def test_cancellation_is_recorded_when_possible_and_reraised() -> None:
    audit = RecordingAudit()
    agent = ScriptedAgent([asyncio.CancelledError()])
    service, _ = _service(agent, audit)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "text")))

    assert audit.event_types == [
        "run_started",
        "attempt_started",
        "attempt_failed",
        "run_failed",
    ]
    cancelled_attempt = audit.events[-2]
    assert isinstance(cancelled_attempt, AttemptFailed)
    assert cancelled_attempt.error_type == "CancelledError"
    cancelled = audit.events[-1]
    assert isinstance(cancelled, RunFailed)
    assert cancelled.error_type == "CancelledError"


def test_cancellation_is_reraised_when_cancellation_audit_fails() -> None:
    audit = FailingAudit(RunFailed)
    agent = ScriptedAgent([asyncio.CancelledError()])
    service, _ = _service(agent, audit)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service.analyze_scene(AnalyzeSceneRequest("project", "scene", 0, 0, "text")))
