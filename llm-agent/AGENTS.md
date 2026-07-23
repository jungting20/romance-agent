# LLM Agent Package Instructions

## Scope and ownership

`llm-agent/` hosts independently bounded LLM agent packages. Keep behavior,
prompts, public contracts, provider composition, and tests inside the owning
agent package. Do not apply one agent's domain rules or processing pipeline to
another agent.

Every agent package under `src/` must have its own `AGENTS.md`. That nested file
defines the package-specific ownership, required reading, public boundary, and
verification requirements. More specific nested instructions take precedence
over this file.

Work only on paths assigned by the main agent. Do not edit backend, frontend,
domain contracts, or OpenAPI without assignment.

## Before editing

1. Read the repository root `AGENTS.md` and this file in full.
2. Read the target package's nested `AGENTS.md`.
3. Read the relevant domain contracts and package coding rules.
4. Inspect nearby implementation and test patterns.
5. Confirm scope, constraints, acceptance criteria, and verification commands.

## Shared boundaries

- Keep each agent's public API explicit and independent from other agents'
  internal modules.
- Keep model-provider details and prompt loading behind the owning agent's
  public facade.
- Keep prompts and package data inside the owning agent package. Update
  `pyproject.toml` package-data configuration when a new implemented package
  needs non-Python assets.
- Do not introduce direct imports between agent packages without an explicitly
  approved shared contract.
- Keep ordinary tests deterministic and network-free by injecting dependencies
  at external model, storage, clock, or ID-generation boundaries as applicable.
- Put focused tests under `tests/unit/`, package integration tests under
  `tests/integration/`, and real-provider evaluations under `tests/live/`.
- Mark real-provider tests with `live`, require explicit opt-in, and keep them
  outside the default test run.
- Do not log prompts, provider responses, credentials, or other sensitive
  model-call data from tests.

## Verification and handoff

Run from `llm-agent/`:

```sh
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Report changed paths, public-contract impact, domain-contract impact, and every
verification result.
