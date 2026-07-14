# Frontend Agent Instructions Design

## Goal

Create a project-scoped `frontend` custom agent and repository instructions for
its task-scoped frontend work. The agent owns frontend implementation quality
and authors the consumer-facing API contract, while the main agent approves
cross-boundary contracts and the backend agent reviews feasibility and
implements the accepted contract.

## Files and Scope

- Add `.codex/agents/frontend.toml` to register the project-scoped custom agent
  with the required `name`, `description`, and `developer_instructions` fields.
- Add `frontend/AGENTS.md` for frontend-specific coding, architecture, testing,
  accessibility, and API-authoring rules.
- Extend root `AGENTS.md` with the shared API contract handoff workflow that
  both frontend and backend tasks must follow and with an explicit instruction
  to spawn the custom agent named `frontend` for suitable frontend work.
- Use `docs/api/openapi.yaml` as the authoritative OpenAPI 3.1 contract after
  the first backend endpoint is designed. Do not create an empty contract file
  before an endpoint is needed.

The nested frontend instructions may refine the root instructions but must not
weaken domain-document synchronization, working-tree safety, or main-agent
integration responsibility.

## Custom Agent Definition

`.codex/agents/frontend.toml` registers the actual Codex custom agent. It uses
the stable name `frontend`, describes when substantial frontend or API-contract
work should be delegated to it, and instructs every spawned instance to read
the root and nested `AGENTS.md` files plus relevant domain contracts before
working. Model, reasoning, sandbox, and tool settings inherit from the parent
session unless a later approved requirement needs an override.

The custom-agent instructions remain concise and reference
`frontend/AGENTS.md` rather than duplicating all coding rules. They restrict the
agent to explicitly assigned files, require Main approval for API contracts,
and require a verification-and-handoff summary at completion.

## Frontend Coding Rules

The frontend agent must preserve the existing modular monolith:

- `modules/<domain>/domain` contains pure domain behavior and cannot depend on
  React, browser APIs, persistence, or another domain's internals.
- `modules/<domain>/ui` contains UI owned by that bounded context.
- `features` orchestrates cross-domain user actions.
- `pages` composes modules and features without owning domain behavior.
- `app` owns application composition, state wiring, and infrastructure setup.
- `components/ui` contains reusable UI primitives rather than product-specific
  behavior.

New TypeScript must remain strict, use the `@/` alias for source imports, avoid
mutation in domain operations, and expose module consumers through the
module's public `index.ts`. React work must use controlled data flow, semantic
HTML, accessible names, keyboard-compatible interaction, and existing UI
primitives before introducing new primitives or dependencies.

Behavior changes require focused Vitest tests. Domain and feature behavior is
tested without React; UI behavior is tested through observable user behavior
with Testing Library. Completion requires `mise exec -- pnpm check` and
`mise exec -- pnpm build` from `frontend/`.

## API Contract Ownership

The frontend agent is the author and steward of the consumer-facing API spec,
not its unilateral approver. When a feature needs an API, the assigned frontend
task must explicitly include ownership of `docs/api/openapi.yaml`, because that
path is outside `frontend/`.

The frontend agent derives each operation from the relevant domain contract
and the UI use case. Each operation must define:

- a stable `operationId`;
- request parameters and body schemas;
- success status codes and response schemas;
- expected error status codes and machine-readable error schemas;
- nullability, required fields, identifiers, formats, and enums;
- representative request, success, and error examples;
- authentication requirements when authentication enters scope.

The API spec describes the transport contract, not backend framework,
database, persistence, or LLM-provider choices. A spec change that changes
domain meaning must update the matching `docs/domains/*.md` file in the same
change.

## API Handoff Workflow

1. **Frontend drafts:** The frontend agent writes or updates
   `docs/api/openapi.yaml`, checks it against the UI use case and relevant
   domain documents, and aligns frontend types, mocks, or API adapters with the
   draft when those artifacts are in scope.
2. **Frontend reports:** The frontend agent returns a handoff package containing
   the spec path, affected `operationId` values, linked domain documents,
   assumptions, frontend artifacts already aligned, and validation performed.
3. **Main approves:** The main agent reviews domain consistency, feature scope,
   error semantics, and backward compatibility. Only the main agent may approve
   the draft for backend implementation.
4. **Main delegates:** The main agent gives the backend agent the approved spec
   path and revision, affected operations, implementation acceptance criteria,
   and required contract verification.
5. **Backend reviews and implements:** The backend agent reviews feasibility
   and implements the approved operations. It must not silently edit the API
   spec. If a change is necessary, it returns a concrete proposed contract
   change and reason to the main agent before continuing with the affected
   implementation.
6. **Frontend evaluates changes:** The main agent routes backend change
   proposals to the frontend agent for consumer-impact review. The frontend
   agent updates the spec only after the main agent resolves the proposal.
7. **Main verifies:** The main agent verifies that the final spec, frontend
   consumer, backend behavior, domain documentation, and contract tests agree.

Frontend and backend work may proceed in parallel only after main-agent
approval and only against the same approved spec revision. Any spec change
invalidates that shared baseline until the main agent approves a new revision.

## Error and Conflict Handling

- Missing product or domain decisions block approval; the frontend agent must
  state the unresolved decision rather than invent backend behavior.
- Backend feasibility objections must cite the affected operation and propose
  a contract-level alternative instead of changing implementation semantics
  silently.
- The main agent resolves disagreements and assigns ownership for every shared
  file so frontend and backend agents never edit `docs/api/openapi.yaml`
  concurrently.
- A cross-stack feature is incomplete if the implementation differs from the
  accepted API spec or if a required domain-document update is missing.

## Verification

The instruction change is complete when:

- `.codex/agents/frontend.toml` parses as TOML and defines the required
  `name`, `description`, and `developer_instructions` fields;
- the custom agent name is exactly `frontend` and root `AGENTS.md` requests it
  by that name for suitable frontend work;
- `frontend/AGENTS.md` contains the frontend coding and API-authoring rules;
- root `AGENTS.md` contains the shared approval and handoff workflow;
- both files identify the main agent as final contract approver;
- both files prohibit silent backend changes to the approved API spec;
- the instructions require domain-document synchronization for semantic
  changes; and
- Markdown whitespace validation passes.
