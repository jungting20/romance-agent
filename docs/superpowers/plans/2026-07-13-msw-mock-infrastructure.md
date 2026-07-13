# MSW Mock Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install Mock Service Worker and establish shared browser/Vitest mock infrastructure before making MSW artifacts mandatory for frontend-authored API specs.

**Architecture:** A single `handlers` collection under `src/mocks/` feeds MSW's browser worker and Node test server. Development startup awaits the browser worker before rendering React, while Vitest owns the Node server lifecycle through its existing setup file. Because no OpenAPI operation exists yet, the base handler collection remains empty and a test-only probe verifies interception without inventing a product API.

**Tech Stack:** React 19, TypeScript 7 strict mode, Vite 8, Vitest 4, MSW 2.15

## Global Constraints

- Do not invent an endpoint, request shape, response shape, or domain mock before `docs/api/openapi.yaml` contains an approved operation.
- Keep all domain code independent of MSW; the mock boundary belongs under `frontend/src/mocks/`.
- Reuse one handler collection in browser development and Vitest.
- Enable the browser worker only in Vite development mode and await it before React renders.
- Fail tests on unhandled requests; bypass unhandled requests in the browser development environment.
- Preserve existing user changes. In particular, `frontend/AGENTS.md` is currently untracked and must not be replaced wholesale.
- Do not commit implementation changes unless the user explicitly requests a commit.

---

### Task 1: Install MSW and Generate Its Browser Worker

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Create: `frontend/public/mockServiceWorker.js`

**Interfaces:**

- Consumes: pnpm 11.4 and the current Vite public directory convention.
- Produces: direct `msw` dev dependency and the browser worker asset used by `setupWorker().start()`.

- [ ] **Step 1: Confirm MSW is not a direct dependency**

Run from `frontend/`:

```sh
mise exec -- pnpm list msw --depth 0
```

Expected: no direct `msw` dependency is listed.

- [ ] **Step 2: Install MSW 2.15**

Run from `frontend/`:

```sh
mise exec -- pnpm add --save-dev 'msw@^2.15.0'
```

Expected: `package.json` lists `msw` in `devDependencies`, and the lockfile records the resolved package.

- [ ] **Step 3: Generate and register the service-worker asset**

Run from `frontend/`:

```sh
mise exec -- pnpm exec msw init public --save
```

Expected: `public/mockServiceWorker.js` exists and `package.json` records `public` as MSW's worker directory.

- [ ] **Step 4: Verify the installation artifacts**

Run from `frontend/`:

```sh
mise exec -- pnpm list msw --depth 0
test -s public/mockServiceWorker.js
```

Expected: MSW 2.15.x is a direct dependency and the generated worker file is non-empty.

### Task 2: Add Shared Handlers and the Vitest Server

**Files:**

- Create: `frontend/src/mocks/handlers.ts`
- Create: `frontend/src/mocks/server.ts`
- Create: `frontend/src/mocks/server.test.ts`
- Modify: `frontend/src/test/setup.ts`

**Interfaces:**

- Produces: `handlers: RequestHandler[]` and `server: SetupServerApi`.
- Consumed by: browser adapter in Task 3, global Vitest lifecycle, and future contract-aligned mock handlers.

- [ ] **Step 1: Write the failing interception test**

Create `frontend/src/mocks/server.test.ts`:

```ts
import { http, HttpResponse } from "msw";
import { describe, expect, test } from "vitest";

import { server } from "@/mocks/server";

describe("MSW test server", () => {
  test("intercepts a test-local request handler", async () => {
    server.use(
      http.get("http://localhost/__msw-probe", () => {
        return HttpResponse.json({ intercepted: true });
      }),
    );

    const response = await fetch("http://localhost/__msw-probe");

    await expect(response.json()).resolves.toEqual({ intercepted: true });
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/server.test.ts
```

Expected: FAIL because `@/mocks/server` does not exist.

