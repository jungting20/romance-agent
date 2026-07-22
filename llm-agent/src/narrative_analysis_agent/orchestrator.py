import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime

from narrative_analysis_agent.assembly.merge import merge_chunk_analyses
from narrative_analysis_agent.assembly.models import ChunkAnalysis, SceneChunkExtraction
from narrative_analysis_agent.assembly.translation import (
    ExtractionTranslationError,
    translate_chunk_extraction,
)
from narrative_analysis_agent.assembly.validation import MergeInvariantError
from narrative_analysis_agent.audit.ports import (
    AgentAuditPort,
    AttemptFailed,
    AttemptStarted,
    AttemptSucceeded,
    RunFailed,
    RunStarted,
    RunSucceeded,
)
from narrative_analysis_agent.chunking import SceneChunk, chunk_scene
from narrative_analysis_agent.contracts import (
    KnownIdentity,
    SceneAnalysisRequest,
    SceneAnalysisResult,
    SceneRelationshipSnapshot,
)
from narrative_analysis_agent.errors import (
    AnalysisAuditError,
    InvalidExtractionError,
    NarrativeAnalysisError,
    PromptLoadError,
    ProviderUnavailableError,
)
from narrative_analysis_agent.extraction.agent import (
    ChunkAnalysisCall,
    ChunkAnalyzerPort,
    _InvalidExtractionOutputError,
    _ProviderCallError,
)
from narrative_analysis_agent.extraction.prompts import (
    PromptRegistryPort,
    render_scene_analysis_user_prompt,
)

_PROMPT_ID = "scene-analysis"
_PROVIDER_FAILURE_MESSAGE = "scene analysis provider call failed"


class _AnalysisFailure(Exception):
    def __init__(self, public_error: NarrativeAnalysisError, audit_error_type: str) -> None:
        super().__init__()
        self.public_error = public_error
        self.audit_error_type = audit_error_type


