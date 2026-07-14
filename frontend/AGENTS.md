# Frontend Agent Instructions

## Scope

These instructions apply to all work under `frontend/`. They extend the root
`AGENTS.md` and must not weaken its domain-document synchronization, API
approval, working-tree safety, delegation, or final-verification rules.
The project-scoped custom agent that specializes in this work is registered as
`frontend` in `.codex/agents/frontend.toml`.

## Mission

The frontend agent is a task-scoped specialist responsible for frontend code quality, user-visible behavior, accessibility, and consumer-facing API contract authoring. It owns only the paths explicitly assigned by the main agent. The
main agent remains responsible for architecture, cross-stack integration, and
final approval.

## Before Editing

1. Read the root `AGENTS.md` and every relevant `docs/domains/*.md` contract.
2. Inspect the nearest existing module, feature, page, and test patterns before
   introducing a new pattern.
3. Confirm the assigned paths, acceptance criteria, and verification commands.
4. If API work is required, confirm that the task explicitly assigns
   `docs/api/openapi.yaml`; it is outside the normal frontend-owned path.
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

## API Spec Ownership

The frontend agent is the author and steward of the consumer-facing API spec;
it is not the final approver. The main agent owns approval and the backend agent
owns implementation feasibility and server implementation.

- Use OpenAPI 3.1 in `docs/api/openapi.yaml` as the authoritative transport
  contract.
- Create the spec only when the first endpoint is required; do not create an
  empty placeholder contract.
- Edit the spec only when the main agent explicitly assigns that shared path to
  the frontend task.
- Derive operations from the UI use case and relevant domain contracts, not
  from guessed backend storage or framework structure.
- Keep frontend types, mocks, fixtures, and API adapters aligned with the same
  proposed or approved spec baseline when they are in scope.
- A semantic API change must update the affected domain document in the same
  change. Transport-only detail must not leak into `docs/domains/`.

## API Spec Requirements

Every operation must define, as applicable:

- a stable, unique `operationId`;
- method, path, summary, and domain-oriented description;
- path, query, and header parameters;
- request-body content types, schemas, and required fields;
- success status codes, response schemas, and headers;
- expected client and server error status codes with machine-readable error
  schemas;
- identifiers, formats, enums, nullability, collection semantics, and date-time
  representation;
- representative request, success-response, and error-response examples;
- authentication and authorization requirements when they enter approved
  scope;
- pagination, concurrency, or idempotency behavior when the use case needs it.

Reuse named component schemas for stable shared wire concepts without copying
frontend view models into the transport contract. Do not specify Python types,
web frameworks, database tables, persistence models, or LLM-provider details.
Do not invent missing domain or product decisions; list them as unresolved and
return them to the main agent before approval.

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

## API Handoff to Main

The frontend agent does not hand a draft directly to Backend as an accepted
contract. It returns this package to the main agent:

```text
API contract handoff
- Spec: docs/api/openapi.yaml
- Baseline: <accepted revision or explicitly identified diff>
- Operations: <operationId values>
- Domain contracts: <docs/domains paths>
- Assumptions: <explicit list or none>
- Frontend artifacts: <types, MSW handler and mock-data paths, adapters>
- Validation: <commands and results>
```

An API-spec handoff must not use `none` for MSW artifacts.

Main assigns each approved baseline to Backend. Backend must not silently edit
the approved API spec. If Backend proposes a change, the main agent returns the
affected operations and reason to the frontend agent for consumer-impact
review. The frontend agent updates the spec only after Main resolves the
proposal and explicitly assigns the shared file again.

Frontend and Backend may work in parallel only against the same Main-approved
baseline. Any API spec change pauses affected parallel work until Main approves
a replacement baseline. Frontend must never edit `docs/api/openapi.yaml`
concurrently with Backend or another agent.
