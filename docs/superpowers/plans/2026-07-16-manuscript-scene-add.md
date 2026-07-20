# Manuscript Scene Addition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a writer immediately add an empty manuscript scene, switch among scenes, and preserve locally added scenes through autosave errors and revision conflicts.

**Architecture:** Add immutable scene-addition and selection operations to the Manuscript domain, keep the existing whole-manuscript save contract, and make the writing workspace coordinate SceneTree events, active-scene rendering, focus, and responsive panel closure. Extend autosave conflict resolution with a separately typed structural-conflict path that performs a conservative three-way merge of local-only scenes onto the latest server manuscript.

**Tech Stack:** React 19, TypeScript 7, TanStack Query v5, TanStack Router, shadcn/ui primitives, Vitest, Testing Library, MSW, Playwright, pnpm via mise.

## Global Constraints

- Approved design: `docs/superpowers/specs/2026-07-16-manuscript-scene-add-design.md`.
- Default title is exactly `제목 없는 장면`; the new scene has empty content and empty related-character/world-entry arrays.
- The next chapter number is the current maximum chapter number plus one.
- Rename, reorder, delete, nested table-of-contents hierarchy, new dependencies, and new API operations are out of scope.
- Continue using `saveManuscript` and the existing whole-Manuscript OpenAPI schema; do not edit `docs/api/openapi.yaml`.
- Domain operations stay deterministic, immutable, and free of React, browser, persistence, and network dependencies.
- During implementation, the frontend agent owns frontend code and `docs/domains/manuscript.md`; the main agent retains integration approval.
- After frontend editing stops, run the read-only `frontend-review`; only after that review gate clears, run the required Playwright planning and generation agents against the approved design.

---

## File Map

- `docs/domains/manuscript.md`: authoritative scene-addition, selection, and invariant language.
- `frontend/src/modules/manuscript/domain/manuscript.ts`: immutable `addScene` and `selectScene` operations.
- `frontend/src/modules/manuscript/domain/manuscript.test.ts`: domain behavior and failure tests.
- `frontend/src/modules/manuscript/ui/scene-tree.tsx`: accessible add/select presentation and active state.
- `frontend/src/modules/manuscript/ui/scene-tree.test.tsx`: isolated SceneTree interaction tests.
- `frontend/src/modules/manuscript/ui/manuscript-editor.tsx`: forwarded Textarea ref for post-navigation focus.
- `frontend/src/features/manuscript-autosave/manuscript-structure-conflict.ts`: pure detection and conservative merge rules.
- `frontend/src/features/manuscript-autosave/manuscript-structure-conflict.test.ts`: structural merge unit tests.
- `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`: expose the acknowledged base to conflict resolution.
- `frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`: load and resolve body versus structural conflicts.
- `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`: autosave structural-conflict integration tests.
- `frontend/src/features/project-persistence/api/project-queries.ts`: reusable workspace query options for explicit conflict refresh.
- `frontend/src/features/project-persistence/api/project-queries.test.tsx`: query-options cache and refresh behavior.
- `frontend/src/features/project-persistence/index.ts`: public query-options export.
- `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.tsx`: structural-conflict copy and actions.
- `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx`: dialog-mode tests.
- `frontend/src/features/manuscript-scene-navigation/use-manuscript-scene-navigation.ts`: scene-add/select coordination, selection reset, announcement, and editor focus.
- `frontend/src/features/manuscript-scene-navigation/use-manuscript-scene-navigation.test.tsx`: focused application-hook behavior.
- `frontend/src/features/manuscript-scene-navigation/index.ts`: public feature exports.
- `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`: compose the scene-navigation feature with SceneTree, editor, header, and responsive context panel.
- `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`: complete screen acceptance tests.
- `frontend/test-plans/manuscript-scene-add-e2e.md`: generated E2E plan after implementation.
- `frontend/manuscript-scene-add.spec.ts`: generated Playwright flow.

---

### Task 1: Manuscript domain contract and operations

**Files:**
- Modify: `docs/domains/manuscript.md`
- Modify: `frontend/src/modules/manuscript/domain/manuscript.ts`
- Modify: `frontend/src/modules/manuscript/domain/manuscript.test.ts`

**Interfaces:**
- Produces: `addScene(manuscript: Manuscript, sceneId: string): Manuscript`
- Produces: `selectScene(manuscript: Manuscript, sceneId: string): Manuscript`
- Consumes: existing `Manuscript` and `Scene` types.

- [ ] **Step 1: Write failing domain tests**

