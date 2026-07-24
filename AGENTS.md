# Romance Agent Repository Instructions

## Scope

These instructions apply to the entire repository unless a more specific
`AGENTS.md` exists in a subdirectory.

## Repository Map

- `frontend/` contains the React, Vite, and TypeScript application.
- `backend/` contains the FastAPI public application, domain composition, and
  Narrative Memory project-snapshot persistence.
- `llm-agent/` contains the provider-independent Narrative Memory scene-analysis
  package, including model adapters, prompts, and its append-only audit storage.
- `docs/domains/` contains the technology-independent domain contracts and is
  the source of truth for domain language, responsibilities, invariants, and
  boundaries.
- `docs/superpowers/` contains design and implementation records.
- Root `mise.toml` and `mise.lock` define the shared toolchain.

## Project Engineering Rule Documentation

Keep persistent application engineering knowledge in the owning project's
documentation rather than accumulating detailed rules in nested agent
instructions.

- Put frontend-specific coding, architecture, TypeScript, React, component,
  state-management, dependency, accessibility, testing, mocking, and other
  implementation-convention rules under `frontend/docs/`. Update
  `frontend/docs/frontend-coding-rules.md` when the topic fits that document.
- Put backend-specific coding, architecture, Python, framework, package,
  persistence, provider, dependency, error-handling, testing, and other
  implementation-convention rules under `backend/docs/`. Update
  `backend/docs/backend-coding-rules.md` when the topic fits that document.
- When a topic is distinct or large enough for a focused document, create it
  under the same project's `docs/` directory and link it from that project's
  existing coding-rules document so the complete rule set remains discoverable
  from one entry point.
- Do not add or duplicate those detailed rule bodies in `frontend/AGENTS.md` or
  `backend/AGENTS.md`. Nested `AGENTS.md` files may define agent scope, file
  ownership, required reading, authority, workflow, verification, and handoff
  behavior, and may point to the authoritative project documents.
- When implementation introduces, changes, or reveals a reusable engineering
  rule, the implementation and its matching project-document update are one
  indivisible change. Do not defer the documentation or leave the rule only in
  an agent handoff or conversation. Work that only follows existing documented
  rules does not require a documentation rewrite.

Keep repository-wide delegation, OpenAPI approval, domain-document ownership,
review, and working-tree policy in this root `AGENTS.md`. Keep domain meaning
and boundaries in `docs/domains/*.md` under the existing synchronization rules;
project engineering documentation does not replace domain contracts.

## Mandatory Feature Ticket Registration

Every request to implement a feature must be registered in the project-local
ticket queue before any implementation work begins. This rule applies regardless
of the feature's size, urgency, or whether the user asks for immediate
implementation.

- Do not edit application code, tests, API contracts, or domain documents in
  response to the feature implementation request.
- Check the existing queue with `zellij-agent ticket-worker list` to avoid
  registering a duplicate ticket.
- Use `zellij-agent ticket-worker add` when an approved specification and
  implementation plan exist.
- Use `zellij-agent ticket-worker fast-add` when the feature is small and clear
  enough to register without specification and plan artifacts.
- After registration, report the ticket ID and registration result to the user,
  then stop. Implementation starts only when the ticket is claimed through the
  ticket workflow.

Ticket registration is mandatory and must not be skipped by directly
implementing the requested feature.

## Main Agent Responsibilities

The main agent owns the end-to-end result. It must:

1. Read the relevant domain contracts before changing domain behavior.
2. Treat the implementation and its matching domain-document update as one
   indivisible change whenever domain content changes.
3. Define scope, acceptance criteria, and cross-boundary contracts.
4. Decide whether frontend or backend implementation and review work is
   substantial and independent enough to delegate.
5. Approve the exact OpenAPI baseline used by implementers and reviewers when
   a consumer-facing API is involved.
6. Triage review findings and resolve contract or implementation conflicts.
7. Integrate delegated work and verify frontend-backend behavior.
8. Run the final checks for every affected application.

Delegation does not transfer responsibility for architecture, integration, or
verification away from the main agent.

## OpenAPI, Implementation, and Review Subagents

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
- After substantial frontend implementation stops, assign the complete affected
  screen to the project-scoped read-only agent named `frontend-review`, defined
  in `.codex/agents/frontend-review.toml`. Supply the approved OpenAPI baseline
  when the screen consumes an API.
- After substantial backend implementation stops, assign the complete affected
  operation to the project-scoped read-only agent named `backend-review`,
  defined in `.codex/agents/backend-review.toml`.
- For cross-stack features, the main agent must define the contract scope and
  acceptance criteria before assigning the OpenAPI draft. Frontend and backend
  implementation may run in parallel only after the main agent approves the
  same OpenAPI baseline and their file ownership does not overlap.
- Frontend and backend review may run in parallel only after implementation
  agents have stopped editing their respective application boundaries. Review
  must not inspect a moving implementation target.
- Do not create a subagent for a trivial edit, a tightly coupled change, or a
  task whose boundary is still unclear.

