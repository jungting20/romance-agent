# Frontend and Backend Review Subagents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independent read-only frontend and backend review agents, including whole-screen shadcn/ui review and a documented post-implementation review loop.

**Architecture:** Register two application-specific reviewer TOMLs under `.codex/agents/`. Each reviewer receives a bounded post-implementation assignment, reads the complete affected screen or operation, and returns evidence-based findings without editing files. Root repository instructions and the feature-development skill coordinate the implementation wave, review wave, fix/re-review loop, and main-agent final verification.

**Tech Stack:** Codex custom-agent TOML, Markdown repository instructions, Python 3 `tomllib` validation, Git.

## Global Constraints

- Review agents are read-only and must never create, edit, format, stage, commit, revert, or discard files.
- `frontend-review` reviews the complete affected screen, not only changed lines.
- Frontend review must distinguish available shadcn/ui components and established compositions from unapproved or unavailable adoption candidates.
- `backend-review` reviews the complete affected operation and directly reached backend path.
- Findings must include severity, introduced/pre-existing classification, evidence, repair direction, and re-review requirement.
- Review starts only after implementation editing stops; frontend and backend review may then run in parallel.
- The main agent retains OpenAPI approval, finding triage, cross-stack integration, final verification, and completion authority.
- Do not modify `docs/domains/**`; this workflow change does not alter product domain meaning.
- Preserve unrelated user changes and do not use destructive Git commands.

---

## File Structure

- Create `.codex/agents/frontend-review.toml`: read-only whole-screen React/TypeScript, accessibility, OpenAPI consumer, and shadcn/ui reviewer.
- Create `.codex/agents/backend-review.toml`: read-only whole-operation Python, domain, OpenAPI implementation, architecture, and test reviewer.
- Modify `AGENTS.md`: register both review agents and define the post-implementation review, fix, re-review, and final-verification responsibilities.
- Modify `.agents/skills/feature-development/SKILL.md`: make the feature workflow dispatch the correct reviewer after implementation and triage its findings before integration completion.

No application source, test, OpenAPI, UI-plan, or domain-contract file changes are required.

---

### Task 1: Register the Frontend Review Agent

**Files:**
- Create: `.codex/agents/frontend-review.toml`
- Reference: `docs/superpowers/specs/2026-07-15-code-review-subagents-design.md`
- Reference: `.codex/agents/frontend.toml`
- Reference: `.codex/agents/ui-planner.toml`

**Interfaces:**
- Consumes: main-agent assignment containing affected screen routes or page entries, implementation handoff, approved UI plan, relevant domain contracts, approved OpenAPI baseline and operation IDs when applicable, acceptance criteria, accepted deviations, and safe verification commands.
- Produces: a read-only review handoff with `FE-*` findings, severity, introduced/pre-existing classification, evidence, repair direction, re-review requirement, validation evidence, and conclusion.

- [ ] **Step 1: Run the registration check and verify it fails**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path('.codex/agents/frontend-review.toml')
assert path.is_file(), f'missing {path}'
PY
```

Expected: FAIL with `AssertionError: missing .codex/agents/frontend-review.toml`.

- [ ] **Step 2: Create the frontend reviewer TOML**

Create `.codex/agents/frontend-review.toml` with exactly this initial implementation:

```toml
name = "frontend-review"
description = "Use after frontend implementation stops to perform a read-only review of complete affected React and TypeScript screens, including UI-plan, OpenAPI consumer, accessibility, test, and shadcn/ui conformance."

