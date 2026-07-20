# Frontend Page Boundary Enforcement Design

## Goal

Prevent page components from accumulating form draft ownership, transport
error handling, unsafe boundary casts, and detailed workflow presentation.
Enforce the boundary through both persistent frontend coding rules and checks
that fail `pnpm check`.

The project setup screen is the first migration target. The existing writing
workspace page remains temporary legacy debt, but the permitted debt must not
grow.

## Problems Being Addressed

`src/pages/new-project/setup-page.tsx` currently combines route handling,
form draft state, transport request construction, `ApiRequestError` mapping,
mutation state, navigation, and detailed form markup. It also casts a
string-valued trope identifier to the transport enum, clears every mutation
error whenever any input changes, and imposes UI validation and copy that do
not fully agree with the domain and OpenAPI contracts.

The existing frontend rules describe thin pages, explicit validation
boundaries, and feature-owned workflows, but they do not define mechanically
checkable page restrictions or a controlled process for legacy exceptions.

## Selected Enforcement Approach

Use three complementary layers without adding a dependency:

1. Add explicit normative rules to
   `frontend/docs/frontend-coding-rules.md`.
2. Add an Oxlint configuration that gives immediate feedback for forbidden
   page imports and React state ownership.
3. Add a TypeScript-AST-based Vitest architecture test that enforces the same
   boundary, rejects unsafe page assertions, and freezes the exact legacy
   baseline for the writing workspace page.

Oxlint alone cannot express the exact legacy baseline or reliably distinguish
safe `as const` declarations from assertions used to bypass boundary
validation. A standalone dependency-boundary package is unnecessary because
the repository already contains Oxlint, Vitest, and the TypeScript compiler
API.

## Persistent Coding Rules

Extend `frontend/docs/frontend-coding-rules.md` in the owning sections with
the following requirements:

- Production page files may coordinate route input, query state, feature
  callbacks, and navigation, but must not import `src/app/infrastructure`.
  Transport requests, transport error classes, and contract-to-UI error
  conversion belong to feature or infrastructure adapters.
- Production page files must not own detailed presentation draft state through
  `useState`, `useReducer`, or `useRef`. That state belongs to the feature or
  presentation unit that owns the interaction. This restriction does not ban
  TanStack Query hooks or routing hooks used by a page to compose screen
  states.
- A type assertion is not a validation boundary. Route search values, decoded
  API values, DOM values, and other untrusted strings must be narrowed by an
  authoritative domain type guard, parser, or adapter before they are used as
  domain or transport identifiers. Production page files must not use
  non-`const` type assertions.
- HTML validation constraints and user-facing guidance must agree with the
  owning domain contract and approved OpenAPI contract. The frontend must not
  silently add a stricter business invariant. Tests for a form change must
  cover any contract-backed required/optional behavior that the UI enforces.
- Editing one field must not erase a server error for an unchanged field.
  Field-error visibility must be tied to the affected field or submitted-value
  snapshot. Do not call a whole-mutation reset from generic field-change
  handlers when it clears unrelated errors.
- Use a reducer only when several values participate in explicit, related
  transitions or when a discriminated state machine prevents impossible
  states. Do not introduce a reducer merely to replace several independent
  setters, and do not duplicate TanStack Query's pending, error, or success
  state in a reducer.
- Related form controls use semantic grouping, and asynchronously rendered
  validation feedback must be announced through an appropriate live region or
  alert mechanism.
- Every temporary page-boundary exception must name the file, enumerate the
  exact accepted violations, state the removal condition, and have a test that
  prevents the baseline from increasing. New exception files are not allowed
  without an approved design and matching rule-document update.

## Oxlint Enforcement

Add `frontend/.oxlintrc.json` using the installed Oxlint configuration schema.
For production files under `src/pages/`, configure `no-restricted-imports` to:

- reject imports matching `@/app/infrastructure/**`; and
- reject the named React imports `useState`, `useReducer`, and `useRef`.

Exclude page test files. Temporarily exclude
`src/pages/writing-workspace/writing-workspace-page.tsx` from this override;
its exact baseline is governed by the architecture test instead of being an
unbounded exception.

The existing `pnpm lint` and `pnpm check` commands continue to be the entry
points. No new package script or dependency is required.

## Architecture Test and Legacy Baseline

Add `frontend/src/architecture/page-boundaries.test.ts`. It uses the installed
TypeScript compiler API to inspect production TypeScript and TSX files under
`src/pages/`. Test files are excluded.

For every production page source, collect:

- imports from `@/app/infrastructure/**`;
- calls to `useState`, `useReducer`, and `useRef`; and
- TypeScript assertions other than `as const`.

