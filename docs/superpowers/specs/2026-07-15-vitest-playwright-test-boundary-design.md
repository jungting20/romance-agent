# Vitest and Playwright Test Boundary Design

## Context

The frontend uses both Vitest and Playwright from the `frontend/` root. Their
default discovery rules overlap in both directions:

- Vitest discovers root-level `*.spec.ts` files and collects
  `frontend/seed.spec.ts`, even though that seed calls Playwright's
  `test.describe()` and cannot run inside Vitest.
- Playwright discovers `src/**/*.test.ts` and `src/**/*.test.tsx` files and
  attempts to load the Vitest suites, which cannot run inside Playwright.

Without explicit ownership, `pnpm check` fails while collecting the Playwright
seed and `playwright test --list` fails while collecting the Vitest suites.

## Goal

Give Vitest and Playwright explicit, non-overlapping test ownership so the normal frontend verification command succeeds without deleting or changing the Playwright seed.

## Design

Define reciprocal, non-overlapping discovery rules for both test runners.

Add an explicit Vitest `include` pattern in `frontend/vite.config.ts`:

```ts
include: ["src/**/*.test.{ts,tsx}"],
```

Add an explicit Playwright `testMatch` pattern in
`frontend/playwright.config.ts`:

```ts
testMatch: "**/*.spec.ts",
```

Vitest therefore owns unit and component tests under `src/` using the
`.test.ts` or `.test.tsx` suffix, while Playwright owns browser and E2E tests
using the `.spec.ts` suffix. All 21 existing Vitest files match the Vitest
pattern, and the existing Playwright seed matches the Playwright pattern. The
same conventions are recorded in `frontend/docs/frontend-coding-rules.md` so
future tests preserve the boundary.

## Alternatives Considered

### Exclude only `seed.spec.ts`

This is the smallest textual edit, but it encodes one filename instead of the test-runner boundary. A future Playwright spec outside that path would recreate the same failure.

### Configure only Vitest

Restricting Vitest fixes `pnpm check`, but leaves Playwright free to collect
Vitest `.test.ts` and `.test.tsx` files. That one-way boundary does not satisfy
the goal of non-overlapping ownership.

### Delete or relocate the seed and introduce a complete E2E layout

The seed is referenced by the repository's Playwright generation workflow.
Relocating it or adding browser projects, a development server, execution
scripts, and generated E2E tests would broaden this discovery fix into a full
E2E infrastructure change.

## Scope

- Restrict Vitest discovery in `frontend/vite.config.ts`.
- Restrict Playwright discovery in `frontend/playwright.config.ts`.
- Document the persistent suffix ownership rule in
  `frontend/docs/frontend-coding-rules.md`.
- Keep this design and its implementation plan synchronized with the finalized
  two-way boundary.
- Preserve `frontend/seed.spec.ts` unchanged.
- Do not change application behavior, dependencies, manifests, lockfiles, OpenAPI, domain documents, or generated tests.
- Keep the manuscript autosave refactor commit unchanged.

## Verification

Before the configuration changes:

- Run `mise exec -- pnpm test` and confirm that Vitest fails while collecting
  `seed.spec.ts`.
- After applying only the Vitest restriction, run
  `mise exec -- pnpm exec playwright test --list` and confirm that Playwright
  fails while collecting `src/**/*.test.ts` and `src/**/*.test.tsx` files.

After the change, run from `frontend/`:

```sh
mise exec -- pnpm exec playwright test --list
mise exec -- pnpm test
mise exec -- pnpm check
mise exec -- pnpm build
```

Acceptance criteria:

- Vitest discovers the existing 21 test files and all 128 tests pass.
- Playwright lists only `frontend/seed.spec.ts` and does not collect Vitest
  tests.
- `frontend/seed.spec.ts` remains unchanged.
- `pnpm check` and `pnpm build` exit successfully.
- The final branch diff contains the autosave refactor, synchronized boundary
  design/plan documentation, the frontend coding-rule update, and the two
  runner configuration changes only.

## Domain and API Impact

None. This change only separates frontend test-runner discovery. It does not change domain behavior, consumer-facing APIs, UI behavior, or product copy.
