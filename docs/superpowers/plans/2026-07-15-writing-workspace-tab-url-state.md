# Writing Workspace Tab URL State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store the writing-workspace context tab in validated TanStack Router search state.

**Architecture:** A page-scoped tab contract supplies the valid union to the file route and page. The route validates `tab`; the page derives the selected context from search, writes user selections with typed navigation, and replacement-canonicalizes malformed or explicit manuscript values.

**Tech Stack:** React 19, TypeScript 7, TanStack Router 1.170.18, Vitest 4, Testing Library

## Global Constraints

- Preserve `/projects/$projectId/write`, layout, copy, accessibility, responsive behavior, autosave, conflicts, and unload protection.
- `tab` accepts `manuscript`, `characters`, or `world`; absent `tab` is canonical manuscript.
- User tab clicks create history entries. Manuscript removes `tab`; characters and world set it.
- Explicit `tab=manuscript` and malformed values replacement-navigate to the clean manuscript URL.
- Mobile tab click opens the existing context sheet; closing it retains URL state.
- Do not URL-own AI tools, manuscript selection, autosave, conflict dialogs, or panel sizing.
- Do not change domain contracts, APIs, persistence, dependencies, or generated route-tree source by hand.
- Implement only from approved `frontend/docs/ui-plans/writing-workspace-tab-url-state.md` and its `REQ-*` IDs.

---

### Task 1: Produce and Approve the UI Plan

**Files:**
- Create: `frontend/docs/ui-plans/writing-workspace-tab-url-state.md`

**Interfaces:**
- Consumes: the approved design, Manuscript and Story Bible contracts, and the existing writing-workspace screen.
- Produces: `REQ-1` through `REQ-7` for default state, direct URLs, click navigation, history, canonicalization, mobile sheet persistence, and regression behavior.

- [ ] **Step 1: Dispatch `ui-planner`**

Assign the exact artifact path above and this exact requirement set:

```text
REQ-1 default URL renders manuscript.
REQ-2 characters/world direct URLs render matching context.
REQ-3 tab clicks write canonical search state.
REQ-4 Back/Forward replays tab selection.
REQ-5 explicit manuscript and malformed values replacement-canonicalize.
REQ-6 mobile sheet close retains selected URL state.
REQ-7 existing Tabs/Sheet accessibility, layout, autosave, AI, and conflict behavior remain unchanged.
```

- [ ] **Step 2: Main-agent approval**

Review the state table, URL mapping, responsive behavior, keyboard behavior, existing shadcn Tabs/Sheet use, and unresolved assumptions. Record the exact approved revision before Task 2.

### Task 2: Implement URL-Owned Context Tabs

**Files:**
- Create: `frontend/src/pages/writing-workspace/writing-workspace-tabs.ts`
- Modify: `frontend/src/routes/projects.$projectId.write.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**
- Produces: `ContextMode`, `contextModes`, `parseContextMode(value: unknown): ContextMode | undefined`, validated `{ tab?: ContextMode }`, and URL-derived selection.

- [ ] **Step 1: Write failing tests**

Update the existing test helper to accept a complete initial URL and return its router. Add tests for direct `?tab=characters` and `?tab=world`, click-produced search state, manuscript parameter removal, Back/Forward replay, malformed/explicit-manuscript replacement canonicalization, and mobile sheet close retention.

The canonicalization assertion is:

```tsx
const { router } = renderWorkspace("/projects/silver-garden/write?tab=unknown");
expect(await screen.findByRole("tab", { name: "원고 보기", selected: true })).toBeInTheDocument();
await waitFor(() => expect(router.state.location.search).toEqual({}));
```

- [ ] **Step 2: Verify RED**

Run from `frontend/`:

```sh
mise exec -- pnpm test src/pages/writing-workspace/writing-workspace-page.test.tsx -t "tab URL|history|canonicalizes"
```

Expected: fail because selected context is local state and the route does not validate `tab`.

- [ ] **Step 3: Add the tab contract and route validation**

Create:

```ts
export const contextModes = ["manuscript", "characters", "world"] as const;
export type ContextMode = (typeof contextModes)[number];
export function parseContextMode(value: unknown): ContextMode | undefined {
  return contextModes.find((mode) => mode === value);
}
```

Add to the writing-workspace route:

```tsx
validateSearch: (search: Record<string, unknown>) => {
  if (search.tab === undefined) return {};
  return { tab: parseContextMode(search.tab) ?? "manuscript" };
},
```

- [ ] **Step 4: Derive selection and write typed search state**

Replace local selected-tab state with:

```tsx
const { tab } = useSearch({ from: "/projects/$projectId/write" });
const navigate = useNavigate({ from: "/projects/$projectId/write" });
const contextMode: ContextMode = tab ?? "manuscript";
```

When `tab === "manuscript"`, use an effect with `replace: true` to remove `tab`. For user clicks, navigate without `replace`; remove `tab` for manuscript and preserve other search values while setting characters/world. Keep mobile `setContextOpen(true)` behavior.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```sh
mise exec -- pnpm test src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm typecheck
mise exec -- pnpm build
git diff -- src/routeTree.gen.ts
```

Expected: all commands succeed and generated route-tree content has no drift.

Commit:

```sh
git add frontend/src/routes/projects.$projectId.write.tsx frontend/src/pages/writing-workspace/writing-workspace-tabs.ts frontend/src/pages/writing-workspace/writing-workspace-page.tsx frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx
git commit -m "feat(frontend): store workspace tabs in URL"
```

### Task 3: E2E and Read-Only Review Gates

**Files:**
- Planned E2E plan: `frontend/docs/e2e-plans/writing-workspace-tab-url-state.md`
- Review boundary: complete `/projects/$projectId/write` screen and Task 2 paths

- [ ] **Step 1: Confirm E2E custom agents**

Run both checks separately:

```sh
test -f .codex/agents/playwright_test_planner.toml
```

```sh
test -f .codex/agents/playwright_test_generator.toml
```

Expected current result: both fail. Mark the pipeline blocked and do not substitute generic E2E agents or dispatch downstream screen review.

- [ ] **Step 2: When configured, dispatch ordered E2E and frontend review**

The planner receives the approved UI-plan revision and `REQ-1` through `REQ-7`; the generator receives the approved E2E plan; `frontend-review` receives the complete screen, UI plan, contracts, diff, and verification output. Resolve all accepted findings and re-review material or High/Blocking repairs.

- [ ] **Step 3: Main-agent final verification**

Run from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: both commands exit 0 with all accepted findings resolved.
