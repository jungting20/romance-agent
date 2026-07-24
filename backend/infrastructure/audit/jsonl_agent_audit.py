"""Owner-only JSONL persistence for provider-independent agent audit events."""

import asyncio
import base64
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from llm_agent_audit import AgentAuditSink, AuditEvent, SensitiveAuditPayload


class AgentAuditConfigurationError(ValueError):
    """Raised when a sensitive audit-log configuration is unsafe."""


@dataclass(frozen=True, slots=True)
class AgentAuditLogConfig:
    directory: Path
    capture_sensitive_content: bool = False
    encryption_key: bytes | None = None
    encryption_key_id: str | None = None
    metadata_retention_days: int = 30
    sensitive_retention_days: int = 7

    def __post_init__(self) -> None:
        if self.metadata_retention_days <= 0 or self.sensitive_retention_days <= 0:
            raise AgentAuditConfigurationError("audit-log retention must be positive")
        if not self.capture_sensitive_content:
            return
        if self.encryption_key is None or len(self.encryption_key) != 32:
            raise AgentAuditConfigurationError("sensitive audit logging requires a 32-byte key")
        if self.encryption_key_id is None or not self.encryption_key_id.strip():
            raise AgentAuditConfigurationError("sensitive audit logging requires a key ID")


class _OwnerOnlyTimedRotatingFileHandler(TimedRotatingFileHandler):
    def _open(self):
        descriptor = os.open(
            self.baseFilename,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        os.fchmod(descriptor, 0o600)
        return os.fdopen(descriptor, self.mode, encoding="utf-8")

    def handleError(self, record: logging.LogRecord) -> None:
        raise


class JsonlAgentAuditSink(AgentAuditSink):
    """Stores sanitized metadata and opt-in encrypted raw audit content."""

    def __init__(
        self,
        config: AgentAuditLogConfig,
        *,
        nonce_factory: Callable[[int], bytes] = os.urandom,
    ) -> None:
        self._config = config
        self._nonce_factory = nonce_factory
        self.capture_sensitive_content = config.capture_sensitive_content
        self._config.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._config.directory, 0o700)
        self.metadata_logger, self._metadata_handler = _build_logger(
            path=config.directory / "llm-audit-metadata.jsonl",
            retention_days=config.metadata_retention_days,
        )
        self.sensitive_logger, self._sensitive_handler = _build_logger(
            path=config.directory / "llm-audit-sensitive.jsonl",
            retention_days=config.sensitive_retention_days,
        )
        self._aesgcm = AESGCM(config.encryption_key) if config.capture_sensitive_content else None

    async def append(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None:
        await asyncio.to_thread(self._append, event, sensitive)

    def _append(self, event: AuditEvent, sensitive: SensitiveAuditPayload | None) -> None:
        self.metadata_logger.info(_canonical_json(_event_data(event)))
        if not self.capture_sensitive_content or sensitive is None:
            return
        assert self._aesgcm is not None
        aad = json.dumps(
            {
                "schema_version": event.schema_version,
                "agent_name": event.agent_name,
                "run_id": event.run_id,
                "attempt_id": event.attempt_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        nonce = self._nonce_factory(12)
        ciphertext = self._aesgcm.encrypt(nonce, _sensitive_json(sensitive), aad)
        envelope = {
            "schema_version": event.schema_version,
            "agent_name": event.agent_name,
            "run_id": event.run_id,
            "attempt_id": event.attempt_id,
            "algorithm": "AES-256-GCM",
            "key_id": self._config.encryption_key_id,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        self.sensitive_logger.info(_canonical_json(envelope))

    def close(self) -> None:
        for logger, handler in (
            (self.metadata_logger, self._metadata_handler),
            (self.sensitive_logger, self._sensitive_handler),
        ):
            logger.removeHandler(handler)
            handler.close()


def _build_logger(
    *,
    path: Path,
    retention_days: int,
) -> tuple[logging.Logger, _OwnerOnlyTimedRotatingFileHandler]:
    logger = logging.getLogger(f"romance_agent.audit.{uuid4().hex}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = _OwnerOnlyTimedRotatingFileHandler(
        path,
        when="midnight",
        backupCount=retention_days,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger, handler


def _event_data(event: AuditEvent) -> dict[str, object]:
    return {
        "schema_version": event.schema_version,
        "event_type": event.event_type,
        "agent_name": event.agent_name,
        "run_id": event.run_id,
        "attempt_id": event.attempt_id,
        "model": {
            "requested_model": event.model.requested_model,
            "requested_provider": event.model.requested_provider,
            "settings": [
                [name, value]
                for name, value in event.model.settings
                if not _is_credential_setting(name)
            ],
        },
        "prompt": {
            "prompt_id": event.prompt.prompt_id,
            "version": event.prompt.version,
            "content_hash": event.prompt.content_hash,
        },
        "started_at": _datetime_text(event.started_at),
        **_finished_event_data(event),
    }


def _finished_event_data(event: AuditEvent) -> dict[str, object]:
    if event.event_type == "attempt_started":
        return {}
    return {
        "ended_at": _datetime_text(event.ended_at),
        "duration_ms": event.duration_ms,
        "status": event.status,
        "actual_provider": event.actual_provider,
        "actual_model": event.actual_model,
        "usage": None
        if event.usage is None
        else {
            "input_tokens": event.usage.input_tokens,
            "output_tokens": event.usage.output_tokens,
            "cache_read_tokens": event.usage.cache_read_tokens,
            "cache_write_tokens": event.usage.cache_write_tokens,
            "details": [list(detail) for detail in event.usage.details],
        },
        "error": None
        if event.error is None
        else {"code": event.error.code, "message": event.error.message},
    }


def _sensitive_json(sensitive: SensitiveAuditPayload) -> bytes:
    return _canonical_json(
        {
            "system_prompt": sensitive.system_prompt,
            "user_prompt": sensitive.user_prompt,
            "raw_response_json": _encoded_bytes(sensitive.raw_response_json),
            "validated_output_json": _encoded_bytes(sensitive.validated_output_json),
        }
    ).encode("utf-8")


def _encoded_bytes(value: bytes | None) -> str | None:
    return None if value is None else base64.b64encode(value).decode("ascii")


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _datetime_text(value: datetime) -> str:
    return value.isoformat()


def _is_credential_setting(name: str) -> bool:
    return any(
        marker in name.casefold()
        for marker in ("authorization", "credential", "key", "password", "secret", "token")
    )
