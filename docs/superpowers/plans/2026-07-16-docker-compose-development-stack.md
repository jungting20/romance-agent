# Docker Compose Development Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docker compose up --build` start the Vite frontend, FastAPI backend, PostgreSQL, and Neo4j as a hot-reloading local development stack.

**Architecture:** A root Compose project builds two development images, bind-mounts application source, and starts two official database images on a private network. MSW stays enabled by default, while the backend receives unused future database connection settings and retains its existing file-backed persistence under a named volume.

**Tech Stack:** Docker Compose v2, Node.js 24.18.0, pnpm 11.4.0, Vite 8, Python 3.13, uv 0.11.28, Uvicorn/FastAPI, PostgreSQL 18 Alpine, Neo4j Community 2026.06.0, Vitest

## Global Constraints

- The default command is exactly `docker compose up --build` from the repository root.
- The default Compose project starts `frontend`, `backend`, `postgres`, and `neo4j`; do not hide databases behind profiles.
- Bind all published host ports to `127.0.0.1`.
- Preserve Vite HMR, Uvicorn reload, and the current MSW-backed frontend behavior.
- Do not add PostgreSQL or Neo4j Python drivers, schemas, migrations, seed data, repositories, plugins, or API operations.
- Do not change SQLite narrative-memory persistence, file-backed Story Bible persistence, domain behavior, or `docs/domains/*.md`.
- Persist PostgreSQL at `/var/lib/postgresql`, Neo4j at `/data`, backend file data at `/data`, and frontend Linux dependencies at `/app/node_modules` using named volumes.
- Use `postgres:18-alpine` and `neo4j:2026.06.0`.
- Use development-only authenticated database defaults; never disable database authentication.
- Ordinary `docker compose down` preserves volumes; only the explicitly documented `docker compose down -v` deletes them.
- Run frontend commands from `frontend/` and backend commands from `backend/` through `mise exec --` where required by repository instructions.
- Preserve unrelated working-tree changes and do not use destructive Git commands.

## File Structure

| Path | Responsibility |
| --- | --- |
| `frontend/src/mocks/enable-mocking.ts` | Start MSW in development unless an explicit Vite environment switch disables it. |
| `frontend/src/mocks/enable-mocking.test.ts` | Prove default-enabled and explicit-disabled MSW behavior. |
| `frontend/src/vite-env.d.ts` | Type the `VITE_ENABLE_MSW` switch. |
| `frontend/Dockerfile.dev` | Provide the Node/pnpm development runtime and dependency layer. |
| `frontend/.dockerignore` | Exclude host artifacts from the frontend build context. |
| `backend/Dockerfile.dev` | Provide the Python/uv development runtime with its virtual environment outside the bind mount. |
| `backend/.dockerignore` | Exclude host artifacts from the backend build context. |
| `compose.yaml` | Orchestrate all four services, health checks, network discovery, ports, and named volumes. |
| `.env.example` | Document every supported local override and development credential. |
| `.gitignore` | Keep the real root `.env` untracked. |
| `README.md` | Document the one-command workflow, endpoints, operations, and data lifecycle. |

---

### Task 1: Add an Explicit MSW Development Switch

**Files:**
- Modify: `frontend/src/mocks/enable-mocking.ts`
- Modify: `frontend/src/mocks/enable-mocking.test.ts`
- Modify: `frontend/src/vite-env.d.ts`

**Interfaces:**
- Consumes: Vite's existing `import.meta.env.DEV` boolean.
- Produces: Optional `VITE_ENABLE_MSW: "true" | "false"`; `enableMocking(): Promise<void>` keeps its existing signature and skips dynamic worker import only when the value is exactly `"false"`.

- [ ] **Step 1: Extend the focused test with explicit disabled behavior**

Replace `frontend/src/mocks/enable-mocking.test.ts` with:

```ts
import { afterEach, describe, expect, test, vi } from "vitest";

const { start } = vi.hoisted(() => ({
  start: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/mocks/browser", () => ({
  worker: { start },
}));

import { enableMocking } from "@/mocks/enable-mocking";

describe("enableMocking", () => {
  afterEach(() => {
    start.mockClear();
    vi.unstubAllEnvs();
  });

  test("starts the browser worker in development by default", async () => {
    await enableMocking();

    expect(start).toHaveBeenCalledWith({ onUnhandledRequest: "bypass" });
  });

  test("does not start the browser worker when explicitly disabled", async () => {
    vi.stubEnv("VITE_ENABLE_MSW", "false");

    await enableMocking();

    expect(start).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the focused test and confirm the new case fails**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/enable-mocking.test.ts
```

