# TanStack Router File-Based Migration Design

## Context

The frontend currently defines four React Router routes in
`frontend/src/app/app.tsx` and imports `react-router-dom` directly from page,
module, and shared UI components. Tests create React Router memory routers or
mount `MemoryRouter` directly. The writing workspace also relies on router
navigation blocking to flush an unsaved manuscript before leaving and on a
browser unload warning when the save has not completed.

The application already uses TanStack Query, but routing is not type-safe
across links, path parameters, or search parameters. The requested migration
replaces React Router throughout the frontend with TanStack Router's
file-based routing while preserving all current user-visible behavior.

## Goal

Make `@tanstack/react-router` the frontend's only application router and use
the TanStack Router Vite plugin to generate a type-safe route tree from route
files.

The migration must preserve:

- the library route at `/`;
- the trope route at `/new`;
- the project setup route at `/new/setup` and its `trope` search parameter;
- the writing workspace route at `/projects/$projectId/write`;
- fallback navigation from unknown URLs to `/`;
- browser back and forward navigation;
- programmatic navigation after project creation; and
- manuscript flush and unload protection during navigation.

## Architecture

### File-based route tree

Add the TanStack Router Vite plugin before the React plugin. Configure route
generation to read `frontend/src/routes/` and emit
`frontend/src/routeTree.gen.ts`.

Create focused route files for the four application URLs and the root layout.
Route files own only route declarations, search validation, and the minimal
adapters required to render existing page components. Existing pages remain
the owners of loading states and screen composition.

The route layout is:

```text
src/routes/
  __root.tsx
  index.tsx
  new.tsx
  new_.setup.tsx
  projects.$projectId.write.tsx
```

The trailing underscore makes `/new/setup` a non-nested route, so the setup
screen does not render inside the `/new` trope-selection component.

The root route renders the existing tooltip provider and an outlet. A router-level
not-found component replaces unknown locations with `/` without adding a new
screen.

### Router construction

Replace `frontend/src/app/app.tsx` with router construction based on the
generated route tree. Production uses browser history. Tests use the same
route tree with TanStack Router memory history and isolated router instances.
The router type is registered through TanStack Router's module augmentation so
links, navigation, parameters, and search objects are inferred throughout the
frontend.

### Navigation consumers

Replace every `react-router-dom` import with the corresponding
`@tanstack/react-router` API.

- Static links continue to use their current paths.
- Project links and navigation use the typed
  `/projects/$projectId/write` destination plus a `projectId` params object.
- The setup page reads a validated optional `trope` search value from its
  route and redirects to `/new` when the value is absent or invalid for the
  existing workflow.
- The writing workspace obtains `projectId` from its typed route parameters.
- Navigation calls use TanStack Router navigation option objects.

No compatibility wrapper is introduced. This keeps route usage directly
type-checked against the generated tree.

### Manuscript navigation protection

Replace React Router's blocker and separate `useBeforeUnload` registration
with TanStack Router `useBlocker`.

The blocker remains enabled only while the manuscript status is not `saved`.
For application navigation, it awaits the existing `flush()` operation and
allows navigation only when flushing succeeds. Concurrent blocked navigation
attempts remain serialized so one transition cannot start multiple flushes.
For reload, tab close, and other browser unload events,
`enableBeforeUnload` is enabled under the same unsaved condition so the browser
continues to show its native warning.

### Generated source and dependencies

Add `@tanstack/react-router` as an application dependency and
`@tanstack/router-plugin` as a development dependency. Remove
`react-router-dom` only after all imports and tests have migrated.

Commit the generated `frontend/src/routeTree.gen.ts` because builds and type
checks consume it and the repository must remain buildable immediately after
checkout. Application code must not hand-edit generated route-tree content.

## Error and Edge-Case Behavior

- Unknown routes navigate to `/` using replacement semantics, avoiding a
  fallback entry that traps browser history.
- Missing or malformed setup search state preserves the existing redirect to
  `/new`.
- Missing projects and transient workspace failures remain owned by the
  existing writing workspace page and retain their current UI.
- A failed manuscript flush keeps the user on the writing workspace.
- Browser unload uses the browser's native confirmation because asynchronous
  manuscript flushing cannot be guaranteed during unload.

## Testing Strategy

Follow test-driven development. First migrate or add focused tests that express
TanStack Router behavior and confirm they fail before the production migration
makes them pass.

Focused coverage includes:

- rendering each route with the shared memory-router factory;
- redirecting unknown URLs to `/`;
- preserving and reading the setup `trope` search parameter;
- navigating to the typed project workspace URL after creation;
- obtaining the dynamic `projectId` in the writing workspace;
- preserving navigation blocking when manuscript flushing fails or succeeds;
  and
- confirming no `react-router-dom` imports remain.

After focused tests pass, run from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

## Alternatives Considered

### Incremental router coexistence

React Router and TanStack Router could coexist while routes migrate one at a
time. This adds nested routing contexts, duplicates test infrastructure, and
makes navigation blocking ambiguous. With only four routes, the temporary
complexity is larger than the migration risk.

### Compatibility wrapper

A local wrapper could imitate React Router's `Link`, parameter, and navigation
APIs. It would reduce individual call-site diffs but weaken TanStack Router's
typed destination and parameter checking and leave permanent adapter code.

### Code-based TanStack Router

A code-defined route tree avoids generation and a Vite plugin. It is compact
for the current route count, but the requested file-based model gives each
route an explicit boundary and allows route types to grow with the application.

## Scope

- Migrate the complete frontend routing layer and every frontend consumer and
  test from React Router to file-based TanStack Router.
- Preserve existing route URLs and user-visible behavior.
- Preserve the existing page, module, feature, and shared-component ownership
  boundaries.
- Do not add route loaders or move TanStack Query ownership into the router.
- Do not change screen layout, copy, API operations, domain rules, persistence
  semantics, or the previously requested tab URL behavior.

## Acceptance Criteria

- All existing URLs render the same screens as before.
- All links, redirects, path parameters, search parameters, and programmatic
  navigation use TanStack Router.
- Unsaved manuscript navigation still flushes before leaving, blocks on a
  failed flush, and warns on browser unload.
- Unknown paths replace-navigate to `/`.
- `react-router-dom` is absent from source, tests, `package.json`, and the
  lockfile.
- The generated route tree is reproducible through the configured Vite plugin.
- Focused routing tests, `mise exec -- pnpm check`, and
  `mise exec -- pnpm build` pass.

## Domain, API, and UI Impact

There is no domain or consumer-facing API change. The existing routes and
screens remain visually and behaviorally equivalent, so no domain-contract,
OpenAPI, or UI-plan update is required. The router and its test infrastructure
are frontend engineering concerns only.
