# Manuscript Scene Title Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a writer edit the active manuscript scene title inline and preserve the normalized title through the existing whole-manuscript autosave and conflict-recovery workflow.

**Architecture:** Add one immutable title-update operation to the Manuscript domain, keep transient input mechanics in a focused Manuscript UI component, and let the writing-workspace page connect a concise commit callback to the existing autosave draft. Reuse ticket #3 scene navigation and the current `saveManuscript` operation without adding an API operation or transport field.

**Tech Stack:** React 19, TypeScript 7, TanStack Query v5, TanStack Router, shadcn/ui primitives, Vitest, Testing Library, MSW, Playwright, pnpm via mise.

## Global Constraints

- Approved design: `docs/superpowers/specs/2026-07-21-manuscript-scene-title-edit-design.md`.
- Prerequisite ticket: ticket-worker `#3 원고 장면 추가와 전환` must be `done` and its approved scene-add/select behavior must be integrated before implementation starts.
- Prerequisite artifacts: `docs/superpowers/specs/2026-07-16-manuscript-scene-add-design.md` and `docs/superpowers/plans/2026-07-16-manuscript-scene-add.md`.
- Edit only the existing `Scene.title`; do not add a chapter, part, episode, or act container.
- Normalize a committed title with `trim()` and reject an empty result with `장면 제목을 입력해 주세요.`.
- Do not add a maximum title length, bulk rename, numbering edit, reorder, move, copy, delete, outline, draft status, project-title editing, or AI behavior.
- Keep `saveManuscript` as the only write operation. Do not add or change an API path, method, operation ID, request field, response field, status code, or error code.
- At plan authoring time, the observed `docs/api/openapi.yaml` blob is `69d64146d62ab12b7462839a1f3ef0f76133374d`; Main must record the exact baseline present after ticket #3 and give it to implementation and review.
- The domain operation stays deterministic, immutable, and free of React, browser, persistence, and network dependencies.
- Update `docs/domains/manuscript.md` in the same implementation slice because the title-modification use case and invariant are domain behavior.
- Preserve ticket #3 editor ref, scene navigation, focus, autosave, and structural-conflict behavior.
- Preserve unrelated working-tree changes, especially current Story Bible backend changes and untracked `docs/product/` documents.
- After implementation editing stops, complete the repository frontend review gate before E2E planning and generation.

---

## File Map

- `docs/domains/manuscript.md`: authoritative scene-title modification language and invariant.
- `frontend/src/modules/manuscript/domain/manuscript.ts`: immutable `updateSceneTitle` operation.
- `frontend/src/modules/manuscript/domain/manuscript.test.ts`: normalization, rejection, preservation, and immutability tests.
- `frontend/src/modules/manuscript/ui/scene-title-field.tsx`: transient inline edit, keyboard, validation, disabled, focus, and announcement behavior.
- `frontend/src/modules/manuscript/ui/scene-title-field.test.tsx`: isolated observable interaction and accessibility tests.
- `frontend/src/modules/manuscript/ui/manuscript-editor.tsx`: compose the title field above the existing manuscript Textarea while preserving its forwarded editor ref.
- `frontend/src/modules/manuscript/ui/manuscript-editor.test.tsx`: title callback wiring and body-editor regression test.
- `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`: connect title commits to the autosave draft and conflict status.
- `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`: complete screen synchronization, autosave, retry, conflict, and responsive acceptance tests.
- `frontend/test-plans/manuscript-scene-title-edit-e2e.md`: generated E2E plan after frontend review clears.
- `frontend/manuscript-scene-title-edit.spec.ts`: generated Playwright coverage.

---

### Task 1: Manuscript title operation and domain contract

**Files:**

- Modify: `docs/domains/manuscript.md`
- Modify: `frontend/src/modules/manuscript/domain/manuscript.ts`
- Modify: `frontend/src/modules/manuscript/domain/manuscript.test.ts`

**Interfaces:**

- Consumes: existing `Manuscript` and `Scene` types plus ticket #3 `addScene` and `selectScene` operations.
- Produces: `updateSceneTitle(manuscript: Manuscript, sceneId: string, title: string): Manuscript` through `@/modules/manuscript`.

- [ ] **Step 1: Verify the prerequisite and API no-change baseline**

From the repository root:

```sh
zellij-agent ticket-worker show 3 --json
rg -n 'export function (addScene|selectScene)' frontend/src/modules/manuscript/domain/manuscript.ts
git hash-object docs/api/openapi.yaml
git status --short
```

Expected: ticket #3 has status `done`; both prerequisite functions exist; one OpenAPI blob hash is printed; unrelated changes are recorded. If ticket #3 is not done or either function is absent, stop and report the unmet prerequisite without copying its implementation into this ticket.

- [ ] **Step 2: Write failing domain tests**

Append focused tests that cover normalization, preservation, identity, and failures:

```ts
test("normalizes and updates only one existing scene title", async () => {
  const { addScene, createInitialManuscript, updateSceneTitle } = await import("./manuscript");
  const manuscript = addScene(createInitialManuscript("project-1"), "scene-2");
  const originalFirst = manuscript.scenes[0];
  const originalSecond = manuscript.scenes[1];

  const updated = updateSceneTitle(manuscript, "scene-2", "  남겨진 편지  ");

  expect(updated.scenes[1]).toEqual({ ...originalSecond, title: "남겨진 편지" });
  expect(updated.scenes[0]).toBe(originalFirst);
  expect(updated.activeSceneId).toBe(manuscript.activeSceneId);
  expect(manuscript.scenes[1]).toBe(originalSecond);
});

test("returns the same manuscript when the normalized title is unchanged", async () => {
  const { createInitialManuscript, updateSceneTitle } = await import("./manuscript");
  const manuscript = createInitialManuscript("project-1");
  const title = manuscript.scenes[0]!.title;

  expect(updateSceneTitle(manuscript, manuscript.activeSceneId, `  ${title}  `)).toBe(manuscript);
});

test.each(["", "   "])("rejects a blank scene title %j", async (title) => {
  const { createInitialManuscript, updateSceneTitle } = await import("./manuscript");
  const manuscript = createInitialManuscript("project-1");

  expect(() => updateSceneTitle(manuscript, manuscript.activeSceneId, title)).toThrow(
    "장면 제목을 입력해 주세요.",
  );
  expect(manuscript.scenes[0]!.title).toBe("비가 그친 뒤의 정원");
});

test("rejects a title update for a missing scene", async () => {
  const { createInitialManuscript, updateSceneTitle } = await import("./manuscript");

  expect(() => updateSceneTitle(createInitialManuscript("project-1"), "missing", "제목")).toThrow(
    "원고 장면을 찾을 수 없습니다.",
  );
});
```

- [ ] **Step 3: Run the focused test and observe the expected failure**

From `frontend/`:

```sh
mise exec -- pnpm test -- src/modules/manuscript/domain/manuscript.test.ts
```

Expected: FAIL because `updateSceneTitle` is not exported.

- [ ] **Step 4: Implement the minimal immutable operation**

Add this operation beside `updateSceneContent`:

```ts
export function updateSceneTitle(
  manuscript: Manuscript,
  sceneId: string,
  title: string,
): Manuscript {
  const scene = manuscript.scenes.find(({ id }) => id === sceneId);
  if (!scene) {
    throw new Error("원고 장면을 찾을 수 없습니다.");
  }

  const normalizedTitle = title.trim();
  if (!normalizedTitle) {
    throw new Error("장면 제목을 입력해 주세요.");
  }
  if (scene.title === normalizedTitle) {
    return manuscript;
  }

  return {
    ...manuscript,
    scenes: manuscript.scenes.map((candidate) =>
      candidate.id === sceneId ? { ...candidate, title: normalizedTitle } : candidate,
    ),
  };
}
```

Update `docs/domains/manuscript.md` in the same step:

- add `장면 제목 수정` to the ubiquitous language and use cases;
- require the modification input to be non-empty after trimming;
- state that only the target title changes and all identifiers, numbering, content, references, other scenes, and input values remain unchanged;
- state that missing scenes and blank normalized titles reject the whole operation;
- do not add chapter hierarchy, title-length, ordering, deletion, outline, or status rules.

- [ ] **Step 5: Run focused domain verification**

```sh
mise exec -- pnpm test -- src/modules/manuscript/domain/manuscript.test.ts
mise exec -- pnpm typecheck
```

Expected: both commands exit 0 and the new title tests pass.

- [ ] **Step 6: Commit the domain slice**

