# Chunk LLM Scene Analysis Design

## Goal

Add an explicitly invoked asynchronous `analyze_scene()` workflow to Narrative
Memory. The workflow divides one immutable manuscript scene into the existing
300-character chunks with 50-character overlap, calls an LLM once per chunk,
validates structured extraction results, converts evidence to absolute scene
offsets, and returns the existing deterministic `SceneRelationshipSnapshot`.

This slice does not attach analysis to manuscript saves. It introduces no HTTP
operation, frontend behavior, background executor, candidate decision flow,
project-snapshot commit, Neo4j projection, or Cypher generation.

## Confirmed Decisions

- `NARRATIVE_LLM_MODEL` contains a Pydantic AI model string, so the provider can
  change without changing Narrative Memory.
- The special value `mock` selects the local mock adapter. No model is selected
  implicitly.
- A missing or blank model setting fails the requested analysis before a model
  call, while the backend process itself remains startable.
- Tests inject scripted per-chunk mock results. The mock's default result is a
  valid empty extraction, not invented story data.
- Calls are serial in numeric chunk order for deterministic prompts, audit
  order, failure behavior, and merge inputs.
- Each chunk receives at most two attempts. A terminal chunk failure prevents a
  scene snapshot from being returned.
- All extracted candidates are `pending`; neither the model nor an adapter can
  approve, reject, or mark a candidate `needs_review`.
- System prompts remain easy to edit under `backend/prompts/`.
- Exact rendered prompts and Pydantic AI's serialized model response messages
  are retained in a dedicated owner-only SQLite audit store. Provider-specific
  raw HTTP packets are not promised by the provider-independent contract.

## Scope and Ownership

### Included paths

- `backend/apps/narrative_memory/` for ports, typed inputs, translation, and the
  scene-analysis application workflow.
- `backend/infrastructure/llm/` for Pydantic AI and scripted mock adapters.
- `backend/infrastructure/audit/` for the SQLite audit adapter.
- `backend/prompts/scene-analysis/` for the editable system prompt.
- `backend/tests/narrative_memory/` for service, adapter, prompt, and audit
  tests.
- `backend/README.md`, `backend/docs/backend-coding-rules.md`, and
  `docs/domains/narrative-memory.md` when needed to keep the new reusable
  provider, prompt, audit, and domain rules discoverable.

### Explicit exclusions

- Manuscript, Story Bible, Writing Assistant, Projects, Worldbuilding, and all
  frontend packages.
- The existing Writing Assistant `TextGenerationPort`.
- `main.py`, consumer-facing API routes, and `docs/api/openapi.yaml`.
- Automatic execution after manuscript save, in-process queues, durable jobs,
  startup recovery, and the internal audit viewer.
- Candidate decisions and automatic project-snapshot persistence.

Narrative Memory owns the meaning of an extraction candidate. Infrastructure
owns provider, prompt-file, and SQLite mechanics. No other domain is read or
mutated by this workflow.

## Architecture

The service depends on narrow typed ports:

```text
SceneAnalysisService.analyze_scene(request)
  -> chunk_scene(scene_id, revision, text)
  -> PromptRegistryPort.load("scene-analysis")
  -> AgentAuditPort.start_run(...)
  -> for chunk in numeric order:
       render typed user message
       AgentAuditPort.start_attempt(... rendered messages ...)
       SceneAnalysisAgentPort.analyze(...)
       AgentAuditPort.record_attempt_result(...)
       translate validated extraction to ChunkAnalysis
  -> merge_chunk_analyses(...)
  -> AgentAuditPort.record_run_result(... scene snapshot ...)
  -> SceneRelationshipSnapshot
```

The service module imports neither Pydantic AI, SQLite, environment variables,
nor provider SDKs. A composition helper in infrastructure reads
`NARRATIVE_LLM_MODEL` only when a caller requests an analyzer. Since this slice
does not wire the helper into FastAPI startup, missing model configuration
cannot prevent the unrelated backend from starting.

## Public Application Types

The workflow consumes one immutable request:

```python
@dataclass(frozen=True, slots=True)
class AnalyzeSceneRequest:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    text: str
    known_entities: tuple[KnownIdentity, ...] = ()
    known_places: tuple[KnownIdentity, ...] = ()
```

`KnownIdentity` contains only a stable key, normalized name, display name, and
aliases. It supplies reference context; this workflow does not query another
domain to obtain it.

`SceneAnalysisService.analyze_scene(request)` is async and returns the existing
`SceneRelationshipSnapshot`. Empty text produces the existing empty scene
snapshot without a model call, while still producing a completed audit run.

## Structured Model Contract

The Pydantic AI adapter uses a strict Pydantic output model rather than asking
for free-form JSON text. The provider may implement structured output through
native JSON schema, a tool call, or another supported mechanism. The adapter
always returns:

- the Pydantic-validated extraction value;
- Pydantic AI's serialized response messages for audit;
- available usage metadata;
- the resolved provider and model identity.

The extraction schema contains no persistent IDs and no status field:

- local entity mentions: local reference, normalized name, display name,
  aliases, relative evidence ranges;
- local place mentions: the same identity fields and evidence;
- relationship events: local or known subject/object references, controlled
  category, description, confidence, and evidence;
- location events: local or known character/place references, controlled event
  type, description, confidence, and evidence;
- one local chunk summary.

Controlled relationship categories are `romance`, `family`, `friendship`,
`professional`, `antagonistic`, and `other`. Location event types remain
`arrived`, `present`, and `departed`. A place mention alone is not a physical
location event.

Pydantic models forbid unknown fields, reject non-finite or out-of-range
confidence, reject invalid enums, and require `0 <= start < end <= chunk
length`. The translation boundary additionally verifies that each evidence
text exactly equals the indicated source slice.

## Translation to Narrative Memory

The application service, not the LLM, creates durable-shaped candidates.

- Relative evidence offsets become absolute scene offsets by adding the
  chunk's absolute start.
- Evidence records receive the authoritative chunk ID, scene ID, and revision.
- Candidate status is always `CandidateStatus.PENDING`.
- Candidate and event IDs are deterministic SHA-256-derived identifiers over
  the schema version, scene identity, revision, candidate kind, normalized
  semantic identity, and evidence range. They contain no secret or prompt
  content.
- Local relationship and location references are resolved through the current
  chunk's local entity/place maps. A reference may also use an explicitly
  supplied known identity key.
- Unknown, ambiguous, or wrong-kind references reject the chunk result.

The resulting `ChunkAnalysis` uses the existing schema and passes through the
existing merge validation. No separate merge implementation is introduced.

## Prompt Management

The editable prompt lives at:

```text
backend/prompts/
├── README.md
└── scene-analysis/
    └── system.md
```

`system.md` has strict Markdown front matter:

```markdown
---
prompt_id: scene-analysis
version: 1
result_schema: chunk-analysis-extraction-v1
---
```

The registry reads the exact bytes for every new scene run, requires UTF-8,
validates the three known metadata keys, rejects missing or extra metadata, and
computes a SHA-256 hash over the complete file. It uses a deliberately small
front-matter parser and adds no YAML dependency.

The audit store registers `prompt_id + version + hash` before any model call.
Reusing a registered ID and version with different bytes fails before the run.
Editors must increment the version for semantic or wording changes. The README
documents the variables, schema, edit procedure, and version rule.

The user message is rendered from typed inputs in a stable JSON envelope. It
contains chunk metadata and text plus the supplied known identity catalogs. API
keys, unrelated environment variables, and whole-project data are never
rendered.

## Model Selection and Mocking

The composition helper accepts an explicit model name or reads
`NARRATIVE_LLM_MODEL` when called.

- Missing or whitespace-only: raise `ModelConfigurationError` before creating
  a run or attempt.
- `mock`: construct the local mock adapter with an empty default result.
- Any other value: pass the exact string to Pydantic AI with deferred model
  checking, allowing supported providers to use their normal API-key
  environment variables.

