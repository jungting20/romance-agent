# Narrative Analysis Agent Instructions

## Scope and ownership

This project owns the provider-independent scene-analysis implementation. Work
only on paths explicitly assigned by the main agent; do not edit backend,
frontend, domain contracts, or `docs/api/openapi.yaml` without assignment.

## Public boundary

- Keep `narrative_analysis_agent` public contracts limited to standard-library
  dataclasses, enums, paths, and primitive types.
- Do not import Pydantic, Pydantic AI, FastAPI, or SQLite from public contract,
  configuration, or error modules.
- Keep all model-provider, prompt, and audit details behind the public facade.
- Preserve the Narrative Memory domain contract: analysis returns immutable
  pending candidates and never mutates other domain state.

## Verification and handoff

Run the focused test while working, then from `llm-agent/` run:

```sh
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Report changed paths, public-contract impact, domain-contract impact, and each
verification command with its result to the main agent.
