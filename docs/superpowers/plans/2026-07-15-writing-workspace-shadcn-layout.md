# Writing Workspace shadcn Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the existing writing workspace with accessible responsive sheets, semantic context tabs, resizable desktop panels, skeleton loading, and alert states.

**Architecture:** `WritingWorkspacePage` remains the composition owner and retains all existing domain and feature callbacks. A small `useMediaQuery` hook chooses exactly one responsive representation for context and assistant panels, while page-local presentation components reuse the same content and callbacks across sheet and inline layouts. shadcn primitives stay generic under `src/components/ui`.

**Tech Stack:** React 19, TypeScript 7, Vite 8, Tailwind CSS 4, shadcn 4 (`radix-nova`), Radix UI, `react-resizable-panels`, Vitest, Testing Library, MSW.

## Global Constraints

- Do not change project, Manuscript, Story Bible, Writing Assistant, autosave, conflict-resolution, API, mock-payload, or backend behavior.
- Keep Korean user-facing copy and Korean accessible names.
- Use `Sheet` below the applicable inline-panel breakpoint and render inline panels at or above that breakpoint; do not expose duplicate responsive representations to assistive technology.
- Use `Tabs` semantics for manuscript, character, and world context selection.
- Desktop resize handles must be keyboard accessible, and no handle may remain next to a closed panel.
- Preserve loading `status`, failure `alert`, autosave announcements, navigation protection, and existing retry behavior.
- Do not edit `docs/api/openapi.yaml` or `docs/domains/*.md`; this change does not alter API or domain contracts.
- Preserve unrelated user changes already present in the working tree.

---

### Task 1: Responsive shadcn writing workspace

**Files:**
- Create: `frontend/src/components/ui/alert.tsx`
- Create: `frontend/src/components/ui/skeleton.tsx`
- Create: `frontend/src/components/ui/resizable.tsx`
- Create: `frontend/src/hooks/use-media-query.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Test: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**
- Consumes: existing `Sheet`, `Tabs`, `Tooltip`, `Button`, `WritingToolPanel`, `SceneTree`, `StoryContextPanel`, `ManuscriptConflictDialog`, and all existing workspace hooks and callbacks.
- Produces: `useMediaQuery(query: string): boolean` and the shadcn exports `Alert`, `AlertTitle`, `AlertDescription`, `AlertAction`, `Skeleton`, `ResizablePanelGroup`, `ResizablePanel`, and `ResizableHandle`.
- Breakpoints: context panel inline at `(min-width: 768px)`; resizable desktop layout and inline AI assistant at `(min-width: 1280px)`.

- [ ] **Step 1: Add failing observable-behavior tests**

Update the Vitest import to include cleanup support for the media-query stub:

```tsx
import { afterEach, describe, expect, test, vi } from "vitest";
```

Add this cleanup and deterministic `matchMedia` helper near the test helpers:

```tsx
afterEach(() => {
  vi.unstubAllGlobals();
});