- [ ] **Step 3: Add the shared empty handler collection**

Create `frontend/src/mocks/handlers.ts`:

```ts
import type { RequestHandler } from "msw";

export const handlers: RequestHandler[] = [];
```

The collection must remain empty until an API operation is specified; the probe handler belongs only in its test.

- [ ] **Step 4: Add the Node server adapter**

Create `frontend/src/mocks/server.ts`:

```ts
import { setupServer } from "msw/node";

import { handlers } from "@/mocks/handlers";

export const server = setupServer(...handlers);
```

- [ ] **Step 5: Connect the server to the existing Vitest lifecycle**

Update `frontend/src/test/setup.ts` to preserve the existing jest-dom import, `ResizeObserverStub`, and Testing Library cleanup while adding this lifecycle:

```ts
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "@/mocks/server";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
  cleanup();
});

afterAll(() => {
  server.close();
});
```

Replace the existing separate `afterEach(cleanup)` call so cleanup runs exactly once.

- [ ] **Step 6: Run the focused test to verify it passes**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/server.test.ts
```

Expected: one passing test proving that the shared server can intercept a test-local handler.

### Task 3: Start Browser Mocking Before React Renders

**Files:**

- Create: `frontend/src/mocks/browser.ts`
- Create: `frontend/src/mocks/enable-mocking.ts`
- Create: `frontend/src/mocks/enable-mocking.test.ts`
- Modify: `frontend/src/main.tsx`

**Interfaces:**

- Consumes: `handlers: RequestHandler[]` from Task 2 and the generated worker asset from Task 1.
- Produces: `worker` and `enableMocking(): Promise<void>`.

- [ ] **Step 1: Write the failing development-bootstrap test**

Create `frontend/src/mocks/enable-mocking.test.ts`:

```ts
import { afterEach, describe, expect, test, vi } from "vitest";

const { start } = vi.hoisted(() => ({
  start: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/mocks/browser", () => ({
  worker: { start },
}));

import { enableMocking } from "@/mocks/enable-mocking";

