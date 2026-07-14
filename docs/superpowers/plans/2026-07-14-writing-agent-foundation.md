# Writing Agent Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the backend Writing Assistant package foundation, define its provider-independent text-generation port, and install Pydantic AI.

**Architecture:** The Writing Assistant remains an existing bounded context under `backend/apps/`. Its service layer exposes an outbound `TextGenerationPort` protocol without importing Pydantic AI, while future provider-specific agent construction will live under `backend/infrastructure/llm/`.

**Tech Stack:** Python 3.13, uv, Pydantic AI, pytest, Ruff

## Global Constraints

- Keep Python compatibility at `>=3.13,<3.14`.
- Do not create or register an API router in this change.
- Do not configure credentials, choose an LLM model, or instantiate an agent.
- Keep `apps.writing_assistant.service.text_generation_port` independent of FastAPI, Pydantic AI, and provider SDKs.
- Do not modify `docs/domains/writing-assistant.md` or `docs/api/openapi.yaml`; this foundation preserves domain behavior and introduces no API operation.
- Preserve the user's unrelated frontend working-tree changes.

---

### Task 1: Add the Writing Assistant foundation and Pydantic AI dependency

**Files:**

- Create: `backend/apps/writing_assistant/__init__.py`
- Create: `backend/apps/writing_assistant/router/__init__.py`
- Create: `backend/apps/writing_assistant/schemas/__init__.py`
- Create: `backend/apps/writing_assistant/service/__init__.py`
- Create: `backend/apps/writing_assistant/service/text_generation_port.py`
- Create: `backend/apps/writing_assistant/repository/__init__.py`
- Create: `backend/infrastructure/__init__.py`
- Create: `backend/infrastructure/llm/__init__.py`
- Create: `backend/tests/writing_assistant/test_text_generation_port.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`

**Interfaces:**

- Consumes: Python's `typing.Protocol`.
- Produces: `TextGenerationPort.generate_text(prompt: str) -> Awaitable[str]` as the provider-independent structural interface for a future Writing Assistant service.

- [ ] **Step 1: Add Pydantic AI through the project package manager**

Run from `backend/`:

```sh
mise exec -- uv add pydantic-ai
```

Expected: exit code 0; `pyproject.toml` contains a `pydantic-ai` runtime dependency and `uv.lock` is refreshed.

- [ ] **Step 2: Write the failing structural-interface test**

Create `backend/tests/writing_assistant/test_text_generation_port.py`:

```python
import asyncio

from pydantic_ai import Agent

from apps.writing_assistant.service.text_generation_port import TextGenerationPort


class StubTextGenerator:
    async def generate_text(self, prompt: str) -> str:
        return prompt


def test_text_generator_implements_async_port_contract() -> None:
    generator: TextGenerationPort = StubTextGenerator()

    assert asyncio.run(generator.generate_text("prompt")) == "prompt"


def test_pydantic_ai_is_available() -> None:
    assert Agent.__module__.startswith("pydantic_ai")
```

- [ ] **Step 3: Run the focused test and confirm it fails for the missing package**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/writing_assistant/test_text_generation_port.py -v
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'apps.writing_assistant'`.

- [ ] **Step 4: Create the backend package scaffold**

Create empty package markers at:

```text
backend/apps/writing_assistant/__init__.py
backend/apps/writing_assistant/router/__init__.py
backend/apps/writing_assistant/schemas/__init__.py
backend/apps/writing_assistant/service/__init__.py
backend/apps/writing_assistant/repository/__init__.py
backend/infrastructure/__init__.py
backend/infrastructure/llm/__init__.py
```

Create `backend/apps/writing_assistant/service/text_generation_port.py`:

```python
from typing import Protocol


class TextGenerationPort(Protocol):
    async def generate_text(self, prompt: str) -> str: ...
```

- [ ] **Step 5: Run the focused test and import smoke check**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/writing_assistant/test_text_generation_port.py -v
mise exec -- uv run python -c "import pydantic_ai; from apps.writing_assistant.service.text_generation_port import TextGenerationPort; print(pydantic_ai.__name__, TextGenerationPort.__name__)"
```

Expected: two tests pass; the smoke check prints `pydantic_ai TextGenerationPort` without making a network request.

- [ ] **Step 6: Run complete backend verification**

Run from `backend/`:

```sh
mise exec -- uv sync --dev
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: dependency sync succeeds, all tests pass, Ruff reports no lint errors, and every Python file is already formatted.

- [ ] **Step 7: Compare the implementation against domain and API boundaries**

Run from the repository root:

```sh
git diff -- backend docs/domains docs/api
git status --short
```

Expected: only the planned backend foundation, dependency files, and test are changed; `docs/domains/` and `docs/api/` have no diff; unrelated frontend changes remain untouched.

- [ ] **Step 8: Commit the implementation**

Run from the repository root:

```sh
git add backend/apps/writing_assistant backend/infrastructure backend/tests/writing_assistant backend/pyproject.toml backend/uv.lock
git commit -m "feat(backend): add writing agent foundation"
```

Expected: the commit includes only the backend foundation and dependency changes.
