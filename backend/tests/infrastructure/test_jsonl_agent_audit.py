import asyncio
import base64
import json
import logging
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from llm_agent_audit import (
    AuditAttemptFinished,
    AuditAttemptStarted,
    ModelConfiguration,
    PromptIdentity,
    SensitiveAuditPayload,
    TokenUsage,
)

from infrastructure.audit.jsonl_agent_audit import (
    AgentAuditConfigurationError,
    AgentAuditLogConfig,
    JsonlAgentAuditSink,
)


def _started(
    *, settings: tuple[tuple[str, str | int | float | bool | None], ...] = ()
) -> AuditAttemptStarted:
    return AuditAttemptStarted(
        schema_version="llm-agent-audit-v1",
        event_type="attempt_started",
        agent_name="dialogue-generation",
        run_id="run-1",
        attempt_id="attempt-1",
        model=ModelConfiguration(
            requested_model="provider:model",
            requested_provider="provider",
            settings=settings,
        ),
        prompt=PromptIdentity.from_text("dialogue-generation.system", 1, "system secret"),
        started_at=datetime(2026, 7, 24, 9, 0, tzinfo=UTC),
    )


def _finished() -> AuditAttemptFinished:
    return AuditAttemptFinished(
        schema_version="llm-agent-audit-v1",
        event_type="attempt_finished",
        agent_name="dialogue-generation",
        run_id="run-1",
        attempt_id="attempt-1",
        model=ModelConfiguration(requested_model="provider:model", requested_provider="provider"),
        prompt=PromptIdentity.from_text("dialogue-generation.system", 1, "system secret"),
        started_at=datetime(2026, 7, 24, 9, 0, tzinfo=UTC),
        ended_at=datetime(2026, 7, 24, 9, 0, 1, tzinfo=UTC),
        duration_ms=1000.0,
        status="success",
        actual_provider="provider",
        actual_model="model",
        usage=TokenUsage(input_tokens=11, output_tokens=7),
        error=None,
    )


def _sensitive() -> SensitiveAuditPayload:
    return SensitiveAuditPayload(
        system_prompt="system secret",
        user_prompt="user secret",
        raw_response_json=b'{"raw":"secret"}',
        validated_output_json=b'{"value":"validated"}',
    )


