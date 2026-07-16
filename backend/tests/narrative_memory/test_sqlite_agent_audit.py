import json
import sqlite3
import stat
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from apps.narrative_memory.repository.analysis_audit import (
    AttemptAlreadyTerminal,
    AttemptFailed,
    AttemptStarted,
    AttemptSucceeded,
    PromptVersionConflict,
    RunFailed,
    RunStarted,
    RunSucceeded,
)
from apps.narrative_memory.service.scene_analysis_ports import PromptDefinition
from apps.narrative_memory.service.scene_analysis_types import AgentUsage
from infrastructure.audit.sqlite_agent_audit import SQLiteAgentAudit, SQLiteAuditSchemaError

OCCURRED_AT = datetime(2026, 7, 16, 9, 30, tzinfo=UTC)


def _prompt() -> PromptDefinition:
    return PromptDefinition(
        prompt_id="scene-analysis",
        version=1,
        result_schema="chunk-analysis-extraction-v1",
        content_hash="sha256:prompt-v1",
        raw_bytes="정확한 시스템 프롬프트\n".encode(),
        body="정확한 시스템 프롬프트\n",
    )


def _initialized_audit(tmp_path) -> tuple[SQLiteAgentAudit, object]:
    path = tmp_path / "private" / "agent-audit.sqlite3"
    audit = SQLiteAgentAudit(path)
    audit.initialize()
    return audit, path


def _stored_events(path, table: str) -> list[tuple[object, ...]]:
    columns = "event_sequence, run_id, event_type, occurred_at, payload_json"
    if table == "attempt_events":
        columns = (
            "event_sequence, run_id, chunk_id, attempt_number, event_type, "
            "occurred_at, payload_json"
        )
    with sqlite3.connect(path) as connection:
        return connection.execute(
            f"SELECT {columns} FROM {table} ORDER BY event_sequence"
        ).fetchall()


def test_audit_initializes_owner_only_database_and_append_only_schema(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)

    assert audit is not None
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with sqlite3.connect(path) as connection:
        schemas = dict(
            connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        )
        columns = {
            table: [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            for table in schemas
        }
        indexes = dict(
            connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
            )
        )

    assert set(schemas) == {"prompt_definitions", "run_events", "attempt_events"}
    assert columns == {
        "prompt_definitions": [
            "prompt_id",
            "version",
            "result_schema",
            "content_hash",
            "raw_bytes",
        ],
        "run_events": ["event_sequence", "run_id", "event_type", "occurred_at", "payload_json"],
        "attempt_events": [
            "event_sequence",
            "run_id",
            "chunk_id",
            "attempt_number",
            "event_type",
            "occurred_at",
            "payload_json",
        ],
    }
    assert all("UPDATE" not in sql.upper() for sql in schemas.values())
    assert all("status" not in table_columns for table_columns in columns.values())
    assert set(indexes) == {"uq_attempt_terminal"}
    assert "UNIQUE INDEX" in indexes["uq_attempt_terminal"].upper()
    assert (
        "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')"
        in indexes["uq_attempt_terminal"]
    )


