# Vitest and Playwright Test Boundary Design

## Context

The frontend `pnpm check` command runs Vitest from the `frontend/` root. Vitest's default discovery includes root-level `*.spec.ts` files, so it collects `frontend/seed.spec.ts`. That file is a Playwright seed used by the project's E2E generation workflow and calls Playwright's `test.describe()`, which cannot run inside Vitest. As a result, formatting, linting, type checking, and 128 Vitest tests pass, but the aggregate check exits with an error while collecting the Playwright seed.

## Goal

Give Vitest and Playwright explicit, non-overlapping test ownership so the normal frontend verification command succeeds without deleting or changing the Playwright seed.

## Design

Add an explicit Vitest `include` pattern in `frontend/vite.config.ts`:

```ts
include: ["src/**/*.test.{ts,tsx}"],
```

This makes Vitest own the existing frontend unit and component-test convention under `src/`. The Playwright workflow continues to own root-level and future E2E `*.spec.ts` files. All 21 existing Vitest files already match the proposed pattern.

## Alternatives Considered

### Exclude only `seed.spec.ts`

This is the smallest textual edit, but it encodes one filename instead of the test-runner boundary. A future Playwright spec outside that path would recreate the same failure.

### Delete or relocate the seed and introduce a complete E2E layout

The seed is referenced by the repository's Playwright generation workflow. Relocating it and adding Playwright scripts or configuration would broaden this verification fix into an E2E infrastructure change.

## Scope

- Change only `frontend/vite.config.ts` for the implementation.
- Preserve `frontend/seed.spec.ts` unchanged.
- Do not change application behavior, dependencies, manifests, lockfiles, OpenAPI, domain documents, or generated tests.
- Keep the manuscript autosave refactor commit unchanged.

## Verification

Before the configuration change, run `mise exec -- pnpm test` and confirm that Vitest fails while collecting `seed.spec.ts`.

After the change, run from `frontend/`:

```sh
mise exec -- pnpm test
mise exec -- pnpm check
mise exec -- pnpm build
```

Acceptance criteria:

- Vitest discovers the existing 21 test files and all 128 tests pass.
- `frontend/seed.spec.ts` is not collected by Vitest and remains unchanged.
- `pnpm check` and `pnpm build` exit successfully.
- The final branch diff contains the autosave refactor files, this design/plan documentation, and the single Vitest configuration change only.

## Domain and API Impact

None. This change only separates frontend test-runner discovery. It does not change domain behavior, consumer-facing APIs, UI behavior, or product copy.
