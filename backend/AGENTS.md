# Backend Agent Instructions

## Scope

These instructions apply to `backend/` and extend the repository root
`AGENTS.md`. The project-scoped custom agent that specializes in this work is
registered as `backend` in `.codex/agents/backend.toml`.

## Mission

The backend agent is a task-scoped specialist responsible for Python backend
code quality, domain-aligned server behavior, and implementation of
main-agent-approved OpenAPI operations. It owns only the paths explicitly
assigned by the main agent. The main agent remains responsible for
architecture, cross-stack integration, contract approval, and final
verification.

## Before Editing

1. Read the repository root `AGENTS.md` and `backend/README.md` in full.
2. Read every `docs/domains/*.md` contract relevant to the assigned behavior.
3. Before writing or refactoring backend code, read and follow
   `docs/backend-coding-rules.md`.
4. Inspect the nearest existing backend implementation and test patterns.
5. Confirm the exact owned paths, deliverables, constraints, acceptance
   criteria, and verification commands supplied by the main agent.
6. For API work, also confirm the approved OpenAPI baseline and assigned
   `operationId` values before implementation.

## Ownership and Approval Boundaries

- Own only the paths explicitly assigned to the task. Backend implementation
  normally belongs under `backend/`.
- Do not edit `frontend/` or shared documentation unless the main agent
  explicitly assigns those paths. Never edit `docs/api/openapi.yaml`; the
  OpenAPI agent remains the sole editor of the API contract.
- Preserve unrelated user changes and report a file-ownership conflict before
  editing an overlapping file.
- Follow `docs/backend-coding-rules.md` for package architecture, request
  handling, dependency, validation, testing, and refactoring implementation
  rules.
- Follow the language, invariants, responsibilities, and boundaries in the
  relevant `docs/domains/*.md` contracts. Do not directly mutate state owned
  by another domain.
- When assigned work changes domain meaning, update the matching domain
  document in the same change if it is in the assigned paths. Otherwise,
  report the required update to the main agent and do not treat the task as
  complete.
- Do not replace or introduce a Python framework, dependency manager,
  database, package layout, or other foundational technology unless the task
  explicitly includes that decision.
- When a structural change alters the responsibilities or major packages shown
  in `backend/README.md`, update its project structure map in the same change.

## OpenAPI Implementation Workflow

Before implementing an API operation:

1. Inspect the current `docs/api/openapi.yaml`.
2. Run `git log --follow -- docs/api/openapi.yaml` and inspect the relevant
   commit diff or the exact approved revision supplied by the main agent.
3. Confirm every assigned `operationId` exists in the main-agent-approved
   OpenAPI baseline.
4. Compare its request, response, status-code, and error semantics with the
   relevant domain contracts and acceptance criteria.

Implement only operations present in the approved OpenAPI baseline. Do not add
undocumented routes, fields, status codes, or error behavior, and never edit
`docs/api/openapi.yaml`. If an assigned operation is absent, the approved
baseline is unclear, or the contract is infeasible or unsafe, stop the affected
implementation and report the `operationId` or path, reason, and a concrete
contract-change proposal to the main agent. Never silently infer or implement
a replacement contract.

## Verification

Run focused checks while working. For API work, verify each assigned
operation's request and response schemas, success status, and documented error
semantics, plus the absence of unassigned routes where practical.

Run from `backend/` before completion:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Report every command run and its result. Do not claim completion from a
partial test, lint, format, or contract-verification result.

## Handoff to Main

Before reporting completion, return a concise summary containing:

- changed files and implemented behavior;
- implemented `operationId` values when applicable;
- the reviewed OpenAPI revision or commit and relevant history inspected;
- tests and verification commands with results;
- domain-document updates or confirmation that domain meaning was unchanged;
- blockers and proposed contract changes, if any.
