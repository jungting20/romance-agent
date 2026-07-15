# Frontend and Backend Review Subagents Design

## Summary

Add two project-scoped, read-only review agents named `frontend-review` and
`backend-review`. They run after the frontend and backend implementation wave,
review their respective application boundaries in parallel, and return
evidence-based findings without modifying files.

The frontend reviewer inspects the complete affected screen rather than only
the changed diff. Its review includes conformance with the approved UI plan and
explicit shadcn/ui adoption checks, including cases where a locally available
shadcn/ui component or an established repository composition was unnecessarily
reimplemented. The backend reviewer inspects the complete affected operation
and its supporting application path for domain, OpenAPI, architecture, error,
and test correctness.

The main agent remains responsible for approving contracts, resolving review
findings, coordinating fixes, checking frontend-backend integration, and
claiming completion.

## Goals

- Give frontend and backend code independent, specialist review after
  implementation.
- Keep reviewers read-only so implementation ownership remains unambiguous.
- Review complete affected behavior, not only changed lines.
- Detect avoidable custom frontend UI where shadcn/ui or an established local
  composition should be used.
- Distinguish newly introduced problems from pre-existing debt.
- Produce actionable findings with severity, evidence, and a concrete repair
  direction.
- Preserve the main agent's responsibility for cross-stack integration and
  final verification.

## Non-goals

- Let reviewers edit implementation, tests, domain documents, UI plans, or the
  OpenAPI contract.
- Replace the main agent's final diff review or integration verification.
- Require every visual element to be a direct shadcn/ui primitive.
- Treat product-specific compositions as defects merely because no single
  shadcn/ui component implements them.
- Audit the entire repository when only one screen or API operation is in
  scope.
- Allow a reviewer to approve or revise an OpenAPI baseline.

## Agent Registration

Create the following project-scoped custom agents:

- `.codex/agents/frontend-review.toml`
  - `name = "frontend-review"`
  - description routes post-implementation React and TypeScript screen reviews
    to this agent.
- `.codex/agents/backend-review.toml`
  - `name = "backend-review"`
  - description routes post-implementation Python backend operation reviews to
    this agent.

Both agents are independent from the implementation agents. They must begin
from repository evidence and the main agent's review assignment rather than
assuming that the implementer's handoff is correct.

## Read-only Authority

Review agents may read repository files, inspect diffs and history, use
CodeGraph, and run non-mutating validation or test commands assigned by the
main agent. They must not:

- edit or create files;
- apply formatting or autofix commands;
- install or update dependencies;
- update snapshots;
- commit, stage, revert, or discard changes;
- author or approve `docs/api/openapi.yaml`;
- silently repair a finding before reporting it.

If a useful verification command is mutating, unavailable, unsafe in the
current worktree, or outside the assigned scope, the reviewer reports the
limitation instead of running it.

## Workflow

The feature-development workflow becomes:

1. `ui-planner` produces the screen plan when UI planning is required.
2. `openapi` drafts the consumer-facing API contract when an API is required.
3. The main agent reviews and approves an exact OpenAPI baseline.
4. `frontend` and `backend` implement in parallel when their work is substantial,
   independently testable, and non-overlapping.
5. After both implementation agents have stopped editing, `frontend-review` and
   `backend-review` review in parallel.
6. The main agent triages findings and sends accepted findings back to the
   owning implementation agent for repair.
7. A reviewer is dispatched again when fixes materially change the reviewed
   behavior or when a blocking or high-severity finding requires confirmation.
8. The main agent performs final cross-stack, domain-document, OpenAPI, diff,
   and application verification.

Review must not run concurrently with implementation in the same application
boundary. This prevents a reviewer from evaluating a moving target. Frontend
and backend review may run concurrently because their file ownership and
review scopes do not overlap.

Frontend-only and backend-only work uses only the matching reviewer. A trivial
change may remain in the main thread when dispatching a specialist would not
add meaningful review coverage; the main agent records that decision in its
handoff.

## Main-agent Dispatch Contract

Every review assignment must provide:

- the implementation goal and acceptance criteria;
- the implementer's changed-file list and handoff;
- the exact review boundary;
- relevant domain contracts;
- the approved UI plan path when frontend UI is affected;
- the approved OpenAPI path, exact baseline, and affected `operationId` values
  when an API is involved;
- known assumptions and accepted deviations;
- verification commands the reviewer may run;
- whether the review is initial or a re-review, including findings expected to
  be resolved during a re-review.

The assignment must identify screen routes or page entry components for
frontend work and operation IDs or backend entry points for backend work. A
reviewer reports an ambiguous boundary rather than expanding into an
unbounded repository audit.