```sh
git add docs/domains/manuscript.md frontend/src/modules/manuscript/domain/manuscript.ts frontend/src/modules/manuscript/domain/manuscript.test.ts
git commit -m "feat: add manuscript scene title operation"
```

---

### Task 2: Accessible inline scene-title field

**Files:**

- Create: `frontend/src/modules/manuscript/ui/scene-title-field.tsx`
- Create: `frontend/src/modules/manuscript/ui/scene-title-field.test.tsx`
- Modify: `frontend/src/modules/manuscript/ui/manuscript-editor.tsx`
- Create: `frontend/src/modules/manuscript/ui/manuscript-editor.test.tsx`

**Interfaces:**

- Consumes: `title: string`, `disabled: boolean`, and `onCommit(title: string): void`.
- Produces: `SceneTitleField` with exact accessible names `장면 제목 수정` and `장면 제목`.
- Extends: ticket #3 `ManuscriptEditor` props with `titleEditingDisabled: boolean` and `onTitleCommit(title: string): void` while preserving the forwarded `HTMLTextAreaElement` ref.

- [ ] **Step 1: Write failing SceneTitleField interaction tests**

Create the focused component test with these observable flows:

```tsx
test("edits the existing title with Enter and restores the heading", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  function StatefulTitleField() {
    const [title, setTitle] = useState("비가 그친 뒤의 정원");
    return (
      <SceneTitleField
        title={title}
        disabled={false}
        onCommit={(nextTitle) => {
          onCommit(nextTitle);
          setTitle(nextTitle.trim());
        }}
      />
    );
  }
  render(<StatefulTitleField />);

  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  const input = screen.getByRole("textbox", { name: "장면 제목" });
  expect(input).toHaveFocus();
  expect(input).toHaveValue("비가 그친 뒤의 정원");
  expect(input).toHaveProperty("selectionStart", 0);
  expect(input).toHaveProperty("selectionEnd", "비가 그친 뒤의 정원".length);

  await user.clear(input);
  await user.type(input, "  남겨진 편지  {Enter}");

  expect(onCommit).toHaveBeenCalledOnce();
  expect(onCommit).toHaveBeenCalledWith("  남겨진 편지  ");
  expect(screen.getByRole("heading", { name: "남겨진 편지" })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("장면 제목을 저장할 준비가 되었어요.");
});

test("commits on blur and cancels with Escape", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  const { rerender } = render(
    <SceneTitleField title="첫 제목" disabled={false} onCommit={onCommit} />,
  );

  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  await user.clear(screen.getByRole("textbox", { name: "장면 제목" }));
  await user.type(screen.getByRole("textbox", { name: "장면 제목" }), "두 번째 제목");
  await user.tab();
  expect(onCommit).toHaveBeenLastCalledWith("두 번째 제목");

  rerender(<SceneTitleField title="두 번째 제목" disabled={false} onCommit={onCommit} />);
  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  await user.type(screen.getByRole("textbox", { name: "장면 제목" }), " 폐기");
  await user.keyboard("{Escape}");
  expect(onCommit).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("heading", { name: "두 번째 제목" })).toBeInTheDocument();
});

test("keeps a blank title in edit mode with a linked error", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  render(<SceneTitleField title="기존 제목" disabled={false} onCommit={onCommit} />);

  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  const input = screen.getByRole("textbox", { name: "장면 제목" });
  await user.clear(input);
  await user.type(input, "   {Enter}");

  expect(onCommit).not.toHaveBeenCalled();
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(input).toHaveAccessibleDescription("장면 제목을 입력해 주세요.");
});

test("preserves an in-progress value but blocks commit while disabled", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  const { rerender } = render(
    <SceneTitleField title="기존 제목" disabled={false} onCommit={onCommit} />,
  );
  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  await user.clear(screen.getByRole("textbox", { name: "장면 제목" }));
  await user.type(screen.getByRole("textbox", { name: "장면 제목" }), "보존할 제목");

  rerender(<SceneTitleField title="기존 제목" disabled onCommit={onCommit} />);

  expect(screen.getByRole("textbox", { name: "장면 제목" })).toHaveValue("보존할 제목");
  expect(screen.getByRole("textbox", { name: "장면 제목" })).toBeDisabled();
  expect(onCommit).not.toHaveBeenCalled();
});
```

Import `useState` in the test for the stateful parent harness. The harness models the production parent updating the authoritative `title` prop synchronously after `onCommit`; do not make the field maintain a second persisted title.

