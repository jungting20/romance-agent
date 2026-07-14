# State Persistence API Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an approved-ready OpenAPI 3.1 draft and contract-aligned frontend types, mock data, and stateful MSW handlers for project workspace persistence.

**Architecture:** Expose application use cases instead of an app-state snapshot or domain-by-domain CRUD. One OpenAPI document defines project listing, atomic workspace creation, workspace loading, and revision-safe manuscript saving; frontend transport types and one in-memory MSW state implement the same wire behavior without changing `AppProvider` or domain models.

**Tech Stack:** OpenAPI 3.1, Redocly CLI 2.39.0, TypeScript 7 strict mode, MSW 2.15, Vitest 4, pnpm 11.4

## Global Constraints

- `docs/api/openapi.yaml` has one editor: the assigned frontend subagent. No backend or other agent may edit it concurrently.
- The draft is not approved until the main agent reviews its exact diff; the frontend subagent must not approve its own contract.
- Operations are exactly `listProjects`, `createProjectWorkspace`, `getProjectWorkspace`, and `saveManuscript`.
- `lastProjectId` is browser-owned and must not appear in the OpenAPI document, transport types, mock data, or handlers.
- Do not modify `AppProvider`, `createAppStorage`, backend files, or any `docs/domains/*.md` file.
- Do not add authentication, pagination, deletion, project editing, Story Bible editing, Story Concept editing, or Writing Assistant operations.
- Preserve the current domain names and invariants from `docs/domains/README.md`, `projects.md`, `story-design.md`, `story-bible.md`, and `manuscript.md`.
- `POST /projects` atomically creates and returns Project, Story Concept, Story Bible, initial Manuscript, and `manuscriptRevision: 1`.
- `PUT /manuscripts/{manuscriptId}` saves the complete manuscript, increments the expected revision, and updates the owning project's `updatedAt` atomically.
- A stale manuscript revision returns HTTP 409 without mutating mock state.
- Identifiers are non-empty strings, timestamps are RFC 3339 UTC date-times, and collections are required non-null arrays.
- Shared MSW handlers must not include artificial error trigger headers, query parameters, or reserved field values.
- Existing untracked `.codex/`, `seed.spec.ts`, and `specs/` paths belong to the user and must not be edited, formatted, staged, or committed.

---

### Task 1: Author and Validate the OpenAPI Contract

**Files:**

