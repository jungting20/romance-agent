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
├── infrastructure/audit/   # Application-owned LLM audit sink adapter
├── tests/                  # API, service, repository, and domain tests
├── docs/
│   ├── backend-coding-rules.md
│   └── llm-audit-logging.md
├── pyproject.toml
└── uv.lock
```

Keep domain-specific code inside its owning `apps/<domain>/` package. Update
this map when a structural change alters the responsibilities or major packages
shown here; individual files do not need to be listed.

LLM audit storage is application-owned infrastructure. The Narrative Memory
composition builders accept an optional `AgentAuditSink` and pass it unchanged
to the public agent facade; application startup chooses whether to inject the
JSONL sink. See [LLM audit logging operations](docs/llm-audit-logging.md) for
the secure configuration and lifecycle boundary.

The backend composes the public `NarrativeAnalysisAgent` facade and returns its
chunk-by-chunk scene analysis unchanged after independently merging the result
into the current scene set and persisting immutable, versioned canonical
project JSON snapshots in SQLite. The separate `llm-agent/` package owns
chunking, prompts, structured model calls, and read-only project graph access.

`AnalyzeSceneUseCase` is the backend application boundary for an explicit scene
analysis request. It constructs the public request, invokes an injected
facade-compatible dependency, verifies the analysis source snapshot version,
replaces the analyzed scene, rebuilds the next project snapshot, and commits
both records atomically. It returns the public analysis unchanged and sanitizes
analysis, merge, and repository errors without exposing internal causes.

Narrative Memory scene analysis is invoked explicitly; it is not attached to
manuscript saves or a background process, and this slice exposes no HTTP or API
operation. The normal composition path initializes the backend-owned database
and constructs the analysis workflow:

```python
from pathlib import Path

from narrative_analysis_agent import packaged_prompt_path

from apps.narrative_memory.composition import build_analyze_scene_use_case

data_root = Path("/srv/romance-agent/data")
use_case = build_analyze_scene_use_case(
    model_name="provider:model",
    prompt_path=packaged_prompt_path(),
    project_graph_path=data_root / "narrative-memory.sqlite3",
)
```

`build_analyze_scene_use_case()` calls `repository.initialize()` before the
agent opens its read-only project graph reader and passes the exact same
`project_graph_path` to both the reader and writer. Only a successful analysis
whose source snapshot version matches the current version reaches the atomic
scene-and-project commit; analysis, merge, or persistence failure publishes no
partial snapshot.

`build_narrative_analysis_agent()` is the lower-level facade builder. Its
`project_graph_path` is required, and backend code must initialize that exact
database file and its v2 tables before constructing the read-only agent:

```python
from pathlib import Path

from narrative_analysis_agent import packaged_prompt_path

from apps.narrative_memory.composition import build_narrative_analysis_agent
from apps.narrative_memory.repository.sqlite_snapshot_repository import (
    SQLiteSnapshotRepository,
)

data_root = Path("/srv/romance-agent/data")
project_graph_path = data_root / "narrative-memory.sqlite3"
repository = SQLiteSnapshotRepository(project_graph_path)
repository.initialize()
agent = build_narrative_analysis_agent(
    model_name="provider:model",
    prompt_path=packaged_prompt_path(),
    project_graph_path=project_graph_path,
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
