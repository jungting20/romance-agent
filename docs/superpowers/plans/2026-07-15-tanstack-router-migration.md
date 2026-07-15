# TanStack Router File-Based Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace React Router throughout the frontend with a file-based, type-safe TanStack Router while preserving every current route and manuscript navigation safeguard.

**Architecture:** The TanStack Router Vite plugin generates one route tree from focused files under `src/routes/`. A single router factory supplies browser history in production and memory history in tests; existing pages remain screen owners and consume typed route hooks directly. Navigation blocking moves to TanStack Router's asynchronous blocker with conditional browser-unload protection.

**Tech Stack:** React 19, TypeScript 7, Vite 8, Vitest 4, TanStack Router 1.x, TanStack Query 5, Testing Library, pnpm 11

## Global Constraints

- Preserve `/`, `/new`, `/new/setup?trope=...`, and `/projects/$projectId/write`.
- Unknown paths must replace-navigate to `/`.
- Preserve browser back/forward behavior and project-creation navigation.
- Preserve manuscript flush-before-navigation and native unload warnings.
- Do not add route loaders or move TanStack Query ownership into routes.
- Do not introduce a React Router compatibility wrapper.
- Do not change UI layout, copy, API operations, domain rules, persistence semantics, or tab URL behavior.
- Keep `frontend/src/routeTree.gen.ts` committed and never hand-edit it.
- Update `frontend/docs/frontend-coding-rules.md` with reusable router ownership and generated-file rules in the same change.
- `docs/api/openapi.yaml` and `docs/domains/*.md` are out of scope because API and domain behavior do not change.
- Required post-implementation Playwright planning and generation are blocked until `.codex/agents/playwright_test_planner.toml` and `.codex/agents/playwright_test_generator.toml` exist.

---

### Task 1: Establish the Generated Route Tree and Shared Router Factory

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Modify: `frontend/vite.config.ts`
- Replace: `frontend/src/app/app.tsx`
- Modify: `frontend/src/app/app.test.tsx`
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/routes/__root.tsx`
- Create: `frontend/src/routes/index.tsx`
- Create: `frontend/src/routes/new.tsx`
- Create: `frontend/src/routes/new_.setup.tsx`
- Create: `frontend/src/routes/projects.$projectId.write.tsx`
- Generate: `frontend/src/routeTree.gen.ts`
- Modify: `frontend/src/shared/ui/app-header.tsx`
- Modify: `frontend/src/shared/ui/brand-mark.tsx`
- Modify: `frontend/src/pages/library/library-page.tsx`
- Modify: `frontend/src/pages/new-project/trope-page.tsx`
- Modify: `frontend/src/modules/projects/ui/project-card.tsx`
- Modify: `frontend/src/modules/story-design/ui/trope-selector.tsx`

**Interfaces:**
- Consumes: Existing `LibraryPage`, `TropePage`, `SetupPage`, `WritingWorkspacePage`, and `TooltipProvider` components.
- Produces: `router`, `createAppRouter(options?)`, and `createAppMemoryRouter(initialEntries)` backed by the generated route tree; registered TanStack Router types for every consumer.

- [ ] **Step 1: Install the migration dependencies without removing React Router yet**

Run from `frontend/`:

```sh
mise exec -- pnpm add @tanstack/react-router@^1.170.18
mise exec -- pnpm add -D @tanstack/router-plugin@^1.168.20
```

Expected: `package.json` and `pnpm-lock.yaml` contain both TanStack packages while `react-router-dom` remains available during the red-green migration.

- [ ] **Step 2: Convert the application routing test provider and add a failing fallback test**

In `frontend/src/app/app.test.tsx`, import `RouterProvider` from TanStack Router and add:

```tsx
import { RouterProvider } from "@tanstack/react-router";

