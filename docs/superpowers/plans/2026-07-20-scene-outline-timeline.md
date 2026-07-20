# Scene Outline Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a URL-restorable, ordered scene-outline timeline where a writer can plan, edit, reorder, delete, and open manuscript scenes while preserving the existing autosave and conflict-recovery guarantees.

**Architecture:** Extend the Manuscript aggregate with outline metadata and immutable ordering/removal operations, then keep the existing whole-manuscript save operation as the only persistence boundary. A focused `organize-scenes` frontend feature owns timeline presentation and interactions; the writing-workspace page only composes it and maps URL search state. OpenAPI remains the consumer contract, while legacy response normalization supplies the approved defaults for stored scenes that predate the new fields.

**Tech Stack:** OpenAPI 3.1, React 19, TypeScript 7, TanStack Query v5, TanStack Router, shadcn/ui primitives, native HTML drag events with explicit move-button alternatives, Vitest, Testing Library, MSW, Playwright, pnpm via mise.

## Global Constraints

- Approved design: `docs/superpowers/specs/2026-07-20-scene-outline-timeline-design.md`.
- Prerequisite design and plan: `docs/superpowers/specs/2026-07-16-manuscript-scene-add-design.md` and `docs/superpowers/plans/2026-07-16-manuscript-scene-add.md` must already be integrated; stop and report the unmet prerequisite rather than duplicating it.
- Branch/worktree execution uses `feature/장면-구성-타임라인` when a new feature worktree is created.
- Scene outline status values are exactly `planned`, `drafting`, and `draft_complete`; user-facing labels are exactly `계획`, `집필 중`, and `초고 완료`.
- New scenes have `outline: ""` and `draftStatus: "planned"`; existing non-empty scenes without the fields normalize once to `drafting`, and existing empty scenes normalize once to `planned`.
- After normalization, manuscript content changes never change `draftStatus` automatically.
- Scene array order is authoritative and `chapterNumber` is recalculated to contiguous values starting at 1 after insert, move, or removal.
- The last remaining scene cannot be removed; removing the active scene selects the following scene or, when none follows, the preceding scene.
- Keep `saveManuscript` as the only write operation. Do not add a scene-specific API operation, dependency, AI behavior, hierarchy, template, version history, or export feature.
- `docs/api/openapi.yaml` is edited only by the project OpenAPI agent and requires an exact Main-approved baseline before frontend implementation.
- At plan authoring time the backend exposes only Health and Story Bible routers. This plan does not invent missing Projects or Manuscripts backend operations; if a Manuscript backend boundary exists when execution starts, Main must explicitly re-scope its affected files and backend review.
- Frontend production pages must not exceed the frozen page-boundary exception. New interaction state belongs in the focused feature components.
- Preserve unrelated working-tree changes, especially existing Story Bible backend edits.

---

## File Map

- `docs/api/openapi.yaml`: authoritative `Scene` outline/status shape and affected operation examples.
- `docs/domains/manuscript.md`: authoritative outline, ordering, status, deletion, compatibility, and responsibility rules.
- `frontend/src/modules/manuscript/domain/manuscript.ts`: `SceneDraftStatus`, outline fields, insertion, outline update, movement, removal, and renumbering.
- `frontend/src/modules/manuscript/domain/manuscript.test.ts`: aggregate invariants and immutable transition tests.
- `frontend/src/app/infrastructure/api/contracts.ts`: approved consumer types.
- `frontend/src/app/infrastructure/api/projects-api.ts`: legacy-compatible response normalization at the transport boundary.
- `frontend/src/app/infrastructure/api/projects-api.test.ts`: adapter normalization and new-field preservation tests.
- `frontend/src/mocks/data/project-workspaces.ts`: canonical mock scenes with outline metadata.
- `frontend/src/mocks/handlers/projects.ts`: strict request validation and canonical create/save/compare behavior.
- `frontend/src/mocks/project-handlers.test.ts`: contract-aligned success, malformed, domain-invalid, and round-trip tests.
- `frontend/src/features/organize-scenes/index.ts`: public feature surface.
- `frontend/src/features/organize-scenes/ui/workspace-view-switch.tsx`: accessible `구성 / 집필` view control.
- `frontend/src/features/organize-scenes/ui/scene-outline-workspace.tsx`: ordered timeline, add/open/edit/move/delete orchestration, drag state, and announcements.
- `frontend/src/features/organize-scenes/ui/scene-outline-editor-sheet.tsx`: live-autosaved title, outline, and status controls.
- `frontend/src/features/organize-scenes/ui/scene-delete-dialog.tsx`: destructive confirmation and last-scene protection copy.
- `frontend/src/features/organize-scenes/ui/scene-outline-workspace.test.tsx`: isolated feature interactions and accessibility tests.
- `frontend/src/pages/writing-workspace/writing-workspace-tabs.ts`: validated workspace view/panel/search types and parsers.
- `frontend/src/routes/projects.$projectId.write.tsx`: route search validation.
- `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`: thin feature composition and URL navigation callbacks.
- `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`: route restoration, Back/Forward, autosave, and complete screen acceptance tests.
- `frontend/src/features/manuscript-autosave/manuscript-structure-conflict.ts`: pure detection of outline-structure changes in addition to prerequisite addition merging.
- `frontend/src/features/manuscript-autosave/manuscript-structure-conflict.test.ts`: outline-change detection tests.
- `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`: expose acknowledged manuscript and structural conflict surface.
- `frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`: fetch and resolve outline conflicts without automatic merge.
- `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`: conflict integration tests.
- `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.tsx`: dedicated outline-conflict explanation and actions.
- `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx`: outline conflict accessibility and retry tests.
- `frontend/test-plans/scene-outline-timeline-e2e.md`: generated E2E plan after frontend review clears.
- `frontend/scene-outline-timeline.spec.ts`: generated Playwright coverage.

---

### Task 1: Approve the changed OpenAPI baseline

**Files:**
- Modify only through OpenAPI agent: `docs/api/openapi.yaml`

**Interfaces:**
- Produces: `SceneDraftStatus` schema with `planned | drafting | draft_complete`.
- Produces: `Scene.outline: string` and `Scene.draftStatus: SceneDraftStatus` as required fields.
- Affects: `createProjectWorkspace`, `getProjectWorkspace`, `saveManuscript`, and `compareManuscriptScene` because their requests or responses embed `Scene`.
- Preserves: all paths, methods, operation IDs, existing status codes, revision semantics, and error codes.

- [ ] **Step 1: Verify the prerequisite and record the starting API revision**

