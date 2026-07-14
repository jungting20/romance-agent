# Frontend Agent Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register a project-scoped `frontend` custom agent, add its frontend-specific instructions, and define a shared contract-first API handoff workflow.

**Architecture:** `.codex/agents/frontend.toml` registers the actual named Codex agent and points it to repository guidance. Root `AGENTS.md` owns delegation and the cross-stack approval gate, while nested `frontend/AGENTS.md` owns frontend coding standards and API-authoring responsibilities. `docs/api/openapi.yaml` will be created only when the first endpoint is designed.

**Tech Stack:** Markdown, React 19, TypeScript 7 strict mode, Vite 8, Vitest, Testing Library, OpenAPI 3.1

## Global Constraints

- Preserve all existing root instructions.
- Register the custom agent under `.codex/agents/frontend.toml` with the exact
  name `frontend` and the required `name`, `description`, and
  `developer_instructions` fields.
- Frontend authors and stewards the consumer-facing API spec; Main is the final approver; Backend reviews feasibility and implements the accepted contract.
- Backend must not silently edit an approved API spec.
- Domain-semantic API changes must update the relevant `docs/domains/*.md` in the same change.
- Do not create an empty `docs/api/openapi.yaml` before the first endpoint is needed.
- Do not commit changes unless the user explicitly requests a commit.

---

### Task 1: Add the Shared API Contract Gate

**Files:**

- Modify: `AGENTS.md`

**Interfaces:**

- Consumes: root main-agent responsibility and domain-document synchronization rules.
- Produces: the shared Frontend → Main → Backend contract handoff protocol.

- [ ] **Step 1: Confirm the handoff gate is absent**

Run:

```sh
test -z "$(rg '^## API Contract Workflow$' AGENTS.md)"
```

Expected: exit 0 because the section does not yet exist.

- [ ] **Step 2: Add `API Contract Workflow` after the shared domain rules**

The section must require this sequence:

```text
Frontend drafts OpenAPI 3.1 and returns a handoff package
→ Main reviews and approves an exact spec baseline
→ Main delegates approved operations to Backend
→ Backend implements or returns a concrete change proposal
→ Frontend reviews consumer impact
→ Main approves a new baseline and performs final verification
```

It must name `docs/api/openapi.yaml`, require the spec path, accepted revision,
affected `operationId` values, linked domain contracts, assumptions, aligned
frontend artifacts, and validation results in the handoff. It must prohibit
silent backend spec edits and concurrent frontend/backend edits to the spec.

- [ ] **Step 3: Verify the shared gate**

Run:

```sh
rg -n '^## API Contract Workflow$|Frontend drafts|Main approves|must not silently edit|same approved spec baseline' AGENTS.md
git diff --check -- AGENTS.md
```

Expected: the heading and all workflow gates are present, and whitespace
validation exits 0.

### Task 2: Create the Frontend Agent Instructions

**Files:**

- Create: `frontend/AGENTS.md`

**Interfaces:**

- Consumes: root repository instructions, `docs/domains/*.md`, the current
  modular-monolith layout, and the shared API contract gate from Task 1.
- Produces: frontend coding, architecture, testing, accessibility, API
  authoring, and handoff rules for any task scoped under `frontend/`.

- [ ] **Step 1: Confirm no nested instructions exist**

Run:

```sh
test ! -e frontend/AGENTS.md
```

Expected: exit 0.

- [ ] **Step 2: Create `frontend/AGENTS.md`**

The file must contain these exact responsibility sections:

```text
Scope
Mission
Before Editing
Architecture Boundaries
TypeScript and Domain Code
React and UI Code
Testing and Verification
API Spec Ownership
API Spec Requirements
API Handoff to Main
```

The architecture rules must map domain behavior to
`src/modules/<domain>/domain`, domain UI to `src/modules/<domain>/ui`,
cross-domain workflows to `src/features`, composition to `src/pages`, and
application wiring to `src/app`. It must require strict TypeScript, immutable
domain operations, public module imports through `index.ts`, semantic and
accessible UI, existing primitives before new dependencies, and behavior-based
Vitest and Testing Library tests.

The API rules must identify Frontend as author and steward but not final
approver, use OpenAPI 3.1 at `docs/api/openapi.yaml`, define complete request,
response, error, schema, example, and authentication details, avoid backend
implementation details, and use this handoff template:

```text
API contract handoff
- Spec: docs/api/openapi.yaml
- Baseline: <accepted revision or explicitly identified diff>
- Operations: <operationId values>
- Domain contracts: <docs/domains paths>
- Assumptions: <explicit list or none>
- Frontend artifacts: <types, mocks, adapters, or none>
- Validation: <commands and results>
```

- [ ] **Step 3: Verify the nested instructions**

Run:

```sh
rg -n '^## (Scope|Mission|Before Editing|Architecture Boundaries|TypeScript and Domain Code|React and UI Code|Testing and Verification|API Spec Ownership|API Spec Requirements|API Handoff to Main)$' frontend/AGENTS.md
rg -n 'OpenAPI 3\.1|docs/api/openapi\.yaml|author and steward|final approver|must not|operationId|API contract handoff' frontend/AGENTS.md
git diff --check -- frontend/AGENTS.md
```

Expected: all sections, ownership constraints, spec path, and handoff template
are present, with no whitespace errors.

### Task 3: Register the Project-Scoped Frontend Custom Agent

**Files:**

- Create: `.codex/agents/frontend.toml`
- Modify: `AGENTS.md`
- Modify: `frontend/AGENTS.md`

**Interfaces:**

- Consumes: the shared delegation rules and frontend-specific repository
  guidance from Tasks 1 and 2.
- Produces: a custom agent that Codex can select by the stable name `frontend`.

- [ ] **Step 1: Confirm the custom agent is absent**

Run:

```sh
test ! -e .codex/agents/frontend.toml
```

Expected: exit 0 before registration.

- [ ] **Step 2: Create the custom agent definition**

Create `.codex/agents/frontend.toml` with exactly these top-level fields:

```toml
name = "frontend"
description = "Use for substantial, independently testable React and TypeScript frontend work, including consumer-facing OpenAPI contract drafting."
developer_instructions = """
Read root AGENTS.md, frontend/AGENTS.md, and the relevant domain contracts.
Own only explicitly assigned files, follow the nested frontend rules, return
API drafts to Main for approval, and report verification evidence.
"""
```

The complete `developer_instructions` must also prohibit unassigned backend or
shared-document changes, require domain-document synchronization, and require
the API handoff defined in `frontend/AGENTS.md` when applicable.

- [ ] **Step 3: Connect repository guidance to the named agent**

Update root `AGENTS.md` to require the project-scoped custom agent named
`frontend` for substantial, independently testable frontend work. Update
`frontend/AGENTS.md` to identify `.codex/agents/frontend.toml` as the matching
custom-agent definition.

- [ ] **Step 4: Verify the custom-agent schema and references**

Run with a TOML 1.0 parser available in the environment, then assert:

```text
name == "frontend"
description is a non-empty string
developer_instructions is a non-empty string
```

Also run:

```sh
rg -n 'custom agent named `frontend`|\.codex/agents/frontend\.toml' AGENTS.md frontend/AGENTS.md
```

Expected: the agent definition parses and both repository instruction layers
refer to the same path and name.

### Task 4: Cross-Check and Verify the Instruction Set

**Files:**

- Verify: `AGENTS.md`
- Verify: `frontend/AGENTS.md`
- Verify: `docs/superpowers/specs/2026-07-13-frontend-agent-instructions-design.md`

**Interfaces:**

- Consumes: the shared workflow and frontend-specific rules.
- Produces: a coherent instruction hierarchy with a single API approval owner.

- [ ] **Step 1: Check ownership consistency**

Run:

```sh
rg -n 'final approver|Only the main agent may approve|Main approves' AGENTS.md frontend/AGENTS.md
rg -n 'must not silently edit|must not edit the approved API spec' AGENTS.md frontend/AGENTS.md
```

Expected: both files assign approval to Main and prohibit silent Backend spec
changes.

- [ ] **Step 2: Check the complete diff**

Run:

```sh
git diff --check
git status --short
```

Expected: no whitespace errors; only the approved specification, plan, root
instructions, and frontend instructions are modified or untracked.

- [ ] **Step 3: Run the frontend quality gate**

Run from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: formatting, linting, type checking, all tests, and the production
build pass.
