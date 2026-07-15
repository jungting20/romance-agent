# Vitest and Playwright Test Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Vitest and Playwright explicit, non-overlapping test discovery while preserving all existing frontend tests.

**Architecture:** Define Vitest's owned test paths explicitly in the existing Vite/Vitest configuration and define Playwright's owned test paths in a dedicated Playwright configuration. Keep the seed unchanged, persist the suffix convention in the frontend coding rules, and verify both runner boundaries.

**Tech Stack:** Vite 8, Vitest 4, TypeScript, Playwright 1.61, pnpm 11

## Global Constraints

- Modify `frontend/vite.config.ts` and create `frontend/playwright.config.ts`
  for the two runner boundaries.
- Document the suffix ownership convention in
  `frontend/docs/frontend-coding-rules.md`.
- Keep this design and plan synchronized with the finalized boundary.
- Preserve `frontend/seed.spec.ts` unchanged.
- Do not change application behavior, dependencies, manifests, lockfiles, OpenAPI, domain documents, or generated tests.
- Keep the existing manuscript autosave refactor unchanged.

---

### Task 1: Define the Two-Way Frontend Test Discovery Boundary

**Files:**
- Modify: `frontend/vite.config.ts`
- Create: `frontend/playwright.config.ts`
- Modify: `frontend/docs/frontend-coding-rules.md`
- Modify: `docs/superpowers/specs/2026-07-15-vitest-playwright-test-boundary-design.md`
- Modify: `docs/superpowers/plans/2026-07-15-vitest-playwright-test-boundary.md`
- Verify unchanged: `frontend/seed.spec.ts`

**Interfaces:**
- Consumes: Vitest's `test.include`, Playwright's `testMatch`, and the existing `.test.ts` / `.test.tsx` and `.spec.ts` conventions.
- Produces: Vitest discovery limited to `src/**/*.test.{ts,tsx}` and Playwright discovery limited to `**/*.spec.ts`.

- [ ] **Step 1: Verify the failing test-runner boundary**

Run from `frontend/`:

```sh
mise exec -- pnpm test
```

Expected: exit 1; 21 test files and 128 tests pass, while `seed.spec.ts` fails during collection because Playwright's `test.describe()` is invoked by Vitest.

- [ ] **Step 2: Add the minimal Vitest include boundary**

In the existing `test` object in `frontend/vite.config.ts`, add:

```ts
include: ["src/**/*.test.{ts,tsx}"],
```

Keep the existing environment, setup file, and CSS options unchanged.

- [ ] **Step 3: Verify the focused regression command is green**

Run from `frontend/`:

```sh
mise exec -- pnpm test
```

Expected: exit 0; 21 test files and 128 tests pass; `seed.spec.ts` is absent from Vitest collection.

- [ ] **Step 4: Verify the failing Playwright-side boundary**

After the Vitest-only restriction and before adding the Playwright config, run
from `frontend/`:

```sh
mise exec -- pnpm exec playwright test --list
```

Expected: exit 1 because Playwright's default discovery collects Vitest
`src/**/*.test.ts` and `src/**/*.test.tsx` files.

- [ ] **Step 5: Add the Playwright boundary and persistent rule**

Create `frontend/playwright.config.ts` with:

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testMatch: "**/*.spec.ts",
});
```

Update `frontend/docs/frontend-coding-rules.md` to record Vitest ownership of
`src/**/*.test.{ts,tsx}` and Playwright ownership of `**/*.spec.ts`. Synchronize
the design and this plan with the finalized two-way scope.

- [ ] **Step 6: Verify both runner boundaries and full frontend checks**

Run from `frontend/`:

```sh
mise exec -- pnpm exec playwright test --list
mise exec -- pnpm test
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: Playwright lists only the seed; Vitest reports 21 files and 128 tests;
all four commands exit 0.

- [ ] **Step 7: Verify scope and commit**

Run from the repository root:

```sh
git diff --check
git diff --exit-code -- frontend/seed.spec.ts
git diff --name-only HEAD
```

Expected: no whitespace errors; the seed and autosave implementation are
unchanged; uncommitted changes are limited to the Playwright config, frontend
coding rules, and synchronized design/plan documents.

Commit:

```sh
git add \
  frontend/playwright.config.ts \
  frontend/docs/frontend-coding-rules.md \
  docs/superpowers/specs/2026-07-15-vitest-playwright-test-boundary-design.md \
  docs/superpowers/plans/2026-07-15-vitest-playwright-test-boundary.md
git commit -m "test(frontend): enforce Playwright test boundary"
```