From the repository root:

```sh
git log -1 --format=%H -- docs/api/openapi.yaml
rg -n 'addScene|selectScene' frontend/src/modules/manuscript/domain/manuscript.ts
```

Expected: the first command prints one commit hash, and the second finds both prerequisite operations. If either operation is absent, stop this ticket as blocked by the approved prerequisite rather than copying its work into this ticket.

- [ ] **Step 2: Assign the exact contract change to the OpenAPI agent**

Give the OpenAPI agent sole ownership of `docs/api/openapi.yaml`, the four operation IDs above, the approved design, and these exact schema requirements:

```yaml
SceneDraftStatus:
  type: string
  enum: [planned, drafting, draft_complete]
  description: 사용자가 명시적으로 관리하는 장면 초고 진행 상태

Scene:
  type: object
  additionalProperties: false
  required:
    - id
    - title
    - chapterNumber
    - outline
    - draftStatus
    - content
    - relatedCharacterIds
    - relatedWorldEntryIds
  properties:
    outline:
      type: string
      description: 비어 있을 수 있는 한 줄 장면 계획
    draftStatus:
      $ref: "#/components/schemas/SceneDraftStatus"
```

Require every affected request/response example to include `outline` and `draftStatus`. Change `chapterNumber.minimum` to `1`, document contiguous array-order numbering in `saveManuscript`, and add an `INVALID_MANUSCRIPT` example for non-contiguous numbering. Do not add a migration endpoint or make response fields optional.

- [ ] **Step 3: Review and lint the proposed contract**

From `frontend/`:

```sh
mise exec -- pnpm api:lint
```

Expected: `Woohoo! Your API description is valid.` or the Redocly version-equivalent success message, with exit code 0.

Main compares the diff against the approved design and rejects any new operation, AI field, outline length limit, automatic status transition, hierarchy, or changed revision/error behavior.

- [ ] **Step 4: Approve and record the exact implementation baseline**

```sh
git diff --check -- docs/api/openapi.yaml
git hash-object docs/api/openapi.yaml
```

Expected: no whitespace errors and one proposed blob hash. Main records that proposed blob hash as the exact content approved for commit.

- [ ] **Step 5: Commit the contract slice**

```sh
git add docs/api/openapi.yaml
git commit -m "docs(api): add scene outline metadata"
git rev-parse HEAD
git rev-parse HEAD:docs/api/openapi.yaml
```

Expected: the commit contains only the approved OpenAPI change, and the committed blob hash exactly equals the proposed blob hash Main approved in Step 4. Supply the printed commit and blob hashes to every implementer and reviewer.

---

### Task 2: Extend the Manuscript aggregate and domain contract

**Files:**
- Modify: `docs/domains/manuscript.md`
- Modify: `frontend/src/modules/manuscript/domain/manuscript.ts`
- Modify: `frontend/src/modules/manuscript/domain/manuscript.test.ts`

**Interfaces:**
- Consumes: prerequisite `addScene(manuscript, sceneId)` and `selectScene(manuscript, sceneId)`.
- Produces: `SceneDraftStatus`, extended `Scene`, and optional `afterSceneId` on `addScene`.
- Produces: `updateSceneOutline(manuscript, sceneId, values): Manuscript`.
- Produces: `moveScene(manuscript, sceneId, targetIndex): Manuscript`.
- Produces: `removeScene(manuscript, sceneId): Manuscript`.

- [ ] **Step 1: Write failing aggregate tests**

Add tests covering exact defaults, insertion after the active scene, manual outline/status changes, movement, deletion, renumbering, failures, and immutability:

```ts
test("inserts a planned scene after the selected scene and renumbers all scenes", async () => {
  const { addScene, createInitialManuscript } = await import("./manuscript");
  const one = createInitialManuscript("project-1");
  const two = addScene(one, "scene-2");
  const inserted = addScene(two, "scene-between", one.activeSceneId);

  expect(inserted.scenes.map(({ id, chapterNumber }) => ({ id, chapterNumber }))).toEqual([
    { id: "project-1-scene-1", chapterNumber: 1 },
    { id: "scene-between", chapterNumber: 2 },
    { id: "scene-2", chapterNumber: 3 },
  ]);
  expect(inserted.scenes[1]).toMatchObject({ outline: "", draftStatus: "planned" });
  expect(inserted.activeSceneId).toBe("scene-between");
});

test("updates only explicit scene outline values", async () => {
  const { createInitialManuscript, updateSceneOutline } = await import("./manuscript");
  const manuscript = createInitialManuscript("project-1");
  const updated = updateSceneOutline(manuscript, manuscript.activeSceneId, {
    title: "남겨진 편지",
    outline: "두 사람이 과거의 오해를 확인한다.",
    draftStatus: "draft_complete",
  });

  expect(updated.scenes[0]).toMatchObject({
    title: "남겨진 편지",
    outline: "두 사람이 과거의 오해를 확인한다.",
    draftStatus: "draft_complete",
    content: manuscript.scenes[0]?.content,
  });
  expect(manuscript.scenes[0]?.title).not.toBe("남겨진 편지");
});

test("moves a scene immutably and recalculates contiguous numbers", async () => {
  const { addScene, createInitialManuscript, moveScene } = await import("./manuscript");
  const manuscript = addScene(createInitialManuscript("project-1"), "scene-2");
  const moved = moveScene(manuscript, "scene-2", 0);
  expect(moved.scenes.map(({ id, chapterNumber }) => [id, chapterNumber])).toEqual([
    ["scene-2", 1],
    ["project-1-scene-1", 2],
  ]);
  expect(manuscript.scenes[0]?.id).toBe("project-1-scene-1");
});

test("selects the following scene when the active middle scene is removed", async () => {
  const { addScene, createInitialManuscript, removeScene } = await import("./manuscript");
  const first = createInitialManuscript("project-1");
  const second = addScene(first, "scene-2");
  const third = addScene(second, "scene-3");
  const activeMiddle = { ...third, activeSceneId: "scene-2" };
  const removed = removeScene(activeMiddle, "scene-2");
  expect(removed.activeSceneId).toBe("scene-3");
  expect(removed.scenes.map(({ chapterNumber }) => chapterNumber)).toEqual([1, 2]);
});

test("rejects removing the last scene", async () => {
  const { createInitialManuscript, removeScene } = await import("./manuscript");
  const manuscript = createInitialManuscript("project-1");
  expect(() => removeScene(manuscript, manuscript.activeSceneId)).toThrow(
    "마지막 원고 장면은 삭제할 수 없습니다.",
  );
});
```