## Frontend Review Boundary

For every affected screen, `frontend-review` reviews:

- the route or page entry component;
- all product components rendered by that screen, including components not
  changed in the current diff;
- hooks, state, validation, API adapters, view models, and tests directly used
  by the screen;
- the screen's use of shared UI primitives and local shadcn/ui components;
- loading, empty, error, disabled, validation, responsive, and accessibility
  behavior that can occur on that screen.

The reviewer may inspect shared primitives to understand their contract and
the affected screen's usage. It does not audit unrelated call sites on other
screens unless the current change modified the primitive in a way that can
regress those callers. This defines “complete affected screen” without turning
each feature review into a whole-frontend audit.

## Frontend Review Sources of Truth

The reviewer uses the following precedence:

1. relevant `docs/domains/*.md` contracts;
2. the main-agent-approved OpenAPI baseline for transport behavior;
3. the approved UI plan for screen behavior, state coverage, component intent,
   and shadcn/ui adoption decisions;
4. root and frontend `AGENTS.md` instructions;
5. established repository architecture, components, tokens, and test patterns;
6. the assigned acceptance criteria and accepted deviations.

If these sources conflict, the reviewer reports the conflict and does not
invent a resolution. Domain and API semantics cannot be overridden by a UI
plan. The main agent owns resolution.

## shadcn/ui Review Policy

The frontend reviewer must determine repository reality from evidence,
including `components.json`, package dependencies, generated component files,
imports, and established local compositions. It then compares that evidence
with the approved UI plan's `shadcn/ui Status and Adoption Assumptions` and
`Component Structure` sections.

The reviewer reports a finding when:

- an approved UI-plan component mapping was ignored without an accepted
  deviation;
- a shadcn/ui component already available in the repository was replaced by
  custom JSX, CSS, or interaction logic without a product-specific need;
- an established local composition was duplicated instead of reused;
- custom controls duplicate accessibility, keyboard, focus, overlay, form, or
  state behavior already provided by an available component;
- shadcn/ui variants or repository design tokens were bypassed by one-off
  styling that creates inconsistent states or unnecessary duplication;
- a component is claimed to be shadcn/ui but does not use or faithfully wrap
  the repository component;
- the implementation silently omitted an adoption candidate that the approved
  plan and implementation brief required for this feature.

The reviewer does not report a defect merely because:

- no single shadcn/ui primitive represents a product-specific composition;
- semantic HTML or a small layout element is clearer than introducing a UI
  primitive;
- the required shadcn/ui component is not installed and its adoption was not
  approved;
- a repository wrapper intentionally adds product behavior while retaining the
  underlying primitive's contract.

When an appropriate component is not installed, the reviewer labels it an
`Adoption candidate` and explains the benefit and evidence. An adoption
candidate is non-blocking unless the approved UI plan or implementation brief
explicitly required its adoption.

## Additional Frontend Review Checks

In addition to shadcn/ui, the reviewer checks:

- domain language and behavior;
- page, feature, module, and infrastructure boundaries;
- React state ownership and component responsibilities;
- TypeScript correctness and unsafe type escapes;
- approved OpenAPI request, response, status, and error handling;
- keyboard access, focus behavior, labels, announcements, and error
  communication;
- responsive behavior and all applicable UI states from the UI plan;
- regression and behavior test coverage;
- unnecessary duplication and violations of nearby repository patterns.

The reviewer does not reject code for subjective style preferences unsupported
by repository rules or observable maintenance, correctness, consistency, or
accessibility impact.

## Backend Review Boundary

For every affected operation, `backend-review` reviews:

- the route or handler entry point;
- request parsing and validation;
- the application use case and domain logic reached by the operation;
- persistence and external-provider adapters directly used by the operation;
- response mapping and error translation;
- tests covering the affected behavior;
- shared backend code modified by the implementation and its relevant callers.

It may inspect surrounding code to understand contracts but does not audit
unrelated operations unless the implementation changed a shared dependency in
a way that can regress them.

## Backend Review Checks

The backend reviewer checks:

- exact conformance with the approved OpenAPI operation;
- domain responsibilities, invariants, language, and dependency direction;
- separation of domain logic from FastAPI, persistence, and external providers;
- validation ownership and consistent machine-readable errors;
- authentication and authorization when included in approved scope;
- transaction, concurrency, idempotency, and persistence behavior when
  relevant;
- unsafe logging or exposure of sensitive values;
- exception handling and failure recovery;
- deterministic and meaningful test coverage;
- consistency between implementation and assigned domain-document updates.

