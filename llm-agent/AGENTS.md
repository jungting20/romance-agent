# Narrative Analysis Agent Instructions

## Scope and ownership

This project owns the provider-independent scene-analysis implementation. Work
only on paths explicitly assigned by the main agent; do not edit backend,
frontend, domain contracts, or `docs/api/openapi.yaml` without assignment.

Provider adapters, prompt definitions and loading, structured extraction, and
append-only analysis audit storage are owned here. Backend owns only public
facade composition, result translation, scene-to-project merge, and project
snapshot persistence.

## Before editing

1. Read the repository root `AGENTS.md`, this file, and
   `docs/llm-agent-coding-rules.md` in full.
2. Read `docs/domains/narrative-memory.md` and every other domain contract
   relevant to the assigned behavior.
3. Inspect the nearest implementation and test patterns before changing code.
4. Confirm assigned paths, deliverables, constraints, acceptance criteria, and
   verification commands with the main agent.

## Public boundary

- Keep `narrative_analysis_agent` public contracts limited to standard-library
  dataclasses, enums, paths, and primitive types.
- Do not import Pydantic, Pydantic AI, FastAPI, or SQLite from public contract,
  configuration, or error modules.
- Keep all model-provider, prompt, and audit details behind the public facade.
- Preserve the Narrative Memory domain contract: analysis returns immutable
  pending candidates and never mutates other domain state.
- Apply the detailed provider, prompt, audit, validation, and testing rules in
  `docs/llm-agent-coding-rules.md`.

## Verification and handoff

Run the focused test while working, then from `llm-agent/` run:

```sh
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Report changed paths, public-contract impact, domain-contract impact, and each
verification command with its result to the main agent.
