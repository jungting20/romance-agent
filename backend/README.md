# Backend

FastAPI application code is organized by domain under `apps/`.

## Project structure

```text
backend/
├── main.py                 # FastAPI application entry point
├── apps/                   # Domain-owned backend packages
│   ├── narrative_memory/ # Versioned narrative analysis snapshots
│   └── <domain>/
│       ├── router/         # HTTP request and response boundary
│       ├── service/        # Application workflows and domain coordination
│       ├── repository/     # Persistence ports and implementations
│       └── schemas/        # Transport schemas
├── infrastructure/         # Cross-cutting provider adapters
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
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```
