# Frontend API, Autosave, and Conflict Diff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect all current project persistence UI flows to MSW-backed API operations through TanStack Query v5, add 800 ms manuscript autosave, and resolve revision conflicts through a new scene-diff API and accessible UI.

**Architecture:** TanStack Query owns remote project/workspace state; typed application-infrastructure adapters own HTTP; cross-domain query/mutation orchestration lives in a persistence feature. The writing page retains only a local draft and UI state. A 409 save response invokes a new OpenAPI/MSW scene-diff operation and a modal resolution workflow.

**Tech Stack:** React 19, TypeScript 7, TanStack Query v5, React Router, MSW 2, Vitest, Testing Library, OpenAPI 3.1, Redocly

## Global Constraints

- Read `AGENTS.md`, `frontend/AGENTS.md`, `docs/domains/projects.md`, `docs/domains/manuscript.md`, and the approved design before editing.
- Owned paths are `frontend/`, `docs/api/openapi.yaml`, and `docs/domains/manuscript.md`; do not edit backend or other domain documents.
- `docs/api/openapi.yaml` has a single editor for this task. The backend is out of scope.
- Use `@tanstack/react-query` v5 for all frontend server state. React components must not call `fetch` directly.
- Keep pure domain modules independent of React, TanStack Query, browser APIs, persistence, and transport.
- Preserve Korean product copy and accessible keyboard behavior.
- Use MSW for all transport behavior in browser development and UI/integration tests.
- Do not modify or hide the unrelated `seed.spec.ts` Playwright/Vitest baseline issue.
- Do not commit; the main agent reviews and integrates the shared working-tree diff.

---

### Task 1: Add the scene-diff domain and OpenAPI contract

**Files:**
- Modify: `docs/domains/manuscript.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `frontend/src/app/infrastructure/api/contracts.ts`
- Modify: `frontend/src/mocks/data/project-workspaces.ts`
- Modify: `frontend/src/mocks/handlers/projects.ts`
- Modify: `frontend/src/mocks/project-handlers.test.ts`

**Interfaces:**
- Produces: `POST /api/manuscripts/:manuscriptId/scene-diffs`, operation `compareManuscriptScene`
- Produces: `CompareManuscriptSceneRequest`, `CompareManuscriptSceneResponse`, `SceneDiffRow`, and new scene error codes
- Consumes: Current in-memory mock workspace and revision

- [ ] **Step 1: Extend the domain contract**

Add a technology-neutral `장면 초안 비교` use case to `docs/domains/manuscript.md`. State that comparison receives two versions of the same scene, returns their line-level differences, mutates neither input, and rejects scene/manuscript identity mismatches.

- [ ] **Step 2: Write failing MSW contract tests**

Add tests that POST:

```ts
{
  sceneId: "silver-garden-scene-1",
  localContent: "첫째 줄\n로컬 줄",
}
```

Assert `200` returns the current `serverRevision`, the submitted and stored content, the full current `serverManuscript`, and aligned rows containing `unchanged`, `local-only`, and `server-only`. Add focused `400`, manuscript/scene `404`, manuscript-scene `422`, and `500` override tests.

- [ ] **Step 3: Run the new tests and confirm failure**

Run:

```sh
mise exec -- pnpm vitest run src/mocks/project-handlers.test.ts
```

Expected: FAIL because the scene-diff handler and types do not exist.

- [ ] **Step 4: Add the OpenAPI operation and reusable schemas**

Define `compareManuscriptScene` with the approved request and response. Use strict `additionalProperties: false` objects and nullable line values through OpenAPI 3.1 unions such as:

```yaml
localLineNumber:
  type: [integer, "null"]
  minimum: 1
localText:
  type: [string, "null"]
```

Add representative success and error examples. Add machine-readable `SCENE_NOT_FOUND` and `INVALID_SCENE_REFERENCE` error codes and reusable responses where appropriate.

- [ ] **Step 5: Implement typed mock diff behavior**

Add exact frontend types:

```ts
export type SceneDiffKind = "unchanged" | "local-only" | "server-only";

export interface SceneDiffRow {
  kind: SceneDiffKind;
  localLineNumber: number | null;
  localText: string | null;
  serverLineNumber: number | null;
  serverText: string | null;
}

