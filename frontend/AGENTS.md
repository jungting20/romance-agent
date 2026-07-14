# Frontend Agent Instructions

## Scope

These instructions apply to all work under `frontend/`. They extend the root
`AGENTS.md` and must not weaken its domain-document synchronization, API
approval, working-tree safety, delegation, or final-verification rules.
The project-scoped custom agent that specializes in this work is registered as
`frontend` in `.codex/agents/frontend.toml`.

## Mission

The frontend agent is a task-scoped specialist responsible for frontend code
quality, user-visible behavior, accessibility, and API consumer integration.
It owns only the paths explicitly assigned by the main agent. The main agent
remains responsible for architecture, cross-stack integration, and final
approval.

## Before Editing

1. Read the root `AGENTS.md` and every relevant `docs/domains/*.md` contract.
2. Inspect the nearest existing module, feature, page, and test patterns before
   introducing a new pattern.
3. Confirm the assigned paths, acceptance criteria, and verification commands.
4. For API-consuming work, confirm the main-agent-approved OpenAPI baseline
   and affected `operationId` values. Never edit `docs/api/openapi.yaml`.
5. Preserve unrelated user changes and report a file-ownership conflict before
   editing an overlapping file.

## Architecture Boundaries

- `src/modules/<domain>/domain` owns pure domain models, invariants, and
  operations for one bounded context.
- `src/modules/<domain>/ui` owns UI that belongs to that bounded context.
- `src/features` orchestrates user actions that cross domain boundaries.
- `src/pages` composes modules and features; pages must not own domain rules.
- `src/app` owns application composition, state wiring, routing, and
  infrastructure setup.
- `src/components/ui` contains reusable presentation primitives without
  product-specific domain behavior.
- `src/shared` contains genuinely cross-cutting frontend code. Do not move code
  there merely because two consumers exist.

Do not access another domain's internal files. Cross-domain consumers import a
module through its public `index.ts`, and cross-domain state changes are
coordinated by a feature or application use case.

## TypeScript and Domain Code

- Keep TypeScript strict. Do not weaken compiler, lint, or formatting settings
  to make a change pass.
- Use English identifiers and file names. Keep user-facing product copy and
  domain errors consistent with the existing Korean experience.
- Prefer explicit domain types and discriminated unions over unvalidated
  strings, broad casts, or `any`.
- Keep domain operations deterministic and immutable. Return new values instead
  of mutating entities, arrays, or caller-owned inputs.
- Domain code must not import React, browser APIs, storage, network clients,
  infrastructure adapters, or another domain's internals.
- Use the `@/` alias for imports across source boundaries and relative imports
  within a focused local unit.
- Export only the public surface needed by consumers through the owning
  module's `index.ts`.
- Do not add a dependency when the existing stack or a small local abstraction
  solves the assigned problem. Dependency additions require main-agent scope
  approval.
- When domain meaning or behavior changes, update the matching
  `docs/domains/*.md` contract in the same change as required by root
  instructions.

## React and UI Code

- Keep data flow explicit. Components receive data and callbacks through typed
  props; application and infrastructure state stay outside pure domain code.
- Keep product behavior in modules or features rather than reusable UI
  primitives.
- Use existing `src/components/ui` primitives and established Tailwind patterns
  before creating another primitive or styling system.
- Use semantic HTML, accessible names, visible focus behavior, and
  keyboard-compatible interactions. Do not rely on color alone to communicate
  state.
- Model loading, empty, error, disabled, and success states when the use case
  can reach them.
- Avoid effects for values that can be derived during rendering. Isolate actual
  browser or external-system synchronization in application or infrastructure
  code.
- Keep components and files focused. Extract a unit when it gains an
  independent responsibility, not only because it crosses an arbitrary line
  count.

## TanStack Query and API Access

- Use TanStack Query v5 (`@tanstack/react-query`) for all frontend server state:
  queries for reads and mutations for writes. Do not introduce another
  server-state library or bypass TanStack Query without explicit main-agent
  approval.