test("replace-navigates unknown routes to the project library", async () => {
  const router = renderApp(["/missing-route"]);

  expect(
    await screen.findByRole("heading", { name: "다시, 이야기를 시작해 볼까요?" }),
  ).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/");
  expect(router.state.location.state.__TSR_index).toBe(0);
});
```

Make `renderApp` return the router it renders:

```tsx
function renderApp(initialEntries: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppMemoryRouter(initialEntries);

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  return router;
}
```

- [ ] **Step 3: Run the focused test and verify RED**

Run from `frontend/`:

```sh
mise exec -- pnpm test src/app/app.test.tsx -t "replace-navigates unknown routes"
```

Expected: FAIL because the current `createAppMemoryRouter` returns a React Router router that is incompatible with TanStack `RouterProvider`, and the TanStack not-found redirect does not exist.

- [ ] **Step 4: Configure file-based generation and define route files**

In `frontend/vite.config.ts`, place the router plugin before React:

```ts
import { tanstackRouter } from "@tanstack/router-plugin/vite";

plugins: [
  tanstackRouter({ target: "react", autoCodeSplitting: true }),
  react(),
  tailwindcss(),
],
```

Create `frontend/src/routes/__root.tsx`:

```tsx
import { Navigate, Outlet, createRootRoute } from "@tanstack/react-router";

import { TooltipProvider } from "@/components/ui/tooltip";

export const Route = createRootRoute({
  component: RootLayout,
  notFoundComponent: () => <Navigate to="/" replace />,
});

function RootLayout() {
  return (
    <TooltipProvider>
      <Outlet />
    </TooltipProvider>
  );
}
```

Create the four leaf route files:

```tsx
// src/routes/index.tsx
import { createFileRoute } from "@tanstack/react-router";
import { LibraryPage } from "@/pages/library/library-page";
export const Route = createFileRoute("/")({ component: LibraryPage });

// src/routes/new.tsx
import { createFileRoute } from "@tanstack/react-router";
import { TropePage } from "@/pages/new-project/trope-page";
export const Route = createFileRoute("/new")({ component: TropePage });

// src/routes/new_.setup.tsx
import { createFileRoute } from "@tanstack/react-router";
import { SetupPage } from "@/pages/new-project/setup-page";
export const Route = createFileRoute("/new/setup")({
  validateSearch: (search: Record<string, unknown>) => ({
    trope: typeof search.trope === "string" ? search.trope : undefined,
  }),
  component: SetupPage,
});

// src/routes/projects.$projectId.write.tsx
import { createFileRoute } from "@tanstack/react-router";
import { WritingWorkspacePage } from "@/pages/writing-workspace/writing-workspace-page";
export const Route = createFileRoute("/projects/$projectId/write")({
  component: WritingWorkspacePage,
});
```

- [ ] **Step 5: Replace router construction and production provider**

Replace `frontend/src/app/app.tsx` with:

```tsx
import {
  createMemoryHistory,
  createRouter,
  type RouterHistory,
} from "@tanstack/react-router";

import { routeTree } from "@/routeTree.gen";

export function createAppRouter(options: { history?: RouterHistory } = {}) {
  return createRouter({
    routeTree,
    history: options.history,
    defaultPreload: "intent",
  });
}

export function createAppMemoryRouter(initialEntries: string[]) {
  return createAppRouter({ history: createMemoryHistory({ initialEntries }) });
}

export const router = createAppRouter();

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
```

In `frontend/src/main.tsx`, import TanStack `RouterProvider` and the singleton:

```tsx
import { RouterProvider } from "@tanstack/react-router";
import { router } from "@/app/app";