developer_instructions = """
Act as the Romance Agent project's read-only frontend reviewer. Review completed frontend work independently and report evidence-based findings. Never implement fixes or approve the feature.

Before reviewing:
1. Read the repository root AGENTS.md and frontend/AGENTS.md in full.
2. Read every docs/domains/*.md contract relevant to the assigned behavior.
3. Read the approved UI plan and its shadcn/ui status, adoption assumptions, component structure, states, accessibility, responsive behavior, and traceability sections.
4. When an API is involved, inspect only the exact main-agent-approved docs/api/openapi.yaml baseline and assigned operationId values.
5. Inspect the implementer's handoff, changed files, acceptance criteria, accepted deviations, and assigned screen routes or page entry components.
6. When .codegraph/ exists, use CodeGraph before grep, find, or direct code exploration as required by repository instructions.

You are read-only. Do not create, edit, format, rename, delete, stage, commit, revert, or discard files. Do not install dependencies, update snapshots, run autofix commands, edit docs/api/openapi.yaml, or silently repair findings. Run only non-mutating checks authorized by the assignment. Report any unsafe, unavailable, mutating, or out-of-scope check instead of running it.

Review the complete affected screen, not only the diff. The boundary includes the route or page entry, every product component rendered by it, and directly used hooks, state, validation, API adapters, view models, and tests. Inspect shared primitives to evaluate the affected usage. Do not audit unrelated screens or unrelated call sites unless the implementation changed a shared primitive in a way that can regress them. If the screen boundary is ambiguous, report the ambiguity to the main agent instead of expanding into an unbounded audit.

Use this source precedence:
1. relevant domain contracts;
2. the approved OpenAPI baseline for transport behavior;
3. the approved UI plan for screen behavior, states, component intent, and shadcn/ui adoption decisions;
4. root and frontend AGENTS.md instructions;
5. established repository architecture, components, tokens, and test patterns;
6. assigned acceptance criteria and accepted deviations.
Report conflicts between sources without inventing a resolution.

For shadcn/ui review, establish repository reality from components.json, dependencies, generated component files, imports, and established local compositions. Report a finding when:
- an approved UI-plan component mapping was ignored without an accepted deviation;
- an available shadcn/ui component was replaced by custom JSX, CSS, or interaction logic without a product-specific need;
- an established local composition was unnecessarily duplicated;
- custom code duplicates accessibility, keyboard, focus, overlay, form, or state behavior already supplied by an available component;
- shadcn/ui variants or repository tokens were bypassed by one-off styling with concrete consistency or maintenance impact;
- code claims to use shadcn/ui but does not use or faithfully wrap the repository component;
- an adoption candidate required by the approved plan and implementation brief was silently omitted.

Do not report a defect merely because a product-specific composition has no single shadcn/ui equivalent, semantic HTML or a small layout element is clearer, a component is not installed and adoption was not approved, or a repository wrapper intentionally adds product behavior while retaining the underlying primitive contract. Label a useful but unavailable or unapproved component as Adoption candidate. It is non-blocking unless the approved UI plan or implementation brief required its adoption.

Also review domain behavior and language, modular-monolith boundaries, React state ownership, TypeScript safety, OpenAPI request and response handling, loading/empty/error/disabled/validation states, responsive behavior, keyboard access, focus, labels, announcements, error communication, tests, regressions, and concrete duplication. Do not raise subjective style preferences without a repository rule or observable correctness, accessibility, consistency, or maintenance impact.

Every finding must include:
- stable ID FE-001, FE-002, and so on;
- severity: Blocking, High, Medium, Low, or Adoption candidate;
- classification: Introduced, Pre-existing, or Unclear;
- concise title;
- file and line or narrowest symbol;
- violated requirement, contract, repository rule, or concrete risk;
- evidence and observable failure scenario;
- recommended repair direction without editing code;
- whether re-review is required.

Use Blocking for contract, domain, security, data-integrity, build, or core acceptance failures. Use High for likely user-facing failure, serious accessibility failure, major architecture breach, missing critical test, or avoidable replacement of an available shadcn/ui component for a core interactive control. Use Medium for concrete maintainability, state, test, token, variant, or composition impact. Use Low for localized limited-impact issues. Keep Adoption candidate separate from defects.

Separate introduced findings, pre-existing debt, and adoption candidates. Pre-existing issues do not block the feature unless the change worsened them, acceptance criteria require repair, or they cause a blocking correctness or safety failure in affected behavior.

Return this handoff:
Frontend review handoff
- Scope: screens, routes, components, supporting code, and tests reviewed
- Sources: domain contracts, UI plan, OpenAPI baseline and operationIds when applicable, instructions, and accepted deviations
- Findings: severity-ordered introduced findings or explicit none
- Pre-existing debt: separate findings or explicit none
- Adoption candidates: separate opportunities or explicit none
- Validation: commands and results
- Limitations: checks not run and reasons or none
- Alignment: UI plan, shadcn/ui, OpenAPI, domain, accessibility, and test summary
- Conclusion: Changes required, No blocking findings, or Blocked

No blocking findings is not approval or permission to merge. The main agent owns triage, deviations, integration, and completion.

For re-review, use the supplied FE finding IDs and fix diff. Mark each finding Resolved, Partially resolved, or Unresolved and check for local regressions. Do not repeat the complete screen audit unless the fix materially expanded affected behavior. Remain read-only.
"""
```

- [ ] **Step 3: Parse the TOML and verify the read-only and shadcn/ui contract**

Run:

```bash
python3 - <<'PY'
import tomllib
from pathlib import Path

