import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime

from apps.narrative_memory.repository.analysis_audit import (
    AgentAuditPort,
    AttemptFailed,
    AttemptStarted,
    AttemptSucceeded,
    RunFailed,
    RunStarted,
    RunSucceeded,
)
from apps.narrative_memory.service.chunking import SceneChunk, chunk_scene
from apps.narrative_memory.service.merge import merge_chunk_analyses
from apps.narrative_memory.service.models import ChunkAnalysis, SceneRelationshipSnapshot
from apps.narrative_memory.service.scene_analysis_ports import (
    PromptRegistryPort,
    ProviderCallError,
    SceneAnalysisAgentPort,
    SceneAnalysisCall,
)
from apps.narrative_memory.service.scene_analysis_translation import (
    ExtractionTranslationError,
    translate_chunk_extraction,
)
from apps.narrative_memory.service.scene_analysis_types import (
    AnalyzeSceneRequest,
    KnownIdentity,
    encode_scene_chunk_extraction,
)

_PROMPT_ID = "scene-analysis"
_PROVIDER_FAILURE_MESSAGE = "scene analysis provider call failed"


class SceneAnalysisError(RuntimeError):
    def __init__(self, message: str, *, audit_error_type: str | None = None) -> None:
        super().__init__(message)
        self.audit_error_type = audit_error_type


class SceneAnalysisProviderError(SceneAnalysisError):
    pass


class SceneAnalysisAuditError(SceneAnalysisError):
    pass


class SceneAnalysisService:
    def __init__(
        self,
        agent: SceneAnalysisAgentPort,
        prompt_registry: PromptRegistryPort,
        audit: AgentAuditPort,
        run_id_factory: Callable[[], str],
        clock: Callable[[], datetime],
        monotonic: Callable[[], float],
    ) -> None:
        self._agent = agent
        self._prompt_registry = prompt_registry
        self._audit = audit
        self._run_id_factory = run_id_factory
        self._clock = clock
        self._monotonic = monotonic

    async def analyze_scene(self, request: AnalyzeSceneRequest) -> SceneRelationshipSnapshot:
        _validate_request(request)
        try:
            prompt = self._prompt_registry.load(_PROMPT_ID)
        except Exception as error:
            raise SceneAnalysisError("unable to load scene analysis prompt") from error

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
                    model_name=self._agent.model_name,
                    prompt_id=prompt.prompt_id,
                    prompt_version=prompt.version,
                    occurred_at=self._clock(),
                )
            )
        except Exception as error:
            raise SceneAnalysisAuditError("unable to start scene analysis audit") from error

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
        except SceneAnalysisAuditError as error:
            self._record_run_failure(run_id, type(error).__name__)
            raise
        except ProviderCallError as error:
            self._record_run_failure(run_id, type(error).__name__)
            raise SceneAnalysisProviderError(_PROVIDER_FAILURE_MESSAGE) from error
        except ExtractionTranslationError as error:
            self._record_run_failure(run_id, type(error).__name__)
            raise SceneAnalysisError("scene analysis extraction is invalid") from error
        except SceneAnalysisError as error:
            self._record_run_failure(
                run_id,
                error.audit_error_type or type(error).__name__,
            )
            raise
        except Exception as error:
            service_error = SceneAnalysisError("scene analysis failed")
            self._record_run_failure(run_id, type(error).__name__)
            raise service_error from error

        encoded_snapshot = _encode_scene_snapshot(snapshot)
        try:
            self._audit.append_run_event(
                RunSucceeded(
                    run_id=run_id,
                    occurred_at=self._clock(),
                    scene_snapshot_json=encoded_snapshot,
                )
            )
        except Exception as error:
            audit_error = SceneAnalysisAuditError("unable to complete scene analysis audit")
            self._record_run_failure(run_id, type(audit_error).__name__)
            raise audit_error from error
        return snapshot

    async def _analyze_chunk(
        self,
        run_id: str,
        request: AnalyzeSceneRequest,
        system_prompt: str,
        chunk: SceneChunk,
    ) -> ChunkAnalysis:
        call = SceneAnalysisCall(
            chunk_id=chunk.chunk_id,
            system_prompt=system_prompt,
            user_prompt=_render_user_prompt(request, chunk),
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
            except Exception as error:
                raise SceneAnalysisAuditError("unable to start scene analysis attempt") from error

            started_at = self._monotonic()
            try:
                result = await self._agent.analyze(call)
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
            except ProviderCallError as error:
                latency_ms = (self._monotonic() - started_at) * 1000
                self._append_attempt_failure(
                    run_id=run_id,
                    chunk=chunk,
                    attempt_number=attempt_number,
                    latency_ms=latency_ms,
                    error_type=type(error).__name__,
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
                raise SceneAnalysisError(
                    "scene analysis agent call failed",
                    audit_error_type=type(error).__name__,
                ) from None

            latency_ms = (self._monotonic() - started_at) * 1000
            try:
                extraction_json = encode_scene_chunk_extraction(result.extraction)
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
                raise SceneAnalysisError(
                    "scene analysis extraction result is invalid",
                    audit_error_type=type(error).__name__,
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
                raise SceneAnalysisAuditError(
                    "unable to record scene analysis attempt success"
                ) from error
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
        except Exception as error:
            error.__suppress_context__ = True
            raise SceneAnalysisAuditError(
                "unable to record scene analysis attempt failure"
            ) from error

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
        except Exception as error:
            raise SceneAnalysisAuditError("unable to record scene analysis failure") from error

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


def _validate_request(request: AnalyzeSceneRequest) -> None:
    if not request.project_id.strip():
        raise SceneAnalysisError("project ID must not be blank")
    if not request.scene_id.strip():
        raise SceneAnalysisError("scene ID must not be blank")
    if request.scene_revision < 0:
        raise SceneAnalysisError("scene revision must be nonnegative")
    if request.scene_sequence < 0:
        raise SceneAnalysisError("scene sequence must be nonnegative")
    _validate_identity_keys((*request.known_entities, *request.known_places))


def _validate_identity_keys(identities: tuple[KnownIdentity, ...]) -> None:
    keys = [identity.identity_key for identity in identities]
    if any(not key.strip() for key in keys):
        raise SceneAnalysisError("known identity keys must not be blank")
    if len(set(keys)) != len(keys):
        raise SceneAnalysisError("known identity keys must be unique")


def _render_user_prompt(request: AnalyzeSceneRequest, chunk: SceneChunk) -> str:
    def catalog(identities: tuple[KnownIdentity, ...]) -> list[dict[str, object]]:
        return [
            {
                "identity_key": identity.identity_key,
                "normalized_name": identity.normalized_name,
                "display_name": identity.display_name,
                "aliases": list(identity.aliases),
            }
            for identity in sorted(identities, key=lambda item: item.identity_key)
        ]

    return json.dumps(
        {
            "project_id": request.project_id,
            "scene_id": request.scene_id,
            "scene_revision": request.scene_revision,
            "scene_sequence": request.scene_sequence,
            "chunk": {
                "chunk_id": chunk.chunk_id,
                "ordinal": chunk.ordinal,
                "start_offset": chunk.start_offset,
                "end_offset": chunk.end_offset,
                "content_hash": chunk.content_hash,
                "text": chunk.text,
            },
            "known_entities": catalog(request.known_entities),
            "known_places": catalog(request.known_places),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _encode_scene_snapshot(snapshot: SceneRelationshipSnapshot) -> bytes:
    return json.dumps(
        asdict(snapshot),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