Every delegated task must state the owned paths, expected deliverable,
constraints, and verification commands. A subagent must not edit another
application or shared documentation unless that work is explicitly assigned.
Two agents must not modify the same file concurrently.

Review agents never edit files. Every review assignment must state the affected
screen routes, API operation IDs when applicable, or backend entry points;
implementation handoff; acceptance criteria; relevant domain contracts;
approved OpenAPI baseline when applicable; accepted deviations; review
boundary; and safe verification commands. Reviewers return
evidence-based findings with severity,
introduced/pre-existing classification, source location, impact, repair
direction, and re-review requirement.

The main agent validates and triages every finding. Every accepted finding must
be resolved before completion, regardless of severity. Accepted findings return
to the owning implementation agent for repair when practical; this preference
selects the fixer and never makes resolution optional. Every rejected finding
retains concrete main-agent rationale. Dispatch the same reviewer for re-review
when a blocking or high finding requires confirmation or when any fix materially
changes the reviewed behavior. Medium and low resolutions do not otherwise
require re-review. `No blocking findings` from a reviewer is not approval or
permission to merge.

If delegated work can change domain content, the task must also assign the
matching `docs/domains/*.md` update to that subagent or explicitly retain that
update for the main agent. The delegated work is not complete until both the
implementation and domain documentation are synchronized.

Subagents are temporary specialists, not sources of persistent project truth.
They must reload the relevant repository instructions and domain contracts for
each task.

## Browser Bug-Hunting Subagent

When the user requests browser-based defect discovery for a bounded screen or
flow, use the project-scoped `bug-hunter` agent defined in
`.codex/agents/bug-hunter.toml`. Do not dispatch it for an application-wide
audit or while an implementation agent is modifying the same screen boundary.

Every assignment must state the target route, user flow, starting state and
data, authentication state, viewport sizes, applicable requirements or
acceptance criteria, allowed server and verification commands, excluded
actions, and data-mutation limits.

The `bug-hunter` owns browser exploration, two clean-state reproductions,
duplicate checks, bug-specific spec and plan creation, direct `ticket-worker`
registration, and one Korean HTML report under `docs/bug-reports/`. It may
commit only newly created bug documents, report, and evidence assets.

Before browser setup, run `zellij-agent ticket-worker list --json`; run
`zellij-agent ticket-worker init` once only when the list command reports that
the queue is uninitialized, and retain the existing ticket data for duplicate
checks. Register only defects that are
in-scope, reproduced twice from a clean starting state, supported by
authoritative requirements, concrete, non-duplicate, and independently
repairable. Do not register subjective preferences, feature ideas, invisible
style concerns, unreproduced behavior, or unresolved product decisions. Use
`Blocking`, `High`, `Medium`, or `Low` severity.

For every registrable defect, reserve its HTML report anchor and create one
Korean bug-specific design document and one implementation-ready plan with
evidence and exact verification commands. Both documents must link to the
reserved report path and exact `#bug-NNN` anchor. Self-review the documents,
then register the defect with the `zellij-agent ticket-worker add` JSON command.
The Korean title and summary must describe the defect. The execution prompt
must name both documents, require the `feature-development` skill, skip
`brainstorming` and `writing-plans`, and prohibit work outside the defect scope.
Query fresh JSON after registration and verify that the ticket is `ready` and
every registered value matches. Never edit the ticket database to recover from
a duplicate or registration failure.

The main agent reviews the report and every registered ticket before assigning
implementation. Direct registration does not transfer integration, review, or
final-verification responsibility away from the main agent.

## Backend Bug-Hunting Subagent

When the user requests defect discovery for a bounded backend operation or use
case, use the project-scoped `backend-bug-hunter` agent defined in
`.codex/agents/backend-bug-hunter.toml`. Assign exactly one `operationId` or one
explicit backend use case. Do not dispatch it as an implementation review, a
browser audit, an application-wide backend audit, or while another agent is
modifying the same operation or use-case boundary.

Every assignment must state the target and backend entry point; the exact
main-approved OpenAPI baseline and matching `operationId` when consumer-facing;
relevant domain contracts and acceptance criteria; starting fixture and
authentication state; run-specific temporary database and file paths, approved
temporary parent, isolation, reset, and cleanup method; allowed commands;
excluded scope; data-mutation limits; and error, concurrency, and retry
scenarios. Missing applicable input, multiple targets, an ambiguous boundary,
or unproven storage isolation stops setup. A non-HTTP use case does not require
an OpenAPI artifact.

The `backend-bug-hunter` owns bounded execution, applicable normal and failure
scenario exploration, two independent clean-state reproductions, duplicate
checks, severity classification, direct ticket registration, and one Korean
HTML report under `docs/bug-reports/`. It may create bug-specific specs and
plans only when required by severity. It does not implement fixes, review a
completed implementation, or approve features.

Use only immutable or deterministically generated fixtures copied into a unique
temporary directory for each run. Never use actual production data, external
providers, shared databases, shared files, real credentials, or state left by
another run. Resolve and validate temporary paths beneath the assignment's
approved parent before setup. Clean only paths owned by the current run and
report cleanup failures or leftovers.

