---
name: feature-development
description: Use when adding, building, or implementing product functionality in the Romance Agent repository, including frontend-only, backend-only, API-only, and cross-stack features.
---

# Feature Development

## Overview

Coordinate substantial feature work through this conditional pipeline:

```text
implementation brief -> UI plan -> approved OpenAPI -> parallel implementation
-> frontend E2E -> parallel application reviews -> remediation/re-review
-> main-agent final verification
```

Delegate executable stages when their boundaries are substantial, independent,
and explicit. The main agent alone owns scope, user decisions, brief approval,
UI-plan approval, exact OpenAPI-baseline approval, file ownership, contract
change decisions, integration, and the completion decision. Delegation never
transfers those responsibilities.

Do not use this workflow for explanation-only, diagnosis-only, review-only, or
unrelated refactoring requests.

## 1. Inspect and classify

Read every applicable `AGENTS.md`, relevant `docs/domains/*.md`, and nearby
implementation and test patterns. Classify UI, persistence, consumer-facing
API, frontend, backend, and domain-document impact.

For UI work, establish whether the target is a new or existing screen. Confirm
the route or entry point and primary user action for a new screen; inspect an
existing screen before asking which target is intended. Ask necessary questions
one at a time and do not ask for facts the repository establishes safely.

When persistence is required, obtain the user's `database`, `file`, or
`recommended approach` decision. Before recommending, assess relationships,
concurrency, queries, durability, and operational complexity against backend
constraints.

## 2. Approve the implementation brief

Obtain approval for an implementation brief that records user value, scope,
exclusions, UI target, domain behavior and invariants, persistence and
dependency decisions, API need and semantics, validation ownership, acceptance
criteria, verification commands, file ownership, and domain-document impact.
Do not draft OpenAPI or implement before this approval.

## 3. Produce and approve the UI plan

For substantial UI work, assign the registered project-scoped, planning-only
`ui-planner` from `.codex/agents/ui-planner.toml`. Give it:

- the approved brief, target user, UI target, scope, and exclusions;
- relevant domain contracts, constraints, and acceptance criteria;
- one exact owned `frontend/docs/ui-plans/<feature-name>.md` path;
- confirmation that it owns no domain document, API contract, or application
  code.

Review the planner handoff and plan for domain consistency, screen scope, flows,
states, accessibility, responsive behavior, shadcn/ui decisions, and
traceability. Treat the handoff plus the main agent's approval record as the
returned approved artifact; together they must contain:

- UI-plan path and exact revision or diff;
- assigned in-scope `REQ-*` IDs;
- confirmed decisions and accepted assumptions;
- unresolved material questions.

An unresolved question blocks its affected downstream stage when it can change
domain meaning, security, privacy, required data, API semantics, or the primary
user flow. Resolve or escalate it; do not hide it as an implementation
assumption. Minor presentation assumptions may remain explicit.

Approve the exact plan before API drafting or frontend implementation. If it
changes the brief materially, reconcile and reapprove both. Reuse an existing
plan only after confirming that its exact revision still matches scope and
repository state. Skip this stage when UI behavior is unaffected.

## 4. Draft and approve OpenAPI

For every new or changed consumer-facing operation, assign exclusive ownership
of `docs/api/openapi.yaml` to the registered `openapi` agent. Its assignment
contains the approved brief, approved UI-plan path and revision plus assigned
`REQ-*` IDs when applicable, domain behavior, validation ownership, affected
operations, accepted assumptions, unresolved decisions, and exact validation
commands.

Review the response for complete request, response, status, and error semantics
and domain compatibility. The main agent must approve the `exact proposed baseline`
and record its unambiguous revision or diff. No affected frontend or
backend API work begins until that approval. Every later spec edit creates a
new proposal and pauses affected implementation and review until the main agent
approves a replacement baseline.

Only `openapi` edits the contract. Implementers and reviewers never author,
revise, or approve it. Skip this stage when no consumer-facing operation
changes.

## 5. Delegate implementation

