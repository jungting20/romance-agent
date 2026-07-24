# Dialogue Generation Agent Instructions

## Scope and ownership

This package owns dialogue-generation behavior, its structured request and
response contracts, prompt, provider composition, generation-attempt identity,
information-disclosure validation, and focused tests. Do not place Narrative
Analysis behavior or reuse its package-private modules here.

## Before editing

1. Read the repository root `AGENTS.md`, `llm-agent/AGENTS.md`, and this file in
   full.
2. Read `llm-agent/docs/dialogue-generation-agent-coding-rules.md` and every
   relevant domain contract before changing implementation code.
3. Inspect other agent packages for shared repository conventions without
   copying their domain-specific behavior.
4. Confirm package ownership, public contract, acceptance criteria, and
   verification commands.

## Public boundary

- Public strict Pydantic models are the single structured request and JSON
  result representation.
- Keep provider selection, prompt loading, and generation ID creation behind
  `DialogueGenerationAgent`.
- Validate returned scene, generation, character, turn, and information
  references before returning a result.
- Reject results that reveal current forbidden information or fail to record
  every forbidden information ID as withheld.
- Use only the common `llm_agent_audit` port/decorator for audit events; do not
  add concrete audit storage, normal-log writes, persistence, retries, other
  agent imports, or backend/API integration.

## Verification

Run the common `llm-agent/AGENTS.md` verification commands.