It reports contract problems to the main agent and never edits the OpenAPI
file. A proposed contract change invalidates affected implementation work only
after the main agent accepts the proposal and obtains a replacement OpenAPI
baseline through the `openapi` agent.

## Finding Model

Every finding contains:

- stable local ID, such as `FE-001` or `BE-001`;
- severity;
- classification as `Introduced`, `Pre-existing`, or `Unclear`;
- concise title;
- file path and line number or the narrowest available symbol;
- violated requirement, contract, repository rule, or concrete risk;
- evidence and an observable failure scenario;
- recommended repair direction without supplying an edit;
- re-review requirement.

Severity meanings are:

- `Blocking`: contract, domain, security, data-integrity, build, or core
  acceptance failure that prevents completion.
- `High`: likely user-facing failure, serious accessibility failure, major
  architecture breach, missing critical test, or avoidable replacement of an
  available shadcn/ui component for a core interactive control.
- `Medium`: maintainability, consistency, state coverage, test quality, token,
  variant, or composition issue with concrete impact.
- `Low`: localized improvement with limited impact.
- `Adoption candidate`: a non-defect shadcn/ui opportunity whose component is
  not currently available or whose adoption was not approved.

Introduced blocking and high findings must be resolved or explicitly rejected
with rationale by the main agent before completion. Pre-existing findings are
reported separately and do not block the assigned feature unless the change
made them worse, the acceptance criteria require their repair, or they create
a blocking correctness or safety problem in the affected behavior.

## Review Handoff

Each reviewer returns:

1. review scope and sources inspected;
2. findings ordered by severity;
3. separate pre-existing debt and adoption-candidate sections;
4. verification commands and results;
5. checks not run and limitations;
6. a contract and domain alignment summary;
7. a conclusion of `Changes required`, `No blocking findings`, or `Blocked`.

`No blocking findings` is not approval of the feature or permission to merge.
Only the main agent can accept findings, approve deviations, and declare the
integrated task complete.

If no findings exist, the reviewer explicitly states that fact and still lists
the scope and validation evidence. Reviewers avoid praise, broad summaries, and
findings without a concrete impact.

## Fix and Re-review Loop

The main agent reviews every finding for correctness and scope. Accepted
findings go back to the original owning implementation agent when practical.
Review agents remain read-only throughout the loop.

A re-review assignment includes the original finding IDs and the fix diff. The
reviewer verifies the fix, checks for local regressions, and reports each
finding as `Resolved`, `Partially resolved`, or `Unresolved`. It does not repeat
an entire screen or operation audit unless the fix materially expanded the
affected behavior.

## Repository Workflow Updates

Implementation must update the root `AGENTS.md` and the local
`.agents/skills/feature-development/SKILL.md` so both describe the review wave,
read-only authority, application-specific dispatch, finding triage, re-review,
and main-agent final verification. The agent TOML files remain the detailed
source for each reviewer's behavior.

No domain contract update is required because this change modifies the
development workflow rather than product domain meaning or behavior.

## Verification Strategy

Implementation verification consists of:

- parsing or otherwise validating both TOML files;
- checking that both agent names and descriptions are discoverable;
- confirming all workflow documentation uses the same ordering and authority;
- scanning reviewer instructions for accidental edit or approval authority;
- confirming frontend shadcn/ui rules preserve the distinction between
  available components, established compositions, and adoption candidates;
- confirming the feature-development workflow dispatches review only after
  implementation editing stops;
- reviewing the final diff for domain-document impact and unrelated changes.

Application build commands are not required when implementation changes only
agent configuration and workflow documentation.

## Acceptance Criteria

- `.codex/agents/frontend-review.toml` defines an independent read-only
  frontend reviewer.
- `.codex/agents/backend-review.toml` defines an independent read-only backend
  reviewer.
- Frontend review covers the complete affected screen and its directly used
  product components, state, adapters, and tests.
- Frontend review explicitly detects avoidable custom UI when an approved or
  locally available shadcn/ui component or established composition should be
  used.
- shadcn/ui adoption candidates are distinguished from actual defects.
- Backend review covers the complete affected operation and its directly used
  use case, domain, adapter, mapping, and tests.
- Both reviewers return evidence-based findings and never edit files.
- Findings distinguish introduced issues, pre-existing debt, severity, and
  re-review requirements.
- Frontend and backend reviews may run in parallel only after their respective
  implementations stop editing.
- Accepted findings return to the owning implementation agent; reviewers remain
  read-only during re-review.
- The main agent retains OpenAPI approval, finding triage, cross-stack
  integration, final checks, and completion authority.
- Root repository instructions and the feature-development skill describe the
  same reviewed workflow.
