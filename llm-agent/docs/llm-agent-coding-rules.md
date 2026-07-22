# Narrative Analysis Agent Coding Rules

## Public contracts

- Public request, result, configuration, and error types use immutable,
  slotted standard-library dataclasses, enums, and primitive types only.
- Public contracts must not import Pydantic, Pydantic AI, FastAPI, or SQLite.
- Use tuples for public collection fields so returned snapshots remain
  immutable after construction.
- Keep provider-specific output, prompt loading, audit persistence, and
  orchestration behind the public facade.

## Domain alignment

- Preserve Narrative Memory terminology, immutable input text, deterministic
  analysis semantics, and `pending` candidate ownership from
  `docs/domains/narrative-memory.md`.
- The package does not access or mutate Manuscript, Story Bible, or backend
  project-snapshot state.

## Tests

- Keep ordinary tests deterministic and network-free.
- Mark real-provider evaluations with `live`; they must require explicit
  opt-in and remain outside the default test run.