Add tests that assert exact defaults, maximum-plus-one numbering, immutable append/activation, duplicate and blank ID rejection, immutable selection, and missing-scene rejection:

```ts
test("adds and activates one empty scene after the highest chapter number", async () => {
  const { addScene, createInitialManuscript } = await import("./manuscript");
  const manuscript = createInitialManuscript("project-1");

  const updated = addScene(manuscript, "project-1-scene-2");

  expect(updated.scenes).toHaveLength(2);
  expect(updated.scenes[1]).toEqual({
    id: "project-1-scene-2",
    title: "제목 없는 장면",
    chapterNumber: 2,
    content: "",
    relatedCharacterIds: [],
    relatedWorldEntryIds: [],
  });
  expect(updated.activeSceneId).toBe("project-1-scene-2");
  expect(manuscript.scenes).toHaveLength(1);
});

test("numbers from the maximum chapter rather than the array length", async () => {
  const { addScene, createInitialManuscript } = await import("./manuscript");
  const manuscript = createInitialManuscript("project-1");
  const sparse = {
    ...manuscript,
    scenes: [{ ...manuscript.scenes[0]!, chapterNumber: 4 }],
  };
  expect(addScene(sparse, "scene-5").scenes[1]?.chapterNumber).toBe(5);
});

test.each(["", "project-1-scene-1"])("rejects invalid new scene id %j", async (sceneId) => {
  const { addScene, createInitialManuscript } = await import("./manuscript");
  expect(() => addScene(createInitialManuscript("project-1"), sceneId)).toThrow();
});

test("selects an existing scene without changing scene content", async () => {
  const { addScene, createInitialManuscript, selectScene } = await import("./manuscript");
  const manuscript = addScene(createInitialManuscript("project-1"), "scene-2");
  const selected = selectScene(manuscript, "project-1-scene-1");
  expect(selected.activeSceneId).toBe("project-1-scene-1");
  expect(selected.scenes).toBe(manuscript.scenes);
  expect(manuscript.activeSceneId).toBe("scene-2");
});
```

- [ ] **Step 2: Run the focused test and observe the expected failure**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/modules/manuscript/domain/manuscript.test.ts
```

Expected: FAIL because `addScene` and `selectScene` are not exported.

- [ ] **Step 3: Implement the minimal pure operations**

Add these operations, keeping ID generation outside the domain:

```ts
export function addScene(manuscript: Manuscript, sceneId: string): Manuscript {
  if (!sceneId.trim()) throw new Error("새 장면 식별자가 필요합니다.");
  if (manuscript.scenes.some(({ id }) => id === sceneId)) {
    throw new Error("이미 존재하는 원고 장면입니다.");
  }
  const chapterNumber = Math.max(...manuscript.scenes.map((scene) => scene.chapterNumber)) + 1;
  const scene: Scene = {
    id: sceneId,
    title: "제목 없는 장면",
    chapterNumber,
    content: "",
    relatedCharacterIds: [],
    relatedWorldEntryIds: [],
  };
  return { ...manuscript, scenes: [...manuscript.scenes, scene], activeSceneId: sceneId };
}

export function selectScene(manuscript: Manuscript, sceneId: string): Manuscript {
  if (!manuscript.scenes.some(({ id }) => id === sceneId)) {
    throw new Error("원고 장면을 찾을 수 없습니다.");
  }
  return manuscript.activeSceneId === sceneId ? manuscript : { ...manuscript, activeSceneId: sceneId };
}
```

Update `docs/domains/manuscript.md` in the same change: add scene addition and active-scene selection to ubiquitous language/use cases; require non-empty unique scene IDs for addition; specify max-plus-one numbering, exact defaults, append order, and immutable activation.

- [ ] **Step 4: Run focused verification**

```sh
mise exec -- pnpm test -- src/modules/manuscript/domain/manuscript.test.ts
mise exec -- pnpm typecheck
```

Expected: both commands PASS.

- [ ] **Step 5: Commit the domain slice**

```sh
git add docs/domains/manuscript.md frontend/src/modules/manuscript/domain/manuscript.ts frontend/src/modules/manuscript/domain/manuscript.test.ts
git commit -m "feat: add manuscript scene operations"
```

---

### Task 2: Accessible SceneTree and editor focus surface

**Files:**
- Modify: `frontend/src/modules/manuscript/ui/scene-tree.tsx`
- Create: `frontend/src/modules/manuscript/ui/scene-tree.test.tsx`
- Modify: `frontend/src/modules/manuscript/ui/manuscript-editor.tsx`

**Interfaces:**
- Consumes: `Manuscript` with `activeSceneId`.
- Produces: `SceneTreeProps` callbacks `onAdd(): void`, `onSelect(sceneId: string): void`, and `addDisabled: boolean`.
- Produces: `ManuscriptEditor` forwarded ref of type `HTMLTextAreaElement`.

- [ ] **Step 1: Write failing SceneTree tests**

```tsx
test("adds, selects, and marks the active scene", async () => {
  const manuscript = addScene(createInitialManuscript("project-1"), "scene-2");
  const onAdd = vi.fn();
  const onSelect = vi.fn();
  const user = userEvent.setup();
  render(<SceneTree manuscript={manuscript} onAdd={onAdd} onSelect={onSelect} addDisabled={false} />);

  await user.click(screen.getByRole("button", { name: "새 장면 추가" }));
  await user.click(screen.getByRole("button", { name: "1장 비가 그친 뒤의 정원" }));

  expect(onAdd).toHaveBeenCalledOnce();
  expect(onSelect).toHaveBeenCalledWith("project-1-scene-1");
  expect(screen.getByRole("button", { name: "2장 제목 없는 장면" })).toHaveAttribute(
    "aria-current",
    "true",
  );
});