export interface CompareManuscriptSceneRequest {
  sceneId: string;
  localContent: string;
}

export interface CompareManuscriptSceneResponse {
  sceneId: string;
  serverRevision: number;
  localContent: string;
  serverContent: string;
  serverManuscript: ApiManuscript;
  rows: SceneDiffRow[];
}
```

Implement a deterministic pure LCS line aligner without adding a dependency. The handler validates exact request keys and identity, clones returned state, and never mutates submitted or stored manuscripts.

- [ ] **Step 6: Verify contract and handler**

Run:

```sh
mise exec -- pnpm api:lint
mise exec -- pnpm vitest run src/mocks/project-handlers.test.ts
```

Expected: OpenAPI exits 0 and the focused MSW tests pass. Report any pre-existing Redocly warning separately.

---

### Task 2: Add TanStack Query composition and typed API adapters

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Create: `frontend/src/app/query/query-client.ts`
- Create: `frontend/src/app/query/query-provider.tsx`
- Create: `frontend/src/app/infrastructure/api/api-client.ts`
- Create: `frontend/src/app/infrastructure/api/projects-api.ts`
- Create: `frontend/src/app/infrastructure/api/projects-api.test.ts`
- Modify: `frontend/src/main.tsx`

**Interfaces:**
- Produces: `createAppQueryClient()`, `QueryProvider`, `ApiRequestError`
- Produces: `listProjects`, `createProjectWorkspace`, `getProjectWorkspace`, `saveManuscript`, `compareManuscriptScene`

- [ ] **Step 1: Add the dependency**

Run:

```sh
mise exec -- pnpm add @tanstack/react-query@^5
```

- [ ] **Step 2: Write failing adapter tests**

Use MSW to test all five adapter functions for a success response and at least one typed error. Assert errors expose `status` and the parsed `ApiError`:

```ts
expect(error).toMatchObject({
  status: 404,
  error: { code: "PROJECT_NOT_FOUND" },
});
```

- [ ] **Step 3: Run the adapter tests and confirm failure**

Run:

```sh
mise exec -- pnpm vitest run src/app/infrastructure/api/projects-api.test.ts
```

Expected: FAIL because the adapter modules do not exist.

- [ ] **Step 4: Implement the API client and adapters**

Use one JSON request helper that throws:

```ts
export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly error: ApiError,
  ) {
    super(error.message);
  }
}
```

Adapters use relative `/api` paths and contract types. They do not import React or TanStack Query.

- [ ] **Step 5: Implement Query application composition**

Create one production client and a factory for tests. Default queries use a finite stale time and conservative retry policy; mutations do not retry automatically. Wrap `AppRoutes` with `QueryProvider` in `main.tsx` and remove the runtime `AppProvider` wrapper.

- [ ] **Step 6: Verify adapters and type safety**

Run:

```sh
mise exec -- pnpm vitest run src/app/infrastructure/api/projects-api.test.ts
mise exec -- pnpm typecheck
```

Expected: adapter tests and typecheck pass, except do not attribute the known unrelated root test collection issue to these focused commands.

---

### Task 3: Add project persistence query hooks

**Files:**
- Create: `frontend/src/features/project-persistence/api/query-keys.ts`
- Create: `frontend/src/features/project-persistence/api/project-queries.ts`
- Create: `frontend/src/features/project-persistence/api/project-queries.test.tsx`
- Create: `frontend/src/features/project-persistence/index.ts`

**Interfaces:**
- Produces: `projectKeys`, `useProjectsQuery`, `useProjectWorkspaceQuery`, `useCreateProjectMutation`, `useSaveManuscriptMutation`, `useCompareManuscriptSceneMutation`
- Consumes: Task 2 adapter functions and TanStack Query client

- [ ] **Step 1: Write failing hook tests**

Render hooks with a fresh query client. Assert list/workspace keys are stable, creation populates the workspace cache and updates or invalidates the list, and save updates both workspace revision/manuscript and project activity.

- [ ] **Step 2: Run hook tests and confirm failure**

Run:

```sh
mise exec -- pnpm vitest run src/features/project-persistence/api/project-queries.test.tsx
```

Expected: FAIL because the feature does not exist.

- [ ] **Step 3: Implement keys and hooks**

Use keys shaped as:

```ts
export const projectKeys = {
  all: ["projects"] as const,
  list: () => [...projectKeys.all, "list"] as const,
  workspace: (projectId: string) => [...projectKeys.all, "workspace", projectId] as const,
};
```

Mutations accept typed variables and centralize cache synchronization. Export only the consumer-facing feature surface from `index.ts`.

- [ ] **Step 4: Verify hooks**

Run the focused hook tests and `mise exec -- pnpm typecheck`. Expected: PASS.

---

### Task 4: Connect the library and project creation pages

**Files:**
- Modify: `frontend/src/pages/library/library-page.tsx`
- Create: `frontend/src/pages/library/library-page.test.tsx`
- Modify: `frontend/src/pages/new-project/setup-page.tsx`
- Create or modify: `frontend/src/pages/new-project/setup-page.test.tsx`
- Modify: `frontend/src/app/app.test.tsx`

**Interfaces:**
- Consumes: `useProjectsQuery`, `useCreateProjectMutation`
- Produces: observable loading, empty, error/retry, pending, field-error, and success/navigation behavior

- [ ] **Step 1: Write failing page behavior tests**

Use MSW overrides and Testing Library to cover library loading/error retry/empty/success, creation pending disabled state, `422` field messages, generic failure, and successful navigation to the returned project ID.

- [ ] **Step 2: Run focused tests and confirm failure**

Run:

```sh
mise exec -- pnpm vitest run src/pages/library/library-page.test.tsx src/pages/new-project/setup-page.test.tsx src/app/app.test.tsx
```

Expected: FAIL while pages still use local App state.

- [ ] **Step 3: Implement query-backed pages**

Replace `useApp` access with feature hooks. Keep server ordering as returned. Use Korean visible status/error copy, a labelled retry button, input-associated field errors, and `aria-busy` or equivalent pending semantics. Prevent duplicate submission while the mutation is pending.

- [ ] **Step 4: Verify page flows**

Run the focused tests. Expected: PASS.

---

### Task 5: Implement the debounced manuscript autosave feature

**Files:**
- Create: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`
- Create: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`
- Create: `frontend/src/features/manuscript-autosave/index.ts`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**
- Consumes: project workspace query, manuscript domain edit functions, save mutation
- Produces: `draft`, `updateDraft`, `status`, `retry`, and conflict state after exactly 800 ms idle

- [ ] **Step 1: Write failing fake-timer autosave tests**

Cover no request before 800 ms, one request at 800 ms, newer edits retained while a request is active, sequential follow-up save, success revision/cache update, and non-conflict error retaining the draft with retry.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```sh
mise exec -- pnpm vitest run src/features/manuscript-autosave/use-manuscript-autosave.test.tsx
```

Expected: FAIL because the hook does not exist.

- [ ] **Step 3: Implement a serial autosave state machine**

Use explicit states `editing`, `saving`, `saved`, `error`, and `conflict`. Maintain acknowledged revision separately from the current draft. Never run parallel saves; after a save settles, schedule a newer dirty draft rather than replacing it with the response.

- [ ] **Step 4: Connect workspace loading and editor behavior**

Load the workspace by route project ID. Show loading, retryable error, and not-found views. Bind the editor and writing-assistant application to the local draft. Replace the hard-coded saved label with accessible status text and expose retry on non-conflict failure.

- [ ] **Step 5: Verify autosave and existing writing behavior**

Run the autosave hook and writing workspace tests. Expected: PASS.

---

### Task 6: Add conflict diff UI and resolution behavior

**Files:**
- Create: `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.tsx`
- Create: `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx`
- Create: `frontend/src/features/manuscript-conflict/index.ts`
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**
- Consumes: `CompareManuscriptSceneResponse`, compare/save mutations, existing `Dialog` primitive
- Produces: accessible side-by-side rows and `keepLocal` / `applyServer` actions

- [ ] **Step 1: Write failing conflict workflow tests**

Assert a 409 triggers one diff request; the dialog labels `내 편집본` and `서버 최신본`; rows expose unchanged/local-only/server-only text labels and line numbers; Escape retains the draft; both resolution buttons are keyboard accessible.

Assert local resolution starts from `serverManuscript`, changes only the compared scene content, saves with `serverRevision`, and refreshes the diff on a second 409. Assert server resolution adopts `serverManuscript` and closes the dialog.

- [ ] **Step 2: Run conflict tests and confirm failure**

Run the conflict dialog, autosave, and workspace tests. Expected: FAIL because conflict resolution is not implemented.

- [ ] **Step 3: Implement the dialog**

Use `src/components/ui/dialog.tsx`. Render two scrollable columns with aligned rows. Include visible `변경 없음`, `내 편집본에만 있음`, and `서버 최신본에만 있음` labels so color is not the only indicator. Explain each resolution consequence in Korean.

- [ ] **Step 4: Implement conflict orchestration**

On 409, suspend autosave and compare the active scene. For local resolution, immutably replace the scene content in the returned server manuscript and save at `serverRevision`. For server resolution, adopt the complete returned manuscript and revision. Preserve local content through compare errors and repeated conflicts.

- [ ] **Step 5: Verify the full conflict flow**

Run all focused conflict/autosave/workspace tests. Expected: PASS.

---

### Task 7: Remove legacy localStorage server-state ownership

**Files:**
- Delete: `frontend/src/app/infrastructure/app-storage.ts`
- Delete: `frontend/src/app/infrastructure/app-storage.test.ts`
- Delete: `frontend/src/app/state/app-state.ts`
- Delete: `frontend/src/app/state/app-state.test.ts`
- Delete: `frontend/src/app/state/app-provider.tsx`
- Delete: `frontend/src/app/state/app-provider.test.tsx`
- Modify: `frontend/src/app/app.test.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**
- Consumes: Query provider and query-backed features from Tasks 2–6
- Produces: one server-state owner with no runtime localStorage snapshot

