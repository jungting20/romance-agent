# Backend Agent Instructions Design

## Goal

Register a project-scoped `backend` custom agent with clear ownership,
contract, domain, verification, and handoff responsibilities. The agent must
implement only API operations already present in the main-agent-approved
`docs/api/openapi.yaml` baseline and must inspect that file's Git history before
starting API implementation.

## Scope

Add `.codex/agents/backend.toml` with the required `name`, `description`, and
`developer_instructions` fields. This change does not select a Python
framework, dependency manager, database, or package layout, and it does not
modify the OpenAPI contract or domain behavior.

The custom agent instructions will reference existing repository sources of
truth instead of duplicating their full contents:

- root `AGENTS.md` for delegation, API approval, ownership, and integration;
- `backend/README.md` and any future nested `backend/AGENTS.md` for backend
  setup and verification;
- relevant `docs/domains/*.md` files for domain language and invariants; and
- `docs/api/openapi.yaml` for the approved consumer-facing transport contract.

## Responsibilities and Boundaries

Before editing or proposing implementation, the backend agent must read the
repository instructions, backend documentation, relevant domain contracts,
and the assigned OpenAPI operations. It owns only paths explicitly assigned by
the main agent, normally under `backend/**`, and must preserve unrelated user
changes and avoid files another agent is editing.

Backend domain rules must remain independent of the web framework, persistence
technology, and external LLM provider. HTTP adapters, persistence adapters,
and provider integrations must not become the authoritative owners of domain
invariants. Cross-domain workflows must follow the ownership and orchestration
boundaries defined in the domain documents.

The agent must not choose a framework, dependency manager, database, or package
layout unless the assigned task explicitly includes that decision.

## OpenAPI Implementation Gate

Before implementing any API operation, the backend agent must:

1. inspect `docs/api/openapi.yaml` in its current working tree;
2. inspect its change history with
   `git log --follow -- docs/api/openapi.yaml` and review the relevant diff or
   approved revision supplied by the main agent;
3. identify the assigned `operationId` values and confirm that each exists in
   the approved OpenAPI baseline; and
4. compare request, response, status-code, and error semantics with the
   relevant domain contracts and implementation acceptance criteria.

The agent may implement only operations present in that approved baseline. It
must not add an undocumented route, request field, response field, status code,
or error behavior. It must not edit `docs/api/openapi.yaml`; the frontend agent
is its steward and sole editor under the repository workflow. Required changes
must be proposed to the main agent through the escalation path below.

If an assigned operation is absent, the approved baseline is unclear, or the
contract is infeasible or unsafe, the backend agent must stop the affected
implementation. It returns the affected `operationId` or path, the blocking
reason, and a concrete contract-change proposal to the main agent. It must not
silently infer or implement a replacement contract.

## Verification and Handoff

The backend agent runs focused tests while working and all backend verification
commands defined by repository instructions or explicitly assigned by the main
agent before reporting completion. Until a backend toolchain is established,
the custom-agent instructions must not invent verification commands.

For API work, verification must cover each assigned operation's request and
response schemas, success status, documented error semantics, and absence of
unassigned routes where practical. The completion report must include:

- changed files and implemented behavior;
- implemented `operationId` values and the reviewed OpenAPI revision or commit;
- the OpenAPI history command and relevant history reviewed;
- tests and verification commands with results;
- domain-document updates, or confirmation that domain meaning was unchanged;
  and
- blockers or proposed contract changes, if any.

## Acceptance Criteria

- `.codex/agents/backend.toml` parses as TOML and declares the custom-agent name
  exactly as `backend`.
- Its instructions require reading root and backend guidance plus relevant
  domain contracts before implementation.
- Its instructions require inspecting both the current OpenAPI file and its
  Git change history before API implementation.
- It permits implementation only for operations present in the approved
  OpenAPI baseline and prohibits undocumented API behavior.
- It prohibits backend edits to `docs/api/openapi.yaml` and defines the
  contract-change escalation path through the main agent.
- It preserves domain isolation, assigned-path ownership, working-tree safety,
  verification, and completion-handoff requirements.
- No backend technology or verification command is invented before the
  repository establishes it.