- Keep direct HTTP calls out of React components. Put typed transport calls and
  response conversion in API adapters, then call those adapters from query and
  mutation functions.
- Configure `QueryClient` and `QueryClientProvider` in `src/app`. Do not make
  domain modules or reusable presentation components depend on TanStack Query.
- Define stable, feature-scoped query keys. After a successful mutation,
  explicitly invalidate or update every affected cached query.
- Model reachable loading, error, empty, disabled, and success states in the
  consuming UI.
- Test observable query and mutation behavior with Testing Library and MSW,
  including meaningful success and contract-declared error responses.
- When an assigned API-consuming task first needs TanStack Query, adding
  `@tanstack/react-query` v5 is in scope for that task. Other dependency
  additions still require main-agent approval.

## Testing and Verification

- For behavior changes, add or update a focused test before the implementation
  when practical, then confirm the test fails for the missing behavior and
  passes after the change.
- Test domain and feature behavior without rendering React.
- Test UI through observable user behavior with Testing Library; prefer roles,
  labels, and visible text over implementation selectors.
- Cover domain invariant failures and meaningful loading, empty, error, and
  interaction states introduced by the change.
- Keep tests deterministic. Inject time, identifiers, storage, and network
  boundaries rather than depending on ambient global state.
- Run focused tests while iterating. Before handoff, run from `frontend/`:

  ```sh
  mise exec -- pnpm check
  mise exec -- pnpm build
  ```

Report the commands run and their results. Do not claim completion from a
partial test, lint, type-check, or build result.

## E2E Test Planning and Generation

After implementing a frontend feature, use the project-scoped custom agents in
the following order before handing the work back to the main agent:

1. Use `.codex/agents/playwright_test_planner.toml` to inspect the implemented
   behavior and produce an E2E test plan covering the acceptance criteria,
   critical user flows, meaningful failure states, and relevant accessibility
   interactions.
2. Give the approved E2E test plan to
   `.codex/agents/playwright_test_generator.toml` and use it to generate the
   corresponding Playwright tests.

Each delegated E2E task must include the implemented feature's owned paths,
acceptance criteria, relevant domain contracts, test-plan output, and the exact
verification commands. The planner must not modify implementation or test
files. The generator may modify only the explicitly assigned Playwright test
paths and must not change product behavior to make a test pass.

Review the generated tests against the implemented behavior and E2E plan, run
the relevant Playwright verification, and include the plan, generated test
paths, commands, and results in the frontend handoff. If either custom agent is
missing or unavailable, report that blocker to the main agent instead of
silently skipping or replacing the required E2E step.

## API Consumer and MSW Responsibilities

For frontend work that consumes a new or changed operation, use the exact
main-agent-approved `docs/api/openapi.yaml` baseline. Do not author, approve, or
edit the OpenAPI contract. Create or update the aligned frontend types, API
adapters, Mock Service Worker (MSW) handlers, and representative mock response
data within the assigned frontend paths.

- Register shared handlers through `src/mocks/handlers.ts` so browser
  development and Vitest exercise the same transport behavior.
- Cover every affected operation's success response and each meaningful
  contract-declared error response that the UI consumes.
- Keep handler methods, paths, status codes, headers, and payloads aligned with
  the same approved OpenAPI baseline as the frontend types and API adapter.
- Keep scenario-specific overrides in focused tests; do not make one test's
  exceptional response the shared development default.
- OpenAPI examples alone do not satisfy the MSW handler and mock-data
  requirement.
- Do not invent behavior missing from the domain contracts or API decision;
  return unresolved product decisions to the main agent.

If the approved contract cannot support the assigned UI use case, report the
affected operation, consumer impact, and a concrete change request to the main
agent. Continue only after the main agent supplies an approved replacement
baseline. Include the reviewed baseline, affected `operationId` values,
frontend artifact paths, and validation results in the frontend handoff.
