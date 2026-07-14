# FastAPI Backend Foundation Design

## Goal

Create the first executable Python backend foundation with FastAPI. Organize
each domain under `apps/` as a self-contained vertical module whose request
handling flows through router, service, and repository packages.

The initial `health` domain proves that the application boots, dependencies are
wired correctly, and the layer boundaries can be tested without selecting a
database or persistence technology.

## Scope

This change includes:

- Python and `uv` toolchain configuration through the repository's existing
  `mise` setup
- a backend `pyproject.toml` with runtime, development, and test dependencies
- a FastAPI application entry point
- a `GET /health` operation added to the existing consumer-facing OpenAPI
  contract by the frontend agent and approved by the main agent before backend
  implementation
- a `health` domain implemented across router, service, repository, and schema
  packages
- unit tests for service and repository behavior
- an API integration test for `GET /health`
- backend setup, execution, and verification instructions

This change does not include a database, ORM, migrations, authentication,
deployment configuration, or a production readiness check against external
systems.

## Package Structure

```text
backend/
├── apps/
│   ├── __init__.py
│   └── health/
│       ├── __init__.py
│       ├── router/
│       │   ├── __init__.py
│       │   └── health.py
│       ├── service/
│       │   ├── __init__.py
│       │   └── health.py
│       ├── repository/
│       │   ├── __init__.py
│       │   └── health.py
│       └── schemas/
│           ├── __init__.py
│           └── health.py
├── tests/
│   ├── health/
│   │   ├── test_repository.py
│   │   └── test_service.py
│   └── test_health_api.py
├── main.py
├── pyproject.toml
└── README.md
```

New business domains follow the same
`apps/{domain}/{router,service,repository,schemas}` convention. Each layer
directory is a Python package containing focused modules. A domain owns the
implementation inside its directory. Direct mutation of another domain's state
is prohibited; future cross-domain workflows belong in an application use-case
or feature layer introduced when needed.

## Responsibilities

### Application entry point

`main.py` creates the FastAPI application and registers domain routers. It
contains no business or persistence logic.

### Router

The health router owns HTTP concerns: route declaration, dependency injection,
status codes, and response schema selection. It calls the service and does not
access the repository directly.

### Service

The health service coordinates the use case and returns the domain result
required by the router. It depends on the repository abstraction passed to it,
not on FastAPI request objects.

### Repository

The health repository owns the source of application-health state. The initial
implementation reports the process as available without connecting to an
external system. Its boundary allows a future readiness implementation to add
database or provider checks without moving those concerns into the service or
router.

### Schema

Pydantic response models define the consumer-facing payload. `GET /health`
returns HTTP 200 with:

```json
{
  "status": "ok"
}
```

## Request Flow

1. FastAPI receives `GET /health`.
2. The router obtains its service through `Depends`.
3. The service asks the injected repository for the current application status.
4. The service returns the result to the router.
5. FastAPI validates and serializes the result with the health response schema.

Dependency-provider functions live beside the layer they construct, keeping
the initial setup local to the health domain. They can be moved to a shared
composition module later if wiring becomes complex.

## API Contract Workflow

`docs/api/openapi.yaml` is the repository's existing OpenAPI 3.1 contract. The
frontend agent is the single editor and adds the complete `GET /health`
operation with `operationId: getHealth`, an operation-level `/` server override
so the route remains `/health` rather than inheriting the contract's `/api`
base URL, a `200` response, and a `HealthResponse` schema whose `status` field
accepts only `ok`. The operation defines no domain-specific error response
because the initial repository has no external failure mode. The main agent
reviews and approves the exact baseline before assigning backend implementation.

The backend agent implements only the approved operation and does not edit the
OpenAPI document. If the approved contract is infeasible, implementation stops
until the frontend agent evaluates a concrete change proposal and the main
agent approves a replacement baseline. The main agent finally verifies that
the OpenAPI document, FastAPI route, response schema, and integration test
describe the same behavior.

## Error Handling

The initial repository has no external failure mode, so the health endpoint's
defined behavior is the successful response only. The router must not catch
unexpected programming errors and convert them into a false healthy response;
FastAPI's default 500 handling remains in effect.

When external readiness checks are introduced, their failure semantics and API
contract must be designed explicitly before implementation.

## Testing

- Repository unit test: the initial implementation reports `ok`.
- Service unit test: a fake repository proves delegation and result propagation.
- API integration test: the application responds to `GET /health` with HTTP 200
  and the exact response body.
- Static verification: Ruff lint and formatting checks run over application and
  test code.

Verification commands run from `backend/`:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

The development server runs with:

```sh
mise exec -- uv run uvicorn main:app --reload
```

## Acceptance Criteria

- A clean checkout can install and run the backend with the documented `mise`
  and `uv` workflow.
- `GET /health` returns HTTP 200 and `{"status":"ok"}`.
- The request traverses router, service, and repository layers.
- Service behavior can be tested with a repository test double without FastAPI.
- No database or framework concern leaks into the service layer.
- All backend tests, lint checks, and formatting checks pass.
