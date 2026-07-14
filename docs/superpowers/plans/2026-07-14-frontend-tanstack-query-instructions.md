# Frontend TanStack Query Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require frontend agents to use TanStack Query v5 for API-backed server state and document the associated architecture, cache, UI-state, and testing boundaries.

**Architecture:** Add one focused guidance section to `frontend/AGENTS.md` between the existing React/UI and testing sections. Preserve the current domain independence, API specification ownership, and MSW requirements; this documentation-only change does not install or refactor application dependencies.

**Tech Stack:** Markdown agent instructions, TanStack Query v5 (`@tanstack/react-query`), React, TypeScript, Testing Library, MSW

## Global Constraints

- Use `@tanstack/react-query` v5 for all frontend server-state reads and writes.
- Pure domain code must remain independent of TanStack Query, React, browser APIs, and transport details.
- Existing OpenAPI ownership and MSW contract requirements must remain unchanged.
- Do not install the package or refactor the current API implementation in this change.

---

### Task 1: Add frontend TanStack Query API guidance

**Files:**
- Modify: `frontend/AGENTS.md:89`

**Interfaces:**
- Consumes: Existing frontend architecture boundaries and API/MSW rules in `frontend/AGENTS.md`
- Produces: A mandatory `TanStack Query and API Access` instruction section for future frontend-agent work

- [ ] **Step 1: Insert the TanStack Query guidance**

Add this section immediately before `## Testing and Verification`:

```markdown
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
```

- [ ] **Step 2: Verify the documentation diff**

Run:

```sh
git diff --check -- frontend/AGENTS.md
rg -n "TanStack Query and API Access|@tanstack/react-query|QueryClientProvider|feature-scoped query keys|Testing Library and MSW" frontend/AGENTS.md
```

Expected: `git diff --check` exits 0, and `rg` reports the new section and all required architectural/testing terms.

- [ ] **Step 3: Review scope and repository state**

Run:

```sh
git diff -- frontend/AGENTS.md
git status --short
```

Expected: The implementation diff changes only `frontend/AGENTS.md`; the previously committed design and this plan may appear in Git history, but no package or application source file is modified.

- [ ] **Step 4: Commit the instruction update**

```sh
git add frontend/AGENTS.md docs/superpowers/plans/2026-07-14-frontend-tanstack-query-instructions.md
git commit -m "docs(frontend): require TanStack Query for API state"
```
