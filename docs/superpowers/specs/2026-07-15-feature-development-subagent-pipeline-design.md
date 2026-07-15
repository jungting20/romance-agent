# Feature Development Subagent Pipeline Design

## Summary

Revise the project-local `feature-development` skill so substantial feature
work follows a traceable, subagent-oriented pipeline:

1. UI planning;
2. OpenAPI drafting and main-agent approval;
3. parallel frontend and backend implementation;
4. frontend E2E planning and generation;
5. parallel frontend and backend code review;
6. review remediation and re-review;
7. main-agent integration and final verification.

The main agent retains scope, user decisions, UI-plan approval, OpenAPI
baseline approval, file ownership, contract-change resolution, integration,
and the final completion decision. Delegation supplies focused execution and
independent review; it does not transfer project governance.

## Goals

- Make `UI plan -> OpenAPI -> Frontend + Backend` the explicit cross-stack
  feature sequence.
- Give every delegated stage a concrete input and handoff contract.
- Let frontend and backend implementation proceed in parallel only from the
  same approved OpenAPI baseline and with non-overlapping file ownership.
- Trace UI-plan requirement IDs through frontend implementation and review.
- Add independent, parallel frontend and backend code review before final
  integration.
- Require remediation and re-review for blocking findings.
- Preserve the repository's domain-document, OpenAPI ownership, and final
  verification rules.

## Non-goals

- Register or create new custom-agent TOML files.
- Change the responsibilities of the existing `ui-planner`, `openapi`,
  `frontend`, or `backend` agents.
- Let a subagent approve its own UI plan, API baseline, implementation, or
  review remediation.
- Make every small or tightly coupled edit require delegation.
- Define product behavior, domain rules, or API schemas inside the skill.

## Pipeline

### 1. Inspect and classify

The main agent reads repository instructions and domain contracts, inspects
nearby implementation, and classifies the feature by UI, API, persistence,
frontend, backend, and domain-document impact. Read-only exploration may be
delegated when it has a bounded question and no overlapping edits.

### 2. Approve the implementation brief

The main agent resolves material user decisions and obtains approval for an
implementation brief. The brief defines value, scope, UI target, domain
behavior, persistence, API need, validation ownership, acceptance criteria,
verification, and documentation impact.

### 3. Produce and approve the UI plan

For substantial UI work, the main agent assigns one exact Markdown path under
`frontend/docs/ui-plans/` to the project-scoped `ui-planner` agent. The
assignment includes the approved brief, target user, scope, exclusions,
constraints, acceptance criteria, and relevant domain contracts.

The main agent reviews the returned plan before API drafting or frontend
implementation. It records:

- approved UI-plan path and revision or diff;
- in-scope `REQ-*` identifiers;
- confirmed decisions;
- accepted assumptions;
- unresolved questions.

An unresolved item that affects domain meaning, security, privacy, required
data, API semantics, or the primary user flow blocks the affected downstream
stage. Minor presentation assumptions may remain explicit.

Skip this stage for work without substantial UI impact. An existing approved
UI plan may be reused only after the main agent confirms it still matches the
feature scope and repository state.

### 4. Draft and approve OpenAPI

When a consumer-facing API changes, the main agent assigns
`docs/api/openapi.yaml` exclusively to the `openapi` agent. The assignment
includes the approved implementation brief, approved UI-plan references,
domain behavior, validation ownership, affected operations, unresolved
decisions, and validation commands.

The main agent reviews and approves an exact proposed baseline. Frontend and
backend API implementation cannot begin from an unapproved proposal. Every
later OpenAPI edit creates a new proposal and pauses affected implementation
until the replacement baseline is approved.

Skip this stage when no consumer-facing API operation changes.

### 5. Delegate implementation

After UI-plan and API gates are satisfied, the main agent assigns substantial,
independently testable work to the project-scoped `frontend` and `backend`
agents. Run them in parallel when both are required and their owned paths do
not overlap.

Every implementation assignment includes:

- exact owned paths;
- deliverable and exclusions;
- relevant domain contracts;
- acceptance criteria;
- approved UI-plan path and assigned `REQ-*` IDs when applicable;
- approved OpenAPI baseline and assigned `operationId` values when applicable;
- dependency and persistence decisions;
- verification commands;
- ownership of each affected domain document.

Frontend and backend implementers do not edit OpenAPI. Contract concerns flow
through the main agent to the `openapi` agent, followed by approval of a new
exact baseline before affected work resumes.

### 6. Plan and generate frontend E2E tests

After frontend implementation, follow `frontend/AGENTS.md`: first assign an
E2E plan to the configured Playwright planner, then assign the approved plan
and exact test paths to the configured Playwright generator. Review and run
the generated tests before code review.

If a required project-scoped E2E agent is absent, report the blocker rather
than silently replacing or skipping the required step.

### 7. Run parallel code reviews

When implementation and required E2E work are ready, dispatch two independent,
read-only task-scoped review subagents in parallel:

- `frontend-review` reviews only the frontend diff and its assigned contracts;
- `backend-review` reviews only the backend diff and its assigned contracts.

Skip the reviewer whose application is unaffected. These reviewer names are
task-scoped roles defined by their dispatch contracts; this revision does not
require new custom-agent TOML files.

Each review assignment includes:

- base and head revisions or an exact diff boundary;
- implementation summary;
- approved implementation brief;
- approved UI-plan path and assigned `REQ-*` IDs;
- approved OpenAPI baseline and assigned `operationId` values;
- relevant domain contracts;
- owned implementation and test paths;
- acceptance criteria and verification results;
- explicit read-only ownership.

`frontend-review` checks requirement traceability, frontend architecture,
OpenAPI consumption, state handling, accessibility, tests, MSW behavior, and
regression risk. `backend-review` checks domain invariants, backend boundaries,
OpenAPI behavior, validation and error semantics, tests, and regression risk.

Both reviews return findings with severity, file and line evidence, rationale,
recommended correction, and one verdict:

- `approved`;
- `changes-required`.

Severity meanings:

- `Critical`: correctness, security, data loss, contract break, or a result
  that cannot ship;
- `Important`: required behavior, architecture, testing, or maintainability
  problem that must be fixed before final verification;
- `Minor`: non-blocking improvement or residual risk.

Reviewers do not edit implementation, tests, OpenAPI, or domain documents.
They report findings to the main agent.

### 8. Resolve findings and re-review

The main agent verifies every finding against repository facts, approved
decisions, code, and tests. Valid findings are reassigned to the original
implementation agent with exact owned paths and verification commands.
Incorrect or out-of-scope findings receive a technical disposition.

After corrections, rerun the affected focused and full checks and send the
changed scope back to the corresponding reviewer. A feature cannot enter final
verification while any validated `Critical` or `Important` finding remains or
either affected reviewer has a `changes-required` verdict.

### 9. Integrate and verify

The main agent reviews all delegated diffs and handoffs, confirms frontend and
backend agree with the approved OpenAPI baseline, compares domain behavior to
domain-document updates, and runs every affected application's required full
checks. The final report includes UI-plan traceability, the approved API
baseline, implementation paths, review results and dispositions, domain
updates, verification evidence, and remaining risks.

## Conditional Paths

| Feature shape | Required delegated stages |
| --- | --- |
| Cross-stack UI and API | UI planner, OpenAPI, frontend and backend in parallel, frontend E2E, both reviews in parallel |
| Frontend-only substantial UI | UI planner, frontend, frontend E2E, frontend review |
| Backend-only | Backend, backend review; OpenAPI first if a consumer-facing operation changes |
| API without UI | OpenAPI, affected implementers, affected reviewers |
| Trivial or tightly coupled change | Main thread may retain implementation as required by repository instructions; affected review and verification rules still apply proportionally |

## Failure and Blocking Rules

- A material unresolved UI-plan decision blocks the affected API or UI work.
- An unapproved OpenAPI proposal blocks affected frontend and backend work.
- Overlapping write ownership blocks parallel dispatch until ownership is
  resolved.
- A missing required custom agent is reported as a blocker.
- A validated Critical or Important review finding blocks final verification.
- A reviewer edits no files; implementation agents own remediation.
- Main-agent approval and final verification are never delegated.

## Skill Change Scope

Modify only `.agents/skills/feature-development/SKILL.md` after this design is
approved. Preserve its useful clarification, persistence, domain-document,
contract-feedback, and verification rules while restructuring the workflow
around explicit artifacts and delegation contracts.

## Validation Strategy

Use skill TDD:

1. Run realistic scenarios against the current skill and record omissions,
   especially UI planning, artifact handoffs, parallel reviews, and re-review.
2. Make the smallest skill revision that supplies the missing workflow.
3. Run the same scenarios with the revised skill.
4. Confirm the revised behavior preserves main-agent approval gates, exclusive
   OpenAPI ownership, non-overlapping implementation ownership, domain-document
   synchronization, and final verification.
5. Inspect frontmatter, Markdown structure, diff scope, and word count.

## Acceptance Criteria

- The skill defines the conditional `UI plan -> OpenAPI -> implementation`
  sequence.
- Each delegated stage has explicit inputs, ownership, output, and gate.
- Frontend and backend begin API work only from the same main-approved OpenAPI
  baseline.
- UI-plan `REQ-*` identifiers reach frontend implementation and review.
- Frontend and backend reviews run in parallel when both applications change.
- Reviewers are read-only and return evidenced, severity-ranked findings and a
  verdict.
- Validated Critical and Important findings trigger remediation and re-review.
- Main retains all user decisions, approvals, integration, and final checks.
- Frontend-only, backend-only, API-only, and trivial changes have explicit
  conditional behavior.
- No unrelated files or agent definitions are changed by the skill revision.