Add table-driven failures for a missing `sceneId`, missing `afterSceneId`, non-integer or out-of-range `targetIndex`, and an unsupported status passed through an `unknown` boundary test helper. Preserve all prerequisite scene-add/select tests, updating their exact scene object expectations with the two required fields.

- [ ] **Step 2: Run the focused tests and observe the expected failure**

From `frontend/`:

```sh
mise exec -- pnpm test -- src/modules/manuscript/domain/manuscript.test.ts
```

Expected: FAIL because the new fields and operations do not exist and prerequisite exact object expectations lack the new fields.

- [ ] **Step 3: Implement the minimal immutable domain operations**

Use these public types and signatures:

```ts
export const sceneDraftStatuses = ["planned", "drafting", "draft_complete"] as const;
export type SceneDraftStatus = (typeof sceneDraftStatuses)[number];

export interface Scene {
  id: string;
  title: string;
  chapterNumber: number;
  outline: string;
  draftStatus: SceneDraftStatus;
  content: string;
  relatedCharacterIds: string[];
  relatedWorldEntryIds: string[];
}

export interface SceneOutlineValues {
  title: string;
  outline: string;
  draftStatus: SceneDraftStatus;
}
```

Implement one renumber helper and reuse it in insertion, movement, and removal:

```ts
function renumberScenes(scenes: Scene[]): Scene[] {
  return scenes.map((scene, index) =>
    scene.chapterNumber === index + 1 ? scene : { ...scene, chapterNumber: index + 1 },
  );
}

export function updateSceneOutline(
  manuscript: Manuscript,
  sceneId: string,
  values: SceneOutlineValues,
): Manuscript {
  if (!sceneDraftStatuses.includes(values.draftStatus)) {
    throw new Error("지원하지 않는 장면 초고 상태입니다.");
  }
  if (!manuscript.scenes.some(({ id }) => id === sceneId)) {
    throw new Error("원고 장면을 찾을 수 없습니다.");
  }
  return {
    ...manuscript,
    scenes: manuscript.scenes.map((scene) =>
      scene.id === sceneId ? { ...scene, ...values } : scene,
    ),
  };
}

export function moveScene(
  manuscript: Manuscript,
  sceneId: string,
  targetIndex: number,
): Manuscript {
  const sourceIndex = manuscript.scenes.findIndex(({ id }) => id === sceneId);
  if (sourceIndex < 0) throw new Error("원고 장면을 찾을 수 없습니다.");
  if (!Number.isInteger(targetIndex) || targetIndex < 0 || targetIndex >= manuscript.scenes.length) {
    throw new Error("장면 이동 위치가 올바르지 않습니다.");
  }
  if (sourceIndex === targetIndex) return manuscript;
  const scenes = [...manuscript.scenes];
  const [scene] = scenes.splice(sourceIndex, 1);
  scenes.splice(targetIndex, 0, scene!);
  return { ...manuscript, scenes: renumberScenes(scenes) };
}

export function removeScene(manuscript: Manuscript, sceneId: string): Manuscript {
  const removedIndex = manuscript.scenes.findIndex(({ id }) => id === sceneId);
  if (removedIndex < 0) throw new Error("원고 장면을 찾을 수 없습니다.");
  if (manuscript.scenes.length === 1) throw new Error("마지막 원고 장면은 삭제할 수 없습니다.");
  const scenes = renumberScenes(manuscript.scenes.filter(({ id }) => id !== sceneId));
  const activeSceneId =
    manuscript.activeSceneId === sceneId
      ? scenes[Math.min(removedIndex, scenes.length - 1)]!.id
      : manuscript.activeSceneId;
  return { ...manuscript, scenes, activeSceneId };
}
```

Extend prerequisite `addScene` with `afterSceneId = manuscript.scenes.at(-1)!.id`, insert after that ID, create the two exact defaults, renumber, and activate the new scene. `createInitialManuscript` sets `outline: ""` and `draftStatus: "drafting"` because its opening content is non-empty.

- [ ] **Step 4: Synchronize the Manuscript domain contract**

Update `docs/domains/manuscript.md` in the same change. Add scene outline and draft status to ubiquitous language and the core model; add manual-only status, array-order/contiguous-number, last-scene, identity preservation, immutable reorder/removal, and active-scene fallback invariants; add outline editing, scene reordering, and scene removal use cases. Keep Story Bible references and Manuscript-only text ownership unchanged.

- [ ] **Step 5: Run focused verification**

```sh
mise exec -- pnpm test -- src/modules/manuscript/domain/manuscript.test.ts
mise exec -- pnpm typecheck
```

Expected: both commands PASS.

- [ ] **Step 6: Commit the aggregate slice**

```sh
git add docs/domains/manuscript.md frontend/src/modules/manuscript/domain/manuscript.ts frontend/src/modules/manuscript/domain/manuscript.test.ts
git commit -m "feat: model manuscript scene outlines"
```

Expected: the domain implementation and authoritative contract are committed together.

---

### Task 3: Align API consumers, compatibility normalization, and MSW

**Files:**
- Modify: `frontend/src/app/infrastructure/api/contracts.ts`
- Modify: `frontend/src/app/infrastructure/api/projects-api.ts`
- Modify: `frontend/src/app/infrastructure/api/projects-api.test.ts`
- Modify: `frontend/src/mocks/data/project-workspaces.ts`
- Modify: `frontend/src/mocks/handlers/projects.ts`
- Modify: `frontend/src/mocks/project-handlers.test.ts`
- Modify as compilation requires: existing frontend test fixtures returned by `rg -l 'chapterNumber:' frontend/src`

**Interfaces:**
- Consumes: Main-approved OpenAPI blob from Task 1 and `SceneDraftStatus` from Task 2.
- Produces: required `ApiScene.outline` and `ApiScene.draftStatus`.
- Produces internally: `normalizeManuscript()` for response compatibility only.
- Preserves: strict request rejection of missing/extra/invalid new fields.

- [ ] **Step 1: Write failing adapter compatibility tests**

Override each response boundary with a legacy scene that omits both fields and assert exact normalization:

```ts
it("normalizes missing outline fields once when loading a legacy workspace", async () => {
  server.use(
    http.get("/api/projects/:projectId/workspace", () => {
      const workspace = findMockWorkspace("silver-garden")!;
      const legacyScene = { ...workspace.manuscript.scenes[0] } as Record<string, unknown>;
      delete legacyScene.outline;
      delete legacyScene.draftStatus;
      return HttpResponse.json({
        ...workspace,
        manuscript: { ...workspace.manuscript, scenes: [legacyScene] },
      });
    }),
  );

  const workspace = await getProjectWorkspace("silver-garden");
  expect(workspace.manuscript.scenes[0]).toMatchObject({
    outline: "",
    draftStatus: "drafting",
  });
});
```

