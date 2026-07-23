# Dialogue Generation Agent Instructions

## Scope and ownership

This package is reserved for dialogue-generation behavior, prompts, public
contracts, provider composition, and focused tests. Do not place Narrative
Analysis behavior or reuse its package-private modules here.

The package currently contains governance scaffolding only. This file does not
define an implementation contract, request or response schema, prompt format,
provider, orchestration flow, or persistence policy.

## Before editing

1. Read the repository root `AGENTS.md`, `llm-agent/AGENTS.md`, and this file in
   full.
2. Read the approved dialogue-generation specification, implementation plan,
   and every relevant domain contract before adding implementation code.
3. Inspect other agent packages for shared repository conventions without
   copying their domain-specific behavior.
4. Confirm package ownership, public contract, acceptance criteria, and
   verification commands.

## Public boundary

- Keep the future public API independent from other agents' internal modules.
- Keep provider selection and prompt loading behind the package's future public
  facade.
- Do not infer or introduce schemas, prompts, storage, retries, orchestration,
  or cross-agent coordination until those decisions are explicitly approved.
- Add exports, package-data configuration, implementation modules, and tests
  only as part of the future dialogue-generation feature ticket.

## Verification

Run the common `llm-agent/AGENTS.md` verification commands after implementation
begins. Until then, verify that this directory contains only this `AGENTS.md`.