Expected: the default-development test passes and `does not start the browser worker when explicitly disabled` fails because `start` is called once.

- [ ] **Step 3: Implement the minimal environment guard**

Replace `frontend/src/mocks/enable-mocking.ts` with:

```ts
export async function enableMocking(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITE_ENABLE_MSW === "false") {
    return;
  }

  const { worker } = await import("@/mocks/browser");

  await worker.start({ onUnhandledRequest: "bypass" });
}
```

Replace `frontend/src/vite-env.d.ts` with:

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_MSW?: "true" | "false";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

- [ ] **Step 4: Run focused and full frontend checks**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/enable-mocking.test.ts
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: 2 focused tests pass; all frontend checks and the production build pass. The build still excludes MSW startup because `import.meta.env.DEV` is false.

- [ ] **Step 5: Commit the MSW switch**

```sh
git add frontend/src/mocks/enable-mocking.ts frontend/src/mocks/enable-mocking.test.ts frontend/src/vite-env.d.ts
git commit -m "feat(frontend): make development mocks configurable"
```

---

### Task 2: Containerize the Hot-Reloading Application Services

**Files:**
- Create: `frontend/Dockerfile.dev`
- Create: `frontend/.dockerignore`
- Create: `backend/Dockerfile.dev`
- Create: `backend/.dockerignore`
- Create: `compose.yaml`

**Interfaces:**
- Consumes: `VITE_ENABLE_MSW` from Task 1, frontend `package.json`/`pnpm-lock.yaml`, backend `pyproject.toml`/`uv.lock`, FastAPI `GET /health`, and `ROMANCE_AGENT_DATA_ROOT`.
- Produces: Compose services `frontend` and `backend`; named volumes `frontend_node_modules` and `backend_data`; frontend endpoint `http://127.0.0.1:${FRONTEND_PORT:-5173}` and backend endpoint `http://127.0.0.1:${BACKEND_PORT:-8000}`.

- [ ] **Step 1: Create the frontend development image definition**

Create `frontend/Dockerfile.dev`:

```dockerfile
FROM node:24.18.0-bookworm-slim

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN corepack enable && corepack prepare pnpm@11.4.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173

CMD ["sh", "-c", "pnpm install --frozen-lockfile && pnpm dev --host 0.0.0.0 --port 5173"]
```

Create `frontend/.dockerignore`:

```text
node_modules
dist
coverage
*.tsbuildinfo
.git
.DS_Store
```

- [ ] **Step 2: Build the frontend development image**

Run from the repository root:

```sh
docker build --file frontend/Dockerfile.dev --tag romance-agent-frontend-dev:test frontend
```

Expected: the image builds successfully, including `pnpm install --frozen-lockfile`.

- [ ] **Step 3: Create the backend development image definition**

Create `backend/Dockerfile.dev`:

```dockerfile
FROM ghcr.io/astral-sh/uv:0.11.28-python3.13-trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --dev --no-install-project

COPY . .

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

Create `backend/.dockerignore`:

```text
.venv
__pycache__
*.py[cod]
.pytest_cache
.ruff_cache
.git
.DS_Store
```

- [ ] **Step 4: Build the backend development image**

Run from the repository root:

```sh
docker build --file backend/Dockerfile.dev --tag romance-agent-backend-dev:test backend
```

Expected: the image builds successfully, including locked development dependency installation into `/opt/venv`.

- [ ] **Step 5: Create the application-only Compose baseline**

Create `compose.yaml`:

```yaml
name: romance-agent

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    environment:
      CHOKIDAR_USEPOLLING: ${CHOKIDAR_USEPOLLING:-true}
      VITE_ENABLE_MSW: ${VITE_ENABLE_MSW:-true}
    ports:
      - "127.0.0.1:${FRONTEND_PORT:-5173}:5173"
    volumes:
      - ./frontend:/app
      - frontend_node_modules:/app/node_modules
    healthcheck:
      test:
        - CMD
        - node
        - -e
        - >-
          fetch('http://127.0.0.1:5173').then((response) => {
            if (!response.ok) process.exit(1)
          }).catch(() => process.exit(1))
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 20s

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    environment:
      ROMANCE_AGENT_DATA_ROOT: /data
    ports:
      - "127.0.0.1:${BACKEND_PORT:-8000}:8000"
    volumes:
      - ./backend:/app
      - backend_data:/data
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - >-
          import urllib.request;
          urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 10s