Add a separate test that a fresh render with a different React `key` displays the new scene title and contains no prior input draft.

- [ ] **Step 2: Run the focused test and observe the missing-module failure**

```sh
mise exec -- pnpm test -- src/modules/manuscript/ui/scene-title-field.test.tsx
```

Expected: FAIL because `scene-title-field.tsx` does not exist.

- [ ] **Step 3: Implement the focused title field**

Use existing `Button` and `Input` primitives and keep transient text inside this component:

```tsx
interface SceneTitleFieldProps {
  title: string;
  disabled: boolean;
  onCommit: (title: string) => void;
}

export function SceneTitleField({ title, disabled, onCommit }: SceneTitleFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const [error, setError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useLayoutEffect(() => {
    if (editing && !disabled) inputRef.current?.select();
  }, [disabled, editing]);

  const cancel = () => {
    setDraft(title);
    setError(null);
    setEditing(false);
    setAnnouncement("장면 제목 수정을 취소했어요.");
  };

  const commit = () => {
    if (disabled) return;
    const normalized = draft.trim();
    if (!normalized) {
      setError("장면 제목을 입력해 주세요.");
      return;
    }
    onCommit(draft);
    setDraft(normalized);
    setError(null);
    setEditing(false);
    setAnnouncement("장면 제목을 저장할 준비가 되었어요.");
  };

  if (!editing) {
    return (
      <div className="mt-3 flex items-start gap-2">
        <h2 className="min-w-0 flex-1 font-heading text-3xl font-semibold">{title}</h2>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="장면 제목 수정"
          disabled={disabled}
          onClick={() => {
            setDraft(title);
            setError(null);
            setEditing(true);
          }}
        >
          <Pencil />
        </Button>
        <span role="status" aria-live="polite" className="sr-only">
          {announcement}
        </span>
      </div>
    );
  }

  return (
    <div className="mt-3">
      <Input
        ref={inputRef}
        aria-label="장면 제목"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "scene-title-error" : undefined}
        value={draft}
        disabled={disabled}
        onChange={(event) => {
          setDraft(event.target.value);
          if (event.target.value.trim()) setError(null);
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commit();
          }
          if (event.key === "Escape") {
            event.preventDefault();
            cancel();
          }
        }}
        className="h-auto px-0 py-0 font-heading text-3xl font-semibold"
      />
      {error && (
        <p id="scene-title-error" role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
```

Import `Pencil`, React hooks, `Button`, and `Input` explicitly. The viewing branch live region renders immediately after the success or cancel transition, making the announcement observable without duplicating persisted title state.

- [ ] **Step 4: Add ManuscriptEditor integration tests**

Create a test that renders `ManuscriptEditor` with `titleEditingDisabled={false}` and an `onTitleCommit` spy, edits the title through the accessible controls, and expects the callback value. Assert the existing `원고 본문` Textarea still forwards changes and selection callbacks. Add a disabled-state assertion that `장면 제목 수정` is disabled while the body Textarea remains enabled.

- [ ] **Step 5: Integrate the field without losing ticket #3 editor focus support**

Extend the existing props and replace only the title heading:

```tsx
interface ManuscriptEditorProps {
  scene: Scene;
  titleEditingDisabled: boolean;
  onTitleCommit: (title: string) => void;
  onChange: (content: string) => void;
  onSelectionChange: (range: TextRange) => void;
}

<SceneTitleField
  key={scene.id}
  title={scene.title}
  disabled={titleEditingDisabled}
  onCommit={onTitleCommit}
/>;
```

Preserve the prerequisite `forwardRef<HTMLTextAreaElement, ManuscriptEditorProps>` and pass that ref to the existing manuscript Textarea. Do not move body selection, body change, or post-scene-navigation focus behavior into the title component.

- [ ] **Step 6: Run focused UI verification**

```sh
mise exec -- pnpm test -- src/modules/manuscript/ui/scene-title-field.test.tsx src/modules/manuscript/ui/manuscript-editor.test.tsx
mise exec -- pnpm typecheck
```

Expected: both commands exit 0 and every new interaction test passes.

- [ ] **Step 7: Commit the title presentation slice**