test("disables only scene addition during conflict resolution", () => {
  render(<SceneTree manuscript={createInitialManuscript("p")} onAdd={vi.fn()} onSelect={vi.fn()} addDisabled />);
  expect(screen.getByRole("button", { name: "새 장면 추가" })).toBeDisabled();
  expect(screen.getByRole("button", { name: /1장/ })).toBeEnabled();
});
```

- [ ] **Step 2: Run the focused test and observe the prop/API failure**

```sh
mise exec -- pnpm test -- src/modules/manuscript/ui/scene-tree.test.tsx
```

Expected: FAIL because SceneTree lacks the callbacks and active semantics.

- [ ] **Step 3: Implement the presentation contract**

Remove the hard-coded part heading, wire the add button, and render each row as:

```tsx
<Button
  type="button"
  variant="ghost"
  size="icon-xs"
  aria-label="새 장면 추가"
  disabled={addDisabled}
  onClick={onAdd}
>
  <Plus />
</Button>

<button
  type="button"
  aria-current={scene.id === manuscript.activeSceneId ? "true" : undefined}
  aria-label={`${scene.chapterNumber}장 ${scene.title}`}
  onClick={() => onSelect(scene.id)}
  className={cn(
    "flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2.5 text-left",
    scene.id === manuscript.activeSceneId &&
      "bg-sidebar-accent text-sidebar-accent-foreground",
  )}
>
```

Convert `ManuscriptEditor` to `forwardRef<HTMLTextAreaElement, ManuscriptEditorProps>` and pass the ref to the existing `Textarea`; retain all current selection callbacks and accessible name.

- [ ] **Step 4: Run focused UI checks**

```sh
mise exec -- pnpm test -- src/modules/manuscript/ui/scene-tree.test.tsx
mise exec -- pnpm typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit the UI unit**

```sh
git add frontend/src/modules/manuscript/ui/scene-tree.tsx frontend/src/modules/manuscript/ui/scene-tree.test.tsx frontend/src/modules/manuscript/ui/manuscript-editor.tsx
git commit -m "feat: make manuscript scene tree interactive"
```

---

### Task 3: Pure structural-conflict detection and merge

**Files:**
- Create: `frontend/src/features/manuscript-autosave/manuscript-structure-conflict.ts`
- Create: `frontend/src/features/manuscript-autosave/manuscript-structure-conflict.test.ts`

**Interfaces:**
- Produces: `findLocalSceneAdditions(base: Manuscript, local: Manuscript): Scene[]`.
- Produces: `mergeLocalSceneAdditions(base: Manuscript, local: Manuscript, server: Manuscript): Manuscript`.
- Throws exact user-safe domain errors for unsafe merge conditions.

- [ ] **Step 1: Write failing three-way merge tests**

Cover a safe append preserving server edits, local edits inside the new scene, duplicate ID, chapter-number collision, and local edits to a base scene:

```ts
test("appends local-only scenes to the latest server manuscript", () => {
  const base = createInitialManuscript("project-1");
  const local = updateSceneContent(addScene(base, "local-2"), "local-2", "새 장면 본문");
  const server = updateSceneContent(base, base.activeSceneId, "서버 최신 본문");
  const merged = mergeLocalSceneAdditions(base, local, server);
  expect(merged.scenes[0]?.content).toBe("서버 최신 본문");
  expect(merged.scenes[1]?.id).toBe("local-2");
  expect(merged.scenes[1]?.content).toBe("새 장면 본문");
  expect(merged.activeSceneId).toBe("local-2");
});

test("refuses automatic merge when the local draft also changes a base scene", () => {
  const base = createInitialManuscript("project-1");
  const local = updateSceneContent(addScene(base, "local-2"), base.activeSceneId, "로컬 기존 장면 변경");
  expect(() => mergeLocalSceneAdditions(base, local, base)).toThrow(
    "기존 장면의 로컬 변경과 새 장면을 동시에 자동 병합할 수 없습니다.",
  );
});
```

- [ ] **Step 2: Run the focused test and observe the missing-module failure**

```sh
mise exec -- pnpm test -- src/features/manuscript-autosave/manuscript-structure-conflict.test.ts
```

Expected: FAIL because the merge module does not exist.

- [ ] **Step 3: Implement conservative merge rules**

Use scene IDs from the acknowledged base to identify additions. Before merging:

1. Require at least one local-only scene.
2. Compare every base-scene object in local with its base version; reject any local modification or removal.
3. Reject a local-only ID already present on the server.
4. Reject a local-only chapter number already present on the server.
5. Return `{ ...server, scenes: [...server.scenes, ...localOnlyScenes], activeSceneId }`, using the local active ID only when it exists in the merged list and otherwise using the server active ID.

Implement object comparisons explicitly over Scene fields rather than JSON serialization so field ownership remains visible.

```ts
function scenesEqual(left: Scene, right: Scene): boolean {
  return (
    left.id === right.id &&
    left.title === right.title &&
    left.chapterNumber === right.chapterNumber &&
    left.content === right.content &&
    left.relatedCharacterIds.length === right.relatedCharacterIds.length &&
    left.relatedCharacterIds.every((id, index) => id === right.relatedCharacterIds[index]) &&
    left.relatedWorldEntryIds.length === right.relatedWorldEntryIds.length &&
    left.relatedWorldEntryIds.every((id, index) => id === right.relatedWorldEntryIds[index])
  );
}

export function findLocalSceneAdditions(base: Manuscript, local: Manuscript): Scene[] {
  const baseIds = new Set(base.scenes.map(({ id }) => id));
  return local.scenes.filter(({ id }) => !baseIds.has(id));
}

export function mergeLocalSceneAdditions(
  base: Manuscript,
  local: Manuscript,
  server: Manuscript,
): Manuscript {
  const additions = findLocalSceneAdditions(base, local);
  if (additions.length === 0) throw new Error("병합할 새 장면이 없습니다.");
  if (base.scenes.some((scene) => {
    const localScene = local.scenes.find(({ id }) => id === scene.id);
    return !localScene || !scenesEqual(scene, localScene);
  })) {
    throw new Error("기존 장면의 로컬 변경과 새 장면을 동시에 자동 병합할 수 없습니다.");
  }
  const serverIds = new Set(server.scenes.map(({ id }) => id));
  const serverChapters = new Set(server.scenes.map(({ chapterNumber }) => chapterNumber));
  if (additions.some(({ id }) => serverIds.has(id))) {
    throw new Error("서버 원고와 새 장면 식별자가 충돌합니다.");
  }
  if (additions.some(({ chapterNumber }) => serverChapters.has(chapterNumber))) {
    throw new Error("서버 원고와 새 장 번호가 충돌합니다.");
  }
  const scenes = [...server.scenes, ...additions];
  return {
    ...server,
    scenes,
    activeSceneId: scenes.some(({ id }) => id === local.activeSceneId)
      ? local.activeSceneId
      : server.activeSceneId,
  };
}
```

- [ ] **Step 4: Run the merge unit tests**

```sh
mise exec -- pnpm test -- src/features/manuscript-autosave/manuscript-structure-conflict.test.ts
mise exec -- pnpm typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit the merge unit**

```sh
git add frontend/src/features/manuscript-autosave/manuscript-structure-conflict.ts frontend/src/features/manuscript-autosave/manuscript-structure-conflict.test.ts
git commit -m "feat: merge local manuscript scene additions"
```

---

### Task 4: Autosave structural-conflict state and dialog

**Files:**
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`
- Modify: `frontend/src/features/project-persistence/api/project-queries.ts`
- Modify: `frontend/src/features/project-persistence/api/project-queries.test.tsx`
- Modify: `frontend/src/features/project-persistence/index.ts`
- Modify: `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.tsx`
- Modify: `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx`