function setViewportWidth(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => {
    const minimumWidth = Number(query.match(/min-width:\s*(\d+)px/)?.[1] ?? 0);
    return {
      matches: width >= minimumWidth,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } satisfies MediaQueryList;
  });
}
```

Change the loading test to retain the status assertion and prove that the
workspace-shaped state uses multiple skeleton regions:

```tsx
test("shows a workspace skeleton while the workspace is being fetched", () => {
  server.use(
    http.get("/api/projects/:projectId/workspace", async () => {
      await delay("infinite");
      return HttpResponse.json({});
    }),
  );

  const { container } = renderWorkspace();

  expect(screen.getByRole("status")).toHaveTextContent(
    "작업 공간을 불러오는 중이에요.",
  );
  expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(3);
});
```

Replace the existing context-switch test with tab semantics and mobile sheet
coverage:

```tsx
test("opens the selected contextual tab in a mobile sheet", async () => {
  setViewportWidth(375);
  const user = userEvent.setup();
  renderWorkspace();

  const charactersTab = await screen.findByRole("tab", { name: "인물 보기" });
  expect(screen.getAllByRole("tab")).toHaveLength(3);

  await user.click(charactersTab);

  const contextSheet = screen.getByRole("dialog", { name: "인물 보기" });
  expect(contextSheet).toHaveTextContent("등장인물");
  expect(contextSheet).toHaveTextContent("서윤");
  expect(charactersTab).toHaveAttribute("aria-selected", "true");

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog", { name: "인물 보기" })).not.toBeInTheDocument();
});
```

Add AI sheet behavior below the desktop breakpoint:

```tsx
test("opens and closes the AI tool as a sheet below the desktop breakpoint", async () => {
  setViewportWidth(1024);
  const user = userEvent.setup();
  renderWorkspace();

  await user.click(await screen.findByRole("button", { name: "AI 도구 열기" }));
  expect(screen.getByRole("dialog", { name: "AI 집필 도구" })).toBeInTheDocument();

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog", { name: "AI 집필 도구" })).not.toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "원고 본문" })).toBeInTheDocument();
});
```

Add desktop resizable-panel coverage:

```tsx
test("adds a resize handle only for each visible adjacent desktop panel", async () => {
  setViewportWidth(1280);
  const user = userEvent.setup();
  renderWorkspace();

  await screen.findByRole("textbox", { name: "원고 본문" });
  expect(screen.getAllByRole("separator")).toHaveLength(1);

  await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));
  expect(screen.queryByRole("dialog", { name: "AI 집필 도구" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("separator")).toHaveLength(2);

  await user.click(screen.getByRole("button", { name: "AI 도구 닫기" }));
  expect(screen.getAllByRole("separator")).toHaveLength(1);
});
```

Update existing selectors from `button` to `tab` only where they target the
three context-mode controls. Keep all manuscript, autosave, conflict, and
assistant-application tests intact.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```sh
cd frontend && mise exec -- pnpm test -- src/pages/writing-workspace/writing-workspace-page.test.tsx
```

Expected: FAIL because no skeleton slots, context tabs, mobile sheets, or
desktop resize separators exist yet. Confirm the failure is from missing
behavior rather than test setup.

- [ ] **Step 3: Generate the missing shadcn primitives**

Run the repository-installed CLI without overwriting existing primitives:

```sh
cd frontend && mise exec -- pnpm exec shadcn add alert skeleton resizable --yes
```

Expected generated changes:

```text
src/components/ui/alert.tsx
src/components/ui/skeleton.tsx
src/components/ui/resizable.tsx
package.json: react-resizable-panels dependency
pnpm-lock.yaml: resolved react-resizable-panels dependency
```

Do not hand-edit generated primitives unless formatting or the project's strict
TypeScript checks require a minimal compatibility correction.

- [ ] **Step 4: Add the responsive media-query boundary**

Create `frontend/src/hooks/use-media-query.ts`:

```ts
import { useSyncExternalStore } from "react";

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onStoreChange) => {
      if (typeof window === "undefined") {
        return () => undefined;
      }
      const mediaQuery = window.matchMedia(query);
      mediaQuery.addEventListener("change", onStoreChange);
      return () => mediaQuery.removeEventListener("change", onStoreChange);
    },
    () => (typeof window === "undefined" ? false : window.matchMedia(query).matches),
    () => false,
  );
}
```

This hook owns browser synchronization only. It must not acquire or mutate page
or domain state.

- [ ] **Step 5: Replace ad-hoc loading and terminal-state surfaces**

In `writing-workspace-page.tsx`, import the generated `Alert` parts and
`Skeleton`. Extract a page-local `WorkspaceStateSurface` only if it reduces
repeated outer layout without erasing each state's semantic role or action.

The loading tree must have this semantic shape:

```tsx
<main role="status" className="flex min-h-svh flex-col overflow-hidden bg-[#ede6dd]">
  <span className="sr-only">작업 공간을 불러오는 중이에요.</span>
  <header aria-hidden="true" className="flex h-16 items-center gap-3 border-b bg-card px-5">
    <Skeleton className="size-8 rounded-full" />
    <div className="space-y-2">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-3 w-24" />
    </div>
  </header>
  <div aria-hidden="true" className="flex min-h-0 flex-1">
    <div className="w-14 border-r bg-sidebar p-3"><Skeleton className="h-32 w-full" /></div>
    <div className="hidden w-64 border-r bg-sidebar/90 p-4 md:block"><Skeleton className="h-full w-full" /></div>
    <div className="flex-1 p-6"><Skeleton className="mx-auto h-full max-w-3xl bg-card" /></div>
  </div>