Add an empty-content variant expecting `planned`, a save-response variant proving provided values survive unchanged, and a compare-response variant proving `serverManuscript` is normalized.

- [ ] **Step 2: Write failing MSW contract tests**

Add tests that new project creation returns `{ outline: "", draftStatus: "planned" }`, a valid save round-trips changed outline/status/order, missing or invalid `draftStatus` returns `400 MALFORMED_REQUEST`, and non-contiguous `chapterNumber` returns `422 INVALID_MANUSCRIPT` without incrementing revision.

```ts
expect(created.manuscript.scenes[0]).toMatchObject({
  outline: "",
  draftStatus: "planned",
});

changedManuscript.scenes[0] = {
  ...changedManuscript.scenes[0],
  outline: "두 사람이 편지의 발신자를 확인한다.",
  draftStatus: "draft_complete",
};
```

- [ ] **Step 3: Run focused tests and observe contract failures**

```sh
mise exec -- pnpm test -- src/app/infrastructure/api/projects-api.test.ts src/mocks/project-handlers.test.ts
```

Expected: FAIL because `ApiScene`, mock data, strict handlers, and adapters do not yet support the fields.

- [ ] **Step 4: Add the approved consumer types and response-only normalization**

Update `ApiScene` to use the domain status type:

```ts
import type { SceneDraftStatus } from "@/modules/manuscript";

export interface ApiScene {
  id: string;
  title: string;
  chapterNumber: number;
  outline: string;
  draftStatus: SceneDraftStatus;
  content: string;
  relatedCharacterIds: string[];
  relatedWorldEntryIds: string[];
}
```

Keep legacy compatibility local to `projects-api.ts`; never make the public fields optional:

```ts
type CompatibleScene = Omit<ApiScene, "outline" | "draftStatus"> &
  Partial<Pick<ApiScene, "outline" | "draftStatus">>;
type CompatibleManuscript = Omit<ApiManuscript, "scenes"> & { scenes: CompatibleScene[] };

function normalizeManuscript(manuscript: CompatibleManuscript): ApiManuscript {
  return {
    ...manuscript,
    scenes: manuscript.scenes.map((scene) => ({
      ...scene,
      outline: scene.outline ?? "",
      draftStatus: scene.draftStatus ?? (scene.content.length === 0 ? "planned" : "drafting"),
    })),
  };
}
```

Request `CompatibleManuscript` transport shapes for create/get/save/compare responses, then return the public response with `normalizeManuscript()` applied to every embedded manuscript. Do not normalize outgoing save requests or invalid provided values.

- [ ] **Step 5: Make mock data and handlers enforce the approved baseline**

Add canonical fields to both seeded and newly built scenes. Extend `isApiManuscript()` exact keys with `outline` and `draftStatus`, require `outline` to be a string, and validate status using the public domain guard or `sceneDraftStatuses.includes()`.

After transport parsing, reject domain-invalid structure before replacement:

```ts
if (parsedRequest.manuscript.scenes.length === 0) {
  return HttpResponse.json(
    invalidManuscript("manuscript.scenes", "원고 장면이 한 개 이상 필요합니다."),
    { status: 422 },
  );
}

if (
  parsedRequest.manuscript.scenes.some(
    ({ chapterNumber }, index) => chapterNumber !== index + 1,
  )
) {
  return HttpResponse.json(
    invalidManuscript(
      "manuscript.scenes",
      "장면 번호는 이야기 순서대로 1부터 이어져야 합니다.",
    ),
    { status: 422 },
  );
}
```

Retain exact additional-property rejection and all existing identifier, revision, and atomic replacement behavior.

- [ ] **Step 6: Run focused and type verification**

```sh
mise exec -- pnpm test -- src/app/infrastructure/api/projects-api.test.ts src/mocks/project-handlers.test.ts
mise exec -- pnpm typecheck
```

Expected: all commands PASS, including legacy response and strict request tests.

- [ ] **Step 7: Commit the consumer-contract slice**

```sh
git add frontend/src/app/infrastructure/api frontend/src/mocks
git commit -m "feat(frontend): persist scene outline metadata"
```

Expected: API consumer types, normalizers, handlers, data, and tests use the same approved OpenAPI baseline.

---

### Task 4: Build the isolated scene-outline feature UI

**Files:**
- Create: `frontend/src/features/organize-scenes/index.ts`
- Create: `frontend/src/features/organize-scenes/ui/workspace-view-switch.tsx`
- Create: `frontend/src/features/organize-scenes/ui/scene-outline-workspace.tsx`
- Create: `frontend/src/features/organize-scenes/ui/scene-outline-editor-sheet.tsx`
- Create: `frontend/src/features/organize-scenes/ui/scene-delete-dialog.tsx`
- Create: `frontend/src/features/organize-scenes/ui/scene-outline-workspace.test.tsx`

**Interfaces:**
- Consumes: `Manuscript`, `ManuscriptAutosaveStatus`, `addScene`, `selectScene`, `updateSceneOutline`, `moveScene`, and `removeScene`.
- Produces: `WorkspaceViewSwitch` and `SceneOutlineWorkspace` through the feature index.
- `SceneOutlineWorkspace` receives URL-owned `editorSceneId`/`deleteSceneId` and navigation callbacks; it owns only transient drag and announcement state.

- [ ] **Step 1: Write failing feature interaction tests**

Use a harness whose `updateDraft` applies functional updates. Cover ordered cards, exact status labels, add-after-active, live sheet editing, open-for-writing, move buttons, native drag/drop, delete fallback, last-scene protection, conflict disabling, and polite announcements.

