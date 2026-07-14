# FastAPI Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an executable FastAPI backend organized as `apps/{domain}/{router,service,repository,schemas}` and prove the layering with an approved `GET /health` contract and automated tests.

**Architecture:** The existing OpenAPI 3.1 document gains a root-level health operation and a matching MSW handler before backend implementation begins. The backend application composes a health router whose request path flows through a framework-independent service and repository; Pydantic stays at the transport boundary.

**Tech Stack:** Python 3.13, uv, FastAPI, Uvicorn, Pydantic, pytest, HTTPX TestClient, Ruff, OpenAPI 3.1, TypeScript, MSW, Vitest.

## Global Constraints

- Use `apps/{domain}/{router,service,repository,schemas}` packages exactly; do not rename the selected singular layer directories.
- Keep the dependency direction `router -> service -> repository` and keep FastAPI, Pydantic, HTTP, and persistence concerns out of the service.
- Implement only `GET /health` with `operationId: getHealth`, HTTP 200, and the exact body `{"status":"ok"}`.
- Keep `/health` at the root by using an operation-level `/` server override in the existing API contract, whose default server is `/api`.
- The frontend agent is the sole editor of `docs/api/openapi.yaml`; the main agent approves its exact baseline before backend implementation.
- Do not add a database, ORM, migrations, authentication, deployment configuration, external readiness checks, or shared abstractions.
- Domain meaning is unchanged; no `docs/domains/*.md` update is required.
- Preserve unrelated working-tree changes and stage only files owned by the current task.

---

### Task 1: Approve the Health API Contract and MSW Consumer

**Owned paths:**

- `docs/api/openapi.yaml`
- `frontend/src/mocks/data/health.ts`
- `frontend/src/mocks/handlers/health.ts`
- `frontend/src/mocks/handlers.ts`
- `frontend/src/mocks/health-handlers.test.ts`

**Files:**

- Modify: `docs/api/openapi.yaml`
- Create: `frontend/src/mocks/data/health.ts`
- Create: `frontend/src/mocks/handlers/health.ts`
- Modify: `frontend/src/mocks/handlers.ts`
- Test: `frontend/src/mocks/health-handlers.test.ts`

**Interfaces:**

- Consumes: the existing OpenAPI document with default server `/api` and the shared MSW server registered by `frontend/src/test/setup.ts`.
- Produces: approved operation `getHealth`, schema `HealthResponse`, `healthResponse: { readonly status: "ok" }`, and `healthHandlers: RequestHandler[]` for `GET /health`.

- [ ] **Step 1: Assign the frontend contract task**

Assign the project-scoped `frontend` agent all five owned paths above. Require it to read root `AGENTS.md`, `frontend/AGENTS.md`, the approved design, and current OpenAPI history:

```sh
git log --follow -- docs/api/openapi.yaml
```

The task must not edit backend files or domain documents. Its handoff must identify `getHealth`, the resulting commit SHA, the OpenAPI diff, MSW paths, assumptions, and all verification results.

- [ ] **Step 2: Write the failing MSW contract test**

Create `frontend/src/mocks/health-handlers.test.ts`:

```ts
import { describe, expect, test } from "vitest";

describe("health API handler", () => {
  test("returns the contracted process health response", async () => {
    const response = await fetch(`${window.location.origin}/health`);
    const body: unknown = await response.json();

    expect(response.status).toBe(200);
    expect(body).toEqual({ status: "ok" });
  });
});
```

- [ ] **Step 3: Run the focused test and verify RED**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/health-handlers.test.ts
```

Expected: FAIL because the shared MSW handler list has no `GET /health` handler and unhandled requests are configured as errors.

- [ ] **Step 4: Add the OpenAPI operation and response schema**

Add this tag beside the existing top-level tags:

```yaml
  - name: Health
    description: API 프로세스 가용성 확인
```

Add this path before the existing `/projects` path:

```yaml
  /health:
    get:
      servers:
        - url: /
      tags: [Health]
      operationId: getHealth
      summary: API 프로세스 상태 확인
      description: 외부 시스템 의존성 검사 없이 API 프로세스가 요청을 처리할 수 있음을 반환합니다.
      responses:
        "200":
          description: API 프로세스가 요청을 처리할 수 있음
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/HealthResponse"
              example:
                status: ok
```

Add this named schema at the start of `components.schemas`:

```yaml
    HealthResponse:
      type: object
      additionalProperties: false
      required: [status]
      properties:
        status:
          type: string
          enum: [ok]
          description: API 프로세스 가용 상태
```

- [ ] **Step 5: Implement the mock data and handler**

Create `frontend/src/mocks/data/health.ts`:

```ts
export const healthResponse = { status: "ok" } as const;
```

Create `frontend/src/mocks/handlers/health.ts`:

```ts
import { http, HttpResponse, type RequestHandler } from "msw";

