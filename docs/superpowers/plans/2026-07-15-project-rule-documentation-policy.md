# Project Rule Documentation Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-wide instruction that stores detailed frontend and backend engineering rules under each application's `docs/` directory instead of accumulating them in nested `AGENTS.md` files.

**Architecture:** The root `AGENTS.md` owns one policy that applies to both application trees. It classifies detailed engineering knowledge separately from agent-operation instructions, names the default coding-rule documents, defines focused-document discovery, and requires same-change synchronization when reusable rules change.

**Tech Stack:** Markdown repository instructions, Python semantic assertions, Git.

## Global Constraints

- Modify only the root `AGENTS.md` implementation file.
- Do not modify `frontend/AGENTS.md` or `backend/AGENTS.md`.
- Detailed frontend engineering rules belong under `frontend/docs/`.
- Detailed backend engineering rules belong under `backend/docs/`.
- Use `frontend/docs/frontend-coding-rules.md` and `backend/docs/backend-coding-rules.md` as the default destinations when the topic fits.
- Link a new focused project document from the application's existing coding-rules document.
- Nested `AGENTS.md` files retain agent scope, ownership, required reading, authority, workflow, verification, and handoff instructions, but not detailed engineering-rule bodies.
- Repository-wide delegation, OpenAPI, domain, review, and working-tree rules remain in the root `AGENTS.md`.
- Implementation and any newly introduced or changed reusable engineering rule must be documented in the same change.
- Preserve existing domain-document synchronization requirements.

---

## File Structure

- Modify `AGENTS.md`: add one authoritative `Project Engineering Rule Documentation` policy section after the repository map and before main-agent responsibilities.
- Reference `docs/superpowers/specs/2026-07-15-project-rule-documentation-policy-design.md`: approved policy and acceptance criteria.
- Verify but do not modify `frontend/AGENTS.md`, `backend/AGENTS.md`, `frontend/docs/frontend-coding-rules.md`, and `backend/docs/backend-coding-rules.md`.

---

### Task 1: Add the Project Engineering Rule Documentation Policy

**Files:**
- Modify: `AGENTS.md` after `## Repository Map`
- Verify unchanged: `frontend/AGENTS.md`
- Verify unchanged: `backend/AGENTS.md`
- Verify existence: `frontend/docs/frontend-coding-rules.md`
- Verify existence: `backend/docs/backend-coding-rules.md`

**Interfaces:**
- Consumes: the existing root-instruction inheritance model and the two authoritative application coding-rules documents.
- Produces: one repository-wide routing rule for persistent application engineering knowledge.

- [ ] **Step 1: Run the semantic policy check and verify it fails**

Run:

```bash
mise exec -- python - <<'PY'
from pathlib import Path

root = Path('AGENTS.md').read_text()
assert '## Project Engineering Rule Documentation' in root
assert 'frontend/docs/frontend-coding-rules.md' in root
assert 'backend/docs/backend-coding-rules.md' in root
assert 'Do not add or duplicate those detailed rule bodies in `frontend/AGENTS.md` or `backend/AGENTS.md`.' in root
assert 'implementation and its matching project-document update are one indivisible change' in root
PY
```

Expected: FAIL on the missing `## Project Engineering Rule Documentation` assertion.

- [ ] **Step 2: Add the authoritative policy to root instructions**

In `AGENTS.md`, insert the following section after the repository-map bullets
and before `## Main Agent Responsibilities`:

```markdown
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
```

- [ ] **Step 3: Run the semantic policy check and verify it passes**

Run:

```bash
mise exec -- python - <<'PY'
from pathlib import Path

root_path = Path('AGENTS.md')
frontend_agents = Path('frontend/AGENTS.md')
backend_agents = Path('backend/AGENTS.md')
frontend_rules = Path('frontend/docs/frontend-coding-rules.md')
backend_rules = Path('backend/docs/backend-coding-rules.md')

root = root_path.read_text()
for path in (frontend_agents, backend_agents, frontend_rules, backend_rules):
    assert path.is_file(), path

required = (
    '## Project Engineering Rule Documentation',
    '`frontend/docs/`',
    '`backend/docs/`',
    '`frontend/docs/frontend-coding-rules.md`',
    '`backend/docs/backend-coding-rules.md`',
    'link it from that project\'s\n  existing coding-rules document',
    'Do not add or duplicate those detailed rule bodies in `frontend/AGENTS.md` or\n  `backend/AGENTS.md`.',
    'implementation and its matching project-document update are one\n  indivisible change',
    'Work that only follows existing documented\n  rules does not require a documentation rewrite.',
    'Keep repository-wide delegation, OpenAPI approval, domain-document ownership,',
    'project engineering documentation does not replace domain contracts.',
)
for text in required:
    assert text in root, text

assert root.index('## Repository Map') < root.index('## Project Engineering Rule Documentation')
assert root.index('## Project Engineering Rule Documentation') < root.index('## Main Agent Responsibilities')
print('project engineering rule documentation policy: PASS')
PY
```

Expected: `project engineering rule documentation policy: PASS`.

- [ ] **Step 4: Verify the implementation scope and Markdown formatting**

Run:

```bash
git diff --check -- AGENTS.md
git diff --name-only
git diff -- AGENTS.md
```

Expected:

- `git diff --check` produces no output;
- `git diff --name-only` prints only `AGENTS.md`;
- the diff inserts the approved policy after the repository map;
- neither nested `AGENTS.md`, application code, OpenAPI, nor domain documents
  changed.

- [ ] **Step 5: Commit the policy**

```bash
git add AGENTS.md
git commit -m "docs: route project rules to application docs"
```

- [ ] **Step 6: Verify the committed result**

Run:

```bash
git show --check --stat --oneline HEAD
git diff-tree --no-commit-id --name-only -r HEAD
git status --short
```

Expected:

- the commit check has no errors;
- the commit contains only `AGENTS.md`;
- the working tree is clean.