```tsx
function buildManuscript(sceneCount: number): Manuscript {
  let manuscript = createInitialManuscript("silver-garden");
  for (let number = 2; number <= sceneCount; number += 1) {
    const sceneId = `scene-${number}`;
    manuscript = addScene(manuscript, sceneId);
    manuscript = updateSceneOutline(manuscript, sceneId, {
      title: `장면 ${number}`,
      outline: `${number}번째 장면 계획`,
      draftStatus: "planned",
    });
  }
  return manuscript;
}

function OutlineHarness({
  sceneCount = 1,
  initialEditorSceneId,
  initialDeleteSceneId,
  onOpenWriting = vi.fn(),
}: {
  sceneCount?: number;
  initialEditorSceneId?: string;
  initialDeleteSceneId?: string;
  onOpenWriting?: (sceneId: string) => void;
}) {
  const [manuscript, setManuscript] = useState(() => buildManuscript(sceneCount));
  const [editorSceneId, setEditorSceneId] = useState(initialEditorSceneId);
  const [deleteSceneId, setDeleteSceneId] = useState(initialDeleteSceneId);
  return (
    <SceneOutlineWorkspace
      manuscript={manuscript}
      autosaveStatus="saved"
      editorSceneId={editorSceneId}
      deleteSceneId={deleteSceneId}
      updateDraft={(update) =>
        setManuscript((current) => (typeof update === "function" ? update(current) : update))
      }
      onOpenEditor={setEditorSceneId}
      onOpenDelete={setDeleteSceneId}
      onClosePanel={() => {
        setEditorSceneId(undefined);
        setDeleteSceneId(undefined);
      }}
      onOpenWriting={onOpenWriting}
    />
  );
}

test("edits outline values and opens the selected scene for writing", async () => {
  const user = userEvent.setup();
  const onOpenWriting = vi.fn();
  render(<OutlineHarness onOpenWriting={onOpenWriting} />);

  await user.click(screen.getByRole("button", { name: "1장 비가 그친 뒤의 정원 메뉴" }));
  await user.click(screen.getByRole("menuitem", { name: "편집" }));
  expect(screen.getByRole("dialog", { name: "장면 정보 편집" })).toBeInTheDocument();
  await user.type(screen.getByRole("textbox", { name: "한 줄 장면 계획" }), "재회의 목적");
  await user.selectOptions(screen.getByRole("combobox", { name: "초고 상태" }), "draft_complete");
  expect(screen.getByText("재회의 목적")).toBeInTheDocument();
  expect(screen.getByText("초고 완료")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "1장 비가 그친 뒤의 정원 집필" }));
  expect(onOpenWriting).toHaveBeenCalledWith("silver-garden-scene-1");
});

test("moves a card with explicit keyboard-accessible actions", async () => {
  const user = userEvent.setup();
  render(<OutlineHarness sceneCount={3} />);
  await user.click(screen.getByRole("button", { name: "3장 장면 3 메뉴" }));
  await user.click(screen.getByRole("menuitem", { name: "위로 이동" }));
  expect(screen.getAllByRole("article").map((card) => card.getAttribute("aria-label"))).toEqual([
    "1장 비가 그친 뒤의 정원",
    "2장 장면 3",
    "3장 장면 2",
  ]);
  expect(screen.getByRole("status")).toHaveTextContent("장면을 2번째 순서로 이동했어요.");
});

test("confirms deletion and protects the final scene", async () => {
  const user = userEvent.setup();
  render(<OutlineHarness sceneCount={2} initialDeleteSceneId="scene-2" />);
  expect(screen.getByRole("dialog", { name: "장면을 삭제할까요?" })).toHaveTextContent(
    "원고 본문도 함께 삭제돼요",
  );
  await user.click(screen.getByRole("button", { name: "장면 삭제" }));
  expect(screen.getAllByRole("article")).toHaveLength(1);
  await user.click(screen.getByRole("button", { name: "1장 비가 그친 뒤의 정원 메뉴" }));
  expect(screen.getByRole("menuitem", { name: "삭제" })).toHaveAttribute("data-disabled");
});
```

- [ ] **Step 2: Run the isolated test and observe the missing-feature failure**

```sh
mise exec -- pnpm test -- src/features/organize-scenes/ui/scene-outline-workspace.test.tsx
```

Expected: FAIL because the feature files do not exist.

- [ ] **Step 3: Implement the typed feature surface**

Use this public prop contract:

```ts
export interface SceneOutlineWorkspaceProps {
  manuscript: Manuscript;
  autosaveStatus: ManuscriptAutosaveStatus;
  editorSceneId?: string;
  deleteSceneId?: string;
  updateDraft: (update: Manuscript | ((current: Manuscript) => Manuscript)) => void;
  onOpenEditor: (sceneId: string) => void;
  onOpenDelete: (sceneId: string) => void;
  onClosePanel: () => void;
  onOpenWriting: (sceneId: string) => void;
}
```

`WorkspaceViewSwitch` renders two buttons with `aria-pressed`, exact labels `구성` and `집필`, and callbacks supplied by the page. It contains no router import.

In `SceneOutlineWorkspace`, use the existing UI primitives and a single-column ordered list. Each card is an `article` labelled with current number and title. Disable add/edit/move/delete while `autosaveStatus === "conflict"`, but keep opening an existing scene available.

Core handlers use only domain operations:

```ts
const handleAdd = () => {
  const sceneId = `${manuscript.id}-scene-${crypto.randomUUID()}`;
  updateDraft((current) => addScene(current, sceneId, current.activeSceneId));
  setAnnouncement("새 장면을 현재 장면 다음에 추가했어요.");
};

const handleOpenWriting = (sceneId: string) => {
  updateDraft((current) => selectScene(current, sceneId));
  onOpenWriting(sceneId);
};

const handleMove = (sceneId: string, targetIndex: number) => {
  updateDraft((current) => moveScene(current, sceneId, targetIndex));
  setAnnouncement(`장면을 ${targetIndex + 1}번째 순서로 이동했어요.`);
};
```

Native drag/drop calls the same `handleMove`; do not add a drag library. Each card's existing-style dropdown menu contains keyboard-accessible `편집`, `위로 이동`, `아래로 이동`, and `삭제` menu items. These are real user controls rather than hidden test-only controls.

- [ ] **Step 4: Implement live outline editing and deletion presentation**

`SceneOutlineEditorSheet` receives one `Scene`, `disabled`, `onChange(values)`, and `onClose`. It binds title and outline inputs plus a native labelled status select. Every change emits a complete value, so it updates the Manuscript draft immediately and uses the existing debounced autosave; it has no second unsaved form state or Save button.

```tsx
<select
  id="scene-draft-status"
  aria-label="초고 상태"
  value={scene.draftStatus}
  disabled={disabled}
  onChange={(event) =>
    onChange({
      title: scene.title,
      outline: scene.outline,
      draftStatus: event.currentTarget.value as SceneDraftStatus,
    })
  }
>
  <option value="planned">계획</option>
  <option value="drafting">집필 중</option>
  <option value="draft_complete">초고 완료</option>
</select>
```

The cast is confined to the feature input whose options are the authoritative finite set; add a focused test for every option.