Assign substantial, independently testable work to the registered `frontend`
and `backend` agents. Dispatch both in parallel only after all applicable gates
pass and their write ownership is non-overlapping. Every assignment states:

- exact owned implementation, test, and documentation paths;
- deliverables, constraints, exclusions, and accepted deviations;
- relevant domain contracts and acceptance criteria;
- approved UI-plan path, exact revision or diff, and assigned `REQ-*` IDs when
  applicable;
- approved OpenAPI baseline and assigned `operationId` values when applicable;
- approved dependency and persistence decisions;
- ownership of every affected domain document;
- exact focused and full verification commands and required handoff evidence.

Assign each affected `docs/domains/*.md` to exactly one implementer or retain it
in the main thread. Also assign `docs/domains/README.md` when dependency
directions change. Domain behavior and its matching contract update are one
indivisible change. Never let two agents edit the same file concurrently.

Frontend and backend do not edit OpenAPI. An infeasible or unsafe approved
operation returns to the main agent with affected `operationId`, consumer or
implementation impact, and a concrete proposal. Accepted changes return to
`openapi`; affected work resumes only from a newly approved exact baseline.

## 6. Plan and generate frontend E2E tests

After frontend implementation and before application review, follow
`frontend/AGENTS.md` in order:

1. Dispatch the configured planner in
   `.codex/agents/playwright_test_planner.toml` with implementation paths,
   acceptance criteria, relevant domain contracts, approved UI-plan artifact
   and assigned `REQ-*` IDs, exact plan output, and verification commands. It
   plans critical flows, failure states, and accessibility interactions without
   editing implementation or tests.
2. Review the plan, then dispatch the configured generator in
   `.codex/agents/playwright_test_generator.toml` with that exact plan, owned
   Playwright test paths, the same requirements and artifacts, and exact
   verification commands. The generator changes no product behavior.
3. Review generated tests against the plan and implementation, run the required
   Playwright checks, and retain paths, commands, and results for review.

If either required custom agent is absent or unavailable, report a blocker to
the main agent. Do not silently skip the stage or substitute a generic agent.
Skip E2E delegation when frontend is unaffected.

## 7. Dispatch read-only application review

Wait until implementation and required E2E work stop editing their boundaries.
Dispatch the registered project-scoped, read-only `frontend-review` and
`backend-review` agents in parallel when both applications changed. Skip only
the unaffected reviewer; retain review in the main thread only for a trivial or
tightly coupled change and record why specialist dispatch was disproportionate.

Each review assignment contains:

- base/head revisions or another exact diff boundary;
- complete affected screen routes or backend operations and entry points;
- implementation summary and implementer handoff;
- approved brief, relevant domain contracts, and accepted deviations;
- approved UI-plan path/revision and assigned `REQ-*` IDs when applicable;
- approved OpenAPI baseline and `operationId` values when applicable;
- affected implementation and test paths, acceptance criteria, and all
  verification evidence;
- explicit read-only ownership and safe verification commands.

`frontend-review` inspects the complete affected screen, architecture, UI-plan
traceability, OpenAPI consumption, state handling, accessibility, shadcn/ui and
MSW use, tests, and regression risk. `backend-review` inspects the complete
affected operation or boundary, domain invariants, architecture, OpenAPI
behavior when applicable, validation/error/security/persistence semantics,
tests, and regression risk.

Preserve each reviewer's native finding contract. Every finding includes its
native severity (`Blocking`, `High`, `Medium`, `Low`, plus frontend `Adoption
candidate` where applicable), stable ID, introduced/pre-existing
classification, file and line evidence, rationale and impact, recommended
correction, and re-review requirement. Every review also returns its native
conclusion: `Changes required`, `No blocking findings`, or `Blocked`.

For orchestration gates, map native severities without rewriting reviewer
output:

| Native review severity | Gate class |
| --- | --- |
| `Blocking` | `Critical` |
| `High` | `Important` |
| `Medium`, `Low`, `Adoption candidate` | `Minor` or non-defect as classified |

