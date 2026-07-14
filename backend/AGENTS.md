# Backend Agent Instructions

## Scope

These instructions apply to `backend/` and extend the repository root `AGENTS.md`.

## Current Project Structure

Before backend work, compare the assigned paths with this complete inventory of
Git-managed backend files and inspect the nearest implementation and test
patterns. The tree is context, not permission to edit files outside the paths
assigned by the main agent.

```text
backend/
├── AGENTS.md
├── README.md
├── main.py
├── pyproject.toml
├── uv.lock
├── apps/
│   ├── __init__.py
│   ├── health/
│   │   ├── __init__.py
│   │   ├── repository/
│   │   │   ├── __init__.py
│   │   │   └── health.py
│   │   ├── router/
│   │   │   ├── __init__.py
│   │   │   └── health.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── health.py
│   │   └── service/
│   │       ├── __init__.py
│   │       └── health.py
│   └── writing_assistant/
│       ├── __init__.py
│       ├── repository/
│       │   └── __init__.py
│       ├── router/
│       │   └── __init__.py
│       ├── schemas/
│       │   └── __init__.py
│       └── service/
│           ├── __init__.py
│           └── text_generation_port.py
├── infrastructure/
│   ├── __init__.py
│   └── llm/
│       └── __init__.py
└── tests/
    ├── test_health_api.py
    ├── health/
    │   ├── test_repository.py
    │   └── test_service.py
    └── writing_assistant/
        └── test_text_generation_port.py
```

When a task creates, deletes, renames, or moves a Git-managed file under
`backend/`, update this tree in the same change. Do not add virtual
environments, caches, generated files, or ignored artifacts to the tree.

## Architecture

- Put domain code under `apps/{domain}/{router,service,repository,schemas}`.
- Keep HTTP and Pydantic concerns in `router` and `schemas`.
- Keep services independent of FastAPI, browser concerns, persistence technology, and external providers.
- Routers call services; routers must not access repositories directly.
- Cross-domain workflows belong in an application use-case layer introduced when required.

## Verification

Run from `backend/` before completion:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```
