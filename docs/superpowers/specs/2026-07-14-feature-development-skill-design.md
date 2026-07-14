# Feature Development Skill Design

## Goal

Add a repository-scoped `feature-development` skill that coordinates feature
work from user clarification through an approved OpenAPI contract, scoped
frontend and backend implementation, integration review, and final
verification.

The skill applies to all feature-addition requests. It skips OpenAPI and
backend work when a feature is frontend-only, and it skips frontend work when
the feature has no UI or frontend consumer.

## Location and Files

Codex discovers repository skills under `.agents/skills`, so the skill will
use this structure:

```text
.agents/skills/feature-development/
├── SKILL.md
└── scripts/
    └── validate-skill.sh
```

`SKILL.md` contains the workflow. `validate-skill.sh` performs deterministic
structural checks only; it does not run feature-implementation evaluations.

## Trigger and Scope

The skill name is `feature-development`. Its description will trigger for
requests to add, build, or implement product functionality in this repository,
including frontend-only, backend-only, and cross-stack work. It will not
trigger for explanation, diagnosis without implementation, code review, or
unrelated refactoring.

Explicit invocation with `$feature-development` remains supported.

## Clarification Gate

Before authoring an API contract or implementation, the main agent determines
whether the feature affects UI and whether it needs persistent storage.

For UI work, ask the user to choose:

- a new screen; or
- functionality added to an existing screen.

For a new screen, clarify its route or entry point and primary user action.
For an existing screen, inspect the repository first and ask for confirmation
only when multiple plausible targets remain.

For work that needs persistent storage, ask the user to choose:

- database;
- file; or
- recommended approach.

When the user requests a recommendation, inspect the backend architecture and
evaluate data relationships, concurrency, querying needs, durability, and
operational complexity. Recommend one approach with reasons and obtain user
confirmation rather than selecting a foundational storage technology
silently.

Ask feature-specific follow-up questions one at a time. Do not ask for facts
that can be established safely from repository code or documentation.

## Implementation Brief and User Approval

After clarification, the main agent reads the relevant `docs/domains/*.md`
contracts and inspects nearby implementation patterns. It then presents a
concise implementation brief containing:

- user value and in-scope behavior;
- screen type and target, when applicable;
- persistence choice, when applicable;
- domain behavior and invariants;
- whether a consumer-facing API is required;
- request, response, and error semantics at the use-case level;
- frontend and backend boundaries;
- acceptance criteria and verification commands; and
- required domain-document changes or confirmation that domain meaning is
  unchanged.

The user must approve this brief before the main agent assigns OpenAPI or
implementation work.

## API Contract Workflow

When a consumer-facing API is required, the main agent assigns the
project-scoped `openapi` agent sole ownership of `docs/api/openapi.yaml`. The
task provides the approved implementation brief, relevant domain contracts,
affected operations, validation ownership, unresolved decisions, and required
validation commands.

The OpenAPI agent returns a proposed baseline. The main agent reviews its exact
revision or diff for domain consistency, request and response completeness,
error semantics, compatibility, and acceptance-criteria coverage. Only the
main agent may approve that exact baseline.

Any later edit to the OpenAPI document invalidates the prior baseline for
affected work. The main agent resolves the proposed change, reassigns the
affected operations to the OpenAPI agent, and approves the replacement
baseline before implementation resumes.

## Implementation Delegation

After OpenAPI approval, the main agent assigns implementation work using the
project-scoped agents:

- `frontend` owns explicitly assigned paths under `frontend/**`;
- `backend` owns explicitly assigned paths under `backend/**`.

Each task includes the approved OpenAPI baseline, assigned `operationId`
values, owned paths, relevant domain contracts, acceptance criteria,
constraints, and verification commands.

Run frontend and backend agents in parallel only when both sides are needed,
their work is independently testable, and their file ownership does not
overlap. Use only the relevant agent for frontend-only or backend-only work.
Do not spawn an implementation agent for a trivial or tightly coupled edit
when repository instructions require the main agent to retain it.

If domain meaning changes, the main agent assigns the matching
`docs/domains/*.md` file to exactly one agent or retains it. No two agents may
edit the same file concurrently. A dependency-direction change also assigns
`docs/domains/README.md` to one owner.

## Contract Feedback and Failure Handling

If the OpenAPI agent identifies a domain conflict or missing semantic
decision, pause only the affected operation and obtain the needed decision.

Frontend and backend agents never edit `docs/api/openapi.yaml`. If an approved
contract is infeasible or unsafe, they report the affected operation,
consumer or implementation impact, and a concrete contract-change proposal to
the main agent. The main agent either rejects the proposal or sends the
resolved change back to the OpenAPI agent. A revised contract requires a new
main-agent approval.

## Integration and Verification

The main agent reviews all delegated diffs and confirms:

- OpenAPI operations match frontend and backend request, response, status, and
  error behavior;
- frontend consumer types, API adapters, TanStack Query integration, MSW
  handlers, mock data, and tests match the approved baseline when applicable;
- backend routes, schemas, persistence behavior, and error mapping match the
  approved baseline when applicable;
- implementation and matching domain-document changes describe the same
  meaning and boundaries; and
- agents changed only their assigned paths.

The main agent runs the full verification required for every affected
application. Frontend verification includes, from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Backend verification follows `backend/README.md`, any nested
`backend/AGENTS.md`, and established backend commands. The skill must not
invent a new backend toolchain as part of an unrelated feature.

## Structural Validation

`scripts/validate-skill.sh` fails unless the skill contains:

- valid `name` and `description` frontmatter;
- the conditional UI question;
- the conditional persistence question with database, file, and recommendation
  choices;
- the user-approved implementation brief gate;
- OpenAPI delegation before API implementation;
- main-agent approval of the exact proposed baseline;
- conditional parallel frontend and backend delegation;
- non-overlapping file ownership and a single OpenAPI editor;
- contract-change and reapproval handling; and
- final frontend and backend verification responsibilities.

The script is the only requested skill-specific test artifact. Behavioral
benchmark scenarios and browser-based evaluation reports are out of scope.

## Acceptance Criteria

1. Codex can discover the skill from
   `.agents/skills/feature-development/SKILL.md`.
2. The skill asks UI and storage questions only when relevant and asks
   follow-ups one at a time.
3. No API contract or implementation begins before user approval of the
   implementation brief.
4. `openapi` exclusively authors API changes and the main agent approves an
   exact baseline before implementation.
5. Necessary frontend and backend agents receive the same approved baseline
   and may run in parallel only with disjoint ownership.
6. Frontend-only and backend-only work skip irrelevant agents.
7. Domain documents, API contract, implementation, and tests remain aligned.
8. The structural validation script passes and detects removal of each major
   workflow gate.