describe("enableMocking", () => {
  afterEach(() => {
    start.mockClear();
  });

  test("starts the browser worker in development", async () => {
    await enableMocking();

    expect(start).toHaveBeenCalledWith({ onUnhandledRequest: "bypass" });
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/enable-mocking.test.ts
```

Expected: FAIL because `@/mocks/enable-mocking` does not exist.

- [ ] **Step 3: Add the browser worker adapter**

Create `frontend/src/mocks/browser.ts`:

```ts
import { setupWorker } from "msw/browser";

import { handlers } from "@/mocks/handlers";

export const worker = setupWorker(...handlers);
```

- [ ] **Step 4: Add the development-only bootstrap**

Create `frontend/src/mocks/enable-mocking.ts`:

```ts
export async function enableMocking(): Promise<void> {
  if (!import.meta.env.DEV) {
    return;
  }

  const { worker } = await import("@/mocks/browser");

  await worker.start({ onUnhandledRequest: "bypass" });
}
```

- [ ] **Step 5: Await mocking before application render**

In `frontend/src/main.tsx`, import the bootstrap and await it after validating the root element but before calling `createRoot`:

```ts
import { enableMocking } from "@/mocks/enable-mocking";

await enableMocking();

createRoot(root).render(
  // Preserve the existing StrictMode, BrowserRouter, AppProvider, and AppRoutes tree.
);
```

- [ ] **Step 6: Run focused tests and the production build**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/enable-mocking.test.ts src/mocks/server.test.ts
mise exec -- pnpm build
```

Expected: both focused tests pass and the production bundle builds without trying to start the worker.

### Task 4: Make MSW Mocks Mandatory for API Spec Work

**Files:**

- Modify: `frontend/AGENTS.md`

**Interfaces:**

- Consumes: the API-spec ownership and handoff rules already defined in `frontend/AGENTS.md`.
- Produces: a mandatory Spec → MSW handlers/data → Main handoff sequence.

- [ ] **Step 1: Confirm the mandatory MSW rule is absent**

Run from the repository root:

```sh
test -z "$(rg '^## MSW API Mock Requirements$' frontend/AGENTS.md)"
```

Expected: exit 0 because the section does not yet exist.

- [ ] **Step 2: Add the MSW requirements after `API Spec Requirements`**

Add this section without rewriting unrelated instructions:

```markdown
## MSW API Mock Requirements

After creating or changing an API operation in `docs/api/openapi.yaml`, create
or update its Mock Service Worker (MSW) handlers and representative mock
response data before returning the contract to the main agent. An API draft is
not ready for review until these artifacts exist.

- Register shared handlers through `src/mocks/handlers.ts` so browser
  development and Vitest exercise the same transport behavior.
- Cover every affected operation's success response and each meaningful
  contract-declared error response that the UI consumes.
- Keep handler methods, paths, status codes, headers, and payloads aligned with
  the same proposed or approved OpenAPI baseline as the frontend types and API
  adapter.
- Keep scenario-specific overrides in focused tests; do not make one test's
  exceptional response the shared development default.
- OpenAPI examples alone do not satisfy the MSW handler and mock-data
  requirement.
- Do not invent behavior missing from the domain contracts or API decision;
  return unresolved product decisions to the main agent.
```

- [ ] **Step 3: Make MSW artifacts explicit in the handoff**

Change the handoff template's frontend-artifacts line to:

```text
- Frontend artifacts: <types, MSW handler and mock-data paths, adapters>
```

Add a sentence after the template stating that an API-spec handoff must not use
`none` for MSW artifacts. Preserve the existing baseline, operation, domain,
assumption, and validation fields.

- [ ] **Step 4: Verify the instruction contract**

Run from the repository root:

```sh
rg -n '^## MSW API Mock Requirements$|not ready for review|src/mocks/handlers\.ts|OpenAPI examples alone|MSW handler and mock-data paths|must not use `none`' frontend/AGENTS.md
git diff --check -- frontend/AGENTS.md
```

Expected: every mandatory rule and handoff field is present, and whitespace validation exits 0.

### Task 5: Run the Complete Frontend Quality Gate

**Files:**

- Verify: `frontend/package.json`
- Verify: `frontend/public/mockServiceWorker.js`
- Verify: `frontend/src/mocks/handlers.ts`
- Verify: `frontend/src/mocks/browser.ts`
- Verify: `frontend/src/mocks/server.ts`
- Verify: `frontend/src/mocks/enable-mocking.ts`
- Verify: `frontend/src/mocks/server.test.ts`
- Verify: `frontend/src/mocks/enable-mocking.test.ts`
- Verify: `frontend/src/main.tsx`
- Verify: `frontend/src/test/setup.ts`
- Verify: `frontend/AGENTS.md`

**Interfaces:**

- Consumes: all preceding tasks.
- Produces: verification evidence for the completed MSW infrastructure and instruction update.

- [ ] **Step 1: Run formatting, lint, types, and all tests**

Run from `frontend/`:

```sh
mise exec -- pnpm check
```

Expected: formatting check, lint, type checking, and the full Vitest suite all pass.

- [ ] **Step 2: Run the production build**

Run from `frontend/`:

```sh
mise exec -- pnpm build
```

Expected: TypeScript and Vite production build pass; the development-only browser worker is not started at runtime.

- [ ] **Step 3: Review the final diff and instruction alignment**

Run from the repository root:

```sh
git diff --check
git status --short
git diff -- frontend/package.json frontend/src/main.tsx frontend/src/test/setup.ts frontend/AGENTS.md
```

Expected: no whitespace errors; only the approved MSW infrastructure, tests, dependency metadata, generated worker, and nested instruction changes belong to this task. Confirm the code provides the exact shared handler path and runtime behavior that `frontend/AGENTS.md` now requires.