</main>
```

Use `Alert`, `AlertTitle`, `AlertDescription`, and `AlertAction` for transient
load error, project not found, and missing scene. Preserve these exact actions:

```text
프로젝트를 찾을 수 없어요 -> 작품 서재로 돌아가기
작업 공간을 불러오지 못했어요. 잠시 후 다시 시도해 주세요. -> 작업 공간 다시 불러오기
현재 집필할 장면을 찾을 수 없어요. -> no action
```

- [ ] **Step 6: Implement semantic context tabs and responsive panels**

Import `Tabs`, `TabsList`, `TabsTrigger`, and `TabsContent`; `Sheet`,
`SheetContent`, `SheetHeader`, `SheetTitle`, and `SheetDescription`; the
resizable primitives; and `useMediaQuery`.

Keep these page-owned states and derived boundaries:

```tsx
const [contextMode, setContextMode] = useState<ContextMode>("manuscript");
const [contextOpen, setContextOpen] = useState(false);
const [assistantOpen, setAssistantOpen] = useState(false);
const contextIsInline = useMediaQuery("(min-width: 768px)");
const desktopIsResizable = useMediaQuery("(min-width: 1280px)");
```

Use a controlled vertical `Tabs` root. Each icon trigger keeps its tooltip and
accessible label, and its click opens the context sheet only when
`contextIsInline` is false:

```tsx
<Tabs value={contextMode} orientation="vertical" onValueChange={(value) => setContextMode(value as ContextMode)}>
  <TabsList aria-label="집필 도메인" variant="line">
    {contextTools.map((tool) => {
      const Icon = tool.icon;
      return (
        <TabsTrigger
          key={tool.mode}
          value={tool.mode}
          aria-label={tool.label}
          onClick={() => {
            setContextMode(tool.mode);
            if (!contextIsInline) setContextOpen(true);
          }}
        >
          <Icon />
        </TabsTrigger>
      );
    })}
  </TabsList>
  {/* active responsive context and editor layout */}
</Tabs>
```

Implement one page-local `ContextPanelContent` that returns the three
`TabsContent` elements so inline and sheet layouts reuse the same selection
contract:

```tsx
function ContextPanelContent({ draft, bible }: ContextPanelContentProps) {
  return (
    <>
      <TabsContent value="manuscript"><SceneTree manuscript={draft} /></TabsContent>
      <TabsContent value="characters"><StoryContextPanel bible={bible} mode="characters" /></TabsContent>
      <TabsContent value="world"><StoryContextPanel bible={bible} mode="world" /></TabsContent>
    </>
  );
}
```

Render this content exactly once: inside a left `Sheet` below 768px, in the
fixed inline aside from 768px through 1279px, and in the first
`ResizablePanel` at 1280px and above. The sheet uses the selected
`contextTools` label as `SheetTitle`, includes a concise Korean
`SheetDescription`, and may use `ScrollArea` for its bounded content.

At 1280px and above, create a horizontal `ResizablePanelGroup` with:

```text
context: default 20%, minimum 15%
editor: default 55%, minimum 40%
assistant when open: default 25%, minimum 20%
```

Render one `ResizableHandle withHandle` between every visible adjacent pair.
When `assistantOpen` is false, omit both its panel and its preceding handle.

- [ ] **Step 7: Implement the responsive AI assistant representation**

Extract only the repeated `WritingToolPanel` prop wiring into a page-local
component or a `renderAssistantPanel` helper. Do not move domain or application
workflow ownership into `src/components/ui`.

Below 1280px, render a controlled right `Sheet`:

```tsx
<Sheet open={assistantOpen} onOpenChange={setAssistantOpen}>
  <SheetContent side="right" showCloseButton={false} className="w-full gap-0 p-0 sm:max-w-md">
    <SheetHeader className="sr-only">
      <SheetTitle>AI 집필 도구</SheetTitle>
      <SheetDescription>현재 장면을 바탕으로 집필 제안을 만들고 원고에 적용합니다.</SheetDescription>
    </SheetHeader>
    <WritingToolPanel {...assistantProps} onClose={() => setAssistantOpen(false)} />
  </SheetContent>