import { healthResponse } from "@/mocks/data/health";

export const healthHandlers: RequestHandler[] = [
  http.get("/health", () => HttpResponse.json(healthResponse)),
];
```

Replace `frontend/src/mocks/handlers.ts` with:

```ts
import type { RequestHandler } from "msw";

import { healthHandlers } from "@/mocks/handlers/health";
import { projectHandlers } from "@/mocks/handlers/projects";

export const handlers: RequestHandler[] = [...healthHandlers, ...projectHandlers];
```

- [ ] **Step 6: Run the focused test and verify GREEN**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/health-handlers.test.ts
```

Expected: PASS with one passing test.

- [ ] **Step 7: Validate and hand off the frontend contract**

Run from `frontend/`:

```sh
mise exec -- pnpm api:lint
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: OpenAPI lint, formatting, lint, type checking, all frontend tests, and the production build exit successfully.

Commit only the owned paths:

```sh
git add ../docs/api/openapi.yaml src/mocks/data/health.ts src/mocks/handlers/health.ts src/mocks/handlers.ts src/mocks/health-handlers.test.ts
git commit -m "feat(api): define health check contract"
```

- [ ] **Step 8: Main-agent contract approval checkpoint**

From the repository root, inspect the exact committed baseline:

```sh
git show --stat --oneline HEAD
git show HEAD -- docs/api/openapi.yaml frontend/src/mocks
mise exec -- pnpm --dir frontend api:lint
```

Approve the commit SHA only if `getHealth`, the `/` operation server, `HealthResponse`, the MSW response, and the test all agree. Give that SHA and `operationId: getHealth` to the backend implementer. Do not start Task 2 before this approval.

### Task 2: Establish the Python Toolchain and Health Repository

**Owned paths:**

- `mise.toml`
- `mise.lock`
- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/apps/__init__.py`
- `backend/apps/health/__init__.py`
- `backend/apps/health/repository/__init__.py`
- `backend/apps/health/repository/health.py`
- `backend/tests/health/test_repository.py`

**Files:**

- Modify: `mise.toml`
- Modify: `mise.lock` through mise's lock resolution
- Create: `backend/pyproject.toml`
- Create: `backend/uv.lock` through uv's lock resolution
- Create: `backend/apps/__init__.py`
- Create: `backend/apps/health/__init__.py`
- Create: `backend/apps/health/repository/__init__.py`
- Create: `backend/apps/health/repository/health.py`
- Test: `backend/tests/health/test_repository.py`

**Interfaces:**

- Consumes: the main-approved OpenAPI baseline SHA from Task 1; Python 3.13 and uv supplied by root mise configuration.
- Produces: `HealthStatus = Literal["ok"]`, `HealthRepository.get_status() -> HealthStatus`, and `ProcessHealthRepository.get_status() -> HealthStatus`.

- [ ] **Step 1: Assign the backend implementation task**

Assign a backend subagent the Task 2 owned paths and the approved OpenAPI commit SHA. Require it to read root `AGENTS.md`, `backend/README.md`, the approved design, `docs/domains/README.md`, current `docs/api/openapi.yaml`, and its history:

```sh
git log --follow -- docs/api/openapi.yaml
```

The backend agent must confirm `operationId: getHealth` exists at the approved baseline, must not edit the OpenAPI file, and must report domain meaning as unchanged.

- [ ] **Step 2: Configure the root Python and uv toolchain**

Change root `mise.toml` to:

```toml
[tools]
node = "24.18.0"
"npm:pnpm" = "11.4.0"
python = "3.13"
uv = "latest"

[settings]
experimental = true
```

Run from the repository root:

```sh
mise install
```

Expected: mise installs the selected Python 3.13 and uv versions and refreshes `mise.lock` without changing the Node or pnpm selections.

- [ ] **Step 3: Add backend dependency and quality configuration**

Create `backend/pyproject.toml`:

```toml
[project]
name = "romance-agent-backend"
version = "0.1.0"
description = "FastAPI backend for Romance Agent"
requires-python = ">=3.13,<3.14"
dependencies = [
  "fastapi>=0.116,<1",
  "uvicorn[standard]>=0.35,<1",
]

[dependency-groups]
dev = [
  "httpx>=0.28,<1",
  "pytest>=8.4,<10",
  "ruff>=0.12,<1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Run from `backend/`:

```sh
mise exec -- uv lock
mise exec -- uv sync --dev
```

Expected: `uv.lock` is created and the runtime and development dependencies install successfully.

- [ ] **Step 4: Write the failing repository test**

Create `backend/tests/health/test_repository.py`:

```python
from apps.health.repository.health import ProcessHealthRepository