Normalize `Changes required` and `Blocked` to the orchestration verdict
`changes-required`. `No blocking findings` means only `review-complete`; it is
never an `approved` verdict, merge permission, or final approval. The main
agent must record the native conclusion and normalized verdict for every
affected reviewer.

## 8. Triage, remediate, and re-review

The main agent verifies every finding against repository facts, the diff,
requirements, domain contracts, UI plan, approved OpenAPI baseline, and tests.
Record one disposition for every finding: accept; reject with concrete technical
rationale; or escalate a genuine product or contract decision.

Resolve every accepted finding regardless of severity. Send valid corrections
to the original implementer when practical with exact owned paths, finding IDs,
and verification commands; reviewers never edit. Keep pre-existing debt and
frontend adoption candidates separate unless the feature worsened them,
acceptance criteria require repair, or they expose an affected Blocking failure.

After correction, rerun focused and full affected checks and redispatch the same
reviewer with original finding IDs and the exact fix diff. Re-review is mandatory
for every accepted `Blocking`/`Critical` or `High`/`Important` correction and
for any fix that materially changes reviewed behavior. Continue remediation and
re-review until the reviewer resolves those findings and no affected review has
a `changes-required` verdict.

Final verification is blocked while a validated Critical or Important finding
remains, any accepted finding remains unresolved, or an affected reviewer is
`Blocked`/`Changes required` (normalized `changes-required`). A native `No
blocking findings` conclusion clears only the review gate; the main agent still
owns the completion decision.

## 9. Integrate, verify, and report

The main agent reviews all delegated diffs and handoffs. Confirm implementation
matches assigned UI-plan `REQ-*` IDs; frontend consumers and backend handlers
match the same approved OpenAPI request, response, status, and error behavior;
domain implementation and documents agree; and every finding has a resolved or
technically justified disposition.

Run focused checks and every full check required by each affected application.
From `frontend/` run:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

For backend work, use commands defined by `backend/README.md` and nested
`backend/AGENTS.md`; do not invent a toolchain for an unrelated feature.

The final report includes implemented behavior and changed paths; approved
UI-plan path/revision with `REQ-*` implementation and verification traceability;
approved OpenAPI baseline and operations; domain updates; implementation and
E2E handoffs; each review's native conclusion, normalized verdict, findings,
and dispositions; exact verification commands and results; accepted deviations;
and remaining risks. Only the main agent declares completion.

## Conditional paths

| Feature shape | Required path |
| --- | --- |
| Cross-stack UI and API | Brief -> `ui-planner` -> `openapi` -> parallel frontend/backend -> frontend E2E -> parallel reviews -> remediation/re-review -> main verification |
| Frontend-only substantial UI | Brief -> `ui-planner` -> frontend -> E2E -> `frontend-review` -> remediation/re-review -> main verification |
| Backend-only | Brief -> `openapi` first only if a consumer operation changes -> backend -> `backend-review` -> remediation/re-review -> main verification |
| API-only or API without UI | Brief -> `openapi` -> affected implementers -> affected reviewers -> remediation/re-review -> main verification |
| Trivial or tightly coupled | Main thread may retain implementation and proportional review; all applicable approval, contract, domain, and final-verification gates remain |

## Common mistakes

- Implementing before the approved brief or exact UI-plan gate.
- Starting API work from an unapproved or mismatched OpenAPI baseline.
- Dispatching concurrent writers with overlapping paths or ambiguous domain-doc
  ownership.
- Omitting `REQ-*`, artifact revisions, exclusions, or exact verification
  commands from downstream assignments.
- Skipping planner-to-generator E2E work or silently replacing a missing custom
  agent.
- Letting reviewers edit code, review moving targets, or inspect an unbounded
  area.
- Treating `No blocking findings` as approval or ignoring a
  `changes-required` verdict.
- Fixing validated severe findings without rerunning checks and re-review.
- Delegating contract approval, integration, final verification, or the final
  completion decision.