def test_metadata_log_is_owner_only_canonical_jsonl_and_does_not_propagate(tmp_path: Path) -> None:
    config = AgentAuditLogConfig(directory=tmp_path / "private")
    sink = JsonlAgentAuditSink(config)

    asyncio.run(sink.append(_started()))
    sink.close()

    path = config.directory / "llm-audit-metadata.jsonl"
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["agent_name"] == "dialogue-generation"
    assert (
        text
        == json.dumps(
            payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    )
    assert "system secret" not in text
    assert stat.S_IMODE(config.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert sink.metadata_logger.propagate is False
    assert sink.metadata_logger.handlers == []


def test_raw_capture_is_disabled_and_sensitive_file_is_not_created(tmp_path: Path) -> None:
    config = AgentAuditLogConfig(directory=tmp_path / "private")
    sink = JsonlAgentAuditSink(config)

    assert sink.capture_sensitive_content is False
    asyncio.run(sink.append(_finished(), _sensitive()))
    sink.close()

    assert not (config.directory / "llm-audit-sensitive.jsonl").exists()


def test_sensitive_log_contains_only_aes_gcm_envelope(tmp_path: Path) -> None:
    config = AgentAuditLogConfig(
        directory=tmp_path / "private",
        capture_sensitive_content=True,
        encryption_key=b"k" * 32,
        encryption_key_id="key-2026-07",
    )
    sink = JsonlAgentAuditSink(config, nonce_factory=lambda size: b"n" * size)

    asyncio.run(sink.append(_finished(), _sensitive()))
    sink.close()

    text = (config.directory / "llm-audit-sensitive.jsonl").read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["algorithm"] == "AES-256-GCM"
    assert payload["key_id"] == "key-2026-07"
    assert payload["nonce"] == base64.b64encode(b"n" * 12).decode("ascii")
    assert "system secret" not in text
    assert "user secret" not in text
    assert "validated" not in text
    assert stat.S_IMODE((config.directory / "llm-audit-sensitive.jsonl").stat().st_mode) == 0o600


def test_sensitive_envelope_requires_event_aad(tmp_path: Path) -> None:
    key = b"k" * 32
    config = AgentAuditLogConfig(
        directory=tmp_path / "private",
        capture_sensitive_content=True,
        encryption_key=key,
        encryption_key_id="key-2026-07",
    )
    sink = JsonlAgentAuditSink(config, nonce_factory=lambda size: b"n" * size)

    asyncio.run(sink.append(_finished(), _sensitive()))
    sink.close()

    envelope = json.loads(
        (config.directory / "llm-audit-sensitive.jsonl").read_text(encoding="utf-8")
    )
    aad = json.dumps(
        {
            "schema_version": "llm-agent-audit-v1",
            "agent_name": "dialogue-generation",
            "run_id": "run-1",
            "attempt_id": "attempt-1",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    plaintext = AESGCM(key).decrypt(
        base64.b64decode(envelope["nonce"]),
        base64.b64decode(envelope["ciphertext"]),
        aad,
    )

    assert json.loads(plaintext) == {
        "raw_response_json": base64.b64encode(b'{"raw":"secret"}').decode("ascii"),
        "system_prompt": "system secret",
        "user_prompt": "user secret",
        "validated_output_json": base64.b64encode(b'{"value":"validated"}').decode("ascii"),
    }
    with pytest.raises(InvalidTag):
        AESGCM(key).decrypt(
            base64.b64decode(envelope["nonce"]),
            base64.b64decode(envelope["ciphertext"]),
            b"different event",
        )


@pytest.mark.parametrize(
    "config",
    (
        {"capture_sensitive_content": True},
        {
            "capture_sensitive_content": True,
            "encryption_key": b"short",
            "encryption_key_id": "key-id",
        },
        {"capture_sensitive_content": True, "encryption_key": b"k" * 32, "encryption_key_id": "  "},
    ),
)
def test_raw_capture_requires_exact_aes_key_and_key_id(
    tmp_path: Path, config: dict[str, object]
) -> None:
    with pytest.raises(AgentAuditConfigurationError):
        AgentAuditLogConfig(directory=tmp_path / "private", **config)  # type: ignore[arg-type]


def test_log_handlers_rotate_at_midnight_with_separate_retention(tmp_path: Path) -> None:
    sink = JsonlAgentAuditSink(
        AgentAuditLogConfig(
            directory=tmp_path / "private",
            capture_sensitive_content=True,
            encryption_key=b"k" * 32,
            encryption_key_id="key-id",
        )
    )

    metadata_handler = sink.metadata_logger.handlers[0]
    sensitive_handler = sink.sensitive_logger.handlers[0]
    sink.close()

    assert metadata_handler.when == "MIDNIGHT"
    assert metadata_handler.backupCount == 30
    assert sensitive_handler.when == "MIDNIGHT"
    assert sensitive_handler.backupCount == 7


def test_audit_handlers_are_not_attached_to_other_loggers(tmp_path: Path) -> None:
    root_handlers = tuple(logging.getLogger().handlers)
    unrelated = logging.getLogger("unrelated.audit.consumer")
    unrelated_handlers = tuple(unrelated.handlers)

    sink = JsonlAgentAuditSink(AgentAuditLogConfig(directory=tmp_path / "private"))
    sink.close()

    assert tuple(logging.getLogger().handlers) == root_handlers
    assert tuple(unrelated.handlers) == unrelated_handlers


def test_metadata_serialization_excludes_provider_credentials(tmp_path: Path) -> None:
    sink = JsonlAgentAuditSink(AgentAuditLogConfig(directory=tmp_path / "private"))

    asyncio.run(
        sink.append(_started(settings=(("api_key", "provider credential"), ("temperature", 0.4))))
    )
    sink.close()

    text = (tmp_path / "private" / "llm-audit-metadata.jsonl").read_text(encoding="utf-8")
    payload = json.loads(text)
    assert "provider credential" not in text
    assert payload["model"]["settings"] == [["temperature", 0.4]]


def test_config_requires_positive_retention_days(tmp_path: Path) -> None:
    with pytest.raises(AgentAuditConfigurationError):
        AgentAuditLogConfig(directory=tmp_path / "private", metadata_retention_days=0)