`SceneDeleteDialog` names the scene, says `원고 본문도 함께 삭제돼요. 이 작업은 되돌릴 수 없어요.`, offers `취소` and destructive `장면 삭제`, and disables confirmation for the last scene. Confirmation calls `removeScene`, closes the URL-owned panel, and announces the replacement active scene when the active card was deleted.

- [ ] **Step 5: Export only the page-facing components**

```ts
export { SceneOutlineWorkspace, type SceneOutlineWorkspaceProps } from "./ui/scene-outline-workspace";
export { WorkspaceViewSwitch } from "./ui/workspace-view-switch";
```

Keep editor and delete presentation private to the feature.

- [ ] **Step 6: Run focused feature checks**

```sh
mise exec -- pnpm test -- src/features/organize-scenes/ui/scene-outline-workspace.test.tsx
mise exec -- pnpm typecheck
```

Expected: PASS with no new dependency and no page-boundary change.

- [ ] **Step 7: Commit the isolated feature**

```sh
git add frontend/src/features/organize-scenes
git commit -m "feat(frontend): add scene outline timeline"
```

---

### Task 5: Integrate URL-owned outline state into the writing workspace

**Files:**
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-tabs.ts`
- Modify: `frontend/src/routes/projects.$projectId.write.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`
- Verify only: `frontend/src/architecture/page-boundaries.test.ts`

**Interfaces:**
- Produces search: `workspace?: "outline"`, `panel?: "world-editor" | "scene-editor" | "scene-delete"`, and `sceneId?: string`.
- Canonical default writing view omits `workspace`.
- `panel=scene-editor|scene-delete` requires `workspace=outline` and a current Manuscript scene ID.
- Consumes `WorkspaceViewSwitch` and `SceneOutlineWorkspace` from Task 4.

- [ ] **Step 1: Write failing route and screen tests**

Add direct-link, canonicalization, history, and integrated autosave tests:

```tsx
test("restores the outline from a direct URL and returns to writing through history", async () => {
  const user = userEvent.setup();
  const { router } = renderWorkspace("/projects/silver-garden/write?workspace=outline");
  expect(await screen.findByRole("heading", { name: "장면 구성" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "구성", pressed: true })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "집필" }));
  await waitFor(() => expect(router.state.location.search).toEqual({}));
  router.history.back();
  expect(await screen.findByRole("heading", { name: "장면 구성" })).toBeInTheDocument();
});

test("deep-links an editor and canonicalizes an invalid scene target", async () => {
  const valid = renderWorkspace(
    "/projects/silver-garden/write?workspace=outline&panel=scene-editor&sceneId=silver-garden-scene-1",
  );
  expect(await screen.findByRole("dialog", { name: "장면 정보 편집" })).toBeInTheDocument();
  valid.unmount();

  const invalid = renderWorkspace(
    "/projects/silver-garden/write?workspace=outline&panel=scene-delete&sceneId=missing",
  );
  await waitFor(() =>
    expect(invalid.router.state.location.search).toEqual({ workspace: "outline" }),
  );
});

test("autosaves a reordered and edited outline then restores it from the workspace response", async () => {
  const saveRequests: SaveManuscriptRequest[] = [];
  vi.stubGlobal("crypto", { randomUUID: () => "outline-2" });
  server.use(
    http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
      const body = (await request.json()) as SaveManuscriptRequest;
      saveRequests.push(body);
      return HttpResponse.json({
        manuscript: body.manuscript,
        manuscriptRevision: body.expectedRevision + 1,
        projectActivity: { projectId: "silver-garden", updatedAt: "2026-07-20T00:00:00.000Z" },
      });
    }),
  );
  const user = userEvent.setup();
  const firstRender = renderWorkspace("/projects/silver-garden/write?workspace=outline");
  await user.click(await screen.findByRole("button", { name: "새 장면 추가" }));
  await user.click(screen.getByRole("button", { name: "2장 제목 없는 장면 메뉴" }));
  await user.click(screen.getByRole("menuitem", { name: "편집" }));
  await user.type(
    screen.getByRole("textbox", { name: "한 줄 장면 계획" }),
    "첫 번째 갈등을 드러낸다.",
  );
  await user.selectOptions(screen.getByRole("combobox", { name: "초고 상태" }), "drafting");
  await user.click(screen.getByRole("button", { name: "장면 정보 편집 닫기" }));
  await user.click(screen.getByRole("button", { name: "2장 제목 없는 장면 메뉴" }));
  await user.click(screen.getByRole("menuitem", { name: "위로 이동" }));
  await waitFor(() =>
    expect(saveRequests.at(-1)?.manuscript.scenes[0]).toMatchObject({
      chapterNumber: 1,
      outline: "첫 번째 갈등을 드러낸다.",
      draftStatus: "drafting",
    }),
  );
  const savedManuscript = structuredClone(saveRequests.at(-1)!.manuscript);
  firstRender.unmount();
  server.use(
    http.get("/api/projects/:projectId/workspace", () => {
      const workspace = getWorkspace();
      return HttpResponse.json({ ...workspace, manuscript: savedManuscript, manuscriptRevision: 2 });
    }),
  );
  renderWorkspace("/projects/silver-garden/write?workspace=outline");
  expect(await screen.findByText("첫 번째 갈등을 드러낸다.")).toBeInTheDocument();
});
```

Also test unknown workspace/panel values are removed while unrelated `view=dense` is preserved, opening/closing the editor and delete dialog pushes history, selecting a card activates it before writing, and mobile outline remains one column.

- [ ] **Step 2: Run the screen test and observe missing search/UI failures**

```sh
mise exec -- pnpm test -- src/pages/writing-workspace/writing-workspace-page.test.tsx
```

Expected: FAIL because route search and feature composition are absent.

- [ ] **Step 3: Add authoritative search parsers**

Extend `writing-workspace-tabs.ts` without reusing the unrelated `view` parameter already preserved by tests:

```ts
export type WorkspaceView = "outline";
export type WorkspacePanel = "world-editor" | "scene-editor" | "scene-delete";

export function parseWorkspaceView(value: unknown): WorkspaceView | undefined {
  return value === "outline" ? value : undefined;
}

export function parseWorkspacePanel(value: unknown): WorkspacePanel | undefined {
  return value === "world-editor" || value === "scene-editor" || value === "scene-delete"
    ? value
    : undefined;
}

