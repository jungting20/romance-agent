# Frontend Coding Rules

## Purpose and Scope

These are the authoritative implementation rules for code under `frontend/`.
`AGENTS.md` owns agent scope, approval boundaries, delegation, and required
handoff workflows. If the documents conflict, follow `AGENTS.md` and raise the
conflict before editing.

## Architecture and Module Boundaries

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
- Do not access another domain's internal files. Cross-domain consumers import
  a module through its public `index.ts`, and cross-domain state changes are
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

## React, UI, and Accessibility

- Keep data flow explicit. Components receive data and callbacks through typed
  props; application and infrastructure state stay outside pure domain code.
- Keep product behavior in modules or features rather than reusable UI
  primitives.
- Use existing `src/components/ui` primitives and established Tailwind patterns
  before creating another primitive or styling system.
- Use semantic HTML, accessible names, visible focus behavior, and
  keyboard-compatible interactions. Do not rely on color alone to communicate
  state.
- Group related form controls semantically and expose asynchronously rendered
  validation feedback through an appropriate live-region or alert mechanism.
- HTML validation constraints and product guidance must agree with the owning
  domain contract and approved OpenAPI baseline. The frontend must not silently
  add a stricter business invariant; focused tests must cover each required or
  optional behavior enforced by the UI.
- Model loading, empty, error, disabled, and success states when the use case
  can reach them.
- Avoid effects for values that can be derived during rendering. Isolate actual
  browser or external-system synchronization in application or infrastructure
  code.
- Keep components and files focused. Extract a unit when it gains an
  independent responsibility, not only because it crosses an arbitrary line
  count.

## Page Composition and Workflow Ownership

- Pages coordinate data-loading states and compose modules and features. They
  must not directly implement domain workflows or detailed presentation
  behavior.
- Production files under `src/pages` must not import `src/app/infrastructure`.
  Transport requests, transport error classes, and contract-to-UI error
  conversion belong to feature or infrastructure adapters.
- Production page files must not own detailed presentation draft state through
  `useState`, `useReducer`, or `useRef`. Put that state in the feature or
  presentation unit that owns the interaction. TanStack Query and routing hooks
  used for page composition remain allowed.
- A type assertion is not a validation boundary. Production page files must not
  use non-`const` type assertions; narrow route, API, DOM, and other boundary
  values with an authoritative guard, parser, or adapter.
- When one user action coordinates multiple domains, feature state,
  persistence, or UI selection state, move that workflow into a feature-level
  application hook or handler. Pages should pass a concise callback to the
  relevant UI component.
- Keep data flow explicit when extracting logic. Prefer typed inputs, outputs,
  and callbacks over child components that independently acquire hidden
  application state.

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
- Configure the TanStack Router Vite plugin before the React plugin.
- Register the application router type through TanStack Router module
  augmentation. Use typed `Link`, navigation options, path parameters, and
  validated search parameters instead of assembling route strings or casting
  router values.
- Represent every user-visible page state transition in validated URL search
  parameters. Tabs, modals, drawers, filters, sorting, pagination, and selected
  subviews must derive their state from the URL rather than component-local
  state alone.
- Write each user-initiated page state transition as a new browser history
  entry so Back and Forward replay the same sequence of tabs, modals, and other
  page states. Use replacement navigation only for canonicalization, invalid
  search-value recovery, or another transition that is not a user navigation
  step.
- Define a canonical URL representation and validated default for each
  URL-owned state. Reloading or opening a shared URL must reconstruct the same
  visible page state without relying on prior in-memory state.
- Keep router construction and provider composition in `src/app`. Domain
  modules and reusable presentation primitives must not own router setup or
  depend on route-tree internals.
- Test URL-owned page state through direct links, reload-equivalent initial
  navigation, and browser Back and Forward transitions. Assert both the visible
  state and the resulting search parameters.
- Implement application navigation blocking and browser-unload warnings with
  TanStack Router's supported blocker APIs. Preserve the underlying workflow's
  success and failure semantics instead of allowing navigation unconditionally.

## State and Hook Interfaces

- A feature-level application hook must own one primary workflow or state
  machine. When editing, request serialization, conflict retrieval, or conflict
  resolution introduce independently meaningful asynchronous lifecycles,
  extract them into focused hooks or pure state machines.
- Do not model mutually exclusive or sequential phases with multiple booleans
  when their combinations can represent impossible states. Use a discriminated
  union and explicit reducer transitions for phases such as loading, ready,
  resolving, and failed.
- Do not duplicate the same meaning in React state and a ref by default. When a
  ref is required for concurrency control or for reading the latest value from
  an asynchronous callback, make its distinct role and synchronization point
  explicit.
