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
documentation impact. Do not author OpenAPI or implement code until the user approves this brief.

## 4. Draft and approve the API contract

When an API is required, assign the project-scoped `openapi` agent sole
ownership of `docs/api/openapi.yaml`. Provide the approved use case, domain
behavior, acceptance criteria, validation ownership, affected operations,
unresolved decisions, owned path, and validation commands.

Review the returned contract for domain consistency, completeness, errors, and
compatibility. The main agent must approve the `exact proposed baseline`
before implementation. Every later OpenAPI edit creates a new proposal; pause
affected work until the replacement baseline is approved.

Skip this section when no consumer-facing API changes.

## 5. Delegate implementation

For each assignment, state owned paths, deliverable, constraints, verification
commands, relevant domain contracts, acceptance criteria, approved baseline,
and assigned `operationId` values.

Use the project-scoped `frontend` and `backend` agents in `parallel` only when
both are needed, their work is substantial and independently testable, and
their ownership is `non-overlapping`. Use only the relevant agent for
frontend-only or backend-only work. Retain trivial or tightly coupled edits in
the main thread.

Assign each affected `docs/domains/*.md` file to exactly one agent or retain it
in the main thread. Assign `docs/domains/README.md` too when dependency
directions change. Never let two agents edit the same file concurrently.

## 6. Resolve contract feedback

Frontend and backend agents never edit `docs/api/openapi.yaml`. They report an
infeasible or unsafe operation with its impact and a concrete change proposal.
Resolve the proposal, send accepted changes to `openapi`, and approve the new
exact baseline before affected implementation resumes.

## 7. Integrate and verify

Review every delegated diff and confirm the OpenAPI request, response, status,
and error behavior matches frontend consumers and backend handlers. Confirm
implementation and domain documents describe identical behavior and
boundaries.

Require focused agent checks, then run all checks for each affected app. From
`frontend/`, run:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

For backend work, run commands defined by `backend/README.md` and nested
`backend/AGENTS.md`; do not invent a new toolchain for an unrelated feature.

Report implemented behavior, changed files, the approved OpenAPI baseline and
operations, domain updates, verification commands and results, and remaining
risks.