```sh
git add frontend/src/modules/manuscript/ui/scene-title-field.tsx frontend/src/modules/manuscript/ui/scene-title-field.test.tsx frontend/src/modules/manuscript/ui/manuscript-editor.tsx frontend/src/modules/manuscript/ui/manuscript-editor.test.tsx
git commit -m "feat: edit manuscript scene titles inline"
```

---

### Task 3: Writing-workspace autosave and conflict integration

**Files:**

- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**

- Consumes: `updateSceneTitle`, ticket #3 `sceneNavigation.activeScene`, autosave `draft`, `updateDraft`, and `status`.
- Produces: one concise title-commit callback into `ManuscriptEditor` and synchronized editor/header/SceneTree rendering from the same draft.

- [ ] **Step 1: Write a failing complete-screen title and autosave test**

Add one acceptance test that collects the real MSW save body:

```tsx
test("updates every active-scene title surface and autosaves the whole manuscript", async () => {
  const requests: SaveManuscriptRequest[] = [];
  server.use(
    http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
      const body = (await request.json()) as SaveManuscriptRequest;
      requests.push(body);
      return HttpResponse.json({
        manuscript: body.manuscript,
        manuscriptRevision: 2,
        projectActivity: {
          projectId: body.manuscript.projectId,
          updatedAt: "2026-07-21T08:00:00.000Z",
        },
      } satisfies SaveManuscriptResponse);
    }),
  );
  const user = userEvent.setup();
  renderWorkspace();

  await user.click(await screen.findByRole("button", { name: "장면 제목 수정" }));
  const title = screen.getByRole("textbox", { name: "장면 제목" });
  await user.clear(title);
  await user.type(title, "  남겨진 편지  {Enter}");

  expect(screen.getByRole("heading", { name: "남겨진 편지" })).toBeInTheDocument();
  expect(screen.getByText(/1장 · 남겨진 편지/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "1장 남겨진 편지" })).toBeInTheDocument();
  await waitFor(() => expect(requests).toHaveLength(1), { timeout: 1_500 });
  expect(requests[0]!.manuscript.scenes[0]).toMatchObject({
    title: "남겨진 편지",
    content: expect.stringContaining("비가 그친 뒤의 온실"),
  });
});
```

Import `SaveManuscriptResponse` if the test file does not already import it after ticket #3.

- [ ] **Step 2: Add failing failure, conflict, and scene-switch tests**

Add separate tests with these exact outcomes:

1. Return 500 for the first PUT, commit `실패해도 남는 제목`, wait for `저장 실패`, and assert all three title surfaces retain the local title. Click `원고 저장 다시 시도`, return 200, and assert the second request includes the same title.
2. Return the existing 409 `MANUSCRIPT_REVISION_CONFLICT`, wait for `저장 충돌`, and assert `장면 제목 수정` is disabled. Resolve with the existing server-latest action and assert the server title replaces the local title on all surfaces.
3. Start editing scene 1, type an uncommitted value, select scene 2 through the ticket #3 SceneTree, and assert scene 2 renders its own title with no scene-1 draft in the input or saved Manuscript.
4. Run the success flow at 375px and 1024px and assert the same accessible controls and synchronized title result.

Use existing test helpers for viewport, workspace rendering, conflict responses, timers, and save retry rather than creating a second router or query setup.

- [ ] **Step 3: Run the screen test and observe the expected failures**

```sh
mise exec -- pnpm test -- src/pages/writing-workspace/writing-workspace-page.test.tsx
```

Expected: FAIL because `ManuscriptEditor` is missing title props and the page does not call `updateSceneTitle`.

- [ ] **Step 4: Wire title commits to the autosave draft**

Import `updateSceneTitle` from the Manuscript public surface and extend the existing editor composition:

```tsx
<ManuscriptEditor
  ref={sceneNavigation.editorRef}
  scene={scene}
  titleEditingDisabled={status === "conflict"}
  onTitleCommit={(title) => {
    updateDraft((current) => updateSceneTitle(current, scene.id, title));
  }}
  onChange={(content) => updateDraft((current) => updateSceneContent(current, scene.id, content))}
  onSelectionChange={sceneNavigation.setSelection}
/>
```

Use the ticket #3 actual `sceneNavigation` names established by its approved plan. Keep the page callback concise; do not add title draft `useState` or validation to the page. Preserve the dynamic `${scene.chapterNumber}장 · ${scene.title}` header and SceneTree props from ticket #3.

