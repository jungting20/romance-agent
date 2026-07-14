# Frontend API, Autosave, and Conflict Diff Design

## Goal

Connect the frontend to the approved project persistence API through TanStack Query v5, replace localStorage-owned server state, autosave manuscript edits after an 800 ms idle period, and resolve revision conflicts through a new scene-diff API and accessible comparison UI.

## Scope

The frontend agent owns the implementation under `frontend/`, the API-contract update in `docs/api/openapi.yaml`, and the matching semantic update in `docs/domains/manuscript.md`. The task includes:

- project list, project creation, project workspace, and manuscript save integration;
- a new scene-diff API operation and MSW behavior;
- TanStack Query application setup, typed adapters, query keys, queries, and mutations;
- loading, empty, error, saving, saved, and conflict UI states;
- 800 ms debounced manuscript autosave;
- line-based conflict comparison with local/server resolution actions;
- focused domain, transport, query, and UI tests.

The backend remains out of scope. During frontend development and tests, MSW implements the approved transport contract. The new OpenAPI revision is a frontend proposal until the main agent reviews and approves its exact baseline.

## API contract

### Existing operations

The frontend consumes the current operations without semantic changes:

- `listProjects`
- `createProjectWorkspace`
- `getProjectWorkspace`
- `saveManuscript`

The API adapter validates response status and converts an `ApiError` response into a typed error. React components never call `fetch` directly.

### New `compareManuscriptScene` operation

Add `POST /manuscripts/{manuscriptId}/scene-diffs` with `operationId: compareManuscriptScene` under the `Manuscripts` tag.

Request body:

```json
{
  "sceneId": "silver-garden-scene-1",
  "localContent": "서윤은 온실 문을 열었다."
}
```

Success response fields:

- `sceneId`: compared scene identifier;
- `serverRevision`: current persisted manuscript revision;
- `localContent`: submitted local scene content;
- `serverContent`: current persisted scene content;
- `serverManuscript`: current full server manuscript, used to preserve unrelated server changes when resolving the conflict;
- `rows`: aligned line-diff rows.

Each row contains:

- `kind`: `unchanged`, `local-only`, or `server-only`;
- `localLineNumber`: positive integer or `null`;
- `localText`: string or `null`;
- `serverLineNumber`: positive integer or `null`;
- `serverText`: string or `null`.

Declared responses:

- `200`: diff generated from the submitted local scene and current server scene;
- `400`: malformed JSON or schema violation;
- `404`: manuscript or scene does not exist;
- `422`: the scene exists but does not belong to the path manuscript;
- `500`: unexpected server failure.

The OpenAPI document includes named reusable schemas, representative request/success/error examples, and new machine-readable error codes needed to distinguish scene-not-found and invalid manuscript-scene relationship failures.

## Frontend architecture

### Application composition

Install `@tanstack/react-query` v5. Create one application-owned `QueryClient` and provide it from `src/app`. Tests create a fresh client with retries disabled so cache state does not leak across cases.

### API adapters and query keys

Typed API adapters under application infrastructure own URLs, JSON serialization, response parsing, and `ApiError` conversion. Stable feature-scoped query keys cover:

- the project list;
- a project workspace by project ID.

Feature hooks wrap the adapters:

- project list query;
- project creation mutation;
- project workspace query;
- manuscript save mutation;
- scene comparison mutation.

On project creation, the new workspace is inserted into its workspace cache and the project list cache is invalidated or updated before navigation. On manuscript save, the workspace cache receives the saved manuscript and revision, and the project list cache receives the returned activity timestamp.

### State ownership

Projects, concepts, story bibles, manuscripts, and manuscript revisions become Query cache server state. The existing localStorage snapshot, reducer, and state-provider path are removed from runtime use rather than maintained as a second source of truth.

The writing workspace owns only transient UI state and a local manuscript draft. Domain functions remain responsible for immutable manuscript edits; TanStack Query and transport details do not enter domain modules.

## Page behavior

### Library

The library uses `listProjects` and visibly represents loading, failure with retry, empty, and success states. Recent project ordering remains server-owned.

### Project creation

The setup page submits `createProjectWorkspace` through a mutation. While pending, repeated submission is disabled and visible progress copy is shown. Contract field errors are shown near their corresponding inputs; other failures appear as a form-level Korean error. Success navigates to the returned project workspace.