**Interfaces:**
- Consumes: `findLocalSceneAdditions` and `mergeLocalSceneAdditions` from Task 3.
- Produces: `projectWorkspaceQueryOptions(projectId)` so feature code can refetch the workspace without importing infrastructure APIs.
- Produces: `conflictKind: "scene-content" | "scene-structure" | null` from `useManuscriptAutosave`.
- Produces: conflict dialog prop `kind: "scene-content" | "scene-structure"`.
- Produces: `ManuscriptStructureConflict` containing `serverManuscript` and `serverRevision`.

- [ ] **Step 1: Add failing hook tests for structural conflict**

Use MSW so the first PUT returns 409, the workspace GET returns a newer server manuscript/revision, and the second PUT records the merged payload. Assert:

```ts
expect(result.current.conflictKind).toBe("scene-structure");
await act(async () => result.current.keepLocal());
expect(saveRequests[1]?.expectedRevision).toBe(7);
expect(saveRequests[1]?.manuscript.scenes.map(({ id }) => id)).toEqual([
  "silver-garden-scene-1",
  "server-only-scene",
  "local-new-scene",
]);
```

Add these companion assertions in separate tests using the same MSW setup: after `applyServer()`, expect `draft.scenes` to equal the refreshed server scenes and `status` to be `saved`; after an ID or chapter collision, expect the local-only scene to remain in `draft`, `status` to stay `conflict`, and `isConflictResolutionError` to be true. Keep the existing scene-content conflict tests in the same focused run to prove their comparison and resolution behavior is unchanged.

- [ ] **Step 2: Add failing dialog-mode tests**

Render `ManuscriptConflictDialog` with `kind="scene-structure"` and assert the exact copy and buttons:

```tsx
expect(screen.getByText("서버 최신 원고에 아직 없는 새 장면이 있어요.")).toBeInTheDocument();
expect(screen.getByRole("button", { name: "내 새 장면 유지" })).toBeEnabled();
expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toBeEnabled();
expect(screen.queryByRole("table")).not.toBeInTheDocument();
```

- [ ] **Step 3: Run focused tests and observe failures**

```sh
mise exec -- pnpm test -- src/features/manuscript-autosave/use-manuscript-autosave.test.tsx src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx
```

Expected: FAIL because structural conflict state and dialog mode do not exist.

- [ ] **Step 4: Add reusable project-workspace query options**

Extract the existing workspace query definition and reuse it from `useProjectWorkspaceQuery`:

```ts
export function projectWorkspaceQueryOptions(projectId: string) {
  return queryOptions({
    queryKey: projectKeys.workspace(projectId),
    queryFn: () => getProjectWorkspace(projectId),
  });
}

export function useProjectWorkspaceQuery(projectId: string) {
  return useQuery(projectWorkspaceQueryOptions(projectId));
}
```

Export `projectWorkspaceQueryOptions` through the feature index. Extend `project-queries.test.tsx` to call `queryClient.fetchQuery(projectWorkspaceQueryOptions("silver-garden"))` and assert the returned workspace and populated `projectKeys.workspace("silver-garden")` cache entry.

- [ ] **Step 5: Model conflict phases and load the latest workspace**

Add `getAcknowledgedManuscript` to the conflict host using `acknowledgedManuscriptRef.current`.
On a 409, call `findLocalSceneAdditions(base, currentDraft)`:

- When additions exist, fetch `queryClient.fetchQuery(projectWorkspaceQueryOptions(currentDraft.projectId))`, store its manuscript and revision as a structural comparison, and set the kind to `scene-structure`.
- When none exist, keep the current `scene-diffs` request and `scene-content` behavior.
- Replace the touched hook's independent comparison/resolution booleans with one discriminated state; derive the existing public booleans from its phase so impossible combinations cannot occur. Never clear the draft on a fetch failure.

```ts
interface ManuscriptStructureConflict {
  serverManuscript: Manuscript;
  serverRevision: number;
}

type ConflictPayload =
  | { kind: "scene-content"; comparison: CompareManuscriptSceneResponse }
  | { kind: "scene-structure"; comparison: ManuscriptStructureConflict };

type ConflictState =
  | { phase: "idle" }
  | { phase: "loading"; kind: ConflictPayload["kind"] }
  | { phase: "load-error"; kind: ConflictPayload["kind"] }
  | ({ phase: "ready" | "resolving" | "resolve-error" } & ConflictPayload);

const base = host.getAcknowledgedManuscript();
const local = host.getDraft();
if (findLocalSceneAdditions(base, local).length > 0) {
  setConflictState({ phase: "loading", kind: "scene-structure" });
  const latest = await queryClient.fetchQuery(projectWorkspaceQueryOptions(local.projectId));
  setConflictState({
    phase: "ready",
    kind: "scene-structure",
    comparison: {
      serverManuscript: latest.manuscript,
      serverRevision: latest.manuscriptRevision,
    },
  });
} else {
  requestLatestDraftComparison();
}
```