volumes:
  backend_data:
  frontend_node_modules:
```

- [ ] **Step 6: Validate the application Compose baseline**

Run from the repository root:

```sh
docker compose config --quiet
docker compose config --services | sort
```

Expected: configuration validation succeeds and service output is exactly:

```text
backend
frontend
```

- [ ] **Step 7: Commit the application containers**

```sh
git add compose.yaml frontend/Dockerfile.dev frontend/.dockerignore backend/Dockerfile.dev backend/.dockerignore
git commit -m "build: containerize local application services"
```

---

### Task 3: Add Prepared PostgreSQL and Neo4j Services

**Files:**
- Modify: `compose.yaml`
- Create: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Compose service-name DNS, backend `environment`, official PostgreSQL initialization variables, and Neo4j `NEO4J_AUTH`.
- Produces: Services `postgres` and `neo4j`; named volumes `postgres_data` and `neo4j_data`; future backend variables `DATABASE_URL`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.

- [ ] **Step 1: Add the two database services and future backend settings**

Replace `compose.yaml` with:

```yaml
name: romance-agent

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    environment:
      CHOKIDAR_USEPOLLING: ${CHOKIDAR_USEPOLLING:-true}
      VITE_ENABLE_MSW: ${VITE_ENABLE_MSW:-true}
    ports:
      - "127.0.0.1:${FRONTEND_PORT:-5173}:5173"
    volumes:
      - ./frontend:/app
      - frontend_node_modules:/app/node_modules
    healthcheck:
      test:
        - CMD
        - node
        - -e
        - >-
          fetch('http://127.0.0.1:5173').then((response) => {
            if (!response.ok) process.exit(1)
          }).catch(() => process.exit(1))
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 20s

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-romance_agent}:${POSTGRES_PASSWORD:-romance_agent_dev}@postgres:5432/${POSTGRES_DB:-romance_agent}
      NEO4J_PASSWORD: ${NEO4J_PASSWORD:-romance_agent_dev}
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USERNAME: neo4j
      ROMANCE_AGENT_DATA_ROOT: /data
    ports:
      - "127.0.0.1:${BACKEND_PORT:-8000}:8000"
    volumes:
      - ./backend:/app
      - backend_data:/data
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - >-
          import urllib.request;
          urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 10s

  postgres:
    image: postgres:18-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-romance_agent}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-romance_agent_dev}
      POSTGRES_USER: ${POSTGRES_USER:-romance_agent}
    ports:
      - "127.0.0.1:${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql
    healthcheck:
      test:
        - CMD-SHELL
        - pg_isready -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 10s

  neo4j:
    image: neo4j:2026.06.0
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-romance_agent_dev}
      NEO4J_PASSWORD: ${NEO4J_PASSWORD:-romance_agent_dev}
    ports:
      - "127.0.0.1:${NEO4J_HTTP_PORT:-7474}:7474"
      - "127.0.0.1:${NEO4J_BOLT_PORT:-7687}:7687"
    volumes:
      - neo4j_data:/data
    healthcheck:
      test:
        - CMD-SHELL
        - >-
          cypher-shell -a bolt://127.0.0.1:7687 -u neo4j
          -p "$${NEO4J_PASSWORD}" "RETURN 1" >/dev/null 2>&1
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 30s

volumes:
  backend_data:
  frontend_node_modules:
  neo4j_data:
  postgres_data:
```

Do not add `depends_on`: the applications do not consume the prepared database services yet, and all service health remains independently observable.

- [ ] **Step 2: Document environment overrides**

Create `.env.example`:

```dotenv
# Local-only published ports
FRONTEND_PORT=5173
BACKEND_PORT=8000
POSTGRES_PORT=5432
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687

# Frontend development behavior
VITE_ENABLE_MSW=true
CHOKIDAR_USEPOLLING=true