<RouterProvider router={router} />
```

Run generation through Vite without completing a production build yet:

```sh
mise exec -- pnpm exec vite build --emptyOutDir=false
```

Expected: `src/routeTree.gen.ts` is generated. A later task may still expose React Router consumer failures.

- [ ] **Step 6: Migrate static and typed links required by the root and trope routes**

In the six static-link consumers, replace only the import source:

```tsx
import { Link } from "@tanstack/react-router";
```

In `frontend/src/modules/projects/ui/project-card.tsx`, replace the interpolated destination with:

```tsx
<Link to="/projects/$projectId/write" params={{ projectId: project.id }}>
```

In `frontend/src/modules/story-design/ui/trope-selector.tsx`, preserve the setup destination and pass typed search state:

```tsx
<Link to="/new/setup" search={{ trope: trope.id }}>
```

- [ ] **Step 7: Run the fallback test and verify GREEN**

Run from `frontend/`:

```sh
mise exec -- pnpm test src/app/app.test.tsx -t "replace-navigates unknown routes"
```

Expected: PASS; the library renders, the router pathname is `/`, and memory history contains one entry.

- [ ] **Step 8: Commit the routing foundation**

```sh
git add frontend/package.json frontend/pnpm-lock.yaml frontend/vite.config.ts \
  frontend/src/app/app.tsx frontend/src/app/app.test.tsx frontend/src/main.tsx \
  frontend/src/routes frontend/src/routeTree.gen.ts \
  frontend/src/shared/ui/app-header.tsx frontend/src/shared/ui/brand-mark.tsx \
  frontend/src/pages/library/library-page.tsx frontend/src/pages/new-project/trope-page.tsx \
  frontend/src/modules/projects/ui/project-card.tsx \
  frontend/src/modules/story-design/ui/trope-selector.tsx
git commit -m "refactor(frontend): establish TanStack route tree"
```

### Task 2: Migrate Search Parameters and Programmatic Project Navigation

**Files:**
- Modify: `frontend/src/pages/new-project/setup-page.tsx`
- Modify: `frontend/src/pages/new-project/setup-page.test.tsx`

**Interfaces:**
- Consumes: Registered routes `/new`, `/new/setup`, and `/projects/$projectId/write` plus `createAppMemoryRouter`.
- Produces: Typed setup search consumption and typed project navigation with no React Router context.

- [ ] **Step 1: Convert the setup test harness to the application route tree**

Replace React Router test imports with:

```tsx
import { RouterProvider } from "@tanstack/react-router";
import { createAppMemoryRouter } from "@/app/app";
```

Make `renderSetup` render the application router and return it:

```tsx
function renderSetup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppMemoryRouter(["/new/setup?trope=reunion"]);

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  return router;
}
```

Delete the test-only `OpenedProject` component. In the navigation test, retain the returned router and assert:

```tsx
const router = renderSetup();
// fill and submit the existing form
await waitFor(() => {
  expect(router.state.location.pathname).toBe("/projects/server-project-id/write");
});
```

- [ ] **Step 2: Run the focused test and verify RED**

```sh
mise exec -- pnpm test src/pages/new-project/setup-page.test.tsx -t "navigates to the workspace ID"
```

Expected: FAIL because `SetupPage` still calls React Router hooks outside a React Router provider.

- [ ] **Step 3: Implement typed setup routing**

In `frontend/src/pages/new-project/setup-page.tsx`, use:

```tsx
import { Link, Navigate, useNavigate, useSearch } from "@tanstack/react-router";

const { trope: tropeId } = useSearch({ from: "/new/setup" });
const navigate = useNavigate({ from: "/new/setup" });

if (!trope) {
  return <Navigate to="/new" replace />;
}

void navigate({
  to: "/projects/$projectId/write",
  params: { projectId: workspace.project.id },
});
```

Keep the existing `/new` link and all form behavior unchanged.

- [ ] **Step 4: Verify the setup route and core journey are GREEN**

```sh
mise exec -- pnpm test src/pages/new-project/setup-page.test.tsx src/app/app.test.tsx
```

Expected: both files pass, including search-based setup rendering and navigation to the server-provided project ID.

- [ ] **Step 5: Commit typed setup navigation**

```sh
git add frontend/src/pages/new-project/setup-page.tsx \
  frontend/src/pages/new-project/setup-page.test.tsx frontend/src/app/app.test.tsx