- Create: `docs/api/openapi.yaml`
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`

**Interfaces:**

- Consumes: the approved design in `docs/superpowers/specs/2026-07-14-state-persistence-api-contract-design.md` and the five domain contracts named in Global Constraints.
- Produces: OpenAPI component schema and operation names that Tasks 2 and 3 reproduce exactly.

- [ ] **Step 1: Install the pinned contract linter**

Run from `frontend/`:

```sh
mise exec -- pnpm add --save-dev '@redocly/cli@2.39.0'
```

Add this script to `package.json`:

```json
"api:lint": "redocly lint ../docs/api/openapi.yaml"
```

Expected: `package.json` and `pnpm-lock.yaml` record Redocly CLI 2.39.0, which supports the repository's Node 24 toolchain.

- [ ] **Step 2: Write the OpenAPI 3.1 document**

Create `docs/api/openapi.yaml` with `openapi: 3.1.0`, title
`Romance Agent API`, version `0.1.0`, the relative server URL `/api`, and the
four exact method/path/operation mappings below. Add Korean summaries and
domain-oriented descriptions, path parameters, `application/json` content,
required fields, all response schemas and headers, and representative examples
for every listed status. Define these named schemas with
`additionalProperties: false` on object schemas:

```text
GET /projects -> listProjects
POST /projects -> createProjectWorkspace
GET /projects/{projectId}/workspace -> getProjectWorkspace
PUT /manuscripts/{manuscriptId} -> saveManuscript
```

```text
ProjectId, ConceptId, ManuscriptId, SceneId, CharacterId, WorldEntryId
TropeId, WorldEntryKind, CharacterRole
Project, StoryConcept, Character, WorldEntry, StoryBible, Scene, Manuscript
ProjectWorkspace, CreateProjectRequest, ProjectListResponse
SaveManuscriptRequest, SavedProjectActivity, SaveManuscriptResponse
ApiErrorCode, FieldError, ApiError
```

Use the exact operation response matrix:

| Operation | Success | Errors |
| --- | --- | --- |
| `listProjects` | 200 `ProjectListResponse` | 500 `INTERNAL_ERROR` |
| `createProjectWorkspace` | 201 `ProjectWorkspace` plus required `Location` header | 400 `MALFORMED_REQUEST`; 422 `INVALID_TITLE`, `INVALID_TROPE`, or `INVALID_PROTAGONISTS`; 500 `INTERNAL_ERROR` |
| `getProjectWorkspace` | 200 `ProjectWorkspace` | 404 `PROJECT_NOT_FOUND`; 500 `INTERNAL_ERROR` |
| `saveManuscript` | 200 `SaveManuscriptResponse` | 400 `MALFORMED_REQUEST`; 404 `MANUSCRIPT_NOT_FOUND`; 409 `MANUSCRIPT_REVISION_CONFLICT`; 422 `INVALID_MANUSCRIPT`; 500 `INTERNAL_ERROR` |

Define `ProjectWorkspace` exactly as a required object containing `project`, `concept`, `storyBible`, `manuscript`, and integer `manuscriptRevision` with `minimum: 1`. Define `CreateProjectRequest.protagonistNames` with `minItems: 2` and `maxItems: 2`. Define `SaveManuscriptRequest` as a required object containing `manuscript` and `expectedRevision` with `minimum: 1`. Define `SaveManuscriptResponse` as a required object containing `manuscript`, `manuscriptRevision`, and `projectActivity`, where `projectActivity` contains `projectId` and `updatedAt`.

Use the exact stable enum values:

```yaml
TropeId: [rivals-to-lovers, contract-romance, reunion, friends-to-lovers]
WorldEntryKind: [place, object, rule]
CharacterRole: [protagonist]
ApiErrorCode:
  - MALFORMED_REQUEST
  - PROJECT_NOT_FOUND
  - MANUSCRIPT_NOT_FOUND
  - MANUSCRIPT_REVISION_CONFLICT
  - INVALID_TITLE
  - INVALID_TROPE
  - INVALID_PROTAGONISTS
  - INVALID_MANUSCRIPT
  - INTERNAL_ERROR
```

- [ ] **Step 3: Lint the contract and correct every error**

Run:

```sh
mise exec -- pnpm api:lint
```

Expected: exit 0 with no OpenAPI structural errors. Warnings must be corrected unless they conflict with an approved design requirement; do not add blanket Redocly rule suppressions.

- [ ] **Step 4: Confirm the operation and scope boundary**

Run from the repository root:

```sh
rg -n 'operationId:|lastProjectId|Writing Assistant|securitySchemes|/api' docs/api/openapi.yaml
```

Expected: exactly the four approved `operationId` values; `/api` appears only as the server base; excluded features and `lastProjectId` do not appear.

### Task 2: Add Contract-Aligned Transport Types and Mock State

**Files:**

- Create: `frontend/src/app/infrastructure/api/contracts.ts`
- Create: `frontend/src/mocks/data/project-workspaces.ts`

**Interfaces:**

- Consumes: the Task 1 component schemas.
- Produces: wire types used by Task 3 handlers and `resetProjectWorkspaceMockData()` used by the global test setup.

- [ ] **Step 1: Add the wire-contract types**

Create `contracts.ts` with these public type names and shapes:

```ts
export type TropeId =
  | "rivals-to-lovers"
  | "contract-romance"
  | "reunion"
  | "friends-to-lovers";

export type ApiErrorCode =
  | "MALFORMED_REQUEST"
  | "PROJECT_NOT_FOUND"
  | "MANUSCRIPT_NOT_FOUND"
  | "MANUSCRIPT_REVISION_CONFLICT"
  | "INVALID_TITLE"
  | "INVALID_TROPE"
  | "INVALID_PROTAGONISTS"
  | "INVALID_MANUSCRIPT"
  | "INTERNAL_ERROR";