For `keepLocal`, switch on the ready payload kind: use `updateSceneContent` for scene-content conflicts and `mergeLocalSceneAdditions` for scene-structure conflicts, then save at the comparison's server revision. `applyServer` adopts the comparison's server manuscript and revision for either kind. A repeated 409 transitions back to `loading` and refreshes the matching comparison.

- [ ] **Step 6: Render the structural dialog mode**

Add a `kind` prop. In structural mode, replace the diff table with the approved explanatory copy and use `내 새 장면 유지`; retain the existing scene-content table and `내 편집본 유지` copy in content mode. Both modes keep existing focus trapping, close behavior, progress disabling, alerts, and retry actions.

```tsx
{kind === "scene-structure" && (
  <div className="grid min-h-48 place-items-center text-center">
    <div>
      <p className="font-medium">서버 최신 원고에 아직 없는 새 장면이 있어요.</p>
      <p className="mt-2 text-sm text-muted-foreground">
        현재 로컬 초안은 보관하고 있습니다.
      </p>
    </div>
  </div>
)}

<Button
  type="button"
  onClick={onKeepLocal}
  disabled={
    isComparing ||
    isResolving ||
    compareError ||
    (kind === "scene-content" && !comparison)
  }
>
  {kind === "scene-structure" ? "내 새 장면 유지" : "내 편집본 유지"}
</Button>
```

Prefix the existing loading/error/table JSX block with `kind === "scene-content" &&` and otherwise
leave its current markup unchanged. Do not extract or rename the existing diff table helpers.

- [ ] **Step 7: Run focused autosave, persistence, and dialog tests**

```sh
mise exec -- pnpm test -- src/features/manuscript-autosave/manuscript-structure-conflict.test.ts src/features/manuscript-autosave/use-manuscript-autosave.test.tsx src/features/project-persistence/api/project-queries.test.tsx src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx
mise exec -- pnpm typecheck
```

Expected: PASS, including all pre-existing scene-content conflict tests.

- [ ] **Step 8: Commit conflict support**

```sh
git add frontend/src/features/manuscript-autosave frontend/src/features/project-persistence frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.tsx frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx
git commit -m "feat: resolve manuscript structure conflicts"
```

---

### Task 5: Feature-level scene navigation workflow

**Files:**
- Create: `frontend/src/features/manuscript-scene-navigation/use-manuscript-scene-navigation.ts`
- Create: `frontend/src/features/manuscript-scene-navigation/use-manuscript-scene-navigation.test.tsx`
- Create: `frontend/src/features/manuscript-scene-navigation/index.ts`

**Interfaces:**
- Consumes: `addScene(manuscript, sceneId)`, `selectScene(manuscript, sceneId)`, the current `Manuscript`, and an autosave-compatible functional draft updater.
- Produces: `useManuscriptSceneNavigation(options)` with active-scene derivation, editor selection state, `editorRef`, `announcement`, `addNewScene()`, and `activateScene(sceneId)`.

- [ ] **Step 1: Write failing hook tests**

Use `renderHook` with a stateful Manuscript wrapper. Inject `createSceneId: () => "scene-3"`, mock `requestAnimationFrame` to invoke immediately, and assert that adding creates and activates one scene, resets the selection, announces `3장 장면을 추가했어요`, closes only the mobile context panel, and focuses the editor ref. Add a second test that selecting the first scene preserves both scene objects and clears the selection.

```tsx
const { result } = renderHook(() => {
  const [manuscript, setManuscript] = useState(() =>
    addScene(createInitialManuscript("project-1"), "scene-2"),
  );
  return useManuscriptSceneNavigation({
    manuscript,
    updateDraft: setManuscript,
    contextIsInline: false,
    onCloseContext: closeContext,
    createSceneId: () => "scene-3",
  });
});

act(() => result.current.addNewScene());
expect(result.current.activeScene?.id).toBe("scene-3");
expect(result.current.announcement).toBe("3장 장면을 추가했어요");
expect(closeContext).toHaveBeenCalledOnce();
```

- [ ] **Step 2: Run the hook test and observe the missing-module failure**

```sh
mise exec -- pnpm test -- src/features/manuscript-scene-navigation/use-manuscript-scene-navigation.test.tsx
```

Expected: FAIL because the feature module does not exist.