export function parseSceneId(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}
```

Update the route validator to parse `workspace`, `panel`, and `sceneId`, using `null` only as the existing canonicalization signal for invalid present values. Keep spreading unrelated search values so current URL behavior is preserved.

- [ ] **Step 4: Compose the feature without increasing the page exception**

Derive `workspaceView` and route-owned panel targets from `useSearch`. Add user navigation callbacks that push history. Canonicalization effects may remove invalid search state after workspace data loads, but do not add `useState`, `useReducer`, `useRef`, infrastructure imports, or assertions to the page.

Render `WorkspaceViewSwitch` in the header. When `workspace === "outline"`, replace the contextual rail/editor body with:

```tsx
<SceneOutlineWorkspace
  manuscript={draft}
  autosaveStatus={status}
  editorSceneId={panel === "scene-editor" ? search.sceneId : undefined}
  deleteSceneId={panel === "scene-delete" ? search.sceneId : undefined}
  updateDraft={updateDraft}
  onOpenEditor={(sceneId) => openScenePanel("scene-editor", sceneId)}
  onOpenDelete={(sceneId) => openScenePanel("scene-delete", sceneId)}
  onClosePanel={closeScenePanel}
  onOpenWriting={() => showWritingView()}
/>
```

The feature selects the scene before `onOpenWriting`. The default writing composition remains unchanged. World-editor URLs still canonicalize to `tab=world`; scene panels canonicalize to `workspace=outline` and close when `sceneId` is absent or not in `draft.scenes`.

- [ ] **Step 5: Treat view switches as safe in-workspace navigation**

Extend the current tab-only navigation helper to ignore only canonical presentation changes that cannot discard local state: `tab` and `workspace`. Opening or closing a scene editor is safe because its fields write directly into the Manuscript draft; leaving the route still passes through the existing manuscript `flush()` guard when the destination exits the workspace.

Do not treat deletion confirmation as already executed: closing `panel=scene-delete` without confirmation changes no draft.

- [ ] **Step 6: Run route, page-boundary, and type checks**

```sh
mise exec -- pnpm test -- src/pages/writing-workspace/writing-workspace-page.test.tsx src/architecture/page-boundaries.test.ts
mise exec -- pnpm typecheck
```

Expected: PASS and the frozen writing-workspace page-boundary counts remain exactly unchanged.

- [ ] **Step 7: Commit the workspace integration**

```sh
git add frontend/src/pages/writing-workspace frontend/src/routes/projects.\$projectId.write.tsx
git commit -m "feat(frontend): integrate scene outline workspace"
```

---

### Task 6: Resolve outline-structure revision conflicts explicitly

**Files:**
- Modify prerequisite-created: `frontend/src/features/manuscript-autosave/manuscript-structure-conflict.ts`
- Modify prerequisite-created: `frontend/src/features/manuscript-autosave/manuscript-structure-conflict.test.ts`
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`
- Modify: `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.tsx`
- Modify: `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx`
- Modify composition only: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`

**Interfaces:**
- Consumes prerequisite `findLocalSceneAdditions`, `mergeLocalSceneAdditions`, and `conflictKind: "scene-content" | "scene-structure" | null`.
- Produces: `hasSceneOutlineChanges(base, local): boolean`.
- Extends conflict kind to `"scene-content" | "scene-structure" | "scene-outline" | null`.
- Reuses prerequisite `ManuscriptStructureConflict { serverManuscript; serverRevision }` for the fetched server snapshot.
- Preserves prerequisite automatic merge only for pure local scene additions; outline edits, reorder, and removal never auto-merge.

- [ ] **Step 1: Write failing pure detection tests**

```ts
test.each([
  ["title", (scene: Scene) => ({ ...scene, title: "새 제목" })],
  ["outline", (scene: Scene) => ({ ...scene, outline: "새 계획" })],
  ["status", (scene: Scene) => ({ ...scene, draftStatus: "draft_complete" as const })],
])("detects a %s outline change", (_name, change) => {
  const base = createInitialManuscript("project-1");
  const local = { ...base, scenes: [change(base.scenes[0]!)] };
  expect(hasSceneOutlineChanges(base, local)).toBe(true);
});

