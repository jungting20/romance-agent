# Manuscript Autosave Responsibility Refactor Design

## Summary

Refactor `useManuscriptAutosave` without changing its observable behavior or
public return shape. The existing hook remains the public feature-level
orchestrator for draft ownership, idle autosave, serialized saves, flush, retry,
and manuscript-session reset. A new internal focused hook owns the manuscript
revision-conflict workflow: comparison lifecycle, dialog state, local/server
resolution, conflict retries, and stale-request protection.

The refactor is implemented by the project-scoped `frontend` sub-agent and is
verified against the existing autosave behavior suite. It changes no domain
meaning, API contract, consumer interface, product copy, or UI structure.

## Context

`frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts` currently
contains 441 lines and coordinates several independently meaningful
asynchronous lifecycles:

- draft editing and idle autosave scheduling;
- serialized manuscript saves and `flush` waiters;
- canonical server-response adoption;
- revision-conflict detection;
- scene comparison requests and stale-response rejection;
- keep-local and apply-server resolution;
- dialog visibility and comparison/resolution error presentation;
- manuscript-session replacement and in-flight invalidation.

The hook has multiple related booleans, state/ref pairs, and independent async
operations. These are explicit refactoring triggers under
`frontend/docs/frontend-coding-rules.md`. The existing 16 focused tests cover
deadline behavior, save serialization, retry, conflict comparison, both
resolution paths, failure recovery, and manuscript-switch races.

## Goals

- Give autosave and conflict resolution one primary workflow each.
- Preserve the exported `useManuscriptAutosave` API exactly.
- Preserve all current state transitions, timing, race protection, and query
  cache behavior.
- Keep the page consumer unchanged.
- Keep conflict-specific UI state and async operations together.
- Use a narrow internal host interface rather than exposing unrelated main-hook
  state to the conflict hook.
- Keep the existing focused behavior suite passing.

## Non-goals

- Change the 800 ms idle-save deadline.
- Change save serialization, revision semantics, retry behavior, or conflict
  resolution behavior.
- Redesign the conflict dialog or any screen.
- Change OpenAPI operations, transport types, MSW handlers, or mock data.
- Change Manuscript or Projects domain responsibilities or invariants.
- Replace the workflows with a new reducer or state-machine architecture.
- Rename or regroup the public return fields in this refactor.
- Refactor the writing-workspace page or unrelated persistence hooks.

## Considered Approaches

### 1. Extract the conflict workflow into a focused hook — Selected

This approach separates one independently meaningful asynchronous lifecycle
while leaving the proven autosave/save pipeline in place. It provides a clear
responsibility boundary with the smallest race-condition surface.

### 2. Rewrite the complete hook as a reducer or state machine

This could make impossible state combinations more explicit, but it would
simultaneously change autosave, save serialization, conflict handling, and
reset behavior. The larger rewrite is not justified for a behavior-preserving
refactor.

### 3. Extract only small helpers and effects

This would reduce line count without separating ownership. Conflict state,
requests, resolution, and dialog behavior would remain coupled to the autosave
pipeline, so it does not meet the responsibility goal.

## File Structure

### Existing public orchestrator

`frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`

Owns:

- public `useManuscriptAutosave` API and exported status type;
- draft React state and latest-draft ref;
- acknowledged manuscript and revision refs;
- idle autosave scheduling;
- ordinary save request serialization;
- active-save waiters and `flush`;
- non-conflict retry;
- manuscript generation and session replacement;
- construction of the narrow conflict-host interface;
- composition of autosave and conflict results into the unchanged return
  object.

### New internal conflict hook

`frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`

Owns:

- current `ApiRequestError` revision conflict;
- comparison data and latest-comparison ref;
- dialog visibility;
- comparing, comparison-error, resolving, and resolution-error state;
- comparison request identity and stale-response rejection;
- conflict entry from an ordinary save;
- comparison retry and dialog reopening;
- keep-local resolution and retry;
- apply-server resolution and workspace query-cache update;
- conflict reset when the manuscript session changes.

The new file is internal to the feature and is not re-exported as a new public
feature API.

### Existing behavior tests

`frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`

Remains the public-contract regression suite. Tests may receive narrowly scoped
setup cleanup when required by the extraction, but their observable assertions
must not weaken or change. A separate internal-hook test is added only if an
important extracted branch cannot be verified through the public hook without
testing implementation details.

## Internal Collaboration Contract

The public hook supplies the conflict hook a cohesive internal host contract,
implemented with stable callbacks. The exact TypeScript names may follow the
nearest feature conventions, but the responsibilities are fixed:

- read the latest draft without duplicating draft ownership;
- read the current manuscript-generation token;
- determine whether a save is already active;
- begin a conflict-resolution save only when no save is active;
- settle that save and notify existing `flush` waiters;
- set the public autosave status;
- adopt a returned manuscript and revision into draft and acknowledged state;
- preserve the public query-cache update required by apply-server resolution.

The conflict hook must not independently own another copy of draft,
acknowledged revision, save-in-flight, or manuscript generation state. The
public hook remains the single owner of those values. The host contract exposes
operations rather than a broad bag of setters wherever practical.

The conflict hook returns:

- conflict and comparison presentation state;
- keep-local, apply-server, comparison retry, resolution retry, dialog
  visibility, and dialog-open actions;
- an entry action for a detected revision conflict;
- a session-reset action.

Only the public hook consumes these internal entry/reset actions. Page-facing
fields retain their existing names and meanings, including
`retryKeepLocal: keepLocal` behavior.

## Data and Control Flow

### Ordinary edit and save