Check the normal path and applicable boundary, validation, 404, 409, 422, 500,
persistence rollback, concurrency, retry, provider-failure, and sensitive-log
scenarios. Use fake or stub providers. Record a reason for every non-applicable
scenario instead of forcing an unreachable failure.

Before setup, run `zellij-agent ticket-worker list --json`; run
`zellij-agent ticket-worker init` once only when the list command explicitly
reports that the queue is uninitialized. Immediately before registration, query
fresh JSON again and compare target, trigger, observable failure, impact, and
repair boundary. Register only authoritative, independently repairable defects
that reproduced twice from independent clean states and are not duplicates.
Never edit the ticket database to recover from a duplicate or registration
failure.

Reserve an HTML `#bug-NNN` anchor for every registrable defect. For `Blocking`,
`High`, and `Medium`, create and self-review one Korean bug design and one
implementation-ready plan, link both documents to the exact report anchor, and
register with `zellij-agent ticket-worker add`. For `Low`, create no design or
plan and use `zellij-agent ticket-worker fast-add` with the report path and
anchor as evidence; its prompt must include `FAST 모드로 처리한다`. Every prompt
requires `feature-development`, skips `brainstorming` and `writing-plans`, and
prohibits changes outside the defect scope. Query fresh JSON after registration
and verify the command and every registered value.

The Korean report uses `docs/bug-reports/backend-report-template.html` and
records the target contract, fixture, authentication, temporary paths and
isolation, scenario results, tickets, duplicates, exclusions, commands,
cleanup, and limitations. For each defect include both clean runs' request and
response, sanitized logs, and storage state before and after. Redact
authorization, cookies, tokens, credentials, provider secrets, private keys,
environment secrets, and private manuscript or character content. Do not store
raw database dumps, journals, complete snapshots, binary payloads, or
secret-bearing stack traces.

Owned writes are limited to new backend bug reports and evidence, severity-
required new bug specs and plans, ticket-worker commands, and assigned
run-specific temporary paths. Product code and tests, OpenAPI, domain contracts,
package files, lockfiles, `backend/AGENTS.md`, existing agent definitions, and
pre-existing files are read-only. Commit only newly created bug documents,
reports, and evidence with exact pathspecs; never commit temporary data.

On failure, stop dependent work and return a partial handoff with the target,
failed phase, completed and unexecuted phases, commands and exits, sanitized
error, artifacts and validation state, ticket IDs and verified status,
temporary paths, cleanup result, preserved files, limitations, and the exact
resume condition. Never claim work not proven by fresh evidence. The main agent
reviews the report and every ticket before assigning implementation and retains
integration, review, and final-verification responsibility.

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

1. **Main scopes:** The main agent defines the consumer use case, domain
   behavior, acceptance criteria, validation ownership, and unresolved
   decisions, then explicitly assigns `docs/api/openapi.yaml` to the OpenAPI
   agent.
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
7. **Implementers finish:** Frontend and Backend complete their focused and full
   checks and stop editing the assigned application boundaries.
8. **Reviewers inspect:** The main agent dispatches `frontend-review` and
   `backend-review` as applicable. They independently inspect the approved
   baseline and complete affected screen or operation without editing files.
9. **Main resolves findings:** The main agent accepts, rejects with rationale, or
   escalates each finding. Accepted implementation findings return to the owning
   implementer; accepted contract changes return to the OpenAPI agent and create
   a new proposed baseline. Material fixes receive re-review.
10. **Main verifies:** The main agent confirms that the final spec, frontend
    consumer, backend behavior, contract tests, domain documents, and resolved
    review findings agree.

Frontend and backend tasks may proceed in parallel only after Main approves
the same approved spec baseline for both tasks. Any spec change invalidates
that baseline until Main approves a replacement. The OpenAPI agent is the sole
editor of `docs/api/openapi.yaml`; frontend and backend agents must never edit
it.

Reviewers use only the same exact OpenAPI baseline approved for implementation.
A later spec edit invalidates the affected review baseline until Main approves
its replacement. Review agents must never edit or approve the API spec.

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
- When starting feature development, use the branch name registered on the
  claimed ticket. When creating a worktree, use that exact branch name rather
  than deriving or choosing a new one.
- Do not use destructive Git commands to discard work.
- Verify the smallest relevant checks during implementation, then run the full
  affected-application checks before completion.
- Before completing a domain-affecting task, compare the implementation diff
  with the relevant `docs/domains/*.md` diff and confirm they describe the same
  behavior and boundaries.
- Run the applicable read-only review wave after implementation editing stops
  and before final integration verification.
- Keep introduced findings separate from pre-existing debt and shadcn/ui
  adoption candidates. Pre-existing findings do not block the feature unless
  the change worsened them, acceptance criteria require repair, or they expose
  a blocking correctness or safety problem in affected behavior.
- Confirm every accepted finding is resolved, regardless of severity; re-review
  blocking or high findings that require confirmation and any repair that
  materially changes reviewed behavior.
- Record concrete main-agent rationale for every rejected finding.
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