- [ ] **Step 1: Find all legacy consumers**

Run:

```sh
rg -n "AppProvider|useApp|createAppStorage|createSeedSnapshot|localStorage" frontend/src
```

- [ ] **Step 2: Remove legacy state files and update test render helpers**

Use a fresh test `QueryClient` wrapper instead of `AppProvider`. Do not remove local component state or domain creation functions still used by domain tests.

- [ ] **Step 3: Verify no runtime legacy references remain**

Run the same `rg`. Expected: no application matches for removed symbols and no localStorage ownership of project/workspace data.

- [ ] **Step 4: Run all affected tests**

Run:

```sh
mise exec -- pnpm vitest run src/app src/pages src/features src/mocks
```

Expected: all affected Vitest tests pass.

---

### Task 8: Final contract handoff and verification

**Files:**
- Review all changed files only; do not add unrelated refactors

**Interfaces:**
- Produces: frontend API contract handoff to the main agent

- [ ] **Step 1: Format only changed files**

Run the repository formatter on changed frontend files without rewriting unrelated pre-existing files. Then run `git diff --check`.

- [ ] **Step 2: Run required verification**

From `frontend/` run:

```sh
mise exec -- pnpm api:lint
mise exec -- pnpm check
mise exec -- pnpm build
```

Also run the focused affected test set if `pnpm check` still fails because of the known unrelated `seed.spec.ts` import.

- [ ] **Step 3: Compare domain and transport diffs**

Confirm `docs/domains/manuscript.md` describes the same comparison identity and immutability rules as the frontend implementation, without HTTP or TanStack Query details. Confirm OpenAPI, types, MSW, adapters, and UI use the same fields and error codes.

- [ ] **Step 4: Return the required handoff**

Return:

```text
API contract handoff
- Spec: docs/api/openapi.yaml
- Baseline: working-tree diff against main commit f9c3592
- Operations: listProjects, createProjectWorkspace, getProjectWorkspace, saveManuscript, compareManuscriptScene
- Domain contracts: docs/domains/projects.md, docs/domains/manuscript.md
- Assumptions: write `none` unless implementation uncovers a concrete assumption, then list it explicitly
- Frontend artifacts: list the exact changed paths for types, MSW handlers/data, adapters, query hooks, autosave hook, and conflict UI
- Validation: list each command run with its exit code, pass/fail counts, warnings, and baseline-failure attribution
```

Include a concise changed-file summary, known baseline failures, and any unresolved decision. Do not claim full verification if a required command fails.
