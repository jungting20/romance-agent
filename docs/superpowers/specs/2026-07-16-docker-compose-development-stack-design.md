# Docker Compose Development Stack Design

**Date:** 2026-07-16
**Status:** Approved
**Scope:** Local development orchestration for the frontend, backend,
PostgreSQL, and Neo4j

## Goal

Provide one repository-root command:

```sh
docker compose up --build
```

The command starts the React/Vite frontend, FastAPI backend, PostgreSQL, and
Neo4j together. Frontend and backend source changes reload without rebuilding
the application image. Database containers are ready for later integration but
do not change current persistence behavior.

## User Value

- A contributor can start the complete local stack without installing the
  Node.js or Python project toolchains on the host.
- The current frontend development experience remains available, including
  Vite hot module replacement and MSW-backed application scenarios.
- The backend remains directly observable through its health endpoint.
- PostgreSQL and Neo4j have stable local addresses and durable development
  volumes when application integration begins.

## Scope

### Included

- A root Compose file with `frontend`, `backend`, `postgres`, and `neo4j`
  services enabled by default.
- Development Dockerfiles for frontend and backend.
- Bind-mounted application source and container-owned dependency locations.
- Frontend HMR and backend Uvicorn reload.
- Health checks for all four services.
- Persistent named volumes for PostgreSQL, Neo4j, backend file data, and
  frontend dependencies.
- Local-only host port bindings.
- Development defaults with optional `.env` overrides documented through an
  example file.
- Future PostgreSQL and Neo4j connection settings supplied to the backend
  process but not consumed by backend code yet.
- A frontend MSW switch whose Compose default preserves the current mocked
  experience.
- Development documentation covering start, stop, status, logs, endpoints,
  credentials, and destructive volume cleanup.

### Excluded

- PostgreSQL or Neo4j client libraries in the backend.
- Migrations, schemas, constraints, seed data, or repositories for either
  database.
- Moving the current SQLite narrative-memory repository, file-backed Story
  Bible repository, or any domain data into a new database.
- Production images, TLS, reverse-proxy hardening, secrets management,
  clustering, backup, or deployment configuration.
- New or changed consumer-facing API operations.
- Changes to domain responsibilities, invariants, or contracts.
- Replacing frontend MSW scenarios with real backend implementations.

## Architecture

The root Compose project owns process orchestration and a private default
network. Each application retains its existing development server and project
toolchain.

```text
Host browser
  |
  +-- http://127.0.0.1:5173 --> frontend (Vite + React + MSW)
  |
  +-- http://127.0.0.1:8000 --> backend (Uvicorn + FastAPI)
  |
  +-- 127.0.0.1:5432 --------> postgres
  |
  +-- http://127.0.0.1:7474 --> neo4j Browser
  +-- 127.0.0.1:7687 --------> neo4j Bolt

Compose private network
  backend can later use postgres:5432 and neo4j:7687
```

All host port mappings bind to `127.0.0.1`. Container-to-container addresses
use Compose service names. Services report health independently; the backend
does not wait for databases it does not yet consume, so an unavailable future
dependency does not hide the currently working API.

## Components

### Root Compose Configuration

The root `compose.yaml` defines all services without profiles so the default
command starts the full stack. Service names are stable discovery names.

Default ports are overridable through environment variables:

| Service | Container port | Default host port |
| --- | ---: | ---: |
| Frontend | 5173 | 5173 |
| Backend | 8000 | 8000 |
| PostgreSQL | 5432 | 5432 |
| Neo4j Browser | 7474 | 7474 |
| Neo4j Bolt | 7687 | 7687 |

Compose supplies development-only default credentials so the first startup
requires no manual `.env` file. `.env.example` documents every override, and
the real `.env` remains untracked.

### Frontend Container

The frontend image uses the repository's Node 24 and pnpm 11 requirements. The
source tree is mounted at the container work directory and `node_modules` uses
a named volume so native host dependencies are not mixed with Linux container
dependencies. The startup command reconciles dependencies from the frozen lock
file before starting Vite on `0.0.0.0:5173`.

Vite receives Docker-compatible file-watching settings. Its existing MSW setup
is extended with `VITE_ENABLE_MSW`; Compose sets it to `true`, preserving
current screen behavior. A false value bypasses worker startup for later real
API integration, but this feature does not claim that all frontend operations
already have backend implementations.

The frontend health check requests its root document from inside the
container.

### Backend Container

The backend image uses Python 3.13 and uv. Dependencies are installed from
`pyproject.toml` and `uv.lock` into a container-owned virtual environment
outside the bind-mounted source directory. Uvicorn runs `main:app` with reload
enabled and listens on `0.0.0.0:8000`.

The existing file-backed Story Bible adapter receives
`ROMANCE_AGENT_DATA_ROOT=/data`, backed by a named volume. The backend also
receives these future integration settings:

- `DATABASE_URL=postgresql://<user>:<password>@postgres:5432/<database>`
- `NEO4J_URI=bolt://neo4j:7687`
- `NEO4J_USERNAME=neo4j`
- `NEO4J_PASSWORD=<development password>`

No backend module reads the database settings in this scope. The backend health
check calls `GET /health` from inside the container.

### PostgreSQL Container

PostgreSQL uses the official PostgreSQL 18 Alpine image line. Compose provides
the database name, user, and password and persists the PostgreSQL 18 data root
in a named volume mounted at `/var/lib/postgresql`. The health check uses
`pg_isready` with the configured user and database.

Using the PostgreSQL 18 volume root is intentional: the official image changed
its declared volume and version-specific `PGDATA` layout in PostgreSQL 18.

### Neo4j Container

Neo4j uses the pinned `neo4j:2026.06.0` Community Edition image. Compose sets
`NEO4J_AUTH=neo4j/<password>`, persists `/data`, and exposes Browser and Bolt
only on localhost. The configured development password must satisfy Neo4j's
minimum eight-character requirement. The health check authenticates through
`cypher-shell` and executes a read-only `RETURN 1` query.

No plugins are installed in this scope.

## Runtime Flow

1. Docker Compose builds the two development application images and creates
   the private network and named volumes.
2. All four services start as part of the default project.
3. PostgreSQL and Neo4j initialize their own data volumes and become healthy.
4. Uvicorn loads the existing FastAPI application and exposes `/health`.
5. Vite serves the frontend; MSW starts because Compose enables it.
6. Frontend requests covered by existing MSW handlers remain mocked. The
   backend can be inspected directly at port 8000.
7. Editing frontend or backend source on the host triggers the corresponding
   development reload mechanism.

## Failure Handling

- A failed health check marks only that service unhealthy and is visible in
  `docker compose ps`.
- Application services do not use an automatic restart policy, avoiding
  infinite restart loops caused by source or configuration errors.
- Frontend dependency reconciliation fails fast if its lock file and manifest
  disagree.
- Backend image creation fails fast if locked dependency installation fails.
- PostgreSQL and Neo4j data survive ordinary `docker compose down` and
  container recreation.
- Documentation clearly marks `docker compose down -v` as destructive because
  it deletes all Compose-owned data volumes.
- Credential changes after a database volume has been initialized do not
  rewrite the existing database credentials; developers must intentionally
  recreate the relevant volume when changing initialization credentials.

## Security and Local Boundaries

- Published ports bind only to IPv4 localhost.
- Credentials are explicitly development-only and overridable.
- `.env.example` contains no production secret.
- No database is configured for unauthenticated access.
- Neo4j Community Edition is used, so no enterprise license acceptance is
  required.
- This configuration is not an acceptable production deployment baseline.

## Files and Ownership

Expected implementation paths are:

- `compose.yaml`
- `.env.example`
- `.gitignore` only if the existing `.env` rule is insufficient
- `README.md`
- `frontend/Dockerfile.dev`
- `frontend/.dockerignore`
- `frontend/src/mocks/enable-mocking.ts`
- `frontend/src/mocks/enable-mocking.test.ts`
- `backend/Dockerfile.dev`

The implementation may adjust the exact file list when existing repository
patterns provide a better location, but it must not expand into database
integration or API behavior.

## Acceptance Criteria

1. `docker compose config` succeeds without requiring a local `.env` file.
2. `docker compose up --build -d` starts all four services.
3. All four services become healthy within documented startup timeouts.
4. `http://127.0.0.1:5173` serves the current frontend.
5. `http://127.0.0.1:8000/health` returns HTTP 200 with
   `{"status":"ok"}`.
6. PostgreSQL accepts an authenticated `SELECT 1` from inside its container.
7. Neo4j accepts an authenticated `RETURN 1` from inside its container.
8. A frontend source edit is visible without rebuilding its image.
9. A backend source edit triggers Uvicorn reload without rebuilding its image.
10. Ordinary shutdown preserves database and backend file data volumes.
11. Frontend MSW remains enabled by default in Compose, and its focused switch
    tests cover enabled and disabled behavior.
12. Existing frontend and backend full verification commands still pass.

## Verification

Static and application checks:

```sh
docker compose config

cd frontend
mise exec -- pnpm check
mise exec -- pnpm build

cd ../backend
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Stack checks:

```sh
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:5173/
curl --fail http://127.0.0.1:8000/health
docker compose exec postgres pg_isready
docker compose exec neo4j cypher-shell -u neo4j -p '<development password>' 'RETURN 1'
docker compose down
```

The implementation verification uses the configured environment values rather
than copying a password into shell history when practical.

## Documentation Sources

- PostgreSQL official image documentation:
  <https://hub.docker.com/_/postgres/>
- Neo4j Docker Operations Manual:
  <https://neo4j.com/docs/operations-manual/current/docker/introduction/>