- [ ] **Step 3: Implement the focused application hook**

Keep browser ID generation, focus scheduling, mobile panel coordination, and selection reset in this feature instead of the page. Use an injectable ID factory for deterministic tests while defaulting to `crypto.randomUUID()` in production.

```ts
type DraftUpdate = Manuscript | ((current: Manuscript) => Manuscript);

interface UseManuscriptSceneNavigationOptions {
  manuscript: Manuscript;
  updateDraft: (update: DraftUpdate) => void;
  contextIsInline: boolean;
  onCloseContext: () => void;
  createSceneId?: (manuscript: Manuscript) => string;
}

export function useManuscriptSceneNavigation({
  manuscript,
  updateDraft,
  contextIsInline,
  onCloseContext,
  createSceneId = (current) => `${current.projectId}-scene-${crypto.randomUUID()}`,
}: UseManuscriptSceneNavigationOptions) {
  const [selection, setSelection] = useState<TextRange | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const activeScene = manuscript.scenes.find(({ id }) => id === manuscript.activeSceneId);

  const finishNavigation = () => {
    setSelection(null);
    if (!contextIsInline) onCloseContext();
    requestAnimationFrame(() => editorRef.current?.focus());
  };

  const addNewScene = () => {
    let chapterNumber = 0;
    updateDraft((current) => {
      const next = addScene(current, createSceneId(current));
      chapterNumber = next.scenes.find(({ id }) => id === next.activeSceneId)!.chapterNumber;
      return next;
    });
    setAnnouncement(`${chapterNumber}장 장면을 추가했어요`);
    finishNavigation();
  };

  const activateScene = (sceneId: string) => {
    updateDraft((current) => selectScene(current, sceneId));
    finishNavigation();
  };

  return { activeScene, selection, setSelection, editorRef, announcement, addNewScene, activateScene };
}
```

Export only `useManuscriptSceneNavigation` from the feature `index.ts`.

- [ ] **Step 4: Run focused hook verification**

```sh
mise exec -- pnpm test -- src/features/manuscript-scene-navigation/use-manuscript-scene-navigation.test.tsx
mise exec -- pnpm typecheck
```

Expected: both commands PASS.

- [ ] **Step 5: Commit the feature workflow**

```sh
git add frontend/src/features/manuscript-scene-navigation
git commit -m "feat: coordinate manuscript scene navigation"
```

---

### Task 6: Complete writing-workspace scene integration

**Files:**
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**
- Consumes: `useManuscriptSceneNavigation`, SceneTree callbacks, editor ref, and `conflictKind` from Tasks 2, 4, and 5.
- Produces: complete add/select behavior on `/projects/$projectId/write` without adding detailed scene workflow state to the page.

- [ ] **Step 1: Write failing desktop acceptance tests**

Stub `crypto.randomUUID()` to `scene-2`, collect PUT bodies, click the existing add button, and assert exact behavior:

```ts
vi.stubGlobal("crypto", { randomUUID: () => "scene-2" });
await user.click(await screen.findByRole("button", { name: "새 장면 추가" }));
expect(screen.getByRole("button", { name: "2장 제목 없는 장면" })).toHaveAttribute(
  "aria-current",
  "true",
);
expect(screen.getByRole("heading", { name: "제목 없는 장면" })).toBeInTheDocument();
expect(screen.getByRole("textbox", { name: "원고 본문" })).toHaveFocus();
expect(screen.getByText("2장 장면을 추가했어요")).toBeInTheDocument();
await waitFor(() => expect(saveRequests[0]?.manuscript.scenes).toHaveLength(2));
```

Then select `1장 비가 그친 뒤의 정원` and assert the original content and dynamic header return without losing the second scene.

- [ ] **Step 2: Write failing mobile and persistence-state tests**

At 375px, open `원고 보기`, add a scene, and assert the Sheet closes and the editor has focus. Add tests that the add control is disabled during structural conflict, remains available after a normal save error, retry preserves the new scene, and a reload-equivalent workspace response restores `activeSceneId`.

- [ ] **Step 3: Run the screen test and observe failures**

```sh
mise exec -- pnpm test -- src/pages/writing-workspace/writing-workspace-page.test.tsx
```

Expected: FAIL because the feature hook, SceneTree callbacks, dynamic header, focus, and announcement are not wired.

- [ ] **Step 4: Wire the feature into the screen**

Remove the page-owned manuscript `selection` state and use the feature hook instead:

```ts
const sceneNavigation = useManuscriptSceneNavigation({
  manuscript: draft,
  updateDraft,
  contextIsInline,
  onCloseContext: () => setContextOpen(false),
});
const scene = sceneNavigation.activeScene;
const selection = sceneNavigation.selection;
```

Pass `sceneNavigation.setSelection` to the editor and writing-suggestion flow, `sceneNavigation.editorRef` to `ManuscriptEditor`, and `sceneNavigation.addNewScene`/`activateScene` through every `ContextPanelContent` composition into `SceneTree`. Pass `addDisabled={status === "conflict"}`, render `<p className="sr-only" aria-live="polite">{sceneNavigation.announcement}</p>`, and change the fixed header subtitle to `${scene.chapterNumber}장 · ${scene.title}`.

- [ ] **Step 5: Run screen and related focused tests**

```sh
mise exec -- pnpm test -- src/pages/writing-workspace/writing-workspace-page.test.tsx src/features/manuscript-scene-navigation/use-manuscript-scene-navigation.test.tsx src/modules/manuscript/ui/scene-tree.test.tsx
mise exec -- pnpm typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit the complete screen**

```sh
git add frontend/src/pages/writing-workspace/writing-workspace-page.tsx frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx
git commit -m "feat: add scenes from writing workspace"
```

---

### Task 7: Review, E2E artifacts, and final verification

**Files:**
- Create: `frontend/test-plans/manuscript-scene-add-e2e.md`
- Create: `frontend/manuscript-scene-add.spec.ts`
- Review only: all files listed in the File Map

**Interfaces:**
- Consumes: stopped frontend implementation and `docs/superpowers/specs/2026-07-16-manuscript-scene-add-design.md`.
- Produces: resolved frontend-review findings, required E2E plan/test, and final verification evidence.

- [ ] **Step 1: Stop frontend editing and dispatch read-only frontend review**

Give `frontend-review` the complete `/projects/$projectId/write` screen; implementation handoff; the approved design completion criteria; `docs/domains/manuscript.md`; no OpenAPI change; affected entry points `SceneTree`, `useManuscriptSceneNavigation`, `useManuscriptAutosave`, and `ManuscriptConflictDialog`; and safe commands limited to focused tests plus `pnpm check`/`pnpm build`. The reviewer edits no files.

- [ ] **Step 2: Triage and resolve every accepted review finding**

Record severity, introduced/pre-existing classification, source location, impact, repair direction, and re-review requirement. Return accepted findings to the frontend implementer. Re-run `frontend-review` for blocking/high findings or material behavior changes; record concrete rationale for rejected findings. Do not start E2E planning until the application review gate clears.

- [ ] **Step 3: Dispatch the required Playwright planner**

Give `.codex/agents/playwright_test_planner.toml` the route `/projects/silver-garden/write`, the approved design, `docs/domains/manuscript.md`, implementation handoff, and sole ownership of `frontend/test-plans/manuscript-scene-add-e2e.md`. Require flows for immediate add/focus, typing and autosave, existing-scene reselection, mobile Sheet closure, save failure/retry, safe structural merge, and server-latest adoption. The planner must not edit implementation or test code.

- [ ] **Step 4: Review and approve the E2E plan**

Confirm every approved completion criterion has a user-visible assertion, structural-conflict choices are covered, and no rename/reorder/delete or invented API operation appears. Return gaps to the planner before generation.

- [ ] **Step 5: Dispatch the required Playwright generator**

Give `.codex/agents/playwright_test_generator.toml` the approved E2E plan and sole ownership of `frontend/manuscript-scene-add.spec.ts`. Tests must use the real route and user-visible roles/names; they may install no dependencies or change product behavior.

- [ ] **Step 6: Run Playwright verification**

In one terminal from `frontend/`:

```sh
mise exec -- pnpm dev --host 127.0.0.1
```

Expected: Vite reports the app at `http://127.0.0.1:5173/`.

In a second terminal:

```sh
mise exec -- pnpm exec playwright test manuscript-scene-add.spec.ts
```

Expected: PASS. Stop the development server after the test.

- [ ] **Step 7: Run full affected-application checks**

From `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: both commands exit 0. Also run `git diff --check` from the repository root and compare the implementation diff with `docs/domains/manuscript.md` to confirm they describe identical behavior and boundaries.

- [ ] **Step 8: Commit E2E and reviewed repairs**

```sh
git add frontend/test-plans/manuscript-scene-add-e2e.md frontend/manuscript-scene-add.spec.ts
git commit -m "test: cover manuscript scene addition"
```

Do not claim completion until all accepted findings are resolved and the focused tests, Playwright test, full check, build, and domain-document comparison have been observed.
