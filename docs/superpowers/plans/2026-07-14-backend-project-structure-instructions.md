# Backend Project Structure Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the complete current Git-managed backend file tree and its maintenance rules to the instructions read by every backend subagent.

**Architecture:** Keep `backend/AGENTS.md` as the single source of truth for the backend tree because `.codex/agents/backend.toml` already requires reading it in full. Add one self-contained section without duplicating the tree in custom-agent configuration or changing runtime, domain, API, dependency, or verification behavior.

**Tech Stack:** Markdown, Git, Python 3.13 standard library

## Global Constraints

- Include every Git-managed path under `backend/` that exists when this plan is executed.
- Exclude `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, and other generated or ignored artifacts.
- Keep explicit assigned-path ownership authoritative; the tree is an inventory, not blanket edit permission.
- Require the tree to be updated in the same change whenever a managed backend file is created, deleted, renamed, or moved.
- Do not duplicate the tree in `.codex/agents/backend.toml`.
- Do not change runtime behavior, domain meaning, the OpenAPI contract, dependencies, or backend verification commands.

---

### Task 1: Document and validate the complete backend tree

**Files:**

- Modify: `backend/AGENTS.md`
- Reference: `.codex/agents/backend.toml`
- Reference: `docs/superpowers/specs/2026-07-14-backend-project-structure-instructions-design.md`

**Interfaces:**

- Consumes: the current output of `git ls-files backend` and the custom agent's existing requirement to read `backend/AGENTS.md`.
- Produces: a `Current Project Structure` instruction section containing the complete managed backend tree and same-change maintenance rules.

- [ ] **Step 1: Capture the current managed backend inventory**

Run from the repository root:

```sh
git ls-files backend | sort
```

Expected: the output contains exactly the backend instruction and setup files, `main.py`, `pyproject.toml`, `uv.lock`, the `apps/health` and `apps/writing_assistant` packages, `infrastructure/llm`, and their tests represented in the approved design.

- [ ] **Step 2: Run the instruction assertion and confirm it fails before the change**

Run from the repository root:

```sh
python3 - <<'PY'
from pathlib import Path

instructions = Path("backend/AGENTS.md").read_text()
required = (
    "## Current Project Structure",
    "backend/apps/writing_assistant/service/text_generation_port.py",
    "update this tree in the same change",
)
missing = [value for value in required if value not in instructions]
assert not missing, f"missing backend structure instructions: {missing}"
PY
```

Expected: FAIL with all three required structure-instruction markers listed as missing.

- [ ] **Step 3: Add the complete project structure section**

Insert the following section in `backend/AGENTS.md` after `## Scope` and before `## Architecture`:

````markdown
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
````

- [ ] **Step 4: Verify the instruction markers now pass**

Run from the repository root:

```sh
python3 - <<'PY'
from pathlib import Path

instructions = Path("backend/AGENTS.md").read_text()
required = (
    "## Current Project Structure",
    "text_generation_port.py",
    "update this tree in the same change",
    "The tree is context, not permission",
)
missing = [value for value in required if value not in instructions]
assert not missing, f"missing backend structure instructions: {missing}"
print("backend structure instructions: ok")
PY
```

Expected: `backend structure instructions: ok`.

- [ ] **Step 5: Verify the tree, exclusions, and custom-agent linkage**

Run from the repository root:

```sh
python3 - <<'PY'
from pathlib import Path
import subprocess
import tomllib

expected_paths = {
    "backend/AGENTS.md",
    "backend/README.md",
    "backend/apps/__init__.py",
    "backend/apps/health/__init__.py",
    "backend/apps/health/repository/__init__.py",
    "backend/apps/health/repository/health.py",
    "backend/apps/health/router/__init__.py",
    "backend/apps/health/router/health.py",
    "backend/apps/health/schemas/__init__.py",
    "backend/apps/health/schemas/health.py",
    "backend/apps/health/service/__init__.py",
    "backend/apps/health/service/health.py",
    "backend/apps/writing_assistant/__init__.py",
    "backend/apps/writing_assistant/repository/__init__.py",
    "backend/apps/writing_assistant/router/__init__.py",
    "backend/apps/writing_assistant/schemas/__init__.py",
    "backend/apps/writing_assistant/service/__init__.py",
    "backend/apps/writing_assistant/service/text_generation_port.py",
    "backend/infrastructure/__init__.py",
    "backend/infrastructure/llm/__init__.py",
    "backend/main.py",
    "backend/pyproject.toml",
    "backend/tests/health/test_repository.py",
    "backend/tests/health/test_service.py",
    "backend/tests/test_health_api.py",
    "backend/tests/writing_assistant/test_text_generation_port.py",
    "backend/uv.lock",
}
actual_paths = set(
    subprocess.check_output(["git", "ls-files", "backend"], text=True).splitlines()
)
assert actual_paths == expected_paths, (
    f"backend inventory mismatch: missing={expected_paths - actual_paths}, "
    f"unexpected={actual_paths - expected_paths}"
)

instructions = Path("backend/AGENTS.md").read_text()
for excluded in (".venv/", "__pycache__/", ".pytest_cache/", ".ruff_cache/"):
    assert excluded not in instructions, f"generated path documented: {excluded}"

agent = tomllib.loads(Path(".codex/agents/backend.toml").read_text())
assert "Read backend/README.md and any backend/AGENTS.md in full" in agent[
    "developer_instructions"
]
print("backend tree and agent linkage: ok")
PY
```

Expected: `backend tree and agent linkage: ok`.

- [ ] **Step 6: Review documentation scope and whitespace**

Run from the repository root:

```sh
git diff --check -- backend/AGENTS.md
git diff -- backend/AGENTS.md
git status --short
```

Expected: the whitespace check exits 0; the diff adds only the approved structure section to `backend/AGENTS.md`; no runtime, domain, API, dependency, verification-command, or custom-agent TOML file changes are present.

- [ ] **Step 7: Commit the backend structure instructions**

Run from the repository root:

```sh
git add backend/AGENTS.md
git commit -m "docs(backend): document current project structure"
```

Expected: one commit containing only `backend/AGENTS.md`.
