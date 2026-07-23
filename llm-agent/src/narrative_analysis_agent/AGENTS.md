# Narrative Analysis Agent Instructions

## Scope and ownership

This package owns scene-text chunking, the editable scene-analysis prompt,
structured extraction, sequential model calls, and read-only project graph
lookup for analysis context. Do not place behavior for other LLM agents in this
package.

## Before editing

1. Read the repository root `AGENTS.md`, `llm-agent/AGENTS.md`, and this file in
   full.
2. Read `llm-agent/docs/llm-agent-coding-rules.md` and
   `docs/domains/narrative-memory.md` in full.
3. Read every other relevant domain contract.
4. Inspect nearby implementation and test patterns.
5. Confirm scope, constraints, acceptance criteria, and verification commands.

## Public boundary

- Public Pydantic models are the single extraction and result representation.
- Read the configured v2 project graph once per analysis through a SQLite
  read-only connection and provide that same snapshot to every chunk.
- Process 300-character chunks with 50-character overlap in numeric order.
- Call each chunk exactly once. One failure returns no partial analysis.
- Keep provider selection and prompt loading behind `NarrativeAnalysisAgent`.
- Do not add audit storage, retries, database writes or schema management,
  durable IDs, candidate status, scene snapshot assembly, or cross-chunk
  merging.

## Verification

Run the common `llm-agent/AGENTS.md` verification commands. Focused unit and
integration tests for this package live under the matching `llm-agent/tests/`
directories.
