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
2. Before writing or refactoring frontend code, read and follow
   `docs/frontend-coding-rules.md`.
3. Inspect the nearest existing module, feature, page, and test patterns before
   introducing a new pattern.
4. Confirm the assigned paths, acceptance criteria, and verification commands.
5. For API-consuming work, confirm the main-agent-approved OpenAPI baseline
   and affected `operationId` values. Never edit `docs/api/openapi.yaml`.
6. Preserve unrelated user changes and report a file-ownership conflict before
   editing an overlapping file.

## Ownership and Approval Boundaries

- Follow `docs/frontend-coding-rules.md` for architecture, TypeScript, React,
  accessibility, server-state, API-consumer, mock, and testing implementation
  rules.
- Do not add a dependency when the existing stack or a small local abstraction
  solves the assigned problem. Dependency additions require main-agent scope
  approval. When an assigned API-consuming task first needs TanStack Query,
  adding `@tanstack/react-query` v5 is already in scope.
- When domain meaning or behavior changes, update the matching
  `docs/domains/*.md` contract in the same change as required by the root
  instructions.

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

## API Contract Authority and Handoff

For frontend work that consumes a new or changed operation, use the exact
main-agent-approved `docs/api/openapi.yaml` baseline. Do not author, approve, or
edit the OpenAPI contract. Align the in-scope frontend types, API adapters, MSW
handlers, mock data, and tests with that baseline.

If the approved contract cannot support the assigned UI use case, report the
affected operation, consumer impact, and a concrete change request to the main
agent. Continue only after the main agent supplies an approved replacement
baseline. Include the reviewed baseline, affected `operationId` values,
frontend artifact paths, and validation results in the frontend handoff.

Do not invent behavior missing from the domain contracts or API decision;
return unresolved product decisions to the main agent.

## Required Verification and Handoff

Run focused checks while iterating. Before handoff, run from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Report the changed files, implemented behavior, domain-document updates, and
every verification command with its result. Do not claim completion from a
partial test, lint, type-check, or build result.
