# Romance Agent Repository Instructions

## Scope

These instructions apply to the entire repository unless a more specific
`AGENTS.md` exists in a subdirectory.

## Repository Map

- `frontend/` contains the React, Vite, and TypeScript application.
- `backend/` is reserved for the future Python API application. Its framework
  and package layout have not been selected yet.
- `docs/domains/` contains the technology-independent domain contracts and is
  the source of truth for domain language, responsibilities, invariants, and
  boundaries.
- `docs/superpowers/` contains design and implementation records.
- Root `mise.toml` and `mise.lock` define the shared toolchain.

## Main Agent Responsibilities

The main agent owns the end-to-end result. It must:

1. Read the relevant domain contracts before changing domain behavior.
2. Treat the implementation and its matching domain-document update as one
   indivisible change whenever domain content changes.
3. Define scope, acceptance criteria, and cross-boundary contracts.
4. Decide whether frontend or backend work is substantial and independent
   enough to delegate.
5. Integrate delegated work and resolve contract or implementation conflicts.
6. Run the final checks for every affected application.

Delegation does not transfer responsibility for architecture, integration, or
verification away from the main agent.

## Frontend, OpenAPI, and Backend Subagents

Use task-scoped subagents when multi-agent support is available.

- For substantial, independently testable work under `frontend/`, spawn the
  project-scoped custom agent named `frontend`, defined in
  `.codex/agents/frontend.toml`.
- For every new or changed consumer-facing API operation, assign
  `docs/api/openapi.yaml` to the project-scoped custom agent named `openapi`,
  defined in `.codex/agents/openapi.toml`. It is the only subagent that authors
  or edits the OpenAPI contract.
- Delegate substantial, independently testable work under `backend/` to a
  backend subagent.
- For cross-stack features, the main agent must define the contract scope and
  acceptance criteria before assigning the OpenAPI draft. Frontend and backend
  implementation may run in parallel only after the main agent approves the
  same OpenAPI baseline and their file ownership does not overlap.
- Do not create a subagent for a trivial edit, a tightly coupled change, or a
  task whose boundary is still unclear.

Every delegated task must state the owned paths, expected deliverable,
constraints, and verification commands. A subagent must not edit another
application or shared documentation unless that work is explicitly assigned.
Two agents must not modify the same file concurrently.

If delegated work can change domain content, the task must also assign the
matching `docs/domains/*.md` update to that subagent or explicitly retain that
update for the main agent. The delegated work is not complete until both the
implementation and domain documentation are synchronized.

Subagents are temporary specialists, not sources of persistent project truth.
They must reload the relevant repository instructions and domain contracts for
each task.

## Shared Contracts and Domain Boundaries

- Use the names and meanings defined in `docs/domains/` consistently in code,
  tests, API contracts, and product copy.
- A domain must not directly mutate state owned by another domain. Cross-domain
  workflows belong to application use cases or features.
- Establish request and response shapes, error semantics, and ownership of
  validation before implementing a frontend-backend integration.
- Do not duplicate a business rule across frontend and backend without making
  its authoritative owner explicit.
- Any change to a domain's responsibilities, ubiquitous language, core model,
  invariants, use cases, inputs, outputs, or explicit non-responsibilities must
  update the matching `docs/domains/*.md` document in the same change.
- If relationships or dependency directions between domains change, also
  update the context map in `docs/domains/README.md` in the same change.
- Do not defer a required domain-document update to a later task or follow-up
  change. A domain-affecting task is incomplete without it.
- A refactor that provably preserves domain meaning and behavior does not
  require a domain-document rewrite.

## API Contract Workflow

`docs/api/openapi.yaml` is the authoritative consumer-facing API contract and
uses OpenAPI 3.1. Create it only when the first endpoint is needed. The
OpenAPI agent exclusively authors and stewards this contract, but the main
agent is its final approver.

Use this workflow for every new or changed API operation:

1. **Main scopes:** The main agent defines the UI use case, domain behavior,
   acceptance criteria, validation ownership, and unresolved decisions, then
   explicitly assigns `docs/api/openapi.yaml` to the OpenAPI agent.
2. **OpenAPI drafts:** The OpenAPI agent derives the operation from the
   assigned use case and relevant domain documents, drafts the complete
   request, response, and error contract, and returns the contract handoff
   defined in `.codex/agents/openapi.toml`.
3. **Main approves:** The main agent reviews domain consistency, scope, error
   semantics, and compatibility. Only the main agent may approve an exact spec
   baseline for implementation.
4. **Main delegates:** The main agent gives frontend and backend agents the
   approved spec path and baseline, affected operations, acceptance criteria,
   and required contract verification. Frontend aligns its consumer types,
   adapters, and mocks; Backend implements the approved operations.
5. **Implementers review:** Frontend reports consumer-impact concerns and
   Backend reports infeasible or unsafe contract details to the main agent.
   Neither implementation agent edits the API spec.
6. **OpenAPI revises:** The main agent resolves each proposal and, when a spec
   change is approved, assigns the affected operations back to the OpenAPI
   agent. Any edit creates a new proposed baseline requiring main approval.
7. **Main verifies:** The main agent confirms that the final spec, frontend
   consumer, backend behavior, contract tests, and domain documents agree.

Frontend and backend tasks may proceed in parallel only after Main approves
the same approved spec baseline for both tasks. Any spec change invalidates
that baseline until Main approves a replacement. The OpenAPI agent is the sole
editor of `docs/api/openapi.yaml`; frontend and backend agents must never edit
it.

## Frontend Guidance

- Preserve the modular-monolith structure and existing bounded contexts.
- Keep pure domain logic independent of React, browser APIs, persistence, and
  infrastructure adapters.
- Pages compose modules and features; cross-domain orchestration belongs in
  features rather than domain modules.
- Run frontend commands from `frontend/`:

  ```sh
  mise exec -- pnpm check
  mise exec -- pnpm build
  ```

## Backend Guidance

- Read `backend/README.md` before backend work.
- Do not choose a Python framework, dependency manager, database, or package
  layout as part of an unrelated task.
- When backend implementation begins, keep domain rules independent of the web
  framework, persistence layer, and external LLM provider.
- Add backend-specific verification commands here or in a nested
  `backend/AGENTS.md` after the backend toolchain is established.

## Working Tree and Verification

- Preserve existing user changes and avoid unrelated refactoring.
- Do not use destructive Git commands to discard work.
- Verify the smallest relevant checks during implementation, then run the full
  affected-application checks before completion.
- Before completing a domain-affecting task, compare the implementation diff
  with the relevant `docs/domains/*.md` diff and confirm they describe the same
  behavior and boundaries.
- The main agent must review delegated diffs and integration behavior before
  claiming the task is complete.

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the
repo root), reach for it before grep, find, or reading files when you need to
understand or locate code:

- Prefer the `codegraph_explore` MCP tool when available. It returns relevant
  symbols, verbatim source, and call paths, including dynamic-dispatch hops.
- The shell fallback is `codegraph explore "<symbol names or question>"`.

If there is no `.codegraph/` directory, skip CodeGraph entirely; indexing is
the user's decision.
<!-- CODEGRAPH_END -->