- [ ] **Step 5: Run focused integration verification**

```sh
mise exec -- pnpm test -- src/modules/manuscript/domain/manuscript.test.ts src/modules/manuscript/ui/scene-title-field.test.tsx src/modules/manuscript/ui/manuscript-editor.test.tsx src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm typecheck
```

Expected: both commands exit 0; title success, cancel, validation, save failure, retry, conflict, scene switch, mobile, and desktop tests pass together with ticket #3 scene tests.

- [ ] **Step 6: Commit the workspace integration**

```sh
git add frontend/src/pages/writing-workspace/writing-workspace-page.tsx frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx
git commit -m "feat: autosave manuscript scene titles"
```

---

### Task 4: Review, E2E artifacts, and final verification

**Files:**

- Create: `frontend/test-plans/manuscript-scene-title-edit-e2e.md`
- Create: `frontend/manuscript-scene-title-edit.spec.ts`
- Review only: all implementation and domain files listed above
- Verify unchanged: `docs/api/openapi.yaml`

**Interfaces:**

- Consumes: stopped frontend implementation, approved design, approved implementation plan, `docs/domains/manuscript.md`, and the Main-recorded no-change OpenAPI baseline.
- Produces: resolved review findings, an approved E2E plan, generated Playwright coverage, and final verification evidence.

- [ ] **Step 1: Stop frontend editing and dispatch the read-only frontend review**

Give `frontend-review` the complete route `/projects/$projectId/write`; implementation handoff; ticket #3 prerequisite and accepted interfaces; the approved design and this plan; `docs/domains/manuscript.md`; affected entry points `updateSceneTitle`, `SceneTitleField`, `ManuscriptEditor`, and `WritingWorkspacePage`; the exact no-change OpenAPI baseline; and safe focused/full frontend commands. The reviewer edits no files.

- [ ] **Step 2: Triage and resolve every accepted review finding**

Record severity, introduced/pre-existing classification, source location, impact, repair direction, and re-review requirement. Return accepted findings to the frontend implementer. Re-run the same reviewer for blocking/high findings or material behavior changes. Record concrete rationale for every rejected finding. Do not start E2E planning until the application review gate clears.

- [ ] **Step 3: Dispatch and approve the required E2E plan**

Give `.codex/agents/playwright_test_planner.toml` sole ownership of `frontend/test-plans/manuscript-scene-title-edit-e2e.md`, route `/projects/silver-garden/write`, the approved design, domain contract, implementation handoff, and acceptance criteria. Require user-visible flows for Enter commit, Escape cancel, blank validation, three-surface synchronization, autosave and reload restoration, save failure/retry, conflict/server-latest adoption, scene switching, and mobile/desktop interaction. The planner must not edit implementation or Playwright test files.

Main reviews the generated plan and rejects missing visible assertions, invented title limits, hierarchy, new API behavior, or coverage that duplicates ticket #3 without exercising title editing.

- [ ] **Step 4: Dispatch the required Playwright generator**

Give `.codex/agents/playwright_test_generator.toml` the approved E2E plan and sole ownership of `frontend/manuscript-scene-title-edit.spec.ts`. Tests use the real route and accessible names. The generator may not change product behavior, install dependencies, or edit the E2E plan.

- [ ] **Step 5: Run Playwright verification**

In one terminal from `frontend/`:

```sh
mise exec -- pnpm dev --host 127.0.0.1
```

Expected: Vite reports `http://127.0.0.1:5173/`.

In another terminal:

```sh
mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts
```

Expected: exit 0. Stop the development server afterward.

- [ ] **Step 6: Run full frontend and repository verification**

From `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

From the repository root:

```sh
git diff --check
git diff --exit-code -- docs/api/openapi.yaml
```

Expected: all commands exit 0. Compare the implementation diff with `docs/domains/manuscript.md` and confirm the same normalization, rejection, preservation, and ownership rules. Verify no API operation or schema changed.

- [ ] **Step 7: Commit E2E artifacts and reviewed repairs**

```sh
git add frontend/test-plans/manuscript-scene-title-edit-e2e.md frontend/manuscript-scene-title-edit.spec.ts
git commit -m "test: cover manuscript scene title editing"
```

Do not claim completion until all accepted findings are resolved and the focused tests, Playwright test, full check, build, API no-change check, and domain-document comparison have been observed.