# Development-only database initialization credentials
POSTGRES_DB=romance_agent
POSTGRES_USER=romance_agent
POSTGRES_PASSWORD=romance_agent_dev
NEO4J_PASSWORD=romance_agent_dev
```

Append this entry to the root `.gitignore` after `.mise.local.toml`:

```gitignore
.env
```

- [ ] **Step 3: Validate interpolation, services, volumes, and local bindings**

Run from the repository root:

```sh
docker compose config --quiet
docker compose config --services
docker compose config --volumes
local_binding_count=$(docker compose config | rg -c '^\s+host_ip: 127\.0\.0\.1$')
test "$local_binding_count" -eq 5
```

Expected:

- configuration validation succeeds without a real `.env` file;
- services are `frontend`, `backend`, `postgres`, and `neo4j`;
- volumes are `backend_data`, `frontend_node_modules`, `neo4j_data`, and `postgres_data`;
- the rendered Compose model contains exactly five published ports with host
  IP `127.0.0.1`.

- [ ] **Step 4: Confirm backend database integration remains absent**

Run from the repository root:

```sh
rg -n "DATABASE_URL|NEO4J_URI|NEO4J_USERNAME|NEO4J_PASSWORD" backend --glob '*.py'
rg -n "psycopg|asyncpg|sqlalchemy|neo4j" backend/pyproject.toml backend/uv.lock
```

Expected: both commands return no matches and exit with status 1. Only Compose supplies future settings; backend code and dependencies remain unchanged.

- [ ] **Step 5: Commit the prepared infrastructure**

```sh
git add compose.yaml .env.example .gitignore
git commit -m "build: prepare local postgres and neo4j services"
```

---

### Task 4: Document and Verify the Complete Development Stack

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: all four Compose services and overrides from Tasks 1-3.
- Produces: contributor-facing commands for startup, health, logs, shutdown, and intentional volume deletion.

- [ ] **Step 1: Create the root development quickstart**

Create `README.md`:

````markdown
# Romance Agent

## Docker Compose development stack

Docker Desktop or another Docker Engine with Compose v2 is the only host
runtime required for the containerized workflow.

Start the frontend, backend, PostgreSQL, and Neo4j together from the repository
root:

```sh
docker compose up --build
```

Run in the background with `-d`:

```sh
docker compose up --build -d
docker compose ps
```

### Local endpoints

| Service | Address |
| --- | --- |
| Frontend | <http://127.0.0.1:5173> |
| Backend health | <http://127.0.0.1:8000/health> |
| PostgreSQL | `postgresql://romance_agent:romance_agent_dev@127.0.0.1:5432/romance_agent` |
| Neo4j Browser | <http://127.0.0.1:7474> |
| Neo4j Bolt | `bolt://127.0.0.1:7687` |

Neo4j uses username `neo4j` and the development password
`romance_agent_dev`.

The frontend uses its existing MSW scenarios by default. The backend runs at
the same time and can be checked directly through `/health`. PostgreSQL and
Neo4j are prepared for later integration; the backend does not use either
database yet.

### Configuration

The stack works without a `.env` file. To override ports, mock behavior, or
development credentials:

```sh
cp .env.example .env
```

The real `.env` file is ignored by Git. Database initialization credentials are
applied only when their data volumes are first created.

### Development operations

Frontend and backend source directories are mounted into their containers.
Vite hot module replacement and Uvicorn reload apply source edits without an
image rebuild.

```sh
docker compose logs -f frontend backend
docker compose exec backend uv run --no-sync pytest
docker compose exec frontend pnpm test
```

Stop containers while preserving all data:

```sh
docker compose down
```

Delete containers and all Compose-owned PostgreSQL, Neo4j, backend file, and
frontend dependency volumes:

```sh
docker compose down -v
```

`down -v` is destructive. Use it only when the local stack data should be
reinitialized.
````

- [ ] **Step 2: Run full static and application verification**

Run from the repository root:

```sh
docker compose config --quiet
git diff --check

cd frontend
mise exec -- pnpm check
mise exec -- pnpm build

cd ../backend
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: Compose configuration and diff checks succeed; frontend reports 26 passing test files and 212 or more passing tests, then builds successfully; backend reports 216 or more passing tests, Ruff lint succeeds, and Ruff reports all files formatted.

- [ ] **Step 3: Start an isolated verification stack on alternate ports**

Run from the repository root in one shell:

```sh
export COMPOSE_PROJECT_NAME=romance-agent-compose-test
export FRONTEND_PORT=15173
export BACKEND_PORT=18000
export POSTGRES_PORT=15432
export NEO4J_HTTP_PORT=17474
export NEO4J_BOLT_PORT=17687
export POSTGRES_DB=romance_agent_test
export POSTGRES_USER=romance_agent_test
export POSTGRES_PASSWORD=romance_agent_test_password
export NEO4J_PASSWORD=romance_agent_test_password

docker compose up --build --detach --wait --wait-timeout 180
docker compose ps
```

Expected: all four services are running and healthy under project
`romance-agent-compose-test`. If any service is unhealthy, inspect it before
continuing:

```sh
docker compose ps
docker compose logs frontend backend postgres neo4j
```

- [ ] **Step 4: Verify frontend, backend, PostgreSQL, and Neo4j behavior**

With the isolated stack environment from Step 3 still exported, run:

```sh
curl --fail --silent --show-error http://127.0.0.1:15173/ >/dev/null
curl --fail --silent --show-error http://127.0.0.1:18000/health
docker compose exec -T postgres psql -U romance_agent_test -d romance_agent_test -c "SELECT 1;"
docker compose exec -T neo4j cypher-shell -u neo4j -p romance_agent_test_password "RETURN 1;"
docker compose exec -T frontend test -f /app/src/main.tsx
docker compose exec -T backend test -f /app/main.py
```

Expected:

- frontend request exits 0;
- backend returns `{"status":"ok"}`;
- PostgreSQL prints one row containing `1`;
- Neo4j prints one row containing `1`;
- both source bind-mount checks exit 0.

Inspect the application commands to confirm reload modes are active:

```sh
docker compose top frontend
docker compose top backend
```

Expected: frontend includes `vite --host 0.0.0.0 --port 5173`; backend includes
`uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.

- [ ] **Step 5: Verify ordinary shutdown preserves database volumes**

With the same isolated stack environment, run:

```sh
docker compose down
docker volume inspect romance-agent-compose-test_postgres_data
docker volume inspect romance-agent-compose-test_neo4j_data
docker compose up --detach --wait --wait-timeout 180
docker compose exec -T postgres psql -U romance_agent_test -d romance_agent_test -c "SELECT 1;"
docker compose exec -T neo4j cypher-shell -u neo4j -p romance_agent_test_password "RETURN 1;"
```

Expected: both named volumes remain after `down`, all services become healthy
again, and both authenticated queries succeed without reinitialization errors.

- [ ] **Step 6: Clean up only the isolated verification project**

Run:

```sh
docker compose down -v --remove-orphans
unset COMPOSE_PROJECT_NAME FRONTEND_PORT BACKEND_PORT POSTGRES_PORT
unset NEO4J_HTTP_PORT NEO4J_BOLT_PORT POSTGRES_DB POSTGRES_USER
unset POSTGRES_PASSWORD NEO4J_PASSWORD
```

Expected: the `romance-agent-compose-test` containers, network, and named
volumes are removed. No default `romance-agent` project resources are touched.

- [ ] **Step 7: Commit documentation**

```sh
git add README.md
git commit -m "docs: add docker compose development quickstart"
```

- [ ] **Step 8: Record final diff and verification evidence**

Run from the repository root:

```sh
git status --short
base=$(git merge-base main HEAD)
git log --oneline --decorate "$base"..HEAD
git diff "$base"..HEAD --check
git diff "$base"..HEAD --stat
```

Expected: the worktree is clean; the design, MSW switch, application
containers, prepared databases, and quickstart commits are present; the diff
has no whitespace errors.

## Final Review Boundary

This is a tightly coupled repository-root development-infrastructure change
with one small frontend infrastructure switch and no backend application-code
change. Review the complete diff against:

- `docs/superpowers/specs/2026-07-16-docker-compose-development-stack-design.md`
- the four-service default startup requirement;
- localhost-only port publication;
- preservation of MSW defaults and existing persistence behavior;
- absence of new database drivers and domain/API changes;
- successful full frontend, backend, and live Compose verification evidence.

Any accepted review finding must be resolved before completion. Re-run the
focused MSW test for frontend-switch findings, `docker compose config` for
configuration findings, and the isolated live-stack verification for runtime
or healthcheck findings.
