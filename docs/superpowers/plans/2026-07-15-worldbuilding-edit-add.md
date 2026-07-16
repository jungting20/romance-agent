# Worldbuilding Edit and Add Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an author edit existing Story Bible world entries and add new entries from the writing workspace, with revision-safe project-file persistence.

**Architecture:** The writing-workspace route owns canonical tab/editor URL state, a focused frontend feature owns the editable draft and TanStack Query mutation, and Story Bible UI components remain controlled presentation. FastAPI delegates the approved operations to a Story Bible service and an injected JSON-file repository that locks, revision-checks, and atomically replaces one project file.

**Tech Stack:** React 19, TypeScript 7, TanStack Router 1.170.18, TanStack Query 5.101.2, MSW 2.15, Vitest 4, Playwright 1.61, FastAPI, Pydantic, Python 3.13, pytest, OpenAPI 3.1

## Global Constraints

- Work only in `/Users/in05908_mac/Documents/romance-agent/.worktrees/feature-worldbuilding-edit-add` on `feature/worldbuilding-edit-add`.
- Approved design: `docs/superpowers/specs/2026-07-15-worldbuilding-edit-add-design.md` at commit `1e0ae1ac4634acb6644d91fa7fe3f5ba76d9d0a6`.
- Approved UI plan: `frontend/docs/ui-plans/worldbuilding-edit-add.md` at commit `00a066636a41c971c92dd78ca33bf46069453c55`, blob `574318607e381cd035894f1e2e37e5d9aba22c50` (format-only replacement of the semantically approved artifact).
- Approved API baseline: `docs/api/openapi.yaml` at commit `dfabc8a4f5274737e08ef43036b154b3417fc5f3`, blob `69d64146d62ab12b7462839a1f3ef0f76133374d`.
- Assigned operations are exactly `getStoryBible` and `saveWorldEntries`; frontend and backend never edit or reinterpret the approved OpenAPI file.
- Assigned requirements are exactly `REQ-WORLD-001` through `REQ-WORLD-010`.
- Coverage map: Task 4 implements and verifies `REQ-WORLD-001` through `REQ-WORLD-007` and frontend-observable `REQ-WORLD-008` through `REQ-WORLD-010`; Task 3 implements backend-owned `REQ-WORLD-008` and `REQ-WORLD-009`; Tasks 5–7 verify all ten requirements across integration, E2E, review, and final checks.
- Story Bible owns normalization, nonblank titles/descriptions, stable existing IDs, project-unique new IDs, omitted-entry preservation, and all-or-nothing edits/additions.
- The backend stores one schema-versioned Story Bible JSON file per project beneath an injected data root; it must prevent traversal, lock per project, require exact revision equality, flush a temporary file, and atomically replace the canonical file.
- No database, ORM, dependency addition, delete, reorder, character editing, automatic merge, force save, LLM generation, import/export, or unrelated backend project operation is in scope.
- UI state follows the exact approved plan: canonical `?tab=world&panel=world-editor`, explicit open/close history entries, replacement canonicalization/save-close, dirty-discard confirmation, and equivalent desktop/mobile behavior.
- Preserve existing manuscript autosave, conflict handling, AI tools, responsive panels, and unrelated user changes.
- Use existing shadcn/ui wrappers. The kind field is a styled native `select`; do not add Select or AlertDialog.
- Keep runtime data untracked. Tests inject temporary directories and deterministic identifiers.
- Required full frontend checks are `mise exec -- pnpm check`, `mise exec -- pnpm build`, and `mise exec -- pnpm api:lint` from `frontend/`.
- Required full backend checks are `mise exec -- uv run pytest`, `mise exec -- uv run ruff check .`, and `mise exec -- uv run ruff format --check .` from `backend/`.
- The required Playwright planner and generator configs are present after merging `main`. Use those exact registered agents in order; do not substitute generic agents, dispatch frontend review before they finish, or claim final completion without their evidence.

---

### Task 1: Preserve the Approved Contract Gates

**Files:**

- Existing: `docs/superpowers/specs/2026-07-15-worldbuilding-edit-add-design.md`
- Existing: `frontend/docs/ui-plans/worldbuilding-edit-add.md`
- Existing: `docs/domains/story-bible.md`
- Existing: `docs/api/openapi.yaml`

**Interfaces:**

- Consumes: user-approved persistence and Sheet decisions.
- Produces: immutable downstream baseline identities and `REQ-WORLD-*` traceability.