1. `updateDraft` updates the public hook's draft state/ref.
2. The 800 ms idle effect calls the ordinary save operation.
3. The public hook serializes the request and sends the acknowledged revision.
4. A successful response follows the existing canonical-response adoption and
   follow-up-edit behavior.
5. A non-conflict error sets the existing error status.
6. A revision conflict is delegated to the conflict hook's conflict-entry
   action with the error and latest draft context.

### Conflict comparison

1. Conflict entry stores the API error, sets status to `conflict`, and requests
   comparison for the latest active local scene.
2. The conflict hook records a monotonically increasing request identity and
   the current manuscript-generation token.
3. Comparison results and errors update state only when both identities remain
   current.
4. Dismissed dialogs may be reopened with a fresh comparison built from edits
   made while autosave is suspended.

### Keep local

1. The conflict hook builds a resolved manuscript by applying local scene
   content to the comparison's complete server manuscript.
2. It requests a save at the comparison's server revision through the shared
   save coordination boundary.
3. Success adopts the saved manuscript/revision and clears conflict state.
4. Another revision conflict refreshes comparison using the same local content.
5. A non-conflict failure keeps the dialog open and exposes the existing
   resolution retry state.

### Apply server

1. The comparison's server manuscript and revision become the draft and
   acknowledged state.
2. Conflict presentation state closes and status becomes `saved`.
3. The existing project workspace query cache is updated with the adopted
   manuscript and revision.

### Manuscript session replacement

1. The public hook increments its generation and settles active-save waiters as
   it does today.
2. It resets draft and acknowledged state to the new manuscript.
3. It invokes the conflict hook reset, which invalidates comparison request
   identity and clears every conflict presentation/resolution state.
4. Late ordinary-save, comparison, or resolution responses cannot mutate the
   new session.

## Error and Race Semantics

The following behavior is invariant:

- ordinary saves do not overlap;
- `flush` waits for active saves and continues until saved or terminal error;
- edits made during a save are retained and saved serially;
- revision conflict suspends autosave;
- stale comparison or resolution work from a previous manuscript is ignored;
- comparison failure and resolution failure remain distinct;
- conflict-resolution save failure can be retried with the same server-based
  resolved manuscript;
- dialog dismissal does not erase the conflict, and reopening uses current
  local content;
- apply-server performs no save request.

The refactor must not replace generation/request tokens with closure-only
checks or remove refs that provide the latest value to asynchronous callbacks.

## Public Compatibility

The writing-workspace consumer must continue receiving these fields with the
same types and semantics:

- `draft`, `updateDraft`, `status`, `retry`, and `flush`;
- `conflict` and `conflictComparison`;
- dialog, comparison, and resolution status flags;
- `keepLocal`, `retryKeepLocal`, and `applyServer`;
- `retryConflictComparison`, `setConflictDialogVisibility`, and
  `openConflictDialog`.

No consumer change is expected. If the extraction requires a page change, the
frontend agent must stop and report the reason rather than silently changing
the public contract.

## Testing and Verification

The frontend agent uses behavior-preserving TDD:

1. Run the existing focused test file before extraction and confirm all 16
   behaviors pass.
2. Perform the extraction incrementally, keeping the public test suite green.
3. Add a failing focused test first only if the extraction exposes an
   untested observable behavior needed to protect the boundary.
4. Run the focused test file after the extraction.
5. Run the full frontend commands from `frontend/`:

   ```sh
   mise exec -- pnpm check
   mise exec -- pnpm build
   ```

Verification must also confirm:

- the page consumer is unchanged;
- no API, MSW, domain, or product-copy files changed;
- the public return field set is unchanged;
- the extracted hook does not duplicate primary draft/save/session ownership;
- all existing race and error tests retain their assertions.

Because this is not a user-visible feature or screen change, the Playwright
planning/generation workflow is not required. The existing hook tests provide
the relevant behavioral verification.

## Domain and Contract Impact

This refactor preserves the Manuscript contract, including immutable scene
content updates and draft comparison semantics. It also preserves the Projects
contract behavior that successful manuscript persistence updates workspace
state. No domain document update is required because responsibilities,
invariants, use cases, inputs, outputs, and dependency directions do not
change.

No OpenAPI update is required because request, response, status, error,
revision, and operation semantics do not change.

## Frontend Sub-agent Assignment

The main agent assigns the project-scoped `frontend` sub-agent ownership of:

- `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`;
- `frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`;
- `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`
  only when focused test changes are required.

The sub-agent must not edit the writing-workspace page, shared API contract,
domain documents, backend files, package manifests, lockfiles, or unrelated
frontend files. It must read the root and frontend instructions, frontend
coding rules, `docs/domains/manuscript.md`, `docs/domains/projects.md`, nearby
persistence hooks, the complete current hook, and its tests before editing.

## Acceptance Criteria

- `useManuscriptAutosave` keeps its existing public return shape and consumer
  semantics.
- Draft ownership, idle autosave, ordinary save serialization, `flush`, retry,
  and manuscript-session reset remain in the public hook.
- Conflict comparison, dialog state, resolution state, resolution operations,
  conflict entry, and conflict reset move to one focused internal hook.
- The internal boundary does not duplicate draft, acknowledged revision,
  save-in-flight, or manuscript-generation ownership.
- The 800 ms deadline and all existing race, retry, error, and resolution
  behaviors are preserved.
- The writing-workspace page is unchanged.
- The 16 existing focused behaviors pass without weakened assertions.
- `mise exec -- pnpm check` passes from `frontend/`.
- `mise exec -- pnpm build` passes from `frontend/`.
- No domain document, OpenAPI, backend, package manifest, lockfile, product
  copy, or unrelated frontend file changes.
