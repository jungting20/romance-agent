# Vitest and Playwright Test Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Vitest from collecting Playwright `*.spec.ts` files while preserving all existing frontend unit and component tests.

**Architecture:** Define Vitest's owned test paths explicitly in the existing Vite/Vitest configuration. Keep Playwright artifacts unchanged and verify the boundary through the aggregate frontend commands.

**Tech Stack:** Vite 8, Vitest 4, TypeScript, Playwright 1.61, pnpm 11

## Global Constraints

- Modify only `frontend/vite.config.ts` for implementation.
- Preserve `frontend/seed.spec.ts` unchanged.
- Do not change application behavior, dependencies, manifests, lockfiles, OpenAPI, domain documents, or generated tests.
- Keep the existing manuscript autosave refactor unchanged.

---

### Task 1: Restrict Vitest Discovery to Frontend Test Files

**Files:**
- Modify: `frontend/vite.config.ts`
- Verify unchanged: `frontend/seed.spec.ts`

**Interfaces:**
- Consumes: Vitest's `test.include` configuration and the existing `src/**/*.test.ts` / `src/**/*.test.tsx` convention.
- Produces: Vitest discovery limited to `src/**/*.test.{ts,tsx}`.

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

- [ ] **Step 4: Run complete frontend verification**

Run from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: both commands exit 0.

- [ ] **Step 5: Verify scope and commit**

Run from the repository root:

```sh
git diff --check
git diff --exit-code -- frontend/seed.spec.ts
git diff --name-only HEAD
```

Expected: no whitespace errors, the seed is unchanged, and only `frontend/vite.config.ts` is uncommitted.

Commit:

```sh
git add frontend/vite.config.ts
git commit -m "test(frontend): separate Vitest and Playwright discovery"
```
