# Backend

FastAPI application code is organized by domain under `apps/`.

## Project structure

```text
backend/
├── main.py                 # FastAPI application entry point
├── apps/                   # Domain-owned backend packages
│   ├── narrative_memory/   # Public agent composition and project snapshots
│   └── <domain>/
│       ├── domain/         # Entities, aggregates, value objects, domain errors
│       ├── router/         # HTTP request and response boundary
│       ├── service/        # Application workflows and domain coordination
│       ├── repository/     # Persistence ports and implementations
│       └── schemas/        # Transport schemas
├── tests/                  # API, service, repository, and domain tests
├── docs/
│   └── backend-coding-rules.md
├── pyproject.toml
└── uv.lock
```

Keep domain-specific code inside its owning `apps/<domain>/` package. Update
this map when a structural change alters the responsibilities or major packages
shown here; individual files do not need to be listed.

The backend composes the public `NarrativeAnalysisAgent` facade and translates
its immutable scene result into Narrative Memory's domain snapshot. It owns
scene-to-project merging and persists immutable, versioned canonical project
JSON snapshots in SQLite. The separate `llm-agent/` package owns provider
adapters, prompts, and the append-only analysis audit.

Narrative Memory scene analysis is invoked explicitly; it is not attached to
manuscript saves or a background process, and this slice exposes no HTTP or API
operation. The caller explicitly passes `model_name`, `prompt_root`, and
`audit_path` to `build_narrative_analysis_agent()`. The exact
`model_name="mock"` selects the local, network-free adapter, for example:

```python
agent = build_narrative_analysis_agent(
    model_name="mock",
    prompt_root=prompt_root,
    audit_path=audit_path,
)
```

A missing or blank explicit `model_name` fails the requested analysis without
preventing the unrelated backend process from starting. The analysis audit is separate from
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
  tests/narrative_memory/test_agent_composition.py \
  tests/narrative_memory/test_scene_analysis_result.py -v
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```
