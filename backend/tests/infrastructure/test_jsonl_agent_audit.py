import asyncio
import base64
import json
import logging
import os
import stat
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from llm_agent_audit import (
    AgentAuditWriteError,
    AuditAttemptFinished,
    AuditAttemptStarted,
    AuditedAgentRunner,
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


class _CountingRunner:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, user_prompt: str, *, instructions: str) -> object:
        self.calls += 1
        raise AssertionError("closed audit sink must block the provider call")


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


def test_global_logging_disable_cannot_suppress_owned_audit_persistence(tmp_path: Path) -> None:
    config = AgentAuditLogConfig(directory=tmp_path / "private")
    sink = JsonlAgentAuditSink(config)
    previous_disable = logging.root.manager.disable

    try:
        logging.disable(logging.CRITICAL)
        asyncio.run(sink.append(_started()))
    finally:
        logging.disable(previous_disable)
        sink.close()

    assert json.loads((config.directory / "llm-audit-metadata.jsonl").read_text())[
        "attempt_id"
    ] == ("attempt-1")


def test_disabled_owned_logger_cannot_suppress_audit_persistence(tmp_path: Path) -> None:
    config = AgentAuditLogConfig(directory=tmp_path / "private")
    sink = JsonlAgentAuditSink(config)

    try:
        sink.metadata_logger.disabled = True
        asyncio.run(sink.append(_started()))
    finally:
        sink.metadata_logger.disabled = False
        sink.close()

    assert json.loads((config.directory / "llm-audit-metadata.jsonl").read_text())[
        "attempt_id"
    ] == ("attempt-1")


def test_owned_handler_errors_propagate_from_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = JsonlAgentAuditSink(AgentAuditLogConfig(directory=tmp_path / "private"))

    def fail_to_open() -> object:
        raise OSError("audit storage unavailable")

    monkeypatch.setattr(sink._metadata_handler, "_open", fail_to_open)
    try:
        with pytest.raises(OSError, match="audit storage unavailable"):
            asyncio.run(sink.append(_started()))
    finally:
        sink.close()


def test_closed_concrete_sink_fails_runner_start_before_provider_call(tmp_path: Path) -> None:
    sink = JsonlAgentAuditSink(AgentAuditLogConfig(directory=tmp_path / "private"))
    sink.close()
    wrapped = _CountingRunner()
    runner = AuditedAgentRunner(
        wrapped,
        agent_name="dialogue-generation",
        model="provider:model",
        prompt_id="dialogue-generation.system",
        prompt_version=1,
        sink=sink,
        id_factory=lambda: "attempt-1",
    )

    with pytest.raises(AgentAuditWriteError, match="agent audit logging failed"):
        asyncio.run(
            runner.run(
                instructions="system secret",
                operation=lambda: runner.run_attempt(
                    "user secret",
                    validate=lambda output: None,
                ),
            )
        )

    assert wrapped.calls == 0


def test_close_waits_for_inflight_append_and_later_appends_reject(tmp_path: Path) -> None:
    nonce_requested = threading.Event()
    release_nonce = threading.Event()

    def blocking_nonce(size: int) -> bytes:
        nonce_requested.set()
        if not release_nonce.wait(timeout=2):
            raise TimeoutError("test did not release nonce creation")
        return b"n" * size

    config = AgentAuditLogConfig(
        directory=tmp_path / "private",
        capture_sensitive_content=True,
        encryption_key=b"k" * 32,
        encryption_key_id="key-id",
    )
    sink = JsonlAgentAuditSink(config, nonce_factory=blocking_nonce)
    close_started = threading.Event()
    close_finished = threading.Event()

    def close_sink() -> None:
        close_started.set()
        sink.close()
        close_finished.set()

    async def exercise_race() -> None:
        append_task = asyncio.create_task(sink.append(_finished(), _sensitive()))
        assert await asyncio.to_thread(nonce_requested.wait, 1)
        close_thread = threading.Thread(target=close_sink)
        close_thread.start()
        assert await asyncio.to_thread(close_started.wait, 1)
        try:
            close_completed_during_append = await asyncio.to_thread(close_finished.wait, 0.1)
        finally:
            release_nonce.set()
        await append_task
        close_thread.join(timeout=1)

        assert close_completed_during_append is False
        assert close_thread.is_alive() is False
        with pytest.raises(RuntimeError, match="closed"):
            await sink.append(_started())

    asyncio.run(exercise_race())

    assert (config.directory / "llm-audit-metadata.jsonl").exists()
    assert (config.directory / "llm-audit-sensitive.jsonl").exists()


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