### Workspace loading

The writing page queries `getProjectWorkspace` from the route project ID. It shows a loading state, a retryable generic error, and a project-not-found state without redirecting transient failures to the library.

### Debounced autosave

Editing updates the local draft immediately. After 800 ms without another change, the feature saves the full manuscript with the last acknowledged revision. Only one save is active at a time; newer edits remain dirty and schedule the next save after the current request settles. The header exposes accessible `편집 중`, `저장 중`, `자동 저장됨`, and `저장 실패` states.

Successful saves replace the acknowledged manuscript and revision while preserving any newer local edit. Non-conflict errors keep the local draft, show the failure state, and allow retry through a labelled action.

## Conflict flow and diff UI

When `saveManuscript` returns `409 MANUSCRIPT_REVISION_CONFLICT`:

1. Suspend autosave for the conflicting draft.
2. Call `compareManuscriptScene` for the active scene and its local content.
3. Open a labelled modal dialog with side-by-side `내 편집본` and `서버 최신본` columns.
4. Render aligned rows with line numbers and textual added/removed labels; color is supplementary and never the only signal.
5. Offer `내 편집본 유지` and `서버 최신본 적용` actions.

`내 편집본 유지` starts from `serverManuscript`, replaces only the compared scene content with `localContent`, and calls `saveManuscript` with `serverRevision`. This preserves unrelated server changes. A second revision conflict requests a fresh diff and keeps the dialog open.

`서버 최신본 적용` replaces the local draft and workspace cache with `serverManuscript`, acknowledges `serverRevision`, closes the dialog, and returns the autosave state to saved.

The dialog traps focus, has an accessible name, supports Escape without discarding the local draft, and makes both resolution consequences explicit in Korean copy.

## MSW behavior

Register the new handler through `src/mocks/handlers.ts`. It reads the current in-memory manuscript, validates manuscript-scene ownership, and produces deterministic line-level rows. A small pure line-diff function may use a longest-common-subsequence strategy; no additional diff dependency is introduced.

Shared MSW defaults cover the success path. Focused tests override handlers for list/load/create/save errors, revision conflicts, diff errors, and repeated conflicts. Mock state resets between tests.

## Testing

Tests use fake timers for the 800 ms boundary and MSW for transport behavior. Coverage includes:

- typed adapter success and `ApiError` conversion;
- project list loading, empty, retryable error, and success;
- project creation pending, field error, generic error, cache update, and navigation;
- workspace loading, not-found, retryable error, and success;
- no save before 800 ms, one save after idle, and serialization of overlapping edits;
- cache and revision updates after a successful save;
- non-conflict save failure with retained draft and retry;
- 409 triggering exactly one scene-diff request;
- aligned local/server rows and accessible conflict controls;
- local resolution preserving unrelated fields from `serverManuscript`;
- server resolution replacing the draft;
- repeated conflict refreshing the diff without losing local content.

Run from `frontend/`:

```sh
mise exec -- pnpm api:lint
mise exec -- pnpm check
mise exec -- pnpm build
```

The existing unrelated `seed.spec.ts` Playwright/Vitest collection issue must not be hidden. If it remains in the baseline, report it separately and run all focused affected tests in addition to the required commands.

## Domain documentation

Update `docs/domains/manuscript.md` to describe comparison of a local scene draft with a persisted scene as a Manuscript use case. Add invariants that both compared versions refer to the same manuscript scene and that comparison does not mutate either input. This semantic update stays technology- and transport-neutral; TanStack Query, HTTP paths, revisions, and diff wire rows remain outside the domain document.

The context-map dependency direction does not change, so `docs/domains/README.md` does not require modification.

## Acceptance criteria

- The four existing persistence operations are consumed through TanStack Query v5 and typed adapters.
- localStorage is no longer the owner of API-backed project/workspace state.
- Editing is immediate locally and autosaves after 800 ms idle without parallel save races.
- A save revision conflict calls the new diff operation and opens a line-based accessible comparison UI.
- Users can keep the local scene or apply the server manuscript without silent text loss.
- OpenAPI, frontend types, MSW, adapters, tests, and `docs/domains/manuscript.md` describe the same scene-diff behavior.
- Pure domain modules remain independent of React, TanStack Query, browser APIs, storage, and transport.
- Required verification is run and all new failures are resolved; unrelated baseline failures are reported explicitly.
