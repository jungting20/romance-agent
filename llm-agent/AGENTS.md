# Narrative Analysis Agent Instructions

## Scope and ownership

This package owns scene-text chunking, the editable scene-analysis prompt,
structured extraction, and sequential model calls. Work only on paths assigned
by the main agent; do not edit backend, frontend, domain contracts, or OpenAPI
without assignment.

## Before editing

1. Read the repository root `AGENTS.md`, this file, and
   `docs/llm-agent-coding-rules.md` in full.
2. Read `docs/domains/narrative-memory.md` and every relevant domain contract.
3. Inspect nearby implementation and test patterns.
4. Confirm scope, constraints, acceptance criteria, and verification commands.

## Public boundary

- Public Pydantic models are the single extraction and result representation.
- Process 300-character chunks with 50-character overlap in numeric order.
- Call each chunk exactly once. One failure returns no partial analysis.
- Keep provider selection and prompt loading behind `NarrativeAnalysisAgent`.
- Do not add audit storage, retries, durable IDs, candidate status, scene
  snapshot assembly, or cross-chunk merging.

## Verification and handoff

Run from `llm-agent/`:

```sh
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Report changed paths, public-contract impact, domain-contract impact, and every
verification result.
