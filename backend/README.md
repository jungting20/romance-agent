# Backend

FastAPI application code is organized by domain under `apps/`.

## Project structure

```text
backend/
├── main.py                 # FastAPI application entry point
├── apps/                   # Domain-owned backend packages
│   ├── narrative_memory/   # Versioned narrative analysis snapshots
│   └── <domain>/
│       ├── router/         # HTTP request and response boundary
│       ├── service/        # Application workflows and domain coordination
│       ├── repository/     # Persistence ports and implementations
│       └── schemas/        # Transport schemas
├── infrastructure/         # Cross-cutting provider and persistence adapters
│   ├── llm/                # Prompt registry and typed model/mock adapters
│   └── audit/              # Owner-only append-only LLM audit storage
├── prompts/                # Versioned, hot-loaded editable system prompts
├── tests/                  # API, service, repository, and domain tests
├── docs/
│   └── backend-coding-rules.md
├── pyproject.toml
└── uv.lock
```

Keep domain-specific code inside its owning `apps/<domain>/` package. Update
this map when a structural change alters the responsibilities or major packages
shown here; individual files do not need to be listed.

The Narrative Memory repository persists immutable, versioned canonical JSON
snapshots in SQLite.

Narrative Memory scene analysis is invoked explicitly; it is not attached to
manuscript saves or a background process. `NARRATIVE_LLM_MODEL` selects the
model only when a caller composes the analyzer. Set it to `mock` for the local,
network-free adapter, for example:

```sh
NARRATIVE_LLM_MODEL=mock
```

A missing or blank value fails the requested analysis without preventing the
unrelated backend process from starting. The audit database is separate from
project snapshots and does not automatically persist a returned scene or
project snapshot.

## Setup

From this directory:

```sh
mise install
mise exec -- uv sync --dev
```

## Development server

```sh
mise exec -- uv run uvicorn main:app --reload
```

The process health endpoint is available at `GET /health`.

## Verification

```sh
mise exec -- uv run pytest \
  tests/narrative_memory/test_scene_analysis_service.py::test_analyze_scene_with_mock_and_sqlite_audit_end_to_end -v
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```