class SceneAnalysisOrchestrator:
    def __init__(
        self,
        analyzer: ChunkAnalyzerPort,
        prompt_registry: PromptRegistryPort,
        audit: AgentAuditPort,
        run_id_factory: Callable[[], str],
        clock: Callable[[], datetime],
        monotonic: Callable[[], float],
    ) -> None:
        self._analyzer = analyzer
        self._prompt_registry = prompt_registry
        self._audit = audit
        self._run_id_factory = run_id_factory
        self._clock = clock
        self._monotonic = monotonic

    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysisResult:
        _validate_request(request)
        try:
            prompt = self._prompt_registry.load(_PROMPT_ID)
        except Exception:
            raise PromptLoadError("unable to load scene analysis prompt") from None

        run_id = self._run_id_factory()
        try:
            self._audit.register_prompt(prompt)
            self._audit.append_run_event(
                RunStarted(
                    run_id=run_id,
                    project_id=request.project_id,
                    scene_id=request.scene_id,
                    scene_revision=request.scene_revision,
                    scene_sequence=request.scene_sequence,
                    model_name=self._analyzer.model_name,
                    prompt_id=prompt.prompt_id,
                    prompt_version=prompt.version,
                    occurred_at=self._clock(),
                )
            )
        except Exception:
            raise AnalysisAuditError(
                "unable to start scene analysis audit",
                run_id=run_id,
            ) from None

        analyses: list[ChunkAnalysis] = []
        try:
            for chunk in chunk_scene(request.scene_id, request.scene_revision, request.text):
                analyses.append(await self._analyze_chunk(run_id, request, prompt.body, chunk))
            snapshot = merge_chunk_analyses(
                request.scene_id,
                request.scene_revision,
                request.scene_sequence,
                analyses,
            )
        except asyncio.CancelledError:
            self._record_cancellation(run_id)
            raise
        except AnalysisAuditError as error:
            self._record_run_failure(run_id, type(error).__name__)
            raise
        except _InvalidExtractionOutputError:
            self._record_run_failure(run_id, "InvalidExtractionError")
            raise InvalidExtractionError(
                "scene analysis extraction is invalid",
                run_id=run_id,
            ) from None
        except _ProviderCallError:
            self._record_run_failure(run_id, "ProviderCallError")
            raise ProviderUnavailableError(_PROVIDER_FAILURE_MESSAGE, run_id=run_id) from None
        except (ExtractionTranslationError, MergeInvariantError) as error:
            self._record_run_failure(run_id, type(error).__name__)
            raise InvalidExtractionError(
                "scene analysis extraction is invalid",
                run_id=run_id,
            ) from None
        except _AnalysisFailure as error:
            self._record_run_failure(run_id, error.audit_error_type)
            raise error.public_error from None
        except Exception as error:
            self._record_run_failure(run_id, type(error).__name__)
            raise NarrativeAnalysisError("scene analysis failed", run_id=run_id) from None

        try:
            self._audit.append_run_event(
                RunSucceeded(
                    run_id=run_id,
                    occurred_at=self._clock(),
                    scene_snapshot_json=_encode_scene_snapshot(snapshot),
                )
            )
        except Exception:
            audit_error = AnalysisAuditError(
                "unable to complete scene analysis audit",
                run_id=run_id,
            )
            self._record_run_failure(run_id, type(audit_error).__name__)
            raise audit_error from None
        return SceneAnalysisResult(run_id=run_id, snapshot=snapshot)

    async def _analyze_chunk(
        self,
        run_id: str,
        request: SceneAnalysisRequest,
        system_prompt: str,
        chunk: SceneChunk,
    ) -> ChunkAnalysis:
        call = ChunkAnalysisCall(
            chunk_id=chunk.chunk_id,
            system_prompt=system_prompt,
            user_prompt=render_scene_analysis_user_prompt(request, chunk),
        )
        for attempt_number in (1, 2):
            try:
                self._audit.append_attempt_event(
                    AttemptStarted(
                        run_id=run_id,
                        chunk_id=chunk.chunk_id,
                        attempt_number=attempt_number,
                        occurred_at=self._clock(),
                        system_message=system_prompt,
                        user_message=call.user_prompt,
                    )
                )
            except Exception:
                raise AnalysisAuditError(
                    "unable to start scene analysis attempt",
                    run_id=run_id,
                ) from None

            started_at = self._monotonic()
            try:
                result = await self._analyzer.analyze(call)
            except asyncio.CancelledError:
                with suppress(Exception):
                    self._audit.append_attempt_event(
                        AttemptFailed(
                            run_id=run_id,
                            chunk_id=chunk.chunk_id,
                            attempt_number=attempt_number,
                            occurred_at=self._clock(),
                            latency_ms=(self._monotonic() - started_at) * 1000,
                            error_type="CancelledError",
                            error_message="scene analysis cancelled",
                        )
                    )
                raise
            except _InvalidExtractionOutputError:
                self._append_attempt_failure(
                    run_id=run_id,
                    chunk=chunk,
                    attempt_number=attempt_number,
                    latency_ms=(self._monotonic() - started_at) * 1000,
                    error_type="InvalidExtractionError",
                    error_message="scene analysis extraction is invalid",
                )
                raise
            except _ProviderCallError:
                self._append_attempt_failure(
                    run_id=run_id,
                    chunk=chunk,
                    attempt_number=attempt_number,
                    latency_ms=(self._monotonic() - started_at) * 1000,
                    error_type="ProviderCallError",
                    error_message=_PROVIDER_FAILURE_MESSAGE,
                )
                if attempt_number == 2:
                    raise
                continue
            except Exception as error:
                self._append_attempt_failure(
                    run_id=run_id,
                    chunk=chunk,
                    attempt_number=attempt_number,
                    latency_ms=(self._monotonic() - started_at) * 1000,
                    error_type=type(error).__name__,
                    error_message="scene analysis agent call failed",
                )
                raise _AnalysisFailure(
                    NarrativeAnalysisError(
                        "scene analysis agent call failed",
                        run_id=run_id,
                    ),
                    type(error).__name__,
                ) from None

            latency_ms = (self._monotonic() - started_at) * 1000
            try:
                extraction_json = _encode_chunk_extraction(result.extraction)
            except (TypeError, ValueError) as error:
                self._append_attempt_failure(
                    run_id=run_id,
                    chunk=chunk,
                    attempt_number=attempt_number,
                    latency_ms=latency_ms,
                    error_type=type(error).__name__,
                    error_message="scene analysis extraction result is invalid",
                    response_messages_json=result.response_messages_json,
                )
                raise _AnalysisFailure(
                    InvalidExtractionError(
                        "scene analysis extraction result is invalid",
                        run_id=run_id,
                    ),
                    type(error).__name__,
                ) from None
            try:
                self._audit.append_attempt_event(
                    AttemptSucceeded(
                        run_id=run_id,
                        chunk_id=chunk.chunk_id,
                        attempt_number=attempt_number,
                        occurred_at=self._clock(),
                        latency_ms=latency_ms,
                        response_messages_json=result.response_messages_json,
                        validated_extraction_json=extraction_json,
                        provider_name=result.provider_name,
                        model_name=result.model_name,
                        usage=result.usage,
                    )
                )
            except Exception as error:
                self._append_attempt_failure(
                    run_id=run_id,
                    chunk=chunk,
                    attempt_number=attempt_number,
                    latency_ms=latency_ms,
                    error_type=type(error).__name__,
                    error_message="unable to record scene analysis attempt success",
                    response_messages_json=result.response_messages_json,
                )
                raise AnalysisAuditError(
                    "unable to record scene analysis attempt success",
                    run_id=run_id,
                ) from None
            return translate_chunk_extraction(
                chunk,
                request.scene_sequence,
                result.extraction,
                request.known_entities,
                request.known_places,
            )

        raise AssertionError("unreachable")

    def _append_attempt_failure(
        self,
        *,
        run_id: str,
        chunk: SceneChunk,
        attempt_number: int,
        latency_ms: float,
        error_type: str,
        error_message: str,
        response_messages_json: bytes | None = None,
    ) -> None:
        try:
            self._audit.append_attempt_event(
                AttemptFailed(
                    run_id=run_id,
                    chunk_id=chunk.chunk_id,
                    attempt_number=attempt_number,
                    occurred_at=self._clock(),
                    latency_ms=latency_ms,
                    error_type=error_type,
                    error_message=error_message,
                    response_messages_json=response_messages_json,
                )
            )
        except Exception:
            raise AnalysisAuditError(
                "unable to record scene analysis attempt failure",
                run_id=run_id,
            ) from None

    def _record_run_failure(self, run_id: str, error_type: str) -> None:
        try:
            self._audit.append_run_event(
                RunFailed(
                    run_id=run_id,
                    occurred_at=self._clock(),
                    error_type=error_type,
                    error_message="scene analysis failed",
                )
            )
        except Exception:
            raise AnalysisAuditError(
                "unable to record scene analysis failure",
                run_id=run_id,
            ) from None

    def _record_cancellation(self, run_id: str) -> None:
        with suppress(Exception):
            self._audit.append_run_event(
                RunFailed(
                    run_id=run_id,
                    occurred_at=self._clock(),
                    error_type="CancelledError",
                    error_message="scene analysis cancelled",
                )
            )


def _validate_request(request: SceneAnalysisRequest) -> None:
    if not request.project_id.strip():
        raise NarrativeAnalysisError("project ID must not be blank")
    if not request.scene_id.strip():
        raise NarrativeAnalysisError("scene ID must not be blank")
    if request.scene_revision < 0:
        raise NarrativeAnalysisError("scene revision must be nonnegative")
    if request.scene_sequence < 0:
        raise NarrativeAnalysisError("scene sequence must be nonnegative")
    _validate_identity_keys((*request.known_entities, *request.known_places))


def _validate_identity_keys(identities: tuple[KnownIdentity, ...]) -> None:
    keys = [identity.identity_key for identity in identities]
    if any(not key.strip() for key in keys):
        raise NarrativeAnalysisError("known identity keys must not be blank")
    if len(set(keys)) != len(keys):
        raise NarrativeAnalysisError("known identity keys must be unique")


def _encode_chunk_extraction(extraction: SceneChunkExtraction) -> bytes:
    return json.dumps(
        asdict(extraction),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _encode_scene_snapshot(snapshot: SceneRelationshipSnapshot) -> bytes:
    return json.dumps(
        asdict(snapshot),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
