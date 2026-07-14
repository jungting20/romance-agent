# State Persistence API Contract Design

## Goal

Define the first consumer-facing API contract for persisting the Romance Agent
frontend's domain state, together with contract-aligned TypeScript transport
types, representative mock data, and stateful MSW handlers. This change prepares
the frontend for a later API-adapter integration without converting the current
`AppProvider` from synchronous local storage in this scope.

## Scope

- Create the authoritative OpenAPI 3.1 contract at `docs/api/openapi.yaml`.
- Specify project-library loading, atomic workspace creation, workspace loading,
  and manuscript saving.
- Add frontend transport types aligned with the wire contract.
- Add representative success and error mock data.
- Add stateful MSW handlers shared by browser development and Vitest.
- Add contract-focused tests for success, validation, not-found, and concurrency
  behavior.
- Add OpenAPI linting with `@redocly/cli` and run the full frontend checks.

The current `AppProvider` and `createAppStorage` local-storage integration remain
unchanged. Connecting the UI to the API is a separate follow-up change after the
main agent approves this contract and a backend implementation can target the
same baseline.

## Ownership and Domain Boundaries

The transport contract exposes application use cases rather than independent
CRUD operations for every domain aggregate.

- Projects owns project identity, library metadata, and recent activity time.
- Story Design owns the validated trope and initial story concept.
- Story Bible owns characters and world entries.
- Manuscript owns scenes, active-scene state, and manuscript text.
- The application layer coordinates atomic workspace creation and manuscript
  saving across domain boundaries.

The contract preserves the existing domain meaning and dependency directions.
It adds transport and persistence details only, so no `docs/domains/*.md` change
is required. `lastProjectId` is a browser-owned UI preference and is excluded
from every request and response.

## API Operations

### List Projects

`GET /projects`, with `operationId: listProjects`, returns project metadata in
descending `updatedAt` order. The response is an object containing an `items`
array. The array is never nullable and may be empty. Pagination is excluded from
the initial contract because the current product has no pagination use case.

### Create Project Workspace

`POST /projects`, with `operationId: createProjectWorkspace`, accepts only the
user-authored inputs `title`, `logline`, `tropeId`, and exactly two
`protagonistNames`. The server generates identifiers and timestamps, validates
the domain input, and atomically creates the Project, Story Concept, Story Bible,
and initial Manuscript. A successful response is `201 Created`, includes a
`Location` header for `/projects/{projectId}/workspace`, and returns the complete
workspace plus `manuscriptRevision`.

No partially created workspace is observable. If any domain validation fails,
the operation returns an error and creates nothing.

### Get Project Workspace

`GET /projects/{projectId}/workspace`, with
`operationId: getProjectWorkspace`, returns the Project, Story Concept, Story
Bible, Manuscript, and current `manuscriptRevision`. An unknown project returns
`404 PROJECT_NOT_FOUND`.

### Save Manuscript

`PUT /manuscripts/{manuscriptId}`, with `operationId: saveManuscript`, accepts
the complete Manuscript representation and `expectedRevision`. The path
identifier, body manuscript identifier, and project relationship must agree.
The application use case validates and saves the Manuscript, increments its
revision, and updates the owning Project's `updatedAt` in one transaction.

A successful response returns the stored Manuscript, its new revision, and the
updated Project identity and activity time. If `expectedRevision` is stale, the
operation returns `409 MANUSCRIPT_REVISION_CONFLICT` without changing stored
state. This transport-level revision protects against silent overwrites without
changing the Manuscript domain model.

## Wire Model

Identifiers are non-empty strings. Timestamps use RFC 3339 UTC date-time
strings. Collections are required arrays and never nullable.

The OpenAPI document defines reusable component schemas for:

- `Project`
- `StoryConcept`
- `Character`
- `WorldEntry`
- `StoryBible`
- `Scene`
- `Manuscript`
- `ProjectWorkspace`
- `CreateProjectRequest`
- `ProjectListResponse`
- `SaveManuscriptRequest`
- `SaveManuscriptResponse`
- `ApiError`
- `FieldError`

Stable enums include the four registered trope identifiers, protagonist role,
and world-entry kind. Tuple constraints require exactly two protagonist names.
Scene chapter numbers and manuscript revisions are non-negative integers, with
revisions beginning at `1` for a newly created manuscript.

The API has no authentication or authorization requirement in this baseline.
It also has no pagination, idempotency-key, or deletion behavior.