- [x] **Step 1: Record the approved product and UI artifacts**

Use the exact commits and blobs in Global Constraints. Do not regenerate or silently revise either artifact.

- [x] **Step 2: Synchronize the domain contract**

`docs/domains/story-bible.md` at commit `0c111b51895a3128ed1ff829cd6028ad86dabdeb` defines these authoritative rules:

```text
trim title and description -> reject either normalized blank
existing update -> preserve identifier
omitted existing entry -> preserve unchanged
multiple updates/additions -> return a result only when every item is valid
```

- [x] **Step 3: Approve the OpenAPI baseline**

The exact mappings are:

```text
GET /projects/{projectId}/story-bible -> getStoryBible
PUT /projects/{projectId}/story-bible/world-entries -> saveWorldEntries
```

`saveWorldEntries` requires exact `expectedRevision == storyBibleRevision`; every mismatch returns `409 STORY_BIBLE_REVISION_CONFLICT` without mutation.

### Task 2: Build the Frontend Story Bible Contract and Mock Boundary

**Owner:** registered `frontend` agent. This task may run in parallel with Task 3 after confirming the approved OpenAPI commit.

**Files:**

- Modify: `frontend/src/app/infrastructure/api/contracts.ts`
- Create: `frontend/src/app/infrastructure/api/story-bible-api.ts`
- Create: `frontend/src/app/infrastructure/api/story-bible-api.test.ts`
- Create: `frontend/src/features/story-bible-persistence/api/query-keys.ts`
- Create: `frontend/src/features/story-bible-persistence/api/story-bible-queries.ts`
- Create: `frontend/src/features/story-bible-persistence/api/story-bible-queries.test.tsx`
- Create: `frontend/src/features/story-bible-persistence/index.ts`
- Modify: `frontend/src/mocks/data/project-workspaces.ts`
- Create: `frontend/src/mocks/handlers/story-bible.ts`
- Create: `frontend/src/mocks/story-bible-handlers.test.ts`
- Modify: `frontend/src/mocks/handlers.ts`

**Interfaces:**

- Consumes: approved `getStoryBible` and `saveWorldEntries` schemas.
- Produces: `StoryBibleSnapshot`, `SaveWorldEntriesRequest`, `getStoryBible(projectId)`, `saveWorldEntries(projectId, request)`, `useStoryBibleQuery(projectId)`, and `useSaveWorldEntriesMutation()`.

- [ ] **Step 1: Add failing adapter and MSW contract tests**

Tests must assert the exact server base, path, method, body, response, and consumed errors:

```ts
const request: SaveWorldEntriesRequest = {
  expectedRevision: 1,
  updates: [
    {
      id: "silver-garden-world-1",
      kind: "place",
      title: "비가 그친 유리 온실",
      description: "두 사람이 마지막으로 만난 장소다.",
    },
  ],
  additions: [
    { kind: "rule", title: "왕실의 서약", description: "서약을 어기면 계승권을 잃는다." },
  ],
};

expect(await getStoryBible("silver-garden")).toMatchObject({ storyBibleRevision: 1 });
expect(await saveWorldEntries("silver-garden", request)).toMatchObject({
  storyBibleRevision: 2,
  storyBible: { worldEntries: expect.arrayContaining([expect.objectContaining({ kind: "rule" })]) },
});
```

Also cover `STORY_BIBLE_NOT_FOUND`, exact lower/higher revision conflicts, blank fields, duplicate/unknown IDs, generated addition IDs, omitted-entry preservation, no mutation on every failure, and reset isolation.

- [ ] **Step 2: Verify RED**

Run from `frontend/`:

```sh
mise exec -- pnpm test src/app/infrastructure/api/story-bible-api.test.ts src/mocks/story-bible-handlers.test.ts
```

Expected: FAIL because the types, adapter, handler, and state operations do not exist.

- [ ] **Step 3: Add exact transport types and adapters**

Add these contract-aligned public types without widening enums or optional fields:

```ts
export interface StoryBibleSnapshot {
  storyBible: ApiStoryBible;
  storyBibleRevision: number;
}

export type WorldEntryUpdate = ApiWorldEntry;

export type WorldEntryAddition = Omit<ApiWorldEntry, "id">;

export interface SaveWorldEntriesRequest {
  expectedRevision: number;
  updates: WorldEntryUpdate[];
  additions: WorldEntryAddition[];
}

export interface SaveWorldEntriesMutationVariables {
  projectId: string;
  request: SaveWorldEntriesRequest;
}
```