- Do not let one hook accumulate draft ownership, network requests, request
  serialization, error recovery, and dialog presentation state. Keep transient
  component mechanics near their presentation owner, derive modal and other
  user-visible page state from URL search parameters, and keep persistence
  workflows in feature-level application hooks.
- Group closely related hook results into cohesive, named interfaces when a
  consumer would otherwise destructure many fields. Examples include `draft`,
  `save`, `conflict`, and `navigation`.
- Grouping a hook interface must not hide state ownership. Do not move an
  application hook into a presentation component merely to shorten its parent.
- Keep state in the nearest common owner that coordinates its consumers, and
  pass only the state slice and callbacks each child requires.
- Extract browser synchronization, navigation guards, subscriptions, and other
  lifecycle behavior into focused hooks when they are independent of page
  rendering.
- Before adding state or a ref, check whether the value can be derived during
  rendering, modeled as an existing state-machine transition, or signals a
  separate responsibility that should be extracted.
- Reassess state ownership before review when a hook has two or more independent
  asynchronous operations, three or more related boolean states, two or more
  state/ref pairs for the same values, or more than ten ungrouped top-level
  return fields. These are review triggers, not mechanical failure or file-size
  limits.
- Preserve state transitions and race-condition behavior with focused tests
  when extracting a hook or state machine. Splitting code across files alone
  does not constitute a responsibility boundary.
- Editing one field must not erase a server error for an unchanged field. Tie
  error visibility to the affected field or submitted-value snapshot instead
  of resetting the whole mutation from a generic field-change handler.
- Use a reducer only for explicit related transitions or a discriminated state
  machine that prevents impossible states. Do not replace independent setters
  mechanically or duplicate TanStack Query lifecycle state in a reducer.

## Component Extraction and Colocation

- Extract a component when it has an independent responsibility, a meaningful
  interface, or behavior that can be understood and tested in isolation.
- Keep page-specific components colocated with their page or feature. Do not
  promote product-specific components into `src/components/ui` unless they are
  genuinely reusable presentation primitives.
- Prefer a small number of cohesive components over splitting every JSX block,
  constant, or helper into its own file.
- Headers, navigation regions, status displays, dialogs, and conditional panels
  are extraction candidates when they have distinct inputs or behavior.
- Repeated loading, empty, not-found, and error layouts may share a
  presentation shell, but each state must retain the correct semantic role,
  accessible name, actions, and copy.

## TanStack Query and API Adapters

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

## API Consumer, MSW, and Mock Data

- Create or update frontend types, API adapters, MSW handlers, and
  representative mock response data for every assigned new or changed API
  operation.
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

## Testing Rules

- Vitest owns unit and component tests under `src/` matching
  `src/**/*.test.{ts,tsx}`.
- Playwright owns browser and E2E tests matching `**/*.spec.ts`. Do not use the
  `.test.ts` or `.test.tsx` suffix for Playwright tests.
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

## Constants, Helpers, and Defensive Checks

- Keep small page-specific constants and pure helpers near their only consumer.
  Extract them when they are reused, independently tested, or represent a
  distinct responsibility.
- Do not add optional chaining, fallback values, or null checks to values that
  domain types and invariants guarantee. Defensive checks must reflect an
  actual boundary or reachable state rather than hide an inaccurate type
  model.
- When a supposedly required value can be absent at runtime, correct the
  authoritative type, validation boundary, or domain invariant before adding
  scattered fallbacks.

## Refactoring and Verification

- Prefer incremental extraction over rewriting an entire page. Preserve
  observable behavior and keep focused tests passing after each extraction.
- Define refactoring success by clearer responsibilities, narrower interfaces,
  and preserved behavior, not by a target file length.
- Before extracting code, identify the current owner of state, domain behavior,
  browser synchronization, and presentation. Preserve or deliberately improve
  those ownership boundaries.
- When a large page test covers independent responsibilities, split it by
  user-visible flow after the implementation boundaries are stable.
- A responsibility-preserving refactor does not require a domain-document
  update. If domain behavior, ownership, invariants, or cross-domain workflows
  change, update the matching domain contract in the same change.
- Every temporary page-boundary exception must name the file, enumerate the
  exact accepted violations and removal condition, and have an automated test
  that prevents its baseline from increasing.
- The only temporary page-boundary exception is
  `src/pages/writing-workspace/writing-workspace-page.tsx`. Its accepted
  baseline is two infrastructure imports
  (`@/app/infrastructure/api/api-client` and
  `@/app/infrastructure/api/contracts`), four `useState` calls, four `useRef`
  calls, and one non-`const` type assertion. Remove the exception when the full
  writing-workspace page has been extracted into the appropriate feature and
  presentation owners.