test("detects reorder and removal but ignores content-only edits and pure additions", () => {
  const base = addScene(createInitialManuscript("project-1"), "scene-2");
  expect(hasSceneOutlineChanges(base, moveScene(base, "scene-2", 0))).toBe(true);
  expect(hasSceneOutlineChanges(base, removeScene(base, "scene-2"))).toBe(true);
  expect(hasSceneOutlineChanges(base, updateSceneContent(base, base.activeSceneId, "새 본문"))).toBe(false);
  expect(hasSceneOutlineChanges(base, addScene(base, "scene-3"))).toBe(false);
});
```

- [ ] **Step 2: Write failing hook and dialog integration tests**

Use MSW so the first save returns 409, the workspace GET returns server revision 7, and resolution records the second save.

```ts
expect(result.current.conflictKind).toBe("scene-outline");
expect(result.current.structureConflict?.serverRevision).toBe(7);
await act(async () => result.current.keepLocal());
expect(saveRequests.at(-1)).toMatchObject({
  expectedRevision: 7,
  manuscript: { scenes: [{ outline: "내 구성" }] },
});
```

Assert `applyServer()` discards the local outline/reorder/removal, a repeated 409 refreshes the server snapshot, non-409 resolution failure preserves the local draft and exposes retry, and all prerequisite scene-content and pure-addition conflict tests remain unchanged.

For the dialog, assert outline mode has no diff table and exact copy/actions:

```tsx
expect(screen.getByText("장면 구성과 서버 최신 원고가 충돌했어요.")).toBeInTheDocument();
expect(screen.getByText(/서버의 최신 원고 전체를 내 구성으로 대체할 수 있어요/)).toBeInTheDocument();
expect(screen.getByRole("button", { name: "내 구성 유지" })).toBeEnabled();
expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toBeEnabled();
```

- [ ] **Step 3: Run focused conflict tests and observe failures**

```sh
mise exec -- pnpm test -- src/features/manuscript-autosave/manuscript-structure-conflict.test.ts src/features/manuscript-autosave/use-manuscript-autosave.test.tsx src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx
```

Expected: FAIL because outline detection and the third conflict mode do not exist.

- [ ] **Step 4: Implement pure outline-change detection**

Compare only base-scene membership/order and outline-owned values; ignore content, related refs, active selection, and local-only additions:

```ts
export function hasSceneOutlineChanges(base: Manuscript, local: Manuscript): boolean {
  const baseIds = base.scenes.map(({ id }) => id);
  const localBaseScenes = local.scenes.filter(({ id }) => baseIds.includes(id));
  if (localBaseScenes.length !== base.scenes.length) return true;
  if (localBaseScenes.some((scene, index) => scene.id !== base.scenes[index]?.id)) return true;

  return base.scenes.some((baseScene) => {
    const localScene = local.scenes.find(({ id }) => id === baseScene.id)!;
    return (
      localScene.title !== baseScene.title ||
      localScene.outline !== baseScene.outline ||
      localScene.draftStatus !== baseScene.draftStatus ||
      localScene.chapterNumber !== baseScene.chapterNumber
    );
  });
}
```

- [ ] **Step 5: Add the explicit outline conflict workflow**

Expose `getAcknowledgedManuscript()` from `useManuscriptAutosave` through the prerequisite conflict host. When a 409 occurs, evaluate in this order:

1. `hasSceneOutlineChanges(base, local)` → fetch `getProjectWorkspace`, set `scene-outline`, store server manuscript/revision.
2. Pure local additions → retain prerequisite `scene-structure` conservative merge.
3. Otherwise → retain `scene-content` comparison.

For `scene-outline`, `keepLocal()` saves the complete current local draft at the fetched server revision without merging. `applyServer()` adopts and caches the fetched server manuscript. A repeated 409 refetches before enabling another resolution. Disable further structure controls through the existing `status === "conflict"` prop while keeping the local draft in memory.

- [ ] **Step 6: Render the dedicated dialog mode**

Add `kind` and prerequisite structure snapshot props to `ManuscriptConflictDialog`. Keep existing content and pure-addition modes intact. Outline mode renders the approved warning, buttons `내 구성 유지` and `서버 최신본 적용`, and retry copy `내 구성 저장 다시 시도`. Resolution buttons are enabled only when the current server snapshot exists and no fetch/resolution error is active.

Pass the new kind/snapshot from the writing workspace without adding page-owned state.

- [ ] **Step 7: Run focused conflict and screen checks**

```sh
mise exec -- pnpm test -- src/features/manuscript-autosave/manuscript-structure-conflict.test.ts src/features/manuscript-autosave/use-manuscript-autosave.test.tsx src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm typecheck
```

Expected: PASS, including all prerequisite scene-content and scene-addition conflict cases.

- [ ] **Step 8: Commit outline conflict support**

```sh
git add frontend/src/features/manuscript-autosave frontend/src/features/manuscript-conflict frontend/src/pages/writing-workspace/writing-workspace-page.tsx
git commit -m "feat(frontend): resolve scene outline conflicts"
```

---

### Task 7: Review, E2E generation, and final verification

**Files:**
- Create after review: `frontend/test-plans/scene-outline-timeline-e2e.md`
- Create after plan approval: `frontend/scene-outline-timeline.spec.ts`
- Review only: all implementation and contract files in the File Map

**Interfaces:**
- Consumes: exact Main-approved OpenAPI commit/blob, approved design, completed implementation handoff, and route `/projects/$projectId/write`.
- Produces: resolved frontend review findings, approved E2E plan/test, full verification evidence, and domain/API/consumer agreement.

- [ ] **Step 1: Stop implementation editing and collect the frontend handoff**

Require the frontend implementer to report changed paths, the exact approved OpenAPI baseline, operation IDs, domain-document update, focused commands/results, and confirmation that no backend or unrelated page-boundary file changed. Implementation agents stop editing before review starts.

- [ ] **Step 2: Dispatch the required read-only frontend review first**

Give `frontend-review` the complete `/projects/$projectId/write` screen, all configuration/editor/delete/conflict states, the implementation handoff, this design and plan, `docs/domains/manuscript.md`, exact OpenAPI baseline, affected operation IDs, exclusions, and safe verification commands. The reviewer edits no files.

Require evidence-based findings with severity, introduced/pre-existing classification, source location, impact, repair direction, and re-review requirement.

- [ ] **Step 3: Triage and resolve every accepted review finding**

Main records rationale for rejected findings and returns every accepted finding to the owning frontend implementer. Re-dispatch the same reviewer for blocking/high findings or any repair that materially changes reviewed behavior. Do not start E2E planning until the application review gate clears.

- [ ] **Step 4: Dispatch the Playwright planner after review clears**

Give `.codex/agents/playwright_test_planner.toml` sole ownership of `frontend/test-plans/scene-outline-timeline-e2e.md`, the approved acceptance criteria, exact screen route, contract baseline, and final reviewed implementation. Require flows for:

- direct outline URL and Back/Forward view restoration;
- add-after-active, edit plan/status, reorder, and open-for-writing;
- keyboard move alternative and mobile single-column controls;
- deletion cancellation, confirmation, active fallback, and last-scene protection;
- autosave success, failure/retry, reload-equivalent restoration;
- outline conflict `내 구성 유지` and `서버 최신본 적용`.

The planner must not edit implementation or test files.

- [ ] **Step 5: Review the E2E plan and dispatch the generator**

Main rejects any AI, hierarchy, template, export, new endpoint, or behavior outside the approved design. After plan approval, give `.codex/agents/playwright_test_generator.toml` sole ownership of `frontend/scene-outline-timeline.spec.ts`; the generator may not modify product behavior.

- [ ] **Step 6: Run E2E verification**

From `frontend/`, start Vite in one terminal:

```sh
mise exec -- pnpm dev --host 127.0.0.1
```

Expected: Vite reports `http://127.0.0.1:5173/`.

In a second terminal:

```sh
mise exec -- pnpm exec playwright test scene-outline-timeline.spec.ts
```

Expected: PASS. Stop the Vite process afterward.

- [ ] **Step 7: Run final contract and frontend checks**

From `frontend/`:

```sh
mise exec -- pnpm api:lint
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: all three commands exit 0.

From the repository root:

```sh
git diff --check
git diff -- docs/domains/manuscript.md docs/api/openapi.yaml frontend/src/modules/manuscript/domain/manuscript.ts frontend/src/app/infrastructure/api/contracts.ts
```

Expected: no whitespace errors. Main explicitly confirms the domain document, OpenAPI `Scene`, TypeScript domain model, API consumer type, MSW validation, and reviewed UI all describe the same fields, status values, ordering, deletion, and conflict behavior.

- [ ] **Step 8: Commit E2E artifacts and reviewed repairs**

```sh
git add frontend/test-plans/scene-outline-timeline-e2e.md frontend/scene-outline-timeline.spec.ts
git commit -m "test(frontend): cover scene outline timeline"
```

Do not claim completion until every accepted finding is resolved, required re-review has passed, generated E2E tests pass, and all final commands above have been observed.