Extend `ApiErrorCode` with the three exact approved codes. Implement:

```ts
export function getStoryBible(projectId: string): Promise<StoryBibleSnapshot> {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/story-bible`);
}

export function saveWorldEntries(
  projectId: string,
  request: SaveWorldEntriesRequest,
): Promise<StoryBibleSnapshot> {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/story-bible/world-entries`, {
    method: "PUT",
    body: request,
  });
}
```

- [ ] **Step 4: Implement stateful MSW behavior**

Keep Story Bible revisions separate from `ProjectWorkspaceResponse`. Reset them to `1` with the existing mock reset. The handler must parse exact keys, route shape errors to 400, route domain-invalid commands to 422, compare revision with exact equality, create deterministic project-scoped IDs, preserve omitted entries/characters/order, append additions in request order, and increment once only after the complete command succeeds.

Expose mock data operations with these signatures:

```ts
export function getMockStoryBibleSnapshot(projectId: string): StoryBibleSnapshot | undefined;
export function saveMockWorldEntries(
  projectId: string,
  request: SaveWorldEntriesRequest,
):
  | { status: "not-found" }
  | { status: "revision-conflict" }
  | { status: "invalid"; error: ApiError }
  | { status: "saved"; snapshot: StoryBibleSnapshot };
```

- [ ] **Step 5: Add TanStack Query ownership and verify GREEN**

Use a stable key and update both the focused Story Bible snapshot and existing workspace cache on success:

```ts
export const storyBibleKeys = {
  all: ["story-bible"] as const,
  project: (projectId: string) => ["story-bible", projectId] as const,
};

export function useStoryBibleQuery(projectId: string) {
  return useQuery({
    queryKey: storyBibleKeys.project(projectId),
    queryFn: () => getStoryBible(projectId),
  });
}
```

The mutation `onSuccess` writes the returned snapshot and replaces only `workspace.storyBible` in `projectKeys.workspace(projectId)` when cached.

Run:

```sh
mise exec -- pnpm test src/app/infrastructure/api/story-bible-api.test.ts src/mocks/story-bible-handlers.test.ts src/features/story-bible-persistence/api/story-bible-queries.test.tsx
mise exec -- pnpm typecheck
```

Expected: all focused tests and typecheck pass.

- [ ] **Step 6: Commit the frontend boundary**

```sh
git add frontend/src/app/infrastructure/api frontend/src/features/story-bible-persistence frontend/src/mocks
git commit -m "feat(frontend): add story bible persistence client"
```

### Task 3: Build the File-Backed Story Bible Operations

**Owner:** registered `backend` agent. This task may run in parallel with Task 2; it owns only `backend/**`.

**Files:**

- Create: `backend/apps/story_bible/__init__.py`
- Create: `backend/apps/story_bible/service/__init__.py`
- Create: `backend/apps/story_bible/service/story_bible.py`
- Create: `backend/apps/story_bible/repository/__init__.py`
- Create: `backend/apps/story_bible/repository/story_bible.py`
- Create: `backend/apps/story_bible/schemas/__init__.py`
- Create: `backend/apps/story_bible/schemas/story_bible.py`
- Create: `backend/apps/story_bible/router/__init__.py`
- Create: `backend/apps/story_bible/router/story_bible.py`
- Modify: `backend/main.py`
- Modify: `backend/docs/backend-coding-rules.md`
- Create: `backend/tests/story_bible/test_service.py`
- Create: `backend/tests/story_bible/test_file_repository.py`
- Create: `backend/tests/story_bible/test_api.py`

**Interfaces:**

- Consumes: approved OpenAPI commit `dfabc8a4...` and Story Bible domain contract commit `0c111b51...`.
- Produces: `StoryBibleService.get_story_bible`, `StoryBibleService.save_world_entries`, `FileStoryBibleRepository`, and FastAPI operations with the exact approved operation IDs.

- [ ] **Step 1: Write failing pure-service tests**

Define the expected immutable inputs and outcomes in tests:

```py
command = SaveWorldEntriesCommand(
    expected_revision=1,
    updates=(
        WorldEntryUpdate(
            id="silver-garden-world-1",
            kind="place",
            title="  비가 그친 유리 온실  ",
            description="  마지막 만남의 장소  ",
        ),
    ),
    additions=(
        WorldEntryAddition(kind="rule", title=" 왕실의 서약 ", description=" 계승권 규칙 "),
    ),
)

saved = service.save_world_entries("silver-garden", command)
assert saved.revision == 2
assert saved.story_bible.world_entries[0].id == "silver-garden-world-1"
assert saved.story_bible.world_entries[0].title == "비가 그친 유리 온실"
assert saved.story_bible.world_entries[1].id == "silver-garden-world-2"
```

Cover immutability, blank fields, invalid kinds at the transport boundary, duplicate/unknown update IDs, omitted entries, characters/order, exact lower/higher revision conflicts, all-or-nothing failure, and deterministic ID collision avoidance.

- [ ] **Step 2: Verify service RED**

```sh
mise exec -- uv run pytest tests/story_bible/test_service.py -q
```

Expected: FAIL because `apps.story_bible` does not exist.

- [ ] **Step 3: Implement the domain/application service**

Use frozen dataclasses and explicit errors. The public interface is:

```py
class StoryBibleRepository(Protocol):
    def get(self, project_id: str) -> StoryBibleSnapshot: ...
    def replace(
        self,
        project_id: str,
        expected_revision: int,
        story_bible: StoryBible,
    ) -> StoryBibleSnapshot: ...


class StoryBibleService:
    def __init__(
        self,
        repository: StoryBibleRepository,
        world_entry_id_factory: Callable[[str], str],
    ) -> None: ...

    def get_story_bible(self, project_id: str) -> StoryBibleSnapshot: ...
    def save_world_entries(
        self,
        project_id: str,
        command: SaveWorldEntriesCommand,
    ) -> StoryBibleSnapshot: ...
```

The service normalizes and validates the entire command before calling `replace` once. It never catches repository not-found, conflict, or persistence errors merely to hide them.

- [ ] **Step 4: Write failing file repository tests**

Tests use `tmp_path` and assert the durable envelope:

```json
{
  "schemaVersion": 1,
  "storyBibleRevision": 2,
  "storyBible": {
    "projectId": "silver-garden",
    "characters": [],
    "worldEntries": []
  }
}
```

Cover reload through a new repository instance, missing file, malformed/unsupported envelope, exact revision mismatch in both directions, traversal attempts, same-directory temporary files, cleanup after serialization/replace failure, unchanged canonical bytes after failure, lock-protected concurrent replacement, `flush`/`fsync`, and `os.replace`.

- [ ] **Step 5: Implement the file repository and verify persistence GREEN**

Construct it only from an explicit root:

```py
class FileStoryBibleRepository:
    def __init__(self, data_root: Path) -> None:
        self._data_root = data_root.resolve()

    def get(self, project_id: str) -> StoryBibleSnapshot: ...

    def replace(
        self,
        project_id: str,
        expected_revision: int,
        story_bible: StoryBible,
    ) -> StoryBibleSnapshot: ...
```

Resolve `<root>/projects/<projectId>/story-bible.json`, reject any path outside `data_root`, lock a sibling `.lock` file, re-read under the lock, require exact revision equality, write UTF-8 JSON to a same-directory temporary file, flush and `os.fsync`, then `os.replace`. Remove only the owned temporary file on failure. Document this reusable atomic-file rule in `backend/docs/backend-coding-rules.md`.

Run:

```sh
mise exec -- uv run pytest tests/story_bible/test_service.py tests/story_bible/test_file_repository.py -q
```

Expected: all focused service/repository tests pass.

- [ ] **Step 6: Write failing API tests and implement schemas/router**

API tests override the service dependency and cover every approved response: GET 200/404/500 and PUT 200/400/404/409/422/500. They also assert:

```py
assert app.openapi()["paths"]["/projects/{projectId}/story-bible"]["get"]["operationId"] == "getStoryBible"
assert app.openapi()["paths"]["/projects/{projectId}/story-bible/world-entries"]["put"]["operationId"] == "saveWorldEntries"
```

Pydantic request objects use `ConfigDict(extra="forbid")`. Register a focused FastAPI `RequestValidationError` handler that maps malformed JSON, missing/extra fields, wrong types, invalid enum values, and invalid integer syntax to `400 MALFORMED_REQUEST` in the exact `ApiError` shape; tests must assert the response instead of accepting FastAPI's default 422 body. Convert domain-invalid commands to 422 and known service/repository errors to the other exact approved statuses at the router boundary. Compose the file repository from a data-root environment value only in the FastAPI dependency boundary; domain/service modules never read environment or framework state.

- [ ] **Step 7: Verify and commit backend work**

Run from `backend/`:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: all commands exit 0.

```sh
git add backend
git commit -m "feat(backend): persist story bible world entries"
```

### Task 4: Implement the URL-Owned World Editor Workflow

**Owner:** the same registered `frontend` agent after Task 2 stops and commits. No backend paths are owned.

**Files:**

- Modify: `frontend/src/pages/writing-workspace/writing-workspace-tabs.ts`
- Modify: `frontend/src/routes/projects.$projectId.write.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`
- Modify: `frontend/src/modules/story-bible/domain/story-bible.ts`
- Modify: `frontend/src/modules/story-bible/domain/story-bible.test.ts`
- Modify: `frontend/src/modules/story-bible/ui/story-context-panel.tsx`
- Create: `frontend/src/features/edit-world-entries/world-entry-editor-state.ts`
- Create: `frontend/src/features/edit-world-entries/world-entry-editor-state.test.ts`
- Create: `frontend/src/features/edit-world-entries/use-world-entry-editor.ts`
- Create: `frontend/src/features/edit-world-entries/ui/world-entry-fields.tsx`
- Create: `frontend/src/features/edit-world-entries/ui/world-editor-feedback.tsx`
- Create: `frontend/src/features/edit-world-entries/ui/world-discard-dialog.tsx`
- Create: `frontend/src/features/edit-world-entries/ui/world-editor-sheet.tsx`
- Create: `frontend/src/features/edit-world-entries/ui/world-editor-sheet.test.tsx`
- Create: `frontend/src/features/edit-world-entries/index.ts`

**Interfaces:**

- Consumes: Task 2 query/mutation hooks, approved UI plan, and all `REQ-WORLD-*` IDs.
- Produces: canonical workspace search state, immutable editor reducer, Sheet/Dialog compositions, combined workspace navigation guard, and updated world read panel.

- [ ] **Step 1: Write failing pure-domain and reducer tests**

The Story Bible module exposes deterministic normalization/validation:

```ts
export interface WorldEntryDraftValue {
  kind: WorldEntry["kind"];
  title: string;
  description: string;
}

export interface WorldEntryDraftErrors {
  title?: string;
  description?: string;
}

export function validateWorldEntryDraft(value: WorldEntryDraftValue): {
  value?: WorldEntryDraftValue;
  errors: WorldEntryDraftErrors;
};
```

Reducer tests cover pristine/dirty state, immutable existing rows, client-only addition keys, multiple additions, all validation errors in one pass, first invalid field identity, pending freeze, retryable error, revision conflict, latest reload preserving the old draft until fetch success, and discard intent.

- [ ] **Step 2: Verify domain/reducer RED**

```sh
mise exec -- pnpm test src/modules/story-bible/domain/story-bible.test.ts src/features/edit-world-entries/world-entry-editor-state.test.ts
```

Expected: FAIL because the new exports and reducer do not exist.

- [ ] **Step 3: Implement the pure validation and discriminated state machine**

Use a single phase union:

```ts
export type WorldEditorPhase =
  | { status: "ready" }
  | { status: "validating" }
  | { status: "saving"; submittedDraft: WorldEditorDraft }
  | { status: "retryable-error"; error: ApiRequestError }
  | { status: "conflict" }
  | { status: "reloading" }
  | { status: "unavailable"; error: ApiRequestError };
```

Draft rows are controlled immutable values. Existing rows retain domain IDs; new rows use client-only render keys and never send those keys. Dirty comparison uses the raw draft as required by UI-plan assumption 8.

- [ ] **Step 4: Write failing component/page tests**

Cover populated and empty launch, all existing fields, kind badges, multiple additions/focus, validation summary and first-invalid focus, pending freeze, success/cache/list/announcement/replace-close, retryable 500, 404 unavailable, 409 and confirmed latest reload, every dirty-close source, clean close, direct URLs, invalid canonicalization, open/close history, Back/Forward, success not reopening on Back, and mobile nested Sheets.

Representative observable test:

```tsx
await user.click(screen.getByRole("button", { name: "세계관 수정 및 추가" }));
expect(router.state.location.search).toEqual({ tab: "world", panel: "world-editor" });

await user.clear(screen.getByRole("textbox", { name: "새 항목 1 제목" }));
await user.click(screen.getByRole("button", { name: "저장" }));
expect(screen.getByRole("textbox", { name: "새 항목 1 제목" })).toHaveFocus();
expect(screen.getByRole("alert")).toHaveTextContent("입력하지 않은 항목");
```

- [ ] **Step 5: Verify component/page RED**

```sh
mise exec -- pnpm test src/features/edit-world-entries/ui/world-editor-sheet.test.tsx src/pages/writing-workspace/writing-workspace-page.test.tsx
```

Expected: FAIL because the action, URL contract, editor, and mutation workflow do not exist.

- [ ] **Step 6: Extend the existing canonical tab URL state and implement the approved component tree**

Extend the merged `writing-workspace-tabs.ts`, route validator, and page canonicalizer with the editor panel contract while preserving all existing tab direct-link, history, canonicalization, and save-guard tests:

```ts
export const contextModes = ["manuscript", "characters", "world"] as const;
export type ContextMode = (typeof contextModes)[number];
export type WorkspacePanel = "world-editor";

export interface WritingWorkspaceSearch {
  tab?: ContextMode;
  panel?: WorkspacePanel;
}
```

Unknown/explicit-default values retain enough validated information for replacement canonicalization. User tab/editor open and explicit close push history; save success replaces away `panel`; `panel=world-editor` without world replaces to the canonical pair while preserving unrelated validated search.

Implement the exact UI-plan component structure with existing `Sheet`, `Dialog`, `Alert`, `Badge`, `Card`, `Button`, `Input`, `Label`, `Textarea`, `ScrollArea`, `Skeleton`, and a styled native select. No component calls HTTP directly.

- [ ] **Step 7: Coordinate the single navigation guard**

Replace the manuscript-only page guard with one page-level guard that sequences world-draft confirmation before manuscript flush without discarding either draft when the later step blocks:

```ts
async function shouldBlockWorkspaceNavigation(): Promise<boolean> {
  if (worldEditor.requiresDiscardConfirmation) {
    const confirmed = await worldEditor.confirmNavigationDiscard();
    if (!confirmed) return true;
  }

  return !(await flushManuscript());
}
```

Do not clear the world draft merely because confirmation was granted; let successful navigation unmount it. If manuscript flush fails, the world editor and draft remain. `enableBeforeUnload` is true when either workflow has unsaved work.

- [ ] **Step 8: Verify focused and full frontend GREEN**

Run from `frontend/`:

```sh
mise exec -- pnpm test src/modules/story-bible/domain/story-bible.test.ts src/features/edit-world-entries src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
mise exec -- pnpm api:lint
```

Expected: focused tests, full check, and build exit 0. API lint retains only the two documented pre-existing 4XX warnings.

- [ ] **Step 9: Commit and return the frontend handoff**

```sh
git add frontend
git commit -m "feat(frontend): edit and add world entries"
```

The handoff lists changed files, `REQ-WORLD-*` evidence, exact OpenAPI baseline, focused/full commands, and confirms no OpenAPI/backend/domain document edits.

### Task 5: Inspect Integration and Domain Synchronization

**Owner:** main agent after Tasks 2–4 stop editing.

**Files:**

- Review: all branch changes since `0c111b51895a3128ed1ff829cd6028ad86dabdeb`
- Compare: `docs/domains/story-bible.md`, frontend domain behavior, backend service behavior, and approved OpenAPI baseline

**Interfaces:**

- Consumes: frontend/backend handoffs and exact verification evidence.
- Produces: an accepted integration diff or exact remediation assignments.

- [ ] **Step 1: Verify ownership and baseline integrity**

```sh
git diff dfabc8a4f5274737e08ef43036b154b3417fc5f3 -- docs/api/openapi.yaml
git status --short
```

Expected: no OpenAPI drift and no overlapping/unexplained files.

- [ ] **Step 2: Compare domain and transport semantics**

Confirm all four implementations agree on this table:

```text
normalize title/description | domain authoritative | frontend early feedback
existing ID preservation    | domain/service       | request includes ID
new ID generation           | backend only         | response authoritative
omitted entries/characters  | preserved            | request cannot delete
revision mismatch           | 409, no mutation     | draft preserved
successful command          | one revision step    | cache from response
```

- [ ] **Step 3: Run cross-boundary focused checks**

```sh
cd frontend && mise exec -- pnpm api:lint && mise exec -- pnpm test src/mocks/story-bible-handlers.test.ts src/pages/writing-workspace/writing-workspace-page.test.tsx
cd ../backend && mise exec -- uv run pytest tests/story_bible -q
```

Expected: commands exit 0; only documented pre-existing Redocly warnings remain.

### Task 6: Run the Required Playwright Planner and Generator

**Owner:** configured `playwright_test_planner` followed by configured `playwright_test_generator`; neither may change product behavior.

**Files:**

- Required config: `.codex/agents/playwright_test_planner.toml`
- Required config: `.codex/agents/playwright_test_generator.toml`
- Planned output: `frontend/test-plans/worldbuilding-edit-add.md`
- Generated tests: `frontend/worldbuilding-edit-add.spec.ts`

**Interfaces:**

- Consumes: complete stopped frontend implementation, approved UI plan/blob, `REQ-WORLD-*`, approved OpenAPI baseline, and implementation handoff.
- Produces: approved E2E plan, generated Playwright coverage, and browser verification evidence.

- [ ] **Step 1: Check the mandatory custom agents separately**

```sh
test -f .codex/agents/playwright_test_planner.toml
test -f .codex/agents/playwright_test_generator.toml
```

Expected current result: both commands pass. If either later fails or the registered agent cannot invoke its configured MCP tools, mark the frontend pipeline blocked. Do not substitute a generic agent, create ad hoc tests, dispatch `frontend-review`, or proceed to final verification.

- [ ] **Step 2: When both registered agents exist, dispatch in order**

The planner covers desktop/mobile edit-add-save, direct URL/history, validation/focus, dirty discard, revision conflict/latest reload, retryable failure, persisted reload where the configured backend fixture exists, and keyboard accessibility. Main approves its exact output before generator dispatch.

- [ ] **Step 3: Generate and run the exact approved tests**

From `frontend/`, run the generator-specified Playwright command and then:

```sh
mise exec -- pnpm exec playwright test
```

Expected: all generated critical-flow tests pass without product-code changes by the generator.

### Task 7: Dispatch Read-Only Reviews, Remediate, and Verify

**Owner:** main agent; only after Task 6 completes and all implementation/E2E writers stop.

**Files:**

- Review boundary frontend: complete `/projects/$projectId/write` screen and all directly used Task 2/4 code/tests
- Review boundary backend: `getStoryBible`, `saveWorldEntries`, Story Bible service/repository/schemas/tests

**Interfaces:**

- Consumes: exact stopped diff, both implementer handoffs, E2E plan/tests/results, approved UI plan and OpenAPI baseline.
- Produces: native reviewer conclusions, normalized verdicts, disposition for every finding, re-review evidence where required, and final main-agent verification.

- [ ] **Step 1: Dispatch `frontend-review` and `backend-review` in parallel**

Supply the exact baseline/diff, routes/operation IDs, acceptance criteria, domain contract, UI plan/blob, OpenAPI commit/blob, handoffs, E2E evidence, accepted deviations, and safe read-only commands.

- [ ] **Step 2: Triage every finding**

Record `accept`, `reject` with concrete technical rationale, or `escalate`. Return every accepted finding to the owning implementer. Re-run focused/full checks and redispatch the same reviewer for Blocking/High or material behavior fixes.

- [ ] **Step 3: Require clear review gates**

Both affected native conclusions must be `No blocking findings`, normalized as `review-complete`; no accepted finding may remain unresolved. This is not merge approval.

- [ ] **Step 4: Run final verification**

```sh
cd frontend && mise exec -- pnpm check && mise exec -- pnpm build && mise exec -- pnpm api:lint
cd ../backend && mise exec -- uv run pytest && mise exec -- uv run ruff check . && mise exec -- uv run ruff format --check .
cd .. && git diff --check && git status --short
```

Expected: all application commands exit 0, API lint has only the two classified pre-existing warnings, diff check is clean, and status contains only intentional feature changes.

- [ ] **Step 5: Report completion only when all gates clear**

The final report includes changed paths, `REQ-WORLD-*` traceability, approved UI/OpenAPI identities, domain update, file-persistence behavior, frontend/backend/E2E handoffs, both native review conclusions and normalized verdicts, every finding disposition, exact commands/results, accepted deviations, and remaining risks.
