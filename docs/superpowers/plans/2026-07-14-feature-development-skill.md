# Feature Development Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-scoped `feature-development` skill that safely coordinates clarified and approved feature work across OpenAPI, frontend, backend, domain documentation, and final verification.

**Architecture:** Store the instruction-only workflow in `.agents/skills/feature-development/SKILL.md`, the repository skill path supported by Codex. Add one colocated shell validator that treats the workflow's required gates as a structural contract and fails before the skill exists or whenever a required marker is removed.

**Tech Stack:** Agent Skills `SKILL.md`, POSIX shell, `awk`, `grep`, Git.

## Global Constraints

- Preserve all existing user changes, especially current edits under `.codex/agents/`, root and nested `AGENTS.md` files.
- Do not edit `docs/api/openapi.yaml`, application code, or domain contracts while creating this workflow skill.
- The project skill must live at `.agents/skills/feature-development/SKILL.md`.
- Ask the UI question only for UI work and the persistence question only when persistent storage is required.
- Require user approval of a concise implementation brief before OpenAPI authoring or implementation.
- Keep `openapi` as the sole author of `docs/api/openapi.yaml`; the main agent approves the exact proposed baseline.
- Run frontend and backend agents in parallel only after approval of the same baseline and only with non-overlapping ownership.
- The user selected deterministic structural validation instead of behavioral skill benchmarks.

---

### Task 1: Add the structural contract validator

**Files:**
- Create: `.agents/skills/feature-development/scripts/validate-skill.sh`
- Test: `.agents/skills/feature-development/scripts/validate-skill.sh`

**Interfaces:**
- Consumes: an optional first argument naming the `SKILL.md` to validate; defaults to the sibling `../SKILL.md`.
- Produces: exit status `0` and `feature-development skill structure: OK` on success; a non-zero exit status and a named missing requirement on failure.

- [ ] **Step 1: Create the executable validator before the skill**

Create `.agents/skills/feature-development/scripts/validate-skill.sh` with
this exact content:

```sh
#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_file=${1:-"$script_dir/../SKILL.md"}

fail() {
  printf 'feature-development skill structure: FAIL: %s\n' "$1" >&2
  exit 1
}

if [ ! -f "$skill_file" ]; then
  fail "skill file not found: $skill_file"
fi

frontmatter_delimiters=$(awk '$0 == "---" { count += 1 } END { print count + 0 }' "$skill_file")
if [ "$frontmatter_delimiters" -lt 2 ]; then
  fail "YAML frontmatter must have opening and closing delimiters"
fi

require_fixed() {
  marker=$1
  label=$2
  if ! grep -Fq -- "$marker" "$skill_file"; then
    fail "missing $label: $marker"
  fi
}

require_fixed 'name: feature-development' 'skill name'
require_fixed 'description: Use when' 'trigger description'
require_fixed 'new screen' 'new-screen choice'
require_fixed 'existing screen' 'existing-screen choice'
require_fixed 'database' 'database choice'
require_fixed 'file' 'file choice'
require_fixed 'recommended approach' 'recommendation choice'
require_fixed 'one at a time' 'question sequencing'
require_fixed 'implementation brief' 'implementation brief'
require_fixed 'user approves' 'user approval gate'
require_fixed '`openapi`' 'OpenAPI agent'
require_fixed '`docs/api/openapi.yaml`' 'OpenAPI ownership path'
require_fixed 'exact proposed baseline' 'main-agent baseline approval'
require_fixed '`frontend`' 'frontend agent'
require_fixed '`backend`' 'backend agent'
require_fixed 'parallel' 'parallel delegation'
require_fixed 'non-overlapping' 'disjoint ownership'
require_fixed '`operationId`' 'operation assignment'
require_fixed '`docs/domains/*.md`' 'domain-document synchronization'
require_fixed 'mise exec -- pnpm check' 'frontend check command'
require_fixed 'mise exec -- pnpm build' 'frontend build command'

printf 'feature-development skill structure: OK\n'
```

- [ ] **Step 2: Run the validator to verify RED**

Run:

```sh
chmod +x .agents/skills/feature-development/scripts/validate-skill.sh
.agents/skills/feature-development/scripts/validate-skill.sh
```

Expected: non-zero exit status with `skill file not found`, because
`.agents/skills/feature-development/SKILL.md` does not exist yet.

- [ ] **Step 3: Inspect the validator without changing unrelated files**

Run:

```sh
sh -n .agents/skills/feature-development/scripts/validate-skill.sh
git diff --check -- .agents/skills/feature-development/scripts/validate-skill.sh
```

Expected: both commands exit `0`.

- [ ] **Step 4: Commit the failing structural contract**

```sh
git add .agents/skills/feature-development/scripts/validate-skill.sh
git commit -m "test: define feature development skill contract"
```

### Task 2: Implement the feature-development workflow

**Files:**
- Create: `.agents/skills/feature-development/SKILL.md`
- Test: `.agents/skills/feature-development/scripts/validate-skill.sh`

**Interfaces:**
- Consumes: feature-addition requests, repository instructions, relevant domain contracts, nearby implementation patterns, and user answers.
- Produces: an approved implementation brief, an approved OpenAPI baseline when an API is needed, scoped agent assignments, integrated changes, and evidence-backed final verification.

- [ ] **Step 1: Create the complete workflow skill**

Create `.agents/skills/feature-development/SKILL.md` with this exact content:

````markdown
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
````

- [ ] **Step 2: Run the validator to verify GREEN**

Run:

```sh
.agents/skills/feature-development/scripts/validate-skill.sh
```

Expected: `feature-development skill structure: OK` and exit status `0`.

- [ ] **Step 3: Prove a required gate removal is detected**

Run:

```sh
tmp_skill="$(mktemp)"
sed '/exact proposed baseline/d' .agents/skills/feature-development/SKILL.md > "$tmp_skill"
if .agents/skills/feature-development/scripts/validate-skill.sh "$tmp_skill"; then
  rm -f "$tmp_skill"
  exit 1
fi
rm -f "$tmp_skill"
```

Expected: the validator reports the missing `exact proposed baseline`
requirement and the overall shell block exits `0`.

- [ ] **Step 4: Run final static checks**

Run:

```sh
sh -n .agents/skills/feature-development/scripts/validate-skill.sh
git diff --check -- .agents/skills/feature-development/SKILL.md .agents/skills/feature-development/scripts/validate-skill.sh
git status --short
```

Expected: shell syntax and diff checks pass. `git status --short` shows only
the new skill files plus the user's pre-existing unrelated changes.

- [ ] **Step 5: Commit the skill implementation**

```sh
git add .agents/skills/feature-development/SKILL.md
git commit -m "feat: add feature development skill"
```