## Error Contract

Every error response uses `ApiError`:

```json
{
  "code": "MANUSCRIPT_REVISION_CONFLICT",
  "message": "다른 위치에서 원고가 먼저 수정되었습니다.",
  "fieldErrors": []
}
```

`fieldErrors` is always an array. Entries contain a request-field path and a
Korean user-facing message. The stable machine-readable error codes are:

- `MALFORMED_REQUEST` with HTTP 400
- `PROJECT_NOT_FOUND` with HTTP 404
- `MANUSCRIPT_NOT_FOUND` with HTTP 404
- `MANUSCRIPT_REVISION_CONFLICT` with HTTP 409
- `INVALID_TITLE` with HTTP 422
- `INVALID_TROPE` with HTTP 422
- `INVALID_PROTAGONISTS` with HTTP 422
- `INVALID_MANUSCRIPT` with HTTP 422
- `INTERNAL_ERROR` with HTTP 500

Malformed JSON and structurally invalid request bodies use 400. Well-formed
requests that violate domain or cross-resource invariants use 422. The OpenAPI
contract includes representative request, success, and error examples for every
operation and expected response status.

## Frontend Artifacts

Transport types live in
`frontend/src/app/infrastructure/api/contracts.ts`. They model the wire contract
without changing or replacing the pure domain types. The types use explicit
unions and tuples and do not use `any` or broad casts.

Representative data lives in
`frontend/src/mocks/data/project-workspaces.ts`. The initial mock state contains
the existing `은빛 정원의 약속` workspace and revision `1`, plus reusable error
payloads for contract tests.

Project API handlers live in
`frontend/src/mocks/handlers/projects.ts` and are registered through the existing
`frontend/src/mocks/handlers.ts` collection so browser development and Vitest
exercise the same behavior.

The mock API keeps an in-memory workspace collection and exposes a focused reset
function. `frontend/src/test/setup.ts` resets that data after every test so test
order cannot affect results. The shared handlers implement:

1. recent-first project listing;
2. atomic workspace creation and subsequent visibility in list/get operations;
3. workspace lookup with project-not-found handling;
4. manuscript saving, revision increments, and project activity updates;
5. manuscript-not-found and invalid-manuscript handling;
6. stale-revision conflict handling without state mutation; and
7. create-input validation for title, trope, and protagonist names.

Shared development handlers do not contain magic headers, query parameters, or
reserved values that trigger artificial server failures. A test that needs an
`INTERNAL_ERROR` response uses a focused `server.use()` override.

## Testing and Validation

`frontend/src/mocks/project-handlers.test.ts` performs observable HTTP requests
through the MSW Node server and verifies methods, paths, status codes, headers,
and payloads for:

- project listing and ordering;
- project creation and `Location`;
- reading the newly created workspace;
- unknown project lookup;
- successful manuscript save and revision increment;
- observable project activity-time update;
- stale-revision conflict with unchanged stored data;
- unknown manuscript;
- invalid project creation inputs; and
- test-local internal-server-error override.

OpenAPI validation uses a pinned `@redocly/cli` development dependency and an
`api:lint` package script. Final verification runs from `frontend/`:

```sh
mise exec -- pnpm api:lint
mise exec -- pnpm exec vitest run src/mocks/project-handlers.test.ts
mise exec -- pnpm check
mise exec -- pnpm build
```

The implementation must preserve unrelated user changes. Existing untracked
Playwright artifacts are outside this work and must not be edited.

## Out of Scope

- Replacing `AppProvider` or `createAppStorage` with asynchronous API calls
- Backend framework or persistence implementation
- Authentication, authorization, users, or multi-tenant ownership
- Editing Story Concept or Story Bible after workspace creation
- Project deletion, project metadata editing, or manuscript history
- Persisting `lastProjectId`
- Writing Assistant API operations

## API Contract Handoff Requirements

The frontend subagent returns the required handoff to the main agent with:

- Spec path and an exact diff baseline
- `listProjects`, `createProjectWorkspace`, `getProjectWorkspace`, and
  `saveManuscript` operation identifiers
- The five reviewed domain-contract paths
- Explicit assumptions
- Transport type, mock-data, handler, and test paths
- OpenAPI lint, focused test, full check, and build results

The frontend subagent authors the draft but does not approve it. The main agent
reviews and approves the exact OpenAPI baseline after checking the implementation
and domain alignment.