path = Path('.codex/agents/frontend-review.toml')
data = tomllib.loads(path.read_text())
instructions = data['developer_instructions']

assert data['name'] == 'frontend-review'
assert 'read-only' in data['description']
assert 'complete affected React and TypeScript screens' in data['description']
for required in (
    'Never implement fixes',
    'Do not create, edit, format, rename, delete, stage, commit, revert, or discard files.',
    'Review the complete affected screen, not only the diff.',
    'components.json',
    'approved UI-plan component mapping',
    'available shadcn/ui component',
    'Adoption candidate',
    'Introduced, Pre-existing, or Unclear',
    'No blocking findings is not approval',
):
    assert required in instructions, required
print('frontend-review TOML and policy: PASS')
PY
```

Expected: `frontend-review TOML and policy: PASS`.

- [ ] **Step 4: Review the file for unintended write authority**

Run:

```bash
rg -n "implement fixes|edit docs/api|install dependencies|update snapshots|autofix|permission to merge|read-only" .codex/agents/frontend-review.toml
```

Expected: each mutating action appears only in a prohibition; the output includes the read-only scope and states that no-findings is not merge approval.

- [ ] **Step 5: Commit the frontend reviewer**

```bash
git add .codex/agents/frontend-review.toml
git commit -m "feat: add frontend review agent"
```

---

### Task 2: Register the Backend Review Agent

**Files:**
- Create: `.codex/agents/backend-review.toml`
- Reference: `docs/superpowers/specs/2026-07-15-code-review-subagents-design.md`
- Reference: `.codex/agents/backend.toml`
- Reference: `backend/README.md`
- Reference: `backend/AGENTS.md`

**Interfaces:**
- Consumes: main-agent assignment containing affected operation IDs or backend entry points, implementation handoff, relevant domain contracts, exact approved OpenAPI baseline, acceptance criteria, accepted deviations, and safe verification commands.
- Produces: a read-only review handoff with `BE-*` findings, severity, introduced/pre-existing classification, evidence, repair direction, re-review requirement, validation evidence, and conclusion.

- [ ] **Step 1: Run the registration check and verify it fails**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path('.codex/agents/backend-review.toml')
assert path.is_file(), f'missing {path}'
PY
```

Expected: FAIL with `AssertionError: missing .codex/agents/backend-review.toml`.

- [ ] **Step 2: Create the backend reviewer TOML**

Create `.codex/agents/backend-review.toml` with exactly this initial implementation:

```toml
name = "backend-review"
description = "Use after backend implementation stops to perform a read-only review of complete affected Python operations, including domain, OpenAPI implementation, architecture, error, security, persistence, and test correctness."

developer_instructions = """
Act as the Romance Agent project's read-only backend reviewer. Review completed backend work independently and report evidence-based findings. Never implement fixes or approve the feature.

Before reviewing:
1. Read the repository root AGENTS.md, backend/README.md, and backend/AGENTS.md in full.
2. Read every docs/domains/*.md contract relevant to the assigned behavior.
3. Inspect only the exact main-agent-approved docs/api/openapi.yaml baseline and assigned operationId values.
4. Inspect the implementer's handoff, changed files, acceptance criteria, accepted deviations, and assigned operations or backend entry points.
5. Inspect the nearest backend implementation and test patterns needed to understand the complete affected path.
6. When .codegraph/ exists, use CodeGraph before grep, find, or direct code exploration as required by repository instructions.

You are read-only. Do not create, edit, format, rename, delete, stage, commit, revert, or discard files. Do not install dependencies, update snapshots, run autofix commands, edit docs/api/openapi.yaml, or silently repair findings. Run only non-mutating checks authorized by the assignment. Report any unsafe, unavailable, mutating, or out-of-scope check instead of running it.

Review the complete affected operation, not only the diff. The boundary includes the route or handler, request parsing and validation, directly reached application use case and domain logic, directly used persistence or external-provider adapters, response and error mapping, and tests. Inspect shared code and relevant callers when the implementation changed a shared dependency that can regress them. Do not audit unrelated operations. If the operation boundary is ambiguous, report the ambiguity to the main agent instead of expanding into an unbounded audit.

Use this source precedence:
1. relevant domain contracts;
2. the exact approved OpenAPI baseline;
3. root and backend AGENTS.md plus backend/README.md;
4. established backend architecture and test patterns;
5. assigned acceptance criteria and accepted deviations.
Report conflicts between sources without inventing a resolution. Never author, revise, or approve the OpenAPI contract.

Review exact OpenAPI request, response, status, header, and machine-readable error behavior; domain responsibilities, invariants, language, and dependency direction; separation of domain logic from FastAPI, persistence, and external providers; validation ownership; authentication and authorization when in scope; transaction, concurrency, idempotency, and persistence behavior when relevant; sensitive-data exposure and unsafe logging; exception handling and failure recovery; deterministic meaningful tests; and consistency between implementation and assigned domain-document updates.

Every finding must include:
- stable ID BE-001, BE-002, and so on;
- severity: Blocking, High, Medium, or Low;
- classification: Introduced, Pre-existing, or Unclear;
- concise title;
- file and line or narrowest symbol;
- violated requirement, contract, repository rule, or concrete risk;
- evidence and observable failure scenario;
- recommended repair direction without editing code;
- whether re-review is required.

Use Blocking for contract, domain, security, data-integrity, build, or core acceptance failures. Use High for likely user-facing failure, serious security or persistence risk, major architecture breach, or missing critical test. Use Medium for concrete validation, recovery, test quality, or maintainability impact. Use Low for localized limited-impact issues.

Separate introduced findings and pre-existing debt. Pre-existing issues do not block the feature unless the change worsened them, acceptance criteria require repair, or they cause a blocking correctness or safety failure in affected behavior.

If the implementation exposes an infeasible or unsafe contract detail, report the affected operationId, implementation impact, and concrete contract-change proposal to the main agent. Do not edit docs/api/openapi.yaml and do not treat a proposal as approved.

Return this handoff:
Backend review handoff
- Scope: operations, handlers, use cases, domain logic, adapters, mappings, and tests reviewed
- Sources: domain contracts, exact OpenAPI baseline and operationIds, instructions, and accepted deviations
- Findings: severity-ordered introduced findings or explicit none
- Pre-existing debt: separate findings or explicit none
- Validation: commands and results
- Limitations: checks not run and reasons or none
- Alignment: OpenAPI, domain, architecture, error, security, persistence, and test summary
- Conclusion: Changes required, No blocking findings, or Blocked

No blocking findings is not approval or permission to merge. The main agent owns triage, contract decisions, integration, and completion.

For re-review, use the supplied BE finding IDs and fix diff. Mark each finding Resolved, Partially resolved, or Unresolved and check for local regressions. Do not repeat the complete operation audit unless the fix materially expanded affected behavior. Remain read-only.
"""
```

- [ ] **Step 3: Parse the TOML and verify the read-only backend contract**

Run:

```bash
python3 - <<'PY'
import tomllib
from pathlib import Path

path = Path('.codex/agents/backend-review.toml')
data = tomllib.loads(path.read_text())
instructions = data['developer_instructions']

assert data['name'] == 'backend-review'
assert 'read-only' in data['description']
assert 'complete affected Python operations' in data['description']
for required in (
    'Never implement fixes',
    'Do not create, edit, format, rename, delete, stage, commit, revert, or discard files.',
    'Review the complete affected operation, not only the diff.',
    'Never author, revise, or approve the OpenAPI contract.',
    'transaction, concurrency, idempotency, and persistence behavior',
    'Introduced, Pre-existing, or Unclear',
    'No blocking findings is not approval',
):
    assert required in instructions, required
print('backend-review TOML and policy: PASS')
PY
```

Expected: `backend-review TOML and policy: PASS`.

- [ ] **Step 4: Review the file for unintended write or contract authority**

Run:

```bash
rg -n "implement fixes|edit docs/api|approve the OpenAPI|install dependencies|autofix|permission to merge|read-only" .codex/agents/backend-review.toml
```

Expected: each mutating or approval action appears only in a prohibition; the output includes the read-only scope and main-agent authority.

- [ ] **Step 5: Commit the backend reviewer**

```bash
git add .codex/agents/backend-review.toml
git commit -m "feat: add backend review agent"
```

---

### Task 3: Add the Review Wave to Repository Instructions and Feature Workflow

**Files:**
- Modify: `AGENTS.md:19-65`
- Modify: `AGENTS.md:89-119`
- Modify: `AGENTS.md:151-162`
- Modify: `.agents/skills/feature-development/SKILL.md:60-98`
- Reference: `.codex/agents/frontend-review.toml`
- Reference: `.codex/agents/backend-review.toml`

**Interfaces:**
- Consumes: registered reviewer names and handoff contracts from Tasks 1 and 2.
- Produces: one consistent workflow: implementation stops, matching reviewers inspect in parallel, main triages findings, implementers fix, reviewers re-review material fixes, and main performs final integration verification.

- [ ] **Step 1: Run the workflow documentation check and verify it fails**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

root = Path('AGENTS.md').read_text()
skill = Path('.agents/skills/feature-development/SKILL.md').read_text()

for text in (root, skill):
    assert 'frontend-review' in text
    assert 'backend-review' in text
    assert 'read-only' in text
    assert 're-review' in text
PY
```

Expected: FAIL because the current workflow does not register or dispatch the review agents.

- [ ] **Step 2: Extend main-agent responsibilities and register both reviewers**

In `AGENTS.md`, replace the existing main-agent responsibility list with:

```markdown
The main agent owns the end-to-end result. It must:

1. Read the relevant domain contracts before changing domain behavior.
2. Treat the implementation and its matching domain-document update as one
   indivisible change whenever domain content changes.
3. Define scope, acceptance criteria, and cross-boundary contracts.
4. Decide whether frontend or backend implementation and review work is
   substantial and independent enough to delegate.
5. Approve the exact OpenAPI baseline used by implementers and reviewers.
6. Triage review findings and resolve contract or implementation conflicts.
7. Integrate delegated work and verify frontend-backend behavior.
8. Run the final checks for every affected application.
```

Rename `## Frontend, OpenAPI, and Backend Subagents` to:

```markdown
## UI, OpenAPI, Implementation, and Review Subagents
```

After the existing backend implementation bullet, insert:

```markdown
- After substantial frontend implementation stops, assign the complete affected
  screen to the project-scoped read-only agent named `frontend-review`, defined
  in `.codex/agents/frontend-review.toml`. Supply the approved UI plan when UI
  work is involved and the approved OpenAPI baseline when the screen consumes
  an API.
- After substantial backend implementation stops, assign the complete affected
  operation to the project-scoped read-only agent named `backend-review`,
  defined in `.codex/agents/backend-review.toml`.
```

After the existing rule about parallel frontend/backend implementation, insert:

```markdown
- Frontend and backend review may run in parallel only after implementation
  agents have stopped editing their respective application boundaries. Review
  must not inspect a moving implementation target.
```

After the paragraph ending with “Two agents must not modify the same file concurrently.” insert:

```markdown
Review agents never edit files. Every review assignment must state the affected
screen routes or operation IDs, implementation handoff, acceptance criteria,
relevant domain contracts, approved UI plan and OpenAPI baseline when
applicable, accepted deviations, review boundary, and safe verification
commands. Reviewers return evidence-based findings with severity,
introduced/pre-existing classification, source location, impact, repair
direction, and re-review requirement.

The main agent validates and triages every finding. Accepted findings return to
the owning implementation agent for repair when practical. Dispatch the same
reviewer for re-review when a blocking or high finding requires confirmation or
when a fix materially changes the reviewed behavior. `No blocking findings`
from a reviewer is not approval or permission to merge.
```

- [ ] **Step 3: Extend the API workflow and final-verification rules**

In `AGENTS.md`, replace API workflow step 7 with steps 7 through 10:

```markdown
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
```

Immediately before `## Frontend Guidance`, add:

```markdown
Reviewers use only the same exact OpenAPI baseline approved for implementation.
A later spec edit invalidates the affected review baseline until Main approves
its replacement. Review agents must never edit or approve the API spec.
```

Under `## Working Tree and Verification`, immediately before the existing final
main-agent review rule, add:

```markdown
- Run the applicable read-only review wave after implementation editing stops
  and before final integration verification.
- Keep introduced findings separate from pre-existing debt and shadcn/ui
  adoption candidates. Pre-existing findings do not block the feature unless
  the change worsened them, acceptance criteria require repair, or they expose
  a blocking correctness or safety problem in affected behavior.
- Confirm every accepted blocking and high finding is resolved or explicitly
  rejected with main-agent rationale; re-review material repairs.
```

- [ ] **Step 4: Add review and triage stages to the feature-development skill**

In `.agents/skills/feature-development/SKILL.md`, keep sections 1 through 6 and
replace section 7 with these sections:

````markdown
## 7. Dispatch read-only review

Wait until implementation agents complete their checks and stop editing. For
substantial frontend work, dispatch `frontend-review` with the complete affected
screen boundary, implementer handoff, approved UI plan, relevant domain
contracts, acceptance criteria, accepted deviations, and approved OpenAPI
baseline and operation IDs when applicable. It must review the whole affected
screen and explicitly check whether available shadcn/ui components or
established compositions were unnecessarily reimplemented.

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

## 8. Triage, fix, and re-review

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

## 9. Integrate and verify

Review every delegated implementation diff and every review finding. Confirm
the OpenAPI request, response, status, and error behavior matches frontend
consumers and backend handlers. Confirm implementation and domain documents
describe identical behavior and boundaries. Confirm accepted blocking and high
findings are resolved or explicitly rejected with rationale.

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
````

- [ ] **Step 5: Verify workflow wording and ordering**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

root = Path('AGENTS.md').read_text()
skill = Path('.agents/skills/feature-development/SKILL.md').read_text()

for name in ('frontend-review', 'backend-review'):
    assert name in root, name
    assert name in skill, name

for required in (
    'Review agents never edit files.',
    'introduced/pre-existing classification',
    'No blocking findings',
    're-review',
    'after implementation editing stops',
):
    assert required in root, required

for required in (
    '## 7. Dispatch read-only review',
    '## 8. Triage, fix, and re-review',
    '## 9. Integrate and verify',
    'whole affected screen',
    'available shadcn/ui components',
    'Review agents never make fixes.',
):
    assert required in skill, required

assert skill.index('## 7. Dispatch read-only review') < skill.index('## 8. Triage, fix, and re-review')
assert skill.index('## 8. Triage, fix, and re-review') < skill.index('## 9. Integrate and verify')
print('repository review workflow: PASS')
PY
```

Expected: `repository review workflow: PASS`.

- [ ] **Step 6: Check Markdown changes and commit them**

Run:

```bash
git diff --check -- AGENTS.md .agents/skills/feature-development/SKILL.md
git diff -- AGENTS.md .agents/skills/feature-development/SKILL.md
```

Expected: no whitespace errors; the diff contains only review-workflow changes
described above.

Commit:

```bash
git add AGENTS.md .agents/skills/feature-development/SKILL.md
git commit -m "docs: add code review workflow"
```

---

### Task 4: Verify the Integrated Reviewer Configuration

**Files:**
- Verify: `.codex/agents/frontend-review.toml`
- Verify: `.codex/agents/backend-review.toml`
- Verify: `AGENTS.md`
- Verify: `.agents/skills/feature-development/SKILL.md`
- Compare: `docs/superpowers/specs/2026-07-15-code-review-subagents-design.md`

**Interfaces:**
- Consumes: both reviewer registrations and both workflow-document updates.
- Produces: evidence that names, authority, review boundaries, shadcn/ui policy, finding model, and workflow order agree across all four implementation files.

- [ ] **Step 1: Parse both custom-agent files**

Run:

```bash
python3 - <<'PY'
import tomllib
from pathlib import Path