export interface ApiProject {
  id: string;
  title: string;
  logline: string;
  tropeId: TropeId;
  updatedAt: string;
}

export interface ApiStoryConcept {
  id: string;
  projectId: string;
  tropeId: TropeId;
  logline: string;
  protagonistNames: [string, string];
}

export interface ApiCharacter {
  id: string;
  name: string;
  role: "protagonist";
  desire: string;
  hiddenFeeling: string;
}

export interface ApiWorldEntry {
  id: string;
  kind: "place" | "object" | "rule";
  title: string;
  description: string;
}

export interface ApiStoryBible {
  projectId: string;
  characters: ApiCharacter[];
  worldEntries: ApiWorldEntry[];
}

export interface ApiScene {
  id: string;
  title: string;
  chapterNumber: number;
  content: string;
  relatedCharacterIds: string[];
  relatedWorldEntryIds: string[];
}

export interface ApiManuscript {
  id: string;
  projectId: string;
  scenes: ApiScene[];
  activeSceneId: string;
}

export interface ProjectWorkspaceResponse {
  project: ApiProject;
  concept: ApiStoryConcept;
  storyBible: ApiStoryBible;
  manuscript: ApiManuscript;
  manuscriptRevision: number;
}

export interface ProjectListResponse {
  items: ApiProject[];
}

export interface CreateProjectRequest {
  title: string;
  logline: string;
  tropeId: TropeId;
  protagonistNames: [string, string];
}

export interface SaveManuscriptRequest {
  manuscript: ApiManuscript;
  expectedRevision: number;
}

export interface SaveManuscriptResponse {
  manuscript: ApiManuscript;
  manuscriptRevision: number;
  projectActivity: { projectId: string; updatedAt: string };
}

export interface FieldError {
  path: string;
  message: string;
}

export interface ApiError {
  code: ApiErrorCode;
  message: string;
  fieldErrors: FieldError[];
}
```

Do not import domain types into this file; the transport boundary remains explicit.

- [ ] **Step 2: Add deterministic initial mock data and state operations**

Create `project-workspaces.ts` with:

```ts
export const PROJECT_API_BASE_URL = "/api";
export const MOCK_NOW = "2026-07-14T03:00:00.000Z";

