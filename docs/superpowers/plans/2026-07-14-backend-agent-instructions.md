# Backend Agent Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register a project-scoped `backend` custom agent that implements only approved OpenAPI operations after reviewing the contract's Git history and that follows repository backend, domain, verification, and handoff rules.

**Architecture:** Add one self-contained Codex custom-agent definition at `.codex/agents/backend.toml`, following the existing frontend agent's manifest shape. Keep durable project policy in repository documentation, while the custom agent enforces the required preflight checks, ownership boundaries, OpenAPI implementation gate, and completion report every time it is spawned.

**Tech Stack:** Codex custom-agent TOML, Git, Python 3.11 standard-library `tomllib`

## Global Constraints

- Implement only API operations present in the main-agent-approved `docs/api/openapi.yaml` baseline.
- Before API implementation, inspect the current OpenAPI file and run `git log --follow -- docs/api/openapi.yaml`, then review the relevant diff or approved revision.
- Do not edit `docs/api/openapi.yaml`; report required contract changes to the main agent.
- Do not select a Python framework, dependency manager, database, package layout, or verification command unless repository instructions or the assigned task already establish it.
- Own only explicitly assigned paths, preserve unrelated user changes, and keep domain rules independent of frameworks, persistence, and external LLM providers.

---

### Task 1: Register the backend custom agent

**Files:**
- Create: `.codex/agents/backend.toml`
- Reference: `AGENTS.md`
- Reference: `backend/README.md`
- Reference: `docs/api/openapi.yaml`
- Reference: `docs/superpowers/specs/2026-07-14-backend-agent-instructions-design.md`

**Interfaces:**
- Consumes: the main agent's assigned paths, approved OpenAPI baseline, assigned `operationId` values, acceptance criteria, and verification commands.
- Produces: a custom agent named `backend` whose completion report identifies changed files, implemented operations, reviewed OpenAPI history and revision, verification results, domain-document status, and contract blockers or proposals.

- [ ] **Step 1: Confirm the custom agent does not already exist**

Run:

```sh
test ! -e .codex/agents/backend.toml
```

Expected: exit status 0 with no output. If the file exists, inspect it and adapt the following creation patch into a non-destructive update.

- [ ] **Step 2: Create the backend custom-agent definition**

Create `.codex/agents/backend.toml` with exactly this content:

```toml
name = "backend"
description = "Use for substantial, independently testable Python backend work that implements main-agent-approved OpenAPI operations."

developer_instructions = """
Act as the Romance Agent project's backend specialist.

Before editing or proposing implementation:
1. Read the repository root AGENTS.md.
2. Read backend/README.md and any backend/AGENTS.md in full.
3. Read every docs/domains/*.md contract relevant to the assigned behavior.
4. Inspect the nearest existing backend implementation and test patterns.
5. Confirm the exact owned paths, deliverables, constraints, approved OpenAPI baseline, assigned operationId values, acceptance criteria, and verification commands supplied by the main agent.

Own only the files explicitly assigned to this task. Backend implementation normally belongs under backend/**. Do not edit frontend/** or shared documentation unless the main agent explicitly assigns those paths. Preserve unrelated user changes and stop if another agent is editing an overlapping file.

Keep domain rules independent of the web framework, persistence layer, and external LLM provider. Follow the language, invariants, responsibilities, and boundaries in docs/domains/*.md. Do not directly mutate state owned by another domain. When assigned work changes domain meaning, update the matching domain document in the same change or report the required update to the main agent if that document is not in your assigned paths. Do not select a Python framework, dependency manager, database, package layout, or other foundational technology unless the assigned task explicitly includes that decision.

Before implementing any API operation:
1. Inspect the current docs/api/openapi.yaml.
2. Run `git log --follow -- docs/api/openapi.yaml` and inspect the relevant commit diff or the exact approved revision supplied by the main agent.
3. Confirm every assigned operationId exists in the main-agent-approved OpenAPI baseline.
4. Compare its request, response, status-code, and error semantics with the relevant domain contracts and acceptance criteria.

Implement only API operations present in the approved docs/api/openapi.yaml baseline. Do not add undocumented routes, fields, status codes, or error behavior. Do not edit docs/api/openapi.yaml. If an assigned operation is absent, the approved baseline is unclear, or the contract is infeasible or unsafe, stop the affected implementation and report the operationId or path, reason, and a concrete contract-change proposal to the main agent. Never silently infer or implement a replacement contract.

Run focused checks while working and every backend verification command defined by repository instructions or assigned by the main agent. Do not invent verification commands before the backend toolchain establishes them. For API work, verify each assigned operation's request and response schemas, success status, and documented error semantics, plus the absence of unassigned routes where practical.

Before reporting completion, return a concise summary containing changed files, implemented behavior and operationId values, the reviewed OpenAPI revision or commit, the OpenAPI history command and relevant history reviewed, tests and verification commands with results, domain-document updates or confirmation that domain meaning was unchanged, and any blockers or proposed contract changes.
"""
```

- [ ] **Step 3: Parse the TOML and assert the required agent identity**

Run:

```sh
python3.11 - <<'PY'
from pathlib import Path
import tomllib

path = Path(".codex/agents/backend.toml")
data = tomllib.loads(path.read_text())
assert data["name"] == "backend"
assert data["description"]
assert data["developer_instructions"]
print("backend agent TOML: ok")
PY
```

Expected: `backend agent TOML: ok`

- [ ] **Step 4: Assert the OpenAPI implementation gate is present**

Run:

```sh
python3.11 - <<'PY'
from pathlib import Path
import tomllib

instructions = tomllib.loads(Path(".codex/agents/backend.toml").read_text())["developer_instructions"]
required = (
    "git log --follow -- docs/api/openapi.yaml",
    "Implement only API operations present",
    "Do not edit docs/api/openapi.yaml",
    "concrete contract-change proposal",
    "Do not invent verification commands",
)
missing = [text for text in required if text not in instructions]
assert not missing, f"missing required instructions: {missing}"
print("backend agent policy: ok")
PY
```

Expected: `backend agent policy: ok`

- [ ] **Step 5: Review whitespace and scope**

Run:

```sh
git diff --check -- .codex/agents/backend.toml
git diff -- .codex/agents/backend.toml
git status --short
```

Expected: `git diff --check` exits 0; the diff contains only the new backend agent definition; `git status --short` may also show pre-existing user changes under `frontend/`, which must remain untouched.

- [ ] **Step 6: Commit the custom-agent definition**

Run:

```sh
git add .codex/agents/backend.toml
git commit -m "chore: add backend custom agent instructions"
```

Expected: one new commit containing only `.codex/agents/backend.toml`.