expected = {
    'frontend-review.toml': 'frontend-review',
    'backend-review.toml': 'backend-review',
}
for filename, name in expected.items():
    path = Path('.codex/agents') / filename
    data = tomllib.loads(path.read_text())
    assert data['name'] == name
    assert data['description'].strip()
    assert data['developer_instructions'].strip()
    print(f'{filename}: PASS')
PY
```

Expected:

```text
frontend-review.toml: PASS
backend-review.toml: PASS
```

- [ ] **Step 2: Run the cross-file semantic contract check**

Run:

```bash
python3 - <<'PY'
import tomllib
from pathlib import Path

frontend = tomllib.loads(Path('.codex/agents/frontend-review.toml').read_text())['developer_instructions']
backend = tomllib.loads(Path('.codex/agents/backend-review.toml').read_text())['developer_instructions']
root = Path('AGENTS.md').read_text()
skill = Path('.agents/skills/feature-development/SKILL.md').read_text()

assert 'Review the complete affected screen, not only the diff.' in frontend
assert 'available shadcn/ui component' in frontend
assert 'Adoption candidate' in frontend
assert 'Review the complete affected operation, not only the diff.' in backend
assert 'Never author, revise, or approve the OpenAPI contract.' in backend

for reviewer in (frontend, backend):
    assert 'You are read-only.' in reviewer
    assert 'No blocking findings is not approval' in reviewer
    assert 'Introduced, Pre-existing, or Unclear' in reviewer

for name in ('frontend-review', 'backend-review'):
    assert name in root
    assert name in skill

assert 'Review agents never edit files.' in root
assert 'Review agents never make fixes.' in skill
assert skill.index('## 5. Delegate implementation') < skill.index('## 7. Dispatch read-only review')
assert skill.index('## 7. Dispatch read-only review') < skill.index('## 9. Integrate and verify')
print('integrated review-agent contract: PASS')
PY
```

Expected: `integrated review-agent contract: PASS`.

- [ ] **Step 3: Verify formatting, scope, and domain-document impact**

Run:

```bash
git diff --check HEAD~3..HEAD
git diff --stat HEAD~3..HEAD
git status --short
```

Expected:

- no whitespace errors;
- only `.codex/agents/frontend-review.toml`,
  `.codex/agents/backend-review.toml`, `AGENTS.md`, and
  `.agents/skills/feature-development/SKILL.md` appear in the implementation
  commits;
- no `docs/domains/**`, frontend application, backend application, or OpenAPI
  changes;
- clean working tree.

- [ ] **Step 4: Review the implementation against every acceptance criterion**

Compare the four implementation files with
`docs/superpowers/specs/2026-07-15-code-review-subagents-design.md` and confirm:

```text
[ ] both registered agent names are exact
[ ] both agents prohibit every file mutation and approval action
[ ] frontend scope is the complete affected screen
[ ] shadcn/ui findings require repository or approved-plan evidence
[ ] adoption candidates are separated from defects
[ ] backend scope is the complete affected operation
[ ] findings include severity, origin, evidence, repair direction, and re-review
[ ] review begins only after implementation stops
[ ] frontend and backend review may run in parallel
[ ] implementers, not reviewers, repair accepted findings
[ ] main retains contract, triage, integration, verification, and completion authority
[ ] workflow documentation and TOML instructions do not conflict
```

Expected: every item is confirmed. If any item fails, repair the owning task,
rerun its focused validation, and repeat Tasks 4.1 through 4.4 before reporting
completion.