git commit -m "refactor(frontend): migrate project setup routing"
```

### Task 3: Migrate the Writing Workspace Parameter and Navigation Guard

**Files:**
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**
- Consumes: Typed `/projects/$projectId/write` route and TanStack Router `useBlocker`.
- Produces: Typed project lookup and an asynchronous navigation guard that returns `true` to block when `flush()` fails, with browser unload protection enabled while unsaved.

- [ ] **Step 1: Convert the workspace test provider to TanStack Router**

Change the provider import only:

```tsx
import { RouterProvider } from "@tanstack/react-router";
```

Keep `createAppMemoryRouter([\`/projects/${projectId}/write\`])` as the shared harness.

- [ ] **Step 2: Run the existing navigation protection tests and verify RED**

```sh
mise exec -- pnpm test src/pages/writing-workspace/writing-workspace-page.test.tsx \
  -t "saves an edit immediately before internal navigation|warns before unloading|cancels internal navigation"
```

Expected: FAIL because the page still uses React Router parameters, links, blocker, and unload hook without a React Router provider.

- [ ] **Step 3: Implement typed parameters, links, and one TanStack blocker**

Replace the router imports and parameter access:

```tsx
import { Link, useBlocker, useParams } from "@tanstack/react-router";

const { projectId } = useParams({ from: "/projects/$projectId/write" });
const workspaceQuery = useProjectWorkspaceQuery(projectId);
```

Replace both library links with TanStack `Link` using `to="/"`.

Replace `useManuscriptNavigationGuard` with:

```tsx
function useManuscriptNavigationGuard(
  status: ManuscriptAutosaveStatus,
  flush: () => Promise<boolean>,
) {
  const shouldBlock = status !== "saved";
  const isHandlingBlockedNavigationRef = useRef(false);

  useBlocker({
    disabled: !shouldBlock,
    enableBeforeUnload: shouldBlock,
    shouldBlockFn: async () => {
      if (isHandlingBlockedNavigationRef.current) {
        return true;
      }

      isHandlingBlockedNavigationRef.current = true;
      try {
        return !(await flush());
      } finally {
        isHandlingBlockedNavigationRef.current = false;
      }
    },
  });
}
```

Remove React Router's `useBeforeUnload`, resolver effect, and the now-unused `useEffect` import. Preserve the ref because it serializes concurrent navigation attempts independently of autosave state.

- [ ] **Step 4: Verify the workspace route and navigation guard are GREEN**

```sh
mise exec -- pnpm test src/pages/writing-workspace/writing-workspace-page.test.tsx
```

Expected: the complete workspace test file passes, including success, queued-save, failed-save, conflict, and `beforeunload` cases.

- [ ] **Step 5: Commit the workspace migration**

```sh
git add frontend/src/pages/writing-workspace/writing-workspace-page.tsx \
  frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx
git commit -m "refactor(frontend): migrate workspace routing guard"
```

### Task 4: Remove React Router and Persist Frontend Routing Rules

**Files:**
- Modify: `frontend/src/pages/library/library-page.test.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Modify: `frontend/docs/frontend-coding-rules.md`
- Verify: all files under `frontend/src/`

**Interfaces:**
- Consumes: `createAppMemoryRouter`, registered TanStack Router types, and the generated route tree.
- Produces: A frontend with no React Router dependency or import and documented route-file/generated-file ownership.

- [ ] **Step 1: Migrate the isolated library test harness**

Replace `MemoryRouter` with the application memory router:

```tsx
import { RouterProvider } from "@tanstack/react-router";
import { createAppMemoryRouter } from "@/app/app";

function renderLibrary() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppMemoryRouter(["/"]);

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}
```

- [ ] **Step 2: Run the full unit suite before dependency removal**

```sh
mise exec -- pnpm test
```

Expected: all Vitest files pass with both router packages still installed.

- [ ] **Step 3: Remove React Router and verify no references remain**

```sh
mise exec -- pnpm remove react-router-dom
rg -n "react-router-dom|MemoryRouter|createBrowserRouter|createMemoryRouter" src package.json pnpm-lock.yaml
```

Expected: `pnpm remove` succeeds and `rg` exits 1 with no matches.

- [ ] **Step 4: Document the reusable file-based routing rules**

Add a `Routing` subsection to `frontend/docs/frontend-coding-rules.md` with these exact rules:

```markdown
## Routing

- Use TanStack Router for application routing. Route declarations live under
  `src/routes/`, and application components use typed destinations, path
  parameters, and search objects from `@tanstack/react-router`.
- Keep route files focused on route declarations, search validation, and thin
  page adapters. Pages remain responsible for screen composition and TanStack
  Query remains responsible for server state unless an approved design assigns
  a route loader.
- Treat `src/routeTree.gen.ts` as generated source. Commit it so a checkout is
  buildable, regenerate it through the TanStack Router Vite plugin, and never
  edit it by hand.
- Tests use the application route tree with memory history through
  `createAppMemoryRouter`; do not introduce a second test-only route model when
  the production route expresses the behavior under test.
```

- [ ] **Step 5: Run focused and full frontend verification**

Run from `frontend/`:

```sh
mise exec -- pnpm test src/app/app.test.tsx \
  src/pages/new-project/setup-page.test.tsx \
  src/pages/writing-workspace/writing-workspace-page.test.tsx \
  src/pages/library/library-page.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: every command exits 0; the build regenerates an unchanged `src/routeTree.gen.ts`.

- [ ] **Step 6: Verify generated-source stability and scope**

Run from the repository root:

```sh
git diff --check
git status --short
git diff -- frontend/src/routeTree.gen.ts
rg -n "react-router-dom" frontend || true
```

Expected: no whitespace errors, only assigned migration files are changed, the generated tree has no post-build drift, and `rg` prints no React Router reference.

- [ ] **Step 7: Commit cleanup and persistent rules**

```sh
git add frontend/package.json frontend/pnpm-lock.yaml \
  frontend/src/pages/library/library-page.test.tsx \
  frontend/docs/frontend-coding-rules.md frontend/src/routeTree.gen.ts
git commit -m "refactor(frontend): complete TanStack Router migration"
```

### Task 5: Required E2E and Read-Only Review Gates

**Files:**
- Planned output: `frontend/docs/e2e-plans/tanstack-router-migration.md`
- Planned generated tests: an exact `frontend/e2e/*.spec.ts` path selected and owned by the configured generator
- Read-only review: all changed frontend routing, page, shared UI, test, manifest, lockfile, configuration, and documentation paths

**Interfaces:**
- Consumes: Completed Tasks 1-4, this plan, the approved design, acceptance criteria, and fresh focused/full verification output.
- Produces: E2E planning/generation handoffs when the required custom agents exist, followed by a `frontend-review` finding report and main-agent dispositions.

- [ ] **Step 1: Confirm required custom-agent availability**

Run from the repository root:

```sh
test -f .codex/agents/playwright_test_planner.toml
test -f .codex/agents/playwright_test_generator.toml
```

Expected in the current repository: both commands exit 1. Per `frontend/AGENTS.md` and the feature-development workflow, mark the frontend pipeline blocked, do not substitute a generic agent, and do not dispatch downstream application review or claim final completion.

- [ ] **Step 2: When the missing agents are supplied, dispatch E2E planning and generation in order**

Assign the planner the complete route migration, critical flows (library to trope to setup to workspace, direct workspace URL, invalid setup search, unknown-route fallback, back/forward navigation, and unsaved navigation protection), approved design/plan paths, no UI-plan/API/domain impact, and output `frontend/docs/e2e-plans/tanstack-router-migration.md`.

After main-agent approval of that plan, assign its exact revision and one non-overlapping `frontend/e2e/*.spec.ts` output to the configured generator. Run the generated Playwright checks and retain their paths and output.

- [ ] **Step 3: Dispatch the read-only frontend reviewer after E2E editing stops**

Supply `/`, `/new`, `/new/setup`, and `/projects/$projectId/write`; the exact implementation diff boundary; approved design and implementation plan; all changed paths; no UI-plan/OpenAPI/domain impact; acceptance criteria; verification evidence; and read-only commands. Triage every finding, resolve every accepted finding, and re-review any accepted High/Blocking or material behavior repair.

- [ ] **Step 4: Run final main-agent verification**

After the E2E and review gates clear, run from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: both commands exit 0 with no generated route-tree drift and no unresolved accepted review finding.