def test_register_prompt_is_exact_byte_idempotent_and_rejects_version_reuse(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    prompt = _prompt()

    audit.register_prompt(prompt)
    audit.register_prompt(prompt)

    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT * FROM prompt_definitions").fetchall()
    assert rows == [
        (
            prompt.prompt_id,
            prompt.version,
            prompt.result_schema,
            prompt.content_hash,
            prompt.raw_bytes,
        )
    ]

    for conflicting in (
        replace(prompt, result_schema="different-schema"),
        replace(prompt, content_hash="sha256:different"),
        replace(prompt, raw_bytes=b"different bytes"),
    ):
        with pytest.raises(PromptVersionConflict, match="scene-analysis.*1"):
            audit.register_prompt(conflicting)

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM prompt_definitions").fetchone() == (1,)


def test_frozen_run_events_are_appended_in_order_with_canonical_exact_payloads(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    started = RunStarted(
        run_id="run-01",
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=2,
        scene_sequence=7,
        provider_name="provider",
        model_name="model-v1",
        prompt_id="scene-analysis",
        prompt_version=1,
        occurred_at=OCCURRED_AT,
    )
    succeeded = RunSucceeded(
        run_id="run-01",
        occurred_at=OCCURRED_AT + timedelta(seconds=3),
        scene_snapshot_json='{"summary":"완료"}'.encode(),
    )

    with pytest.raises(FrozenInstanceError):
        started.run_id = "changed"  # type: ignore[misc]
    audit.append_run_event(started)
    audit.append_run_event(succeeded)

    rows = _stored_events(path, "run_events")
    assert [row[:4] for row in rows] == [
        (1, "run-01", "run_started", OCCURRED_AT.isoformat()),
        (2, "run-01", "run_succeeded", (OCCURRED_AT + timedelta(seconds=3)).isoformat()),
    ]
    assert bytes(rows[0][4]) == (
        b'{"model_name":"model-v1","project_id":"project-01",'
        b'"prompt_id":"scene-analysis","prompt_version":1,"provider_name":"provider",'
        b'"scene_id":"scene-01","scene_revision":2,"scene_sequence":7}'
    )
    assert bytes(rows[1][4]).decode() == '{"scene_snapshot_json":"{\\"summary\\":\\"완료\\"}"}'


def test_run_failure_appends_error_without_mutating_started_event(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    audit.append_run_event(
        RunFailed(
            run_id="run-02",
            occurred_at=OCCURRED_AT,
            error_type="ProviderCallError",
            error_message="provider unavailable",
        )
    )

    row = _stored_events(path, "run_events")[0]
    assert row[:4] == (1, "run-02", "run_failed", OCCURRED_AT.isoformat())
    assert json.loads(bytes(row[4])) == {
        "error_message": "provider unavailable",
        "error_type": "ProviderCallError",
    }


def test_attempt_success_preserves_messages_response_validation_usage_and_latency(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    started = AttemptStarted(
        run_id="run-01",
        chunk_id="scene-01:r2:0000",
        attempt_number=1,
        occurred_at=OCCURRED_AT,
        system_message="한국어 시스템 프롬프트",
        user_message='{"text":"장면 본문"}',
    )
    succeeded = AttemptSucceeded(
        run_id="run-01",
        chunk_id="scene-01:r2:0000",
        attempt_number=1,
        occurred_at=OCCURRED_AT + timedelta(milliseconds=125),
        latency_ms=125.5,
        response_messages_json='[{"content":"응답"}]'.encode(),
        validated_extraction_json='{"summary":"요약"}'.encode(),
        provider_name="provider",
        model_name="model-v1",
        usage=AgentUsage(requests=1, input_tokens=21, output_tokens=8),
    )

    audit.append_attempt_event(started)
    audit.append_attempt_event(succeeded)

    rows = _stored_events(path, "attempt_events")
    assert [row[:6] for row in rows] == [
        (1, "run-01", "scene-01:r2:0000", 1, "attempt_started", OCCURRED_AT.isoformat()),
        (
            2,
            "run-01",
            "scene-01:r2:0000",
            1,
            "attempt_succeeded",
            (OCCURRED_AT + timedelta(milliseconds=125)).isoformat(),
        ),
    ]
    assert bytes(rows[0][6]).decode() == (
        '{"system_message":"한국어 시스템 프롬프트","user_message":"{\\"text\\":\\"장면 본문\\"}"}'
    )
    assert json.loads(bytes(rows[1][6])) == {
        "latency_ms": 125.5,
        "model_name": "model-v1",
        "provider_name": "provider",
        "response_messages_json": '[{"content":"응답"}]',
        "usage": {"input_tokens": 21, "output_tokens": 8, "requests": 1},
        "validated_extraction_json": '{"summary":"요약"}',
    }


def test_attempt_failure_preserves_available_response_and_error(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    event = AttemptFailed(
        run_id="run-01",
        chunk_id="scene-01:r2:0000",
        attempt_number=2,
        occurred_at=OCCURRED_AT,
        latency_ms=44.0,
        error_type="ValidationError",
        error_message="structured output rejected",
        response_messages_json='[{"content":"잘못된 응답"}]'.encode(),
    )

    audit.append_attempt_event(event)

    row = _stored_events(path, "attempt_events")[0]
    assert row[:6] == (
        1,
        "run-01",
        "scene-01:r2:0000",
        2,
        "attempt_failed",
        OCCURRED_AT.isoformat(),
    )
    assert json.loads(bytes(row[6])) == {
        "error_message": "structured output rejected",
        "error_type": "ValidationError",
        "latency_ms": 44.0,
        "response_messages_json": '[{"content":"잘못된 응답"}]',
    }


def _terminal_success(attempt_number: int = 1) -> AttemptSucceeded:
    return AttemptSucceeded(
        run_id="run-terminal",
        chunk_id="scene:r1:0000",
        attempt_number=attempt_number,
        occurred_at=OCCURRED_AT,
        latency_ms=10.0,
        response_messages_json=b"[]",
        validated_extraction_json=b'{"summary":"ok"}',
        provider_name="provider",
        model_name="model",
        usage=AgentUsage(requests=1),
    )


def _terminal_failure(attempt_number: int = 1) -> AttemptFailed:
    return AttemptFailed(
        run_id="run-terminal",
        chunk_id="scene:r1:0000",
        attempt_number=attempt_number,
        occurred_at=OCCURRED_AT,
        latency_ms=10.0,
        error_type="ProviderCallError",
        error_message="provider call failed",
    )


@pytest.mark.parametrize(
    ("first", "conflicting"),
    [
        (_terminal_success(), _terminal_failure()),
        (_terminal_failure(), _terminal_success()),
    ],
    ids=["success-then-failure", "failure-then-success"],
)
def test_terminal_attempt_event_is_unique_and_conflict_rolls_back(
    tmp_path,
    first: AttemptSucceeded | AttemptFailed,
    conflicting: AttemptSucceeded | AttemptFailed,
) -> None:
    audit, path = _initialized_audit(tmp_path)

    audit.append_attempt_event(first)
    with pytest.raises(AttemptAlreadyTerminal) as captured:
        audit.append_attempt_event(conflicting)
    audit.append_attempt_event(_terminal_failure(attempt_number=2))

    assert captured.value.__cause__ is None
    assert captured.value.args == ("attempt already has a terminal event",)
    rows = _stored_events(path, "attempt_events")
    first_event_type = (
        "attempt_succeeded" if isinstance(first, AttemptSucceeded) else "attempt_failed"
    )
    assert [(row[2], row[3], row[4]) for row in rows] == [
        ("scene:r1:0000", 1, first_event_type),
        ("scene:r1:0000", 2, "attempt_failed"),
    ]


def test_initialize_rejects_existing_duplicate_terminal_events_without_rewriting(tmp_path) -> None:
    path = tmp_path / "private" / "agent-audit.sqlite3"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE attempt_events (
                event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json BLOB NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO attempt_events (
                run_id, chunk_id, attempt_number, event_type, occurred_at, payload_json
            ) VALUES ('run', 'chunk', 1, ?, ?, '{}')
            """,
            [
                ("attempt_succeeded", OCCURRED_AT.isoformat()),
                ("attempt_failed", OCCURRED_AT.isoformat()),
            ],
        )

    with pytest.raises(AttemptAlreadyTerminal) as captured:
        SQLiteAgentAudit(path).initialize()

    assert captured.value.__cause__ is None
    assert captured.value.args == ("existing attempts contain duplicate terminal events",)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT event_type FROM attempt_events ORDER BY event_sequence"
        ).fetchall()
        index = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'uq_attempt_terminal'"
        ).fetchone()
    assert rows == [("attempt_succeeded",), ("attempt_failed",)]
    assert index is None


@pytest.mark.parametrize(
    "index_sql",
    [
        (
            "CREATE INDEX uq_attempt_terminal "
            "ON attempt_events (run_id, chunk_id, attempt_number) "
            "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')"
        ),
        (
            "CREATE UNIQUE INDEX uq_attempt_terminal "
            "ON attempt_events (run_id, chunk_id, attempt_number, event_type) "
            "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')"
        ),
        (
            "CREATE UNIQUE INDEX uq_attempt_terminal "
            "ON attempt_events (run_id, chunk_id, attempt_number) "
            "WHERE event_type = 'attempt_succeeded'"
        ),
    ],
    ids=["nonunique", "wrong-columns", "wrong-predicate"],
)
def test_initialize_rejects_wrong_named_terminal_index_without_repair(
    tmp_path, index_sql: str
) -> None:
    path = tmp_path / "private" / "agent-audit.sqlite3"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE attempt_events (
                event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json BLOB NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO attempt_events (
                run_id, chunk_id, attempt_number, event_type, occurred_at, payload_json
            ) VALUES ('run', 'chunk', 1, 'attempt_started', ?, '{}')
            """,
            (OCCURRED_AT.isoformat(),),
        )
        connection.execute(index_sql)

    with pytest.raises(SQLiteAuditSchemaError) as captured:
        SQLiteAgentAudit(path).initialize()

    assert captured.value.__cause__ is None
    assert captured.value.args == ("terminal attempt index schema is invalid",)
    with sqlite3.connect(path) as connection:
        stored_index_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'uq_attempt_terminal'"
        ).fetchone()
        rows = connection.execute(
            "SELECT event_type FROM attempt_events ORDER BY event_sequence"
        ).fetchall()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert stored_index_sql == (index_sql,)
    assert rows == [("attempt_started",)]
    assert tables == {"attempt_events"}


def test_initialize_accepts_existing_canonical_terminal_index_idempotently(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)

    audit.initialize()

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'index' AND name = 'uq_attempt_terminal'"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "uq_attempt_terminal"
    assert "CREATE UNIQUE INDEX" in rows[0][1]


def test_invalid_utf8_event_payload_is_not_partially_committed(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    invalid = RunSucceeded(
        run_id="run-01",
        occurred_at=OCCURRED_AT,
        scene_snapshot_json=b"\xff",
    )

    with pytest.raises(UnicodeDecodeError):
        audit.append_run_event(invalid)

    assert _stored_events(path, "run_events") == []


@pytest.mark.parametrize(
    "latency_ms",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_non_finite_event_number_is_not_partially_committed(tmp_path, latency_ms: float) -> None:
    audit, path = _initialized_audit(tmp_path)
    invalid = AttemptFailed(
        run_id="run-01",
        chunk_id="scene-01:r2:0000",
        attempt_number=1,
        occurred_at=OCCURRED_AT,
        latency_ms=latency_ms,
        error_type="ProviderCallError",
        error_message="provider unavailable",
    )

    with pytest.raises(ValueError, match="JSON compliant"):
        audit.append_attempt_event(invalid)

    assert _stored_events(path, "attempt_events") == []


def test_database_error_rolls_back_attempt_append(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_attempt
            AFTER INSERT ON attempt_events
            BEGIN
                SELECT RAISE(ABORT, 'attempt rejected');
            END
            """
        )

    event = AttemptStarted(
        run_id="run-01",
        chunk_id="scene-01:r2:0000",
        attempt_number=1,
        occurred_at=OCCURRED_AT,
        system_message="system",
        user_message="user",
    )
    with pytest.raises(sqlite3.IntegrityError, match="attempt rejected"):
        audit.append_attempt_event(event)

    assert _stored_events(path, "attempt_events") == []
