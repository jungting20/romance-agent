# Backend Project Structure Instructions Design

## Goal

Add the complete current backend source tree to the instructions read by every
backend subagent. The tree gives the agent an explicit inventory before it
selects files, follows existing patterns, or proposes new structure.

## Source of truth

Add a `Current Project Structure` section to `backend/AGENTS.md`.
The project-scoped custom agent at `.codex/agents/backend.toml` already requires
backend agents to read `backend/AGENTS.md` in full, so the tree must not be
duplicated in the TOML instructions.

The documented tree includes every Git-managed file under `backend/` at the
time of this design. Generated and local environment directories such as
`.venv/`, `__pycache__/`, `.pytest_cache/`, and `.ruff_cache/` are excluded.

## Documented structure

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

## Agent behavior

- Before backend work, compare the documented tree with the assigned paths and
  inspect the nearest implementation and test files.
- Treat the tree as an inventory, not permission to edit every listed file;
  explicit task ownership remains authoritative.
- When a task creates, deletes, renames, or moves a Git-managed backend file,
  update the tree in `backend/AGENTS.md` in the same change.
- Do not add generated caches, virtual environments, or other ignored artifacts
  to the tree.
- Continue to follow the architecture and verification rules already present
  in `backend/AGENTS.md` and the repository root instructions.

## Scope and compatibility

This change updates agent instructions only. It does not modify backend runtime
behavior, domain meaning, the OpenAPI contract, dependencies, or verification
commands. No `docs/domains/*.md` update is required.

## Verification

- Enumerate Git-managed backend files and compare them with the documented tree.
- Confirm `backend/AGENTS.md` still contains its existing scope, architecture,
  and verification sections.
- Confirm `.codex/agents/backend.toml` still requires reading
  `backend/AGENTS.md` in full.
- Run `git diff --check` for the changed documentation.

## Acceptance criteria

- `backend/AGENTS.md` contains the complete current Git-managed backend tree.
- Generated and ignored artifacts are absent from the tree.
- The instructions require same-change maintenance when managed backend paths
  are created, deleted, renamed, or moved.
- The tree does not weaken assigned-path ownership or existing architecture and
  verification rules.
- The custom backend-agent TOML does not duplicate the tree.
