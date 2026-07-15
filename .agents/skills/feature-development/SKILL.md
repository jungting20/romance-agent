---
name: feature-development
description: Use when adding, building, or implementing product functionality in the Romance Agent repository, including frontend-only, backend-only, and cross-stack features.
---

# Feature Development

## Overview

Coordinate feature work from clarification through contract approval,
implementation, integration, and verification. The main agent owns scope,
decisions, the approved contract baseline, integration, and the final result.

Do not use this workflow for explanation-only, diagnosis-only, review-only, or
unrelated refactoring requests.

## 1. Inspect and classify

Read every applicable `AGENTS.md`, relevant `docs/domains/*.md`, and nearby
implementation and test patterns. Classify whether the request needs UI,
persistent storage, a consumer-facing API, frontend work, backend work, and a
domain-contract update.

## 2. Clarify before implementation

For UI work, ask whether this is a `new screen` or an `existing screen` change.
For a new screen, confirm its route or entry point and primary user action. For
an existing screen, inspect the code first and ask only if multiple plausible
targets remain.

When persistent storage is required, ask the user to choose `database`, `file`,
or `recommended approach`. For a recommendation, inspect backend constraints
and assess relationships, concurrency, queries, durability, and operational
complexity. Recommend one choice with reasons and obtain confirmation.

Ask necessary feature questions one at a time. Do not ask for facts that the
repository establishes safely.

## 3. Approve the implementation brief

Present an `implementation brief` containing user value and scope, UI target,
persistence, domain behavior and invariants, API need, request/response/error
semantics, ownership, acceptance criteria, verification commands, and domain
documentation impact. For UI-affecting work, use the approved brief's UI target
as the bounded input to UI planning and later keep it consistent with the exact
approved UI plan. Do not author OpenAPI or implement code until the user
approves this brief.

## 4. Plan and approve the UI

When UI behavior changes, assign a bounded planning task to the project-scoped
planning-only `ui-planner` defined in `.codex/agents/ui-planner.toml`. Provide
the approved requirements and UI target, relevant domain contracts, acceptance
criteria, constraints, and one exact owned
`frontend/docs/ui-plans/<feature-name>.md` path. The UI planner authors only
that plan; it never authors domain documents, API contracts, or application
code.

Review the returned plan for domain consistency, screen scope, user flows,
states, accessibility, responsive behavior, shadcn/ui decisions, requirement
traceability, and unresolved questions. The main agent must
approve the exact UI plan before OpenAPI drafting or implementation. If the
plan materially changes the implementation brief's UI target, reconcile and
reapprove the brief and plan before downstream work. Hand the
same exact approved UI plan to frontend implementation and later to
`frontend-review`.

Skip this section when no UI behavior changes. UI planning does not replace
approval of the implementation brief, domain behavior, or API scope.

## 5. Draft and approve the API contract

When an API is required, assign the project-scoped `openapi` agent sole
ownership of `docs/api/openapi.yaml`. Provide the approved use case, domain
behavior, acceptance criteria, validation ownership, affected operations,
unresolved decisions, owned path, and validation commands.

Review the returned contract for domain consistency, completeness, errors, and
compatibility. The main agent must approve the `exact proposed baseline`
before implementation. Every later OpenAPI edit creates a new proposal; pause
affected work until the replacement baseline is approved.

Skip this section when no consumer-facing API changes.

## 6. Delegate implementation

For each assignment, state owned paths, deliverable, constraints, verification
commands, relevant domain contracts, acceptance criteria, approved baseline,
and assigned `operationId` values. For UI-affecting frontend work, also provide
the exact approved UI plan.

Use the project-scoped `frontend` and `backend` agents in `parallel` only when
both are needed, their work is substantial and independently testable, and
their ownership is `non-overlapping`. Use only the relevant agent for
frontend-only or backend-only work. Retain trivial or tightly coupled edits in
the main thread.

Assign each affected `docs/domains/*.md` file to exactly one agent or retain it
in the main thread. Assign `docs/domains/README.md` too when dependency
directions change. Never let two agents edit the same file concurrently.

## 7. Resolve contract feedback

Frontend and backend agents never edit `docs/api/openapi.yaml`. They report an
infeasible or unsafe operation with its impact and a concrete change proposal.
Resolve the proposal, send accepted changes to `openapi`, and approve the new
exact baseline before affected implementation resumes.

## 8. Dispatch read-only review

Wait until implementation agents complete their checks and stop editing. For
substantial frontend work, dispatch `frontend-review` with the complete affected
screen boundary, implementer handoff, approved UI plan, relevant domain
contracts, acceptance criteria, accepted deviations, and approved OpenAPI
baseline and operation IDs when applicable. It must review the
whole affected screen and explicitly check whether
available shadcn/ui components or established compositions were unnecessarily
reimplemented.

For substantial backend work, dispatch `backend-review` with the complete
affected operation boundary, implementer handoff, relevant domain contracts,
acceptance criteria, accepted deviations, and approved OpenAPI baseline and
operation IDs. Frontend and backend review may run in parallel, but neither may
run while its implementation boundary is still being edited.

Reviewers are read-only. Require evidence-based findings with severity,
introduced/pre-existing classification, source location, impact, repair
direction, and re-review requirement. Use only the relevant reviewer for
single-application work. The main agent may retain review of a trivial change
when specialist dispatch would not add meaningful coverage, and must state that
decision in the final handoff.

## 9. Triage, fix, and re-review

Validate every finding against the diff, requirements, domain contracts, UI
plan, approved OpenAPI baseline, and repository instructions. Accept it, reject
it with concrete rationale, or escalate a real contract or product decision.
Send accepted implementation findings to the original owning implementation
agent when practical. Review agents never make fixes.

Re-dispatch the matching reviewer with original finding IDs and the fix diff
when a blocking or high finding requires confirmation or when a fix materially
changes reviewed behavior. A reviewer result of `No blocking findings` is an
input to main-agent judgment, not approval or permission to merge.

Keep pre-existing debt and unapproved shadcn/ui adoption candidates separate
from introduced defects. They do not block the feature unless the change made
them worse, acceptance criteria require repair, or they expose a blocking
correctness or safety failure in affected behavior.

## 10. Integrate and verify

Review every delegated implementation diff and every review finding. Confirm
the OpenAPI request, response, status, and error behavior matches frontend
consumers and backend handlers. Confirm implementation and domain documents
describe identical behavior and boundaries. Confirm accepted blocking and high
findings are resolved. Confirm every rejected finding has concrete main-agent
rationale.

Require focused agent checks, then run all checks for each affected app. From
`frontend/`, run:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

For backend work, run commands defined by `backend/README.md` and nested
`backend/AGENTS.md`; do not invent a new toolchain for an unrelated feature.

Report implemented behavior, changed files, the approved OpenAPI baseline and
operations, domain updates, review scope and finding resolution, verification
commands and results, and remaining risks.