export const apiErrors = {
  malformedRequest: { code: "MALFORMED_REQUEST", message: "요청 형식을 확인해 주세요.", fieldErrors: [] },
  projectNotFound: { code: "PROJECT_NOT_FOUND", message: "프로젝트를 찾을 수 없습니다.", fieldErrors: [] },
  manuscriptNotFound: { code: "MANUSCRIPT_NOT_FOUND", message: "원고를 찾을 수 없습니다.", fieldErrors: [] },
  revisionConflict: { code: "MANUSCRIPT_REVISION_CONFLICT", message: "다른 위치에서 원고가 먼저 수정되었습니다.", fieldErrors: [] },
  internalError: { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
} satisfies Record<string, ApiError>;
```

Add the `silver-garden` workspace using the same values currently returned by `createSeedSnapshot()`, with `manuscriptRevision: 1`. Keep one mutable module-local array produced by a deep clone of the immutable initial fixture. Export only focused operations needed by handlers:

```ts
export function listMockProjects(): ApiProject[];
export function findMockWorkspace(projectId: string): ProjectWorkspaceResponse | undefined;
export function findMockWorkspaceByManuscriptId(manuscriptId: string): ProjectWorkspaceResponse | undefined;
export function addMockWorkspace(workspace: ProjectWorkspaceResponse): void;
export function replaceMockWorkspace(workspace: ProjectWorkspaceResponse): void;
export function resetProjectWorkspaceMockData(): void;
```

Every read operation returns cloned data so callers cannot mutate stored state accidentally. `listMockProjects()` returns a new array sorted by descending `updatedAt`.

- [ ] **Step 3: Format and type-check the new files**

Run:

```sh
mise exec -- pnpm exec oxfmt --write src/app/infrastructure/api/contracts.ts src/mocks/data/project-workspaces.ts
mise exec -- pnpm typecheck
```

Expected: exit 0 without `any`, unchecked broad casts, or domain-module imports in the transport file.

### Task 3: Implement Stateful MSW Project Handlers Test-First

**Files:**

- Create: `frontend/src/mocks/handlers/projects.ts`
- Create: `frontend/src/mocks/project-handlers.test.ts`
- Modify: `frontend/src/mocks/handlers.ts`
- Modify: `frontend/src/test/setup.ts`

**Interfaces:**

- Consumes: Task 2 transport types, mock state operations, and `PROJECT_API_BASE_URL`.
- Produces: `projectHandlers: RequestHandler[]`, registered in the shared `handlers` collection used by both browser and Node MSW adapters.

- [ ] **Step 1: Write failing observable contract tests**

Create `project-handlers.test.ts`. Use `fetch("http://localhost/api/...")` so requests pass through the globally configured MSW Node server. Cover these exact assertions:

```text
GET /api/projects -> 200; seed project; descending updatedAt ordering
POST /api/projects -> 201; Location=/api/projects/{id}/workspace; response revision=1
GET returned Location -> 200 and the same newly created workspace
POST invalid blank title -> 422 INVALID_TITLE with fieldErrors path=title
POST unknown trope -> 422 INVALID_TROPE with fieldErrors path=tropeId
POST missing/blank protagonist -> 422 INVALID_PROTAGONISTS with fieldErrors path=protagonistNames
POST malformed JSON -> 400 MALFORMED_REQUEST
GET unknown workspace -> 404 PROJECT_NOT_FOUND
PUT seed manuscript expectedRevision=1 -> 200; revision=2; new content retained
GET seed workspace after save -> revision=2 and updated project timestamp
PUT the same old revision again -> 409 MANUSCRIPT_REVISION_CONFLICT
GET seed workspace after conflict -> content and revision unchanged from successful save
PUT unknown manuscript -> 404 MANUSCRIPT_NOT_FOUND
PUT path/body manuscript-id mismatch -> 422 INVALID_MANUSCRIPT
test-local server.use() override -> 500 INTERNAL_ERROR fixture
reset between tests -> seed revision is 1 in the next test
```

Use exact response interfaces from `contracts.ts`; do not assert only status codes.

- [ ] **Step 2: Run the focused test and verify the missing-handler failure**

Run:

```sh
mise exec -- pnpm exec vitest run src/mocks/project-handlers.test.ts
```

Expected: FAIL because the shared handler collection does not yet implement the API operations.

- [ ] **Step 3: Implement parsing, validation, and four handlers**

Create `projects.ts` exporting `projectHandlers`. Use MSW `http` and `HttpResponse`. Keep request parsing and validation private to the handler module. IDs and timestamps are injected through exported mock-only defaults or generated in the handler without changing domain modules. The successful create path must construct all resource identifiers consistently:

```text
project: {projectId}
concept: {projectId}-concept
characters: {projectId}-character-1 and {projectId}-character-2
world entry: {projectId}-world-1
manuscript: {projectId}-manuscript
scene: {projectId}-scene-1
```

Register the handlers in this order:

```ts
export const projectHandlers: RequestHandler[] = [
  http.get(`${PROJECT_API_BASE_URL}/projects`, listProjectsHandler),
  http.post(`${PROJECT_API_BASE_URL}/projects`, createProjectHandler),
  http.get(`${PROJECT_API_BASE_URL}/projects/:projectId/workspace`, getWorkspaceHandler),
  http.put(`${PROJECT_API_BASE_URL}/manuscripts/:manuscriptId`, saveManuscriptHandler),
];
```

Use `HttpResponse.json(payload, { status })`. Use status 201 and a `Location` header for creation. Validate JSON parsing separately from domain-input validation. Trim title, logline, and protagonist names before storing. Saving must validate active-scene membership, path/body IDs, project relationship, and revision before replacing mock state.

- [ ] **Step 4: Register the handlers and reset state globally**

Update `src/mocks/handlers.ts` to:

```ts
import type { RequestHandler } from "msw";

import { projectHandlers } from "@/mocks/handlers/projects";

export const handlers: RequestHandler[] = [...projectHandlers];
```

Update the existing `afterEach` in `src/test/setup.ts` so reset order is:

```ts
afterEach(() => {
  server.resetHandlers();
  resetProjectWorkspaceMockData();
  cleanup();
});
```

Do not add a second `afterEach` hook.

- [ ] **Step 5: Run focused tests until every contract case passes**

Run:

```sh
mise exec -- pnpm exec vitest run src/mocks/project-handlers.test.ts src/mocks/server.test.ts src/mocks/enable-mocking.test.ts
```

Expected: all focused test files and all tests pass with no unhandled network requests.

### Task 4: Cross-Artifact Review and Frontend Handoff

**Files:**

- Verify: `docs/api/openapi.yaml`
- Verify: `frontend/src/app/infrastructure/api/contracts.ts`
- Verify: `frontend/src/mocks/data/project-workspaces.ts`
- Verify: `frontend/src/mocks/handlers/projects.ts`
- Verify: `frontend/src/mocks/handlers.ts`
- Verify: `frontend/src/mocks/project-handlers.test.ts`
- Verify: `frontend/src/test/setup.ts`
- Verify: `frontend/package.json`
- Verify: `frontend/pnpm-lock.yaml`

**Interfaces:**

- Consumes: Tasks 1-3.
- Produces: an exact frontend-authored draft baseline for main-agent review and approval.

- [ ] **Step 1: Compare every operation across OpenAPI, types, and handlers**

Confirm each method, path, status, header, field name, required field, enum, example, timestamp, and error code agrees. Confirm `lastProjectId` and all out-of-scope operations are absent.

Run:

```sh
rg -n 'operationId:|/projects|/manuscripts|manuscriptRevision|expectedRevision|ApiErrorCode' ../docs/api/openapi.yaml src/app/infrastructure/api/contracts.ts src/mocks
```

Expected: the four operations and their wire concepts appear consistently with no competing path or field names.

- [ ] **Step 2: Run OpenAPI and focused verification**

Run:

```sh
mise exec -- pnpm api:lint
mise exec -- pnpm exec vitest run src/mocks/project-handlers.test.ts src/mocks/server.test.ts src/mocks/enable-mocking.test.ts
```

Expected: all commands exit 0.

- [ ] **Step 3: Run the full frontend checks**

Run:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected for changed files: formatting, lint, type checking, tests, and production build pass. If the repository-wide command fails only because of pre-existing user-owned untracked Playwright files or pre-existing formatting failures, do not edit those files; report the exact failing paths and separately run changed-file formatting plus focused tests, lint, typecheck, and build.

- [ ] **Step 4: Return the required API contract handoff**

Return exactly this populated structure to the main agent:

```text
API contract handoff
- Spec: docs/api/openapi.yaml
- Baseline: design commit aeb2d85 plus the exact frontend task HEAD SHA and diff range reported by the agent
- Operations: listProjects, createProjectWorkspace, getProjectWorkspace, saveManuscript
- Domain contracts: docs/domains/README.md, docs/domains/projects.md, docs/domains/story-design.md, docs/domains/story-bible.md, docs/domains/manuscript.md
- Assumptions: server-generated identifiers and timestamps; no authentication; one current manuscript per project; lastProjectId remains browser-owned
- Frontend artifacts: frontend/src/app/infrastructure/api/contracts.ts, frontend/src/mocks/data/project-workspaces.ts, frontend/src/mocks/handlers/projects.ts, frontend/src/mocks/handlers.ts, frontend/src/mocks/project-handlers.test.ts
- Validation: list every command, exit status, pass count, and any pre-existing unrelated failing path
```

The frontend subagent must state that the draft awaits main-agent approval and must not assign it to backend work.
