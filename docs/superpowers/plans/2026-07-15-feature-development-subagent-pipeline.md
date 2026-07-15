# Feature Development Subagent Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise the project-local `feature-development` skill so it coordinates UI planning, OpenAPI approval, parallel implementation, E2E work, parallel application reviews, remediation, and final verification through explicit subagent handoffs.

**Architecture:** Keep one orchestration skill as the source of the workflow. The main agent owns decisions and approval gates, while bounded subagents own UI planning, OpenAPI authoring, frontend/backend implementation, E2E generation, and read-only application review. Validate the behavior with the same application scenarios before and after the edit.

**Tech Stack:** Agent Skills Markdown, Codex project-scoped custom agents, task-scoped review subagents, Git, shell assertions

## Global Constraints

- Modify only `.agents/skills/feature-development/SKILL.md` for the deployed skill change.
- Preserve all unrelated working-tree changes.
- Keep the main agent responsible for scope, UI-plan approval, OpenAPI baseline approval, contract-change resolution, integration, and final verification.
- Keep `docs/api/openapi.yaml` exclusively owned by the `openapi` agent.
- Use the same approved OpenAPI baseline for parallel frontend and backend work.
- Assign every writable path to exactly one agent at a time.
- Treat `frontend-review` and `backend-review` as parallel, read-only task-scoped roles.
- Require remediation and re-review for validated Critical and Important findings.
- Do not create custom-agent TOML files in this change.

---

### Task 1: Establish failing workflow scenarios

**Files:**
- Reference: `.agents/skills/feature-development/SKILL.md`
- Reference: `docs/superpowers/specs/2026-07-15-feature-development-subagent-pipeline-design.md`
- Temporary test output: `/tmp/feature-development-skill-eval/old-skill/`

**Interfaces:**
- Consumes: the current skill and approved design specification.
- Produces: baseline outputs demonstrating which required pipeline stages the current skill omits.

- [ ] **Step 1: Snapshot the current skill for baseline evaluation**

Create `/tmp/feature-development-skill-eval/old-skill/SKILL.md` with the exact current contents of `.agents/skills/feature-development/SKILL.md`. Compare them with:

```sh
cmp .agents/skills/feature-development/SKILL.md /tmp/feature-development-skill-eval/old-skill/SKILL.md
```

Expected: exit status `0`.

- [ ] **Step 2: Dispatch three baseline scenarios in parallel**

Give each baseline subagent only the old skill snapshot, relevant repository instructions, and one scenario:

1. A new cross-stack screen requiring a UI plan, a new API operation, frontend/backend implementation, E2E tests, parallel application reviews, remediation, and final verification.
2. A substantial frontend-only new screen requiring a UI plan, no API change, frontend E2E tests, frontend review, and final verification.
3. A backend-only API change requiring OpenAPI approval, backend implementation, backend review, contract feedback handling, and final verification.

Require each subagent to return an ordered workflow, named subagents, artifacts passed between stages, approval gates, review severities, and re-review behavior. The subagents are read-only and must not edit repository files.

- [ ] **Step 3: Verify the baseline fails for the intended reason**

Inspect all three outputs. Expected omissions in the current skill:

- no mandatory `ui-planner` stage or UI-plan approval gate;
- no UI-plan path and `REQ-*` handoff to frontend;
- no frontend E2E planner/generator stage;
- no parallel `frontend-review` and `backend-review` stage;
- no severity-ranked review verdict or remediation/re-review loop.

If the old skill already produces all of these behaviors, stop because the proposed revision has no demonstrated need.

### Task 2: Revise the feature-development workflow

**Files:**
- Modify: `.agents/skills/feature-development/SKILL.md`
- Reference: `docs/superpowers/specs/2026-07-15-feature-development-subagent-pipeline-design.md`

**Interfaces:**
- Consumes: the approved design and baseline failure evidence.
- Produces: one concise orchestration skill with conditional stage gates and complete dispatch contracts.

- [ ] **Step 1: Add the core pipeline and ownership principle**

Revise the overview to state the ordered cross-stack sequence:

```text
implementation brief -> UI plan -> approved OpenAPI -> parallel implementation
-> frontend E2E -> parallel application reviews -> remediation/re-review
-> main-agent final verification
```

State that executable stages may be delegated while main-agent decisions and approvals remain non-delegable.

- [ ] **Step 2: Add UI-plan delegation and approval**

Add a stage requiring substantial UI work to use the project-scoped `ui-planner`. Define its assignment fields and the returned approved artifact fields:

```text
UI-plan path, exact revision or diff, assigned REQ-* IDs, confirmed decisions,
accepted assumptions, unresolved material questions
```

Define observable blocking conditions for unresolved domain, security, privacy, required-data, API-semantic, or primary-flow questions.

- [ ] **Step 3: Connect the approved UI plan to OpenAPI**

Require the OpenAPI assignment to reference the approved UI plan and in-scope requirements. Preserve exclusive OpenAPI ownership and exact-baseline approval. State that no affected frontend/backend API work begins until the main agent approves the proposed baseline.