def test_any_append_deletes_only_rotated_files_older_than_each_retention(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    config = AgentAuditLogConfig(
        directory=tmp_path / "private",
        capture_sensitive_content=True,
        encryption_key=b"k" * 32,
        encryption_key_id="key-id",
    )
    sink = JsonlAgentAuditSink(config, clock=lambda: now)
    metadata_active = config.directory / "llm-audit-metadata.jsonl"
    metadata_expired = config.directory / "llm-audit-metadata.jsonl.2026-07-23"
    metadata_retained = config.directory / "llm-audit-metadata.jsonl.2026-05-01"
    sensitive_expired = config.directory / "llm-audit-sensitive.jsonl.2026-07-23"
    sensitive_retained = config.directory / "llm-audit-sensitive.jsonl.2026-05-01"
    unrelated_rotation = config.directory / "other-audit.jsonl.2026-01-01"
    invalid_suffix = config.directory / "llm-audit-sensitive.jsonl.backup"

    files_by_age = {
        metadata_active: 45,
        metadata_expired: 31,
        metadata_retained: 29,
        sensitive_expired: 8,
        sensitive_retained: 6,
        unrelated_rotation: 100,
        invalid_suffix: 100,
    }
    for path, age_days in files_by_age.items():
        path.write_text("existing\n", encoding="utf-8")
        modified_at = (now - timedelta(days=age_days)).timestamp()
        os.utime(path, (modified_at, modified_at))

    asyncio.run(sink.append(_started()))
    sink.close()

    assert metadata_active.exists()
    assert metadata_expired.exists() is False
    assert metadata_retained.exists()
    assert sensitive_expired.exists() is False
    assert sensitive_retained.exists()
    assert unrelated_rotation.exists()
    assert invalid_suffix.exists()


def test_sensitive_rollover_immediately_deletes_expired_active_file(tmp_path: Path) -> None:
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    config = AgentAuditLogConfig(
        directory=tmp_path / "private",
        capture_sensitive_content=True,
        encryption_key=b"k" * 32,
        encryption_key_id="key-id",
    )
    sink = JsonlAgentAuditSink(
        config,
        nonce_factory=lambda size: b"n" * size,
        clock=lambda: now,
    )
    sensitive_active = config.directory / "llm-audit-sensitive.jsonl"
    sensitive_active.write_text("expired active record\n", encoding="utf-8")
    expired_at = (now - timedelta(days=8)).timestamp()
    os.utime(sensitive_active, (expired_at, expired_at))
    sink._sensitive_handler.rolloverAt = int(time.time()) - 1

    try:
        asyncio.run(sink.append(_finished(), _sensitive()))
    finally:
        sink.close()

    assert list(config.directory.glob("llm-audit-sensitive.jsonl.*")) == []
    active_records = sensitive_active.read_text(encoding="utf-8").splitlines()
    assert len(active_records) == 1
    assert json.loads(active_records[0])["attempt_id"] == "attempt-1"


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


def test_metadata_serialization_uses_only_the_allowed_model_settings(tmp_path: Path) -> None:
    sink = JsonlAgentAuditSink(AgentAuditLogConfig(directory=tmp_path / "private"))

    asyncio.run(
        sink.append(
            _started(
                settings=(
                    ("headers", "Authorization: Bearer headers-secret"),
                    ("auth", "auth-secret"),
                    ("base_url", "https://base-url-secret.example"),
                    ("endpoint", "https://endpoint-secret.example"),
                    ("temperature", 0.4),
                    ("max_tokens", 80),
                )
            )
        )
    )
    sink.close()

    text = (tmp_path / "private" / "llm-audit-metadata.jsonl").read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["model"]["settings"] == [["temperature", 0.4], ["max_tokens", 80]]
    for secret in (
        "Authorization",
        "headers-secret",
        "auth-secret",
        "base-url-secret",
        "endpoint-secret",
    ):
        assert secret not in text


def test_config_requires_positive_retention_days(tmp_path: Path) -> None:
    with pytest.raises(AgentAuditConfigurationError):
        AgentAuditLogConfig(directory=tmp_path / "private", metadata_retention_days=0)
