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
│       ├── service/        # Application workflows, agent use case, domain coordination
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

The backend composes the public `NarrativeAnalysisAgent` facade and returns its
chunk-by-chunk scene analysis without translating it into a project snapshot.
It independently owns scene-to-project merging and persists immutable,
versioned canonical project JSON snapshots in SQLite. The separate `llm-agent/`
package owns chunking, prompts, and structured model calls.

`AnalyzeSceneUseCase` is the backend application boundary for an explicit scene
analysis request. It constructs the public request, invokes an injected
facade-compatible dependency, returns the public analysis unchanged, and
sanitizes public analysis errors without inspecting package-private causes.

Narrative Memory scene analysis is invoked explicitly; it is not attached to
manuscript saves or a background process, and this slice exposes no HTTP or API
operation. The caller explicitly passes `model_name` and `prompt_path` to
`build_narrative_analysis_agent()`, for example:

```python
agent = build_narrative_analysis_agent(
    model_name="provider:model",
    prompt_path=prompt_path,
)
```

A failed analysis does not automatically persist or merge its chunk results
into a scene or project snapshot.

For package-owned installed prompts, callers can explicitly select the public
helper result as the configured root:

```python
from narrative_analysis_agent import packaged_prompt_path

agent = build_narrative_analysis_agent(
    model_name="provider:model",
    prompt_path=packaged_prompt_path(),
)
```

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
  tests/narrative_memory/test_scene_analysis_use_case.py -v
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```
