import json
import os
import re
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from apps.narrative_memory.repository.analysis_audit import (
    AttemptAlreadyTerminal,
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
from apps.narrative_memory.service.scene_analysis_ports import PromptDefinition

_RUN_EVENT_TYPES = {
    RunStarted: "run_started",
    RunSucceeded: "run_succeeded",
    RunFailed: "run_failed",
}
_ATTEMPT_EVENT_TYPES = {
    AttemptStarted: "attempt_started",
    AttemptSucceeded: "attempt_succeeded",
    AttemptFailed: "attempt_failed",
}
_TERMINAL_INDEX_NAME = "uq_attempt_terminal"
_TERMINAL_INDEX_SQL = (
    "CREATE UNIQUE INDEX uq_attempt_terminal "
    "ON attempt_events (run_id, chunk_id, attempt_number) "
    "WHERE event_type IN ('attempt_succeeded', 'attempt_failed')"
)
_TERMINAL_INDEX_COLUMNS = ("run_id", "chunk_id", "attempt_number")
_TERMINAL_INDEX_KEYS = tuple((column, 0, "BINARY", 1) for column in _TERMINAL_INDEX_COLUMNS)
_TERMINAL_PREDICATE = re.compile(
    r"event_type\s+in\s*\(\s*'attempt_succeeded'\s*,\s*'attempt_failed'\s*\)",
    re.IGNORECASE,
)


class SQLiteAuditSchemaError(RuntimeError):
    pass


class SQLiteAgentAudit:
    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        self._path.chmod(0o600)

        connection = sqlite3.connect(self._path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_definitions (
                    prompt_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    result_schema TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    raw_bytes BLOB NOT NULL,
                    PRIMARY KEY (prompt_id, version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json BLOB NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS attempt_events (
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
            _ensure_terminal_index(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def register_prompt(self, prompt: PromptDefinition) -> None:
        connection = sqlite3.connect(self._path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            stored = connection.execute(
                """
                SELECT result_schema, content_hash, raw_bytes
                FROM prompt_definitions
                WHERE prompt_id = ? AND version = ?
                """,
                (prompt.prompt_id, prompt.version),
            ).fetchone()
            expected = (prompt.result_schema, prompt.content_hash, prompt.raw_bytes)
            if stored is not None:
                actual = (stored[0], stored[1], bytes(stored[2]))
                if actual != expected:
                    raise PromptVersionConflict(
                        f"prompt {prompt.prompt_id!r} version {prompt.version} "
                        "is already registered"
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO prompt_definitions (
                        prompt_id,
                        version,
                        result_schema,
                        content_hash,
                        raw_bytes
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        prompt.prompt_id,
                        prompt.version,
                        prompt.result_schema,
                        prompt.content_hash,
                        prompt.raw_bytes,
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def append_run_event(self, event: RunEvent) -> None:
        connection = sqlite3.connect(self._path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO run_events (run_id, event_type, occurred_at, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    _RUN_EVENT_TYPES[type(event)],
                    event.occurred_at.isoformat(),
                    _event_payload(event, {"run_id", "occurred_at"}),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def append_attempt_event(self, event: AttemptEvent) -> None:
        connection = sqlite3.connect(self._path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO attempt_events (
                    run_id,
                    chunk_id,
                    attempt_number,
                    event_type,
                    occurred_at,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.chunk_id,
                    event.attempt_number,
                    _ATTEMPT_EVENT_TYPES[type(event)],
                    event.occurred_at.isoformat(),
                    _event_payload(
                        event,
                        {"run_id", "chunk_id", "attempt_number", "occurred_at"},
                    ),
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            if (
                isinstance(event, (AttemptSucceeded, AttemptFailed))
                and error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE
            ):
                raise AttemptAlreadyTerminal("attempt already has a terminal event") from None
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _event_payload(event: RunEvent | AttemptEvent, excluded_fields: set[str]) -> bytes:
    payload = {
        key: _json_value(value)
        for key, value in asdict(event).items()
        if key not in excluded_fields
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _ensure_terminal_index(connection: sqlite3.Connection) -> None:
    stored = connection.execute(
        "SELECT tbl_name, sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        (_TERMINAL_INDEX_NAME,),
    ).fetchone()
    if stored is None:
        try:
            connection.execute(_TERMINAL_INDEX_SQL)
        except sqlite3.IntegrityError:
            raise AttemptAlreadyTerminal(
                "existing attempts contain duplicate terminal events"
            ) from None
    _validate_terminal_index(connection)


def _validate_terminal_index(connection: sqlite3.Connection) -> None:
    stored = connection.execute(
        "SELECT tbl_name, sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        (_TERMINAL_INDEX_NAME,),
    ).fetchone()
    index_list_row = next(
        (
            row
            for row in connection.execute("PRAGMA index_list('attempt_events')")
            if row[1] == _TERMINAL_INDEX_NAME
        ),
        None,
    )
    index_keys = tuple(
        (row[2], row[3], row[4], row[5])
        for row in connection.execute(f"PRAGMA index_xinfo('{_TERMINAL_INDEX_NAME}')")
        if row[5] == 1
    )
    if (
        stored is None
        or stored[0] != "attempt_events"
        or not isinstance(stored[1], str)
        or index_list_row is None
        or index_list_row[2] != 1
        or index_list_row[4] != 1
        or index_keys != _TERMINAL_INDEX_KEYS
        or not _has_expected_terminal_predicate(stored[1])
    ):
        raise SQLiteAuditSchemaError("terminal attempt index schema is invalid") from None


def _has_expected_terminal_predicate(index_sql: str) -> bool:
    parts = re.split(r"\s+where\s+", index_sql, maxsplit=1, flags=re.IGNORECASE)
    return len(parts) == 2 and _TERMINAL_PREDICATE.fullmatch(parts[1].strip()) is not None


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value
