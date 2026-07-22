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

## Live provider evaluations

- Live evaluations require both `RUN_LLM_LIVE_TESTS=1` and a non-blank
  `NARRATIVE_LLM_MODEL`, plus credentials already configured for that model's
  provider. They can incur provider costs and are intentionally skipped by
  default.
- Run them only after configuring the model and its provider credentials:

  ```sh
  : "${NARRATIVE_LLM_MODEL:?configure NARRATIVE_LLM_MODEL before live tests}"
  RUN_LLM_LIVE_TESTS=1 mise exec -- uv run pytest -m live -v
  ```

- Live assertions compare required relationship identity-pair/category
  semantics, reject unasserted relationship or location-event facts, and
  verify evidence source slices and offsets. They do not compare generated
  prose or confidence values.
- Test output and failure messages must only report configuration presence;
  never print model values, credentials, prompts, or provider responses.