The scripted mock implements the same `SceneAnalysisAgentPort`. Tests can map
chunk IDs to a sequence of validated results or exceptions, allowing success,
retry, terminal failure, overlap, and ordering tests. It records received calls
for assertions and never accesses the network.

## Audit Storage

Agent audit data is separate from the project snapshot repository. A SQLite
adapter owns an owner-only `0600` database and uses append-only records:

- prompt definitions with ID, version, schema, hash, and exact bytes;
- run events with run ID, project/scene/revision, status, model, prompt version,
  timestamps, and terminal error;
- attempt events with run ID, chunk ID, attempt number, exact rendered system
  and user messages, serialized model response messages, validated extraction
  JSON, usage, latency, and error details;
- the terminal merged scene snapshot JSON.

Before a model call, the service commits the prompt definition, run-start
event, and attempt-start event. If any of these writes fails, the model is not
called. Success or failure is then appended as a terminal event; ordinary
console logs never receive prompt, manuscript, response, or validation JSON.

Run IDs, clocks, and latency measurement are injected so tests are deterministic.
Secrets are not accepted by the audit interfaces and therefore cannot be
persisted accidentally through their typed fields.

## Failure and Retry Semantics

- Invalid model configuration, prompt metadata, prompt version reuse, or audit
  start writes fail before a model request.
- Provider errors and structured-output validation failures are retryable once
  for the affected chunk.
- Deterministic translation errors such as invalid evidence slices or unknown
  references are recorded and fail immediately without a second identical
  provider call.
- Attempt numbers are one and two; each start and terminal result is auditable.
- A terminal chunk failure appends a failed run event and raises a typed
  `SceneAnalysisError`. Later chunks are not called and no scene snapshot is
  returned.
- Audit terminal-write failure is surfaced as an audit error. The service does
  not claim a completed result whose audit trail could not be completed.
- Cancellation is recorded when possible and then re-raised; it is never
  converted to a successful or ordinary provider result.

## Testing Strategy

All production behavior is developed test-first.

- Prompt registry tests cover valid loading, exact hash, hot reload, malformed
  metadata, unknown schema, invalid UTF-8, and version/hash conflict.
- Translation tests cover every candidate type, relative-to-absolute evidence,
  exact evidence text, deterministic IDs, pending-only status, known/local
  references, invalid references, and confidence/enums.
- Service tests use the scripted mock for empty scenes, numeric serial order,
  default empty results, two-attempt recovery, terminal failure, no later calls,
  and existing chunk merge/deduplication.
- Audit tests cover `0600` permissions, pre-call persistence, append-only
  attempts, complete rendered messages, response/validated JSON, failures,
  token usage when available, and audit failure blocking a call.
- Pydantic AI adapter tests use Pydantic AI's local test model or a custom
  in-memory model; they perform no network access and prove structured output
  and serialized message capture.
- Configuration tests cover missing, blank, `mock`, and arbitrary Pydantic AI
  model strings without requiring provider credentials.
- The full backend test, Ruff lint, and Ruff format checks remain required.

## Acceptance Criteria

1. One explicit async call analyzes a non-empty scene by its canonical 300/50
   chunks and returns a validated deterministic scene snapshot.
2. Every chunk model call uses the editable versioned system prompt and a typed
   stable user message.
3. Real model selection is provider-configurable through
   `NARRATIVE_LLM_MODEL`; `mock` is explicit and missing configuration fails the
   requested analysis without breaking backend startup.
4. Tests can script a different structured result or failure for every chunk,
   while the default mock result is empty.
5. Every attempt has a pre-call audit record and a terminal success or failure
   record containing the exact rendered messages and available response data.
6. Invalid output never reaches `merge_chunk_analyses()`, and one terminal
   chunk failure yields no scene snapshot.
7. All translated candidates remain pending, use absolute verified evidence,
   and preserve the existing Narrative Memory invariants.
8. No other domain, API, frontend, background executor, project snapshot,
   approval flow, Neo4j, or Cypher code changes.