def test_process_health_repository_reports_ok() -> None:
    repository = ProcessHealthRepository()

    assert repository.get_status() == "ok"
```

- [ ] **Step 5: Run the repository test and verify RED**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/health/test_repository.py -v
```

Expected: FAIL during collection because `apps.health.repository.health` does not exist.

- [ ] **Step 6: Implement the repository boundary**

Create empty package markers:

- `backend/apps/__init__.py`
- `backend/apps/health/__init__.py`
- `backend/apps/health/repository/__init__.py`

Create `backend/apps/health/repository/health.py`:

```python
from typing import Literal, Protocol

HealthStatus = Literal["ok"]


class HealthRepository(Protocol):
    def get_status(self) -> HealthStatus: ...


class ProcessHealthRepository:
    def get_status(self) -> HealthStatus:
        return "ok"
```

- [ ] **Step 7: Run the repository test and verify GREEN**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/health/test_repository.py -v
mise exec -- uv run ruff check apps/health/repository tests/health/test_repository.py
mise exec -- uv run ruff format --check apps/health/repository tests/health/test_repository.py
```

Expected: the repository test and both focused Ruff checks pass.

- [ ] **Step 8: Commit the repository foundation**

From the repository root:

```sh
git add mise.toml mise.lock backend/pyproject.toml backend/uv.lock backend/apps/__init__.py backend/apps/health/__init__.py backend/apps/health/repository backend/tests/health/test_repository.py
git commit -m "build(backend): establish Python health repository"
```

### Task 3: Add the Framework-Independent Health Service

**Owned paths:**

- `backend/apps/health/service/__init__.py`
- `backend/apps/health/service/health.py`
- `backend/tests/health/test_service.py`

**Files:**

- Create: `backend/apps/health/service/__init__.py`
- Create: `backend/apps/health/service/health.py`
- Test: `backend/tests/health/test_service.py`

**Interfaces:**

- Consumes: `HealthRepository.get_status() -> HealthStatus` from Task 2.
- Produces: `HealthService(repository: HealthRepository)` and `HealthService.get_health() -> HealthStatus`.

- [ ] **Step 1: Write the failing service test**

Create `backend/tests/health/test_service.py`:

```python
from apps.health.repository.health import HealthStatus
from apps.health.service.health import HealthService


class RecordingHealthRepository:
    def __init__(self) -> None:
        self.called = False

    def get_status(self) -> HealthStatus:
        self.called = True
        return "ok"


def test_health_service_delegates_to_repository() -> None:
    repository = RecordingHealthRepository()
    service = HealthService(repository)

    result = service.get_health()

    assert result == "ok"
    assert repository.called is True
```

- [ ] **Step 2: Run the service test and verify RED**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/health/test_service.py -v
```

Expected: FAIL during collection because `apps.health.service.health` does not exist.

- [ ] **Step 3: Implement the service**

Create an empty `backend/apps/health/service/__init__.py` and create `backend/apps/health/service/health.py`:

```python
from apps.health.repository.health import HealthRepository, HealthStatus


class HealthService:
    def __init__(self, repository: HealthRepository) -> None:
        self._repository = repository

    def get_health(self) -> HealthStatus:
        return self._repository.get_status()
```

- [ ] **Step 4: Run the service test and verify GREEN**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/health/test_service.py -v
mise exec -- uv run ruff check apps/health/service tests/health/test_service.py
mise exec -- uv run ruff format --check apps/health/service tests/health/test_service.py
```

Expected: the service test and both focused Ruff checks pass.

- [ ] **Step 5: Commit the service layer**

From the repository root:

```sh
git add backend/apps/health/service backend/tests/health/test_service.py
git commit -m "feat(backend): add health service"
```

### Task 4: Expose the FastAPI Health Route and Document Backend Usage

**Owned paths:**

- `backend/apps/health/schemas/__init__.py`
- `backend/apps/health/schemas/health.py`
- `backend/apps/health/router/__init__.py`
- `backend/apps/health/router/health.py`
- `backend/main.py`
- `backend/tests/test_health_api.py`
- `backend/README.md`
- `backend/AGENTS.md`

**Files:**

- Create: `backend/apps/health/schemas/__init__.py`
- Create: `backend/apps/health/schemas/health.py`
- Create: `backend/apps/health/router/__init__.py`
- Create: `backend/apps/health/router/health.py`
- Create: `backend/main.py`
- Test: `backend/tests/test_health_api.py`
- Modify: `backend/README.md`
- Create: `backend/AGENTS.md`

**Interfaces:**

- Consumes: approved `getHealth` contract, `HealthService.get_health() -> HealthStatus`, and `ProcessHealthRepository`.
- Produces: `HealthResponse(status: Literal["ok"])`, `router: APIRouter`, `get_health_service() -> HealthService`, and `app: FastAPI` serving `GET /health`.

- [ ] **Step 1: Write the failing API integration tests**

Create `backend/tests/test_health_api.py`:

```python
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_get_health_returns_contracted_response() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_health_preserves_approved_operation_id() -> None:
    operation = app.openapi()["paths"]["/health"]["get"]

    assert operation["operationId"] == "getHealth"