Files absent from the legacy allowlist must have no collected violations. The
only initial allowlist entry is
`src/pages/writing-workspace/writing-workspace-page.tsx`, with this exact
baseline:

- infrastructure imports:
  `@/app/infrastructure/api/api-client` and
  `@/app/infrastructure/api/contracts`;
- local state-hook calls: four `useState` calls and four `useRef` calls;
- non-`const` type assertions: one.

The comparison is line-independent so ordinary movement does not break the
test, but adding another restricted import, state-hook call, assertion, or
exception file does. Reducing the legacy counts is permitted only when the
allowlist is reduced in the same change. The allowlist comment identifies full
writing-workspace extraction as its removal condition.

## Project Setup Refactor

Refactor the setup flow so `SetupPage` is a thin route-aware composition unit.
It retains only:

- validated trope lookup and invalid-search redirection;
- composition of the project-creation feature; and
- navigation to the server-returned project workspace after success.

Move the setup draft, request construction, mutation-error translation, and
form presentation into the existing `src/features/create-project` boundary.
Expose typed feature interfaces so the page does not import transport types or
errors.

Use one cohesive typed draft plus a submitted-value snapshot. Do not introduce
a reducer. While a mutation is pending, inputs and duplicate submission remain
disabled. After a server validation response, a field error remains visible
until its corresponding submitted value changes or a new submission replaces
the result. Changing the title therefore hides the stale title error without
removing an unchanged protagonist error. A form-level failure may be hidden
after any draft edit because it is not attached to one unchanged field.

Define `TropeId` at the Story Design domain boundary and export it through the
module public API. Type trope templates, story concepts, route search
validation, feature inputs, and the transport contract from that authoritative
type. Remove the setup page cast; invalid route strings are rejected by the
type guard and follow the existing replacement redirect to `/new`.

Align the form with the approved contracts:

- title remains required, but its guidance must no longer claim that an empty
  title is accepted;
- logline no longer adds a frontend-only non-empty requirement;
- both protagonist names remain required;
- the protagonist controls use `fieldset` and `legend`; and
- asynchronously rendered validation feedback is exposed through an
  appropriate live region or alert semantic while retaining input
  descriptions and invalid state.

This is a behavior-preserving ownership refactor except for correcting the
identified validation, error-clearing, copy, typing, and accessibility defects.
It does not change domain meaning.

## Test Coverage

Add or update focused tests to prove:

- new production page files cannot import infrastructure, own the restricted
  local state hooks, or use non-`const` assertions;
- the writing workspace legacy baseline passes unchanged and the architecture
  test would fail if any baseline category increases;
- invalid trope search values redirect to `/new` without a cast;
- a blank logline can be submitted because the contracts do not forbid it;
- the title guidance agrees with the required-title behavior;
- editing one field removes only that field's stale server error;
- the protagonist error remains associated with both inputs and the inputs are
  semantically grouped;
- asynchronous field and form errors are announced accessibly; and
- the existing pending, duplicate-submission, generic-error, success request,
  and server-returned navigation behaviors remain intact.

The implementation must follow the repository's required frontend E2E
planning and generation workflow for the affected setup screen.

## Scope Boundaries

In scope:

- frontend coding-rule updates;
- Oxlint page-boundary configuration;
- the page-boundary architecture test and exact legacy baseline;
- setup-page and create-project feature refactoring;
- authoritative frontend `TropeId` alignment; and
- focused component, feature, architecture, and required E2E tests.

Out of scope:

- refactoring `writing-workspace-page.tsx` beyond registering its frozen
  baseline;
- backend changes;
- OpenAPI changes;
- domain-contract meaning changes;
- new dependencies; and
- unrelated page or component cleanup.

No `docs/domains/*.md` update is required because the implementation is being
aligned to the existing invariants rather than changing them.

## Acceptance Criteria

- `SetupPage` contains no infrastructure import, restricted React state hook,
  or non-`const` assertion.
- Project setup draft and transport-error translation are owned by the
  create-project feature through typed public interfaces.
- Story Design provides the authoritative `TropeId`, and the setup flow
  contains no cast from an unvalidated string to that type.
- Setup validation, copy, field-error lifetime, semantic grouping, and async
  announcements match this design and the existing domain/OpenAPI contracts.
- Oxlint reports a new forbidden page import or restricted React state import
  as an error.
- The architecture test rejects any new page violation and any increase to the
  writing workspace legacy baseline.
- The legacy exception is documented and limited to
  `writing-workspace-page.tsx`; that page is otherwise unchanged.
- No dependency, backend file, OpenAPI operation, or domain contract is
  changed.
- From `frontend/`, both commands succeed:

  ```sh
  mise exec -- pnpm check
  mise exec -- pnpm build
  ```
