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

## Provider, Prompt, and Audit Ownership

- Keep provider clients behind narrow typed extraction ports. Select the model
  only at the explicit facade composition boundary; analysis orchestration must
  not read process globals.
- Store editable, versioned prompt files in this package. Load the prompt for
  each explicitly requested run so edits are hot-loaded, and require a version
  increment whenever registered prompt bytes change.
- Include package-owned `prompts/**/*.md` files in install artifacts and expose
  their installed root through the stdlib-only public `packaged_prompt_root()`
  helper. Callers still pass that path explicitly through
  `NarrativeAnalysisConfig`; the helper does not introduce hidden configuration.
- Persist the prompt definition, run start, and attempt start before making a
  provider call. Treat an audit-start failure as call-blocking, and never write
  prompts, manuscript text, model responses, or validated extraction content to
  ordinary console logs.
- Enforce at most one terminal attempt event (`attempt_succeeded` or
  `attempt_failed`) for each run, chunk, and attempt number in both the audit
  port contract and durable storage. A best-effort failure fallback after an
  ambiguous success append may run, but storage must reject it when success was
  already committed; never repair terminal conflicts with update or delete.
  Compare the identity tuple with exact, case-sensitive (`BINARY`) semantics,
  and validate an existing reserved index from SQLite index metadata, including
  key order, collation, sort direction, uniqueness, and partial predicate,
  before accepting it as the durable constraint.
- Validate structured provider output before translation into public domain
  contracts. Provider adapters must not assign durable domain IDs, candidate
  states, or other Narrative Memory-owned meaning.
- Retry a provider failure once for a chunk. Do not retry an invalid structured
  extraction, and never return a partial scene snapshot after a terminal chunk
  failure.

## Tests

- Keep ordinary tests deterministic and network-free.
- Supply scripted, network-free adapters for unit and integration tests so call
  order, retry behavior, audit rows, and translation can be verified
  deterministically.
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