```

- [ ] **Step 2: Run the API tests and verify RED**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/test_health_api.py -v
```

Expected: FAIL during collection because `main` does not exist.

- [ ] **Step 3: Implement the response schema**

Create an empty `backend/apps/health/schemas/__init__.py` and create `backend/apps/health/schemas/health.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
```

- [ ] **Step 4: Implement dependency composition and the router**

Create an empty `backend/apps/health/router/__init__.py` and create `backend/apps/health/router/health.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from apps.health.repository.health import ProcessHealthRepository
from apps.health.schemas.health import HealthResponse
from apps.health.service.health import HealthService

router = APIRouter(tags=["Health"])


def get_health_service() -> HealthService:
    return HealthService(ProcessHealthRepository())


@router.get("/health", operation_id="getHealth", response_model=HealthResponse)
def get_health(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    return HealthResponse(status=service.get_health())
```

- [ ] **Step 5: Compose the FastAPI application**

Create `backend/main.py`:

```python
from fastapi import FastAPI

from apps.health.router.health import router as health_router

app = FastAPI(title="Romance Agent API", version="0.1.0")
app.include_router(health_router)
```

- [ ] **Step 6: Run the API tests and verify GREEN**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/test_health_api.py -v
mise exec -- uv run ruff check apps/health/router apps/health/schemas main.py tests/test_health_api.py
mise exec -- uv run ruff format --check apps/health/router apps/health/schemas main.py tests/test_health_api.py
```

Expected: both API tests and both focused Ruff checks pass.

- [ ] **Step 7: Document backend ownership and commands**

Replace `backend/README.md` with:

````markdown
# Backend

FastAPI application code is organized by domain under `apps/`.

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
````

Create `backend/AGENTS.md`:

````markdown
# Backend Agent Instructions

## Scope

These instructions apply to `backend/` and extend the repository root `AGENTS.md`.

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
````

- [ ] **Step 8: Run the complete backend verification gate**

Run from `backend/`:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: all four backend tests pass, Ruff reports no lint errors, and Ruff reports every Python file already formatted.

- [ ] **Step 9: Commit the API application and documentation**

From the repository root:

```sh
git add backend/apps/health/router backend/apps/health/schemas backend/main.py backend/tests/test_health_api.py backend/README.md backend/AGENTS.md
git commit -m "feat(backend): expose FastAPI health endpoint"
```

### Task 5: Main-Agent Integration Verification

**Files:**

- Verify: `docs/api/openapi.yaml`
- Verify: `frontend/src/mocks/`
- Verify: `backend/`
- Verify: `mise.toml`
- Verify: `mise.lock`

**Interfaces:**

- Consumes: the approved frontend contract baseline and all backend task commits.
- Produces: evidence that the OpenAPI operation, frontend mock, FastAPI route, layer flow, documentation, and toolchain agree.

- [ ] **Step 1: Review owned diffs and working-tree isolation**

Run from the repository root:

```sh
git status --short
git log --oneline -5
git diff --check
git show --stat --oneline HEAD
```

Expected: task commits contain only assigned files, unrelated user changes remain preserved, and whitespace validation passes.

- [ ] **Step 2: Verify the frontend contract and consumer artifacts**

Run from `frontend/`:

```sh
mise exec -- pnpm api:lint
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: OpenAPI validation, all frontend quality checks and tests, and the production build pass.

- [ ] **Step 3: Verify the backend application**

Run from `backend/`:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: all backend tests pass and Ruff lint and formatting checks exit successfully.

- [ ] **Step 4: Compare contract and implementation semantics**

Confirm all of the following directly in the final files:

- OpenAPI path is `/health`, its operation-level server is `/`, and `operationId` is `getHealth`.
- OpenAPI `HealthResponse.status`, MSW `healthResponse.status`, Pydantic `HealthResponse.status`, and repository `HealthStatus` all permit exactly `"ok"`.
- The router calls `HealthService`; only dependency composition constructs `ProcessHealthRepository`.
- The service imports no FastAPI or Pydantic modules.
- `docs/domains/*.md` remain unchanged because process health introduces no business-domain responsibility or invariant.

- [ ] **Step 5: Report the integrated result**

Report changed files, approved OpenAPI commit SHA and `getHealth`, RED/GREEN evidence, final verification command results, and confirmation that domain meaning and unrelated user changes were preserved.