</Sheet>
```

At 1280px and above, render the same tool panel only inside its resizable inline
panel. Preserve the existing apply flow through `applyWritingSuggestion`,
`updateDraft`, and selection update exactly.

- [ ] **Step 8: Run focused tests and refactor GREEN**

Run:

```sh
cd frontend && mise exec -- pnpm test -- src/pages/writing-workspace/writing-workspace-page.test.tsx
```

Expected: all tests in `writing-workspace-page.test.tsx` PASS. If Radix emits
dialog-title or description accessibility warnings, treat them as failures and
correct the sheet composition.

Then run formatting only on files owned by this task:

```sh
cd frontend && mise exec -- pnpm exec oxfmt --write \
  src/components/ui/alert.tsx \
  src/components/ui/skeleton.tsx \
  src/components/ui/resizable.tsx \
  src/hooks/use-media-query.ts \
  src/pages/writing-workspace/writing-workspace-page.tsx \
  src/pages/writing-workspace/writing-workspace-page.test.tsx \
  package.json pnpm-lock.yaml
```

Re-run the focused test and expect PASS.

- [ ] **Step 9: Run full frontend verification**

Run:

```sh
cd frontend && mise exec -- pnpm check
cd frontend && mise exec -- pnpm build
```

Expected: both commands exit 0 with no format, lint, type-check, unit-test, or
build failures.

- [ ] **Step 10: Commit the implementation**

Stage only the files owned by this task and commit:

```sh
git add \
  frontend/package.json \
  frontend/pnpm-lock.yaml \
  frontend/src/components/ui/alert.tsx \
  frontend/src/components/ui/skeleton.tsx \
  frontend/src/components/ui/resizable.tsx \
  frontend/src/hooks/use-media-query.ts \
  frontend/src/pages/writing-workspace/writing-workspace-page.tsx \
  frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx
git commit -m "feat: improve writing workspace layout"
```

Before reporting, inspect `git status --short` and confirm no unrelated file
was staged or committed.

---

### Task 2: Required E2E planning and generation handoff

**Files:**
- Read: `.codex/agents/playwright_test_planner.toml`
- Read: `.codex/agents/playwright_test_generator.toml`
- Create or modify: only the Playwright paths explicitly assigned by the test generator.

**Interfaces:**
- Consumes: Task 1 implementation, acceptance criteria from
  `docs/superpowers/specs/2026-07-15-writing-workspace-shadcn-layout-design.md`,
  and the existing workspace route `/projects/:projectId/write`.
- Produces: an approved E2E plan and generated Playwright coverage when both
  required project-scoped agent definitions exist.

- [ ] **Step 1: Verify the required project-scoped agent definitions**

Run:

```sh
test -f .codex/agents/playwright_test_planner.toml
test -f .codex/agents/playwright_test_generator.toml
```

Expected in a configured repository: both commands exit 0.

If either file is missing, stop this task and report the exact missing paths to
the main agent. Do not silently substitute another agent or hand-author E2E
tests, because `frontend/AGENTS.md` requires the named planner and generator.

- [ ] **Step 2: Run planner then generator when available**

Assign the planner read-only access to Task 1 paths, the design acceptance
criteria, the Manuscript, Story Bible, and Writing Assistant contracts, and the
exact relevant Playwright command. After main-agent plan approval, assign only
the generated Playwright test paths to the generator. The generator must not
modify product behavior.

- [ ] **Step 3: Review and verify generated E2E coverage**

Confirm coverage includes context tabs, mobile context sheet, AI sheet Escape
behavior, desktop resize handles, loading/error behavior, and preserved editor
interaction. Run the exact Playwright command established by the repository
configuration and record its exit code and test count.
