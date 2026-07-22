import json
import sqlite3
import stat
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from narrative_analysis_agent.audit.ports import (
    AttemptAlreadyTerminal,
    AttemptFailed,
    AttemptStarted,
    AttemptSucceeded,
    PromptVersionConflict,
    RunFailed,
    RunStarted,
    RunSucceeded,
)
from narrative_analysis_agent.audit.sqlite import SQLiteAgentAudit, SQLiteAuditSchemaError
from narrative_analysis_agent.extraction.agent import AgentUsage
from narrative_analysis_agent.extraction.prompts import PromptDefinition

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


def _attempt_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE attempt_events (
            event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL, chunk_id TEXT NOT NULL, attempt_number INTEGER NOT NULL,
            event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, payload_json BLOB NOT NULL
        )
        """
    )


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


def test_initializes_owner_only_append_only_schema_with_terminal_index(tmp_path) -> None:
    _, path = _initialized_audit(tmp_path)

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
    assert (
        "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')"
        in indexes["uq_attempt_terminal"]
    )


def test_register_prompt_is_exact_byte_idempotent_and_rejects_version_reuse(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    prompt = _prompt()

    audit.register_prompt(prompt)
    audit.register_prompt(prompt)
    for conflicting in (
        replace(prompt, result_schema="different-schema"),
        replace(prompt, content_hash="sha256:different"),
        replace(prompt, raw_bytes=b"different bytes"),
    ):
        with pytest.raises(PromptVersionConflict, match="scene-analysis.*1"):
            audit.register_prompt(conflicting)

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT * FROM prompt_definitions").fetchall() == [
            (
                prompt.prompt_id,
                prompt.version,
                prompt.result_schema,
                prompt.content_hash,
                prompt.raw_bytes,
            )
        ]


def test_run_events_are_frozen_ordered_and_have_canonical_payloads(tmp_path) -> None:
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
    with pytest.raises(FrozenInstanceError):
        started.run_id = "changed"  # type: ignore[misc]
    audit.append_run_event(started)
    audit.append_run_event(
        RunSucceeded(
            run_id="run-01",
            occurred_at=OCCURRED_AT + timedelta(seconds=3),
            scene_snapshot_json='{"summary":"완료"}'.encode(),
        )
    )
    audit.append_run_event(
        RunFailed(
            run_id="run-02",
            occurred_at=OCCURRED_AT,
            error_type="ProviderCallError",
            error_message="provider unavailable",
        )
    )

    rows = _stored_events(path, "run_events")
    assert [row[:4] for row in rows] == [
        (1, "run-01", "run_started", OCCURRED_AT.isoformat()),
        (2, "run-01", "run_succeeded", (OCCURRED_AT + timedelta(seconds=3)).isoformat()),
        (3, "run-02", "run_failed", OCCURRED_AT.isoformat()),
    ]
    assert bytes(rows[0][4]) == (
        b'{"model_name":"model-v1","project_id":"project-01","prompt_id":"scene-analysis",'
        b'"prompt_version":1,"provider_name":"provider","scene_id":"scene-01",'
        b'"scene_revision":2,"scene_sequence":7}'
    )
    assert json.loads(bytes(rows[1][4])) == {"scene_snapshot_json": '{"summary":"완료"}'}
    assert json.loads(bytes(rows[2][4])) == {
        "error_type": "ProviderCallError",
        "error_message": "provider unavailable",
    }


def test_attempt_events_preserve_safe_payloads_and_terminal_conflicts_roll_back(tmp_path) -> None:
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
    audit.append_attempt_event(_terminal_success())
    with pytest.raises(
        AttemptAlreadyTerminal, match="attempt already has a terminal event"
    ) as captured:
        audit.append_attempt_event(_terminal_failure())
    audit.append_attempt_event(_terminal_failure(attempt_number=2))

    assert captured.value.__cause__ is None
    assert captured.value.args == ("attempt already has a terminal event",)
    rows = _stored_events(path, "attempt_events")
    assert [(row[2], row[3], row[4]) for row in rows] == [
        ("scene-01:r2:0000", 1, "attempt_started"),
        ("scene-01:r2:0000", 1, "attempt_succeeded"),
        ("scene:r1:0000", 1, "attempt_succeeded"),
        ("scene:r1:0000", 2, "attempt_failed"),
    ]
    assert json.loads(bytes(rows[1][6])) == {
        "latency_ms": 125.5,
        "model_name": "model-v1",
        "provider_name": "provider",
        "response_messages_json": '[{"content":"응답"}]',
        "usage": {"requests": 1, "input_tokens": 21, "output_tokens": 8},
        "validated_extraction_json": '{"summary":"요약"}',
    }


def test_attempt_failure_preserves_available_response_and_error(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    audit.append_attempt_event(
        AttemptFailed(
            run_id="run-01",
            chunk_id="scene-01:r2:0000",
            attempt_number=2,
            occurred_at=OCCURRED_AT,
            latency_ms=44.0,
            error_type="ValidationError",
            error_message="structured output rejected",
            response_messages_json='[{"content":"잘못된 응답"}]'.encode(),
        )
    )

    assert json.loads(bytes(_stored_events(path, "attempt_events")[0][6])) == {
        "error_type": "ValidationError",
        "error_message": "structured output rejected",
        "latency_ms": 44.0,
        "response_messages_json": '[{"content":"잘못된 응답"}]',
    }


def test_initialize_rejects_existing_duplicate_terminals_without_rewriting(tmp_path) -> None:
    path = tmp_path / "private" / "agent-audit.sqlite3"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        _attempt_table(connection)
        connection.executemany(
            "INSERT INTO attempt_events "
            "(run_id, chunk_id, attempt_number, event_type, occurred_at, payload_json) "
            "VALUES ('run', 'chunk', 1, ?, ?, '{}')",
            [
                ("attempt_succeeded", OCCURRED_AT.isoformat()),
                ("attempt_failed", OCCURRED_AT.isoformat()),
            ],
        )

    with pytest.raises(
        AttemptAlreadyTerminal, match="existing attempts contain duplicate terminal events"
    ) as captured:
        SQLiteAgentAudit(path).initialize()
    assert captured.value.__cause__ is None
    assert captured.value.args == ("existing attempts contain duplicate terminal events",)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT event_type FROM attempt_events ORDER BY event_sequence"
        ).fetchall() == [("attempt_succeeded",), ("attempt_failed",)]
        assert (
            connection.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'index' AND name = 'uq_attempt_terminal'"
            ).fetchone()
            is None
        )


@pytest.mark.parametrize(
    "index_sql",
    [
        "CREATE INDEX uq_attempt_terminal "
        "ON attempt_events (run_id, chunk_id, attempt_number) "
        "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')",
        "CREATE UNIQUE INDEX uq_attempt_terminal "
        "ON attempt_events (run_id, chunk_id, attempt_number, event_type) "
        "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')",
        "CREATE UNIQUE INDEX uq_attempt_terminal "
        "ON attempt_events (run_id, chunk_id, attempt_number) "
        "WHERE event_type = 'attempt_succeeded'",
        "CREATE UNIQUE INDEX uq_attempt_terminal "
        "ON attempt_events (run_id COLLATE NOCASE, chunk_id, attempt_number) "
        "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')",
        "CREATE UNIQUE INDEX uq_attempt_terminal "
        "ON attempt_events (run_id COLLATE RTRIM, chunk_id, attempt_number) "
        "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')",
        "CREATE UNIQUE INDEX uq_attempt_terminal "
        "ON attempt_events (run_id, chunk_id, attempt_number DESC) "
        "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')",
    ],
    ids=[
        "nonunique",
        "wrong-columns",
        "wrong-predicate",
        "nocase-collation",
        "rtrim-collation",
        "descending-key",
    ],
)
def test_initialize_rejects_invalid_named_terminal_index_without_repair(
    tmp_path, index_sql: str
) -> None:
    path = tmp_path / "private" / "agent-audit.sqlite3"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        _attempt_table(connection)
        connection.execute(
            "INSERT INTO attempt_events "
            "(run_id, chunk_id, attempt_number, event_type, occurred_at, payload_json) "
            "VALUES ('run', 'chunk', 1, 'attempt_started', ?, '{}')",
            (OCCURRED_AT.isoformat(),),
        )
        connection.execute(index_sql)

    with pytest.raises(
        SQLiteAuditSchemaError, match="terminal attempt index schema is invalid"
    ) as captured:
        SQLiteAgentAudit(path).initialize()
    assert captured.value.__cause__ is None
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'uq_attempt_terminal'"
        ).fetchone() == (index_sql,)
        assert connection.execute(
            "SELECT event_type FROM attempt_events ORDER BY event_sequence"
        ).fetchall() == [("attempt_started",)]


def test_initialize_accepts_canonical_terminal_index_idempotently(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    audit.initialize()
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'uq_attempt_terminal'"
        ).fetchall()
    assert rows == [("uq_attempt_terminal",)]


def test_prompt_and_terminal_identities_are_binary_case_sensitive(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    audit.register_prompt(_prompt())
    audit.register_prompt(replace(_prompt(), prompt_id="SCENE-ANALYSIS"))
    audit.append_attempt_event(_terminal_success())
    audit.append_attempt_event(
        replace(_terminal_failure(), run_id="RUN-TERMINAL", chunk_id="SCENE:R1:0000")
    )

    with sqlite3.connect(path) as connection:
        prompts = connection.execute(
            "SELECT prompt_id FROM prompt_definitions ORDER BY prompt_id"
        ).fetchall()
    assert prompts == [("SCENE-ANALYSIS",), ("scene-analysis",)]
    assert len(_stored_events(path, "attempt_events")) == 2


def test_terminal_failure_also_blocks_a_later_success(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    audit.append_attempt_event(_terminal_failure())

    with pytest.raises(AttemptAlreadyTerminal, match="attempt already has a terminal event"):
        audit.append_attempt_event(_terminal_success())

    assert [row[4] for row in _stored_events(path, "attempt_events")] == ["attempt_failed"]


def test_invalid_payloads_and_database_errors_are_not_partially_committed(tmp_path) -> None:
    audit, path = _initialized_audit(tmp_path)
    with pytest.raises(UnicodeDecodeError):
        audit.append_run_event(
            RunSucceeded(run_id="run-01", occurred_at=OCCURRED_AT, scene_snapshot_json=b"\xff")
        )
    for latency_ms in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="JSON compliant"):
            audit.append_attempt_event(replace(_terminal_failure(), latency_ms=latency_ms))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_attempt AFTER INSERT ON attempt_events "
            "BEGIN SELECT RAISE(ABORT, 'attempt rejected'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="attempt rejected"):
        audit.append_attempt_event(
            AttemptStarted(
                run_id="run-01",
                chunk_id="scene-01:r2:0000",
                attempt_number=1,
                occurred_at=OCCURRED_AT,
                system_message="system",
                user_message="user",
            )
        )
    assert _stored_events(path, "run_events") == []
    assert _stored_events(path, "attempt_events") == []