- [ ] **Step 4: Expand implementation dispatch contracts**

Require frontend/backend assignments to include owned paths, deliverables, exclusions, domain contracts, acceptance criteria, approved UI-plan path and `REQ-*` IDs, approved OpenAPI baseline and `operationId` values, dependency/persistence decisions, domain-document ownership, and exact verification commands.

- [ ] **Step 5: Add frontend E2E delegation**

After frontend implementation, require the configured Playwright planner followed by the configured Playwright generator, using the acceptance criteria and UI-plan requirements. If either required custom agent is absent, require a blocker report rather than silent replacement.

- [ ] **Step 6: Add parallel read-only application review**

Define task-scoped roles named `frontend-review` and `backend-review`. Run affected reviewers in parallel after implementation and required E2E work. Each assignment contains the exact diff boundary, implementation summary, approved artifacts, affected paths, acceptance criteria, and verification evidence.

Require findings to contain:

```text
severity, file and line evidence, rationale, recommended correction, verdict
```

Use `Critical`, `Important`, and `Minor` severities and `approved` or `changes-required` verdicts.

- [ ] **Step 7: Add remediation and re-review**

Require the main agent to verify findings technically, assign valid corrections to the original implementer, record dispositions for rejected findings, rerun checks, and redispatch the affected reviewer. Block final verification while a validated Critical or Important finding remains or an affected reviewer returns `changes-required`.

- [ ] **Step 8: Add conditional-path guidance and common mistakes**

Add a compact table covering cross-stack, frontend-only, backend-only, API-only, and trivial/tightly coupled changes. Add common mistakes covering premature implementation, unapproved baselines, overlapping ownership, reviewers editing code, skipped re-review, and delegated final approval.

- [ ] **Step 9: Check the skill structure**

Run:

```sh
python - <<'PY'
from pathlib import Path

path = Path('.agents/skills/feature-development/SKILL.md')
text = path.read_text()
assert text.startswith('---\nname: feature-development\n')
assert 'description: Use when' in text
for required in (
    'ui-planner',
    'REQ-*',
    'exact proposed baseline',
    'frontend-review',
    'backend-review',
    'Critical',
    'Important',
    'changes-required',
    're-review',
):
    assert required in text, required
print('feature-development skill structure valid')
PY
```

Expected: print `feature-development skill structure valid`.

### Task 3: Verify revised behavior against the baseline

**Files:**
- Reference: `.agents/skills/feature-development/SKILL.md`
- Reference: `/tmp/feature-development-skill-eval/old-skill/SKILL.md`
- Temporary test output: `/tmp/feature-development-skill-eval/revised-skill/`

**Interfaces:**
- Consumes: the same three scenarios from Task 1 and the revised skill.
- Produces: comparison evidence that the revised skill covers the approved pipeline without weakening existing gates.

- [ ] **Step 1: Dispatch the same three scenarios against the revised skill**

Run three fresh, read-only subagents in parallel. Use the exact Task 1 prompts, replacing only the skill path with `.agents/skills/feature-development/SKILL.md`.

- [ ] **Step 2: Grade required behavior**

For each applicable scenario, confirm the output:

- delegates substantial UI planning to `ui-planner`;
- records UI-plan approval, path, and `REQ-*` IDs;
- delegates OpenAPI exclusively and waits for exact baseline approval;
- dispatches frontend/backend in parallel only with non-overlapping ownership;
- performs frontend E2E planning then generation;
- dispatches affected application reviewers in parallel and read-only;
- reports severity, evidence, correction, and verdict;
- remediates through the original implementer and re-reviews;
- retains domain-document ownership and contract-feedback rules;
- leaves final integration and verification with the main agent.

- [ ] **Step 3: Compare old and revised outputs**

Record which assertions fail for the old skill and pass for the revised skill. If the revised output omits an acceptance criterion, make the smallest wording correction and rerun only the affected scenario plus one neighboring scenario.

### Task 4: Final skill verification and commit

**Files:**
- Modify: `.agents/skills/feature-development/SKILL.md`

**Interfaces:**
- Consumes: passing revised behavior scenarios.
- Produces: a reviewed, committed skill change with no unrelated files.

- [ ] **Step 1: Run static verification**

Run:

```sh
git diff --check -- .agents/skills/feature-development/SKILL.md
wc -l -w .agents/skills/feature-development/SKILL.md
git diff -- .agents/skills/feature-development/SKILL.md
git status --short
```

Expected: no whitespace errors; the skill remains below 500 lines; only the intended skill and pre-existing unrelated user changes appear.

- [ ] **Step 2: Self-review against the design**

Confirm every section of the approved design has a corresponding workflow stage or explicit conditional skip. Confirm the wording does not imply that a subagent may approve its own work or that reviewers may edit files.

- [ ] **Step 3: Commit only the skill**

```sh
git add -- .agents/skills/feature-development/SKILL.md
git commit -m "feat: orchestrate feature development subagents"
```

Expected: one commit containing only `.agents/skills/feature-development/SKILL.md`.
