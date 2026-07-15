# Narrative Memory JSON Pipeline Design

## Goal

Build the first backend slice of a novel-writing memory system. A successful
manuscript save queues an in-process analysis job without waiting for an LLM.
The job divides the changed scene into overlapping chunks, extracts structured
character, relationship, place, and location-event candidates, merges those
results into versioned JSON snapshots, and leaves every candidate unconfirmed
until the user decides it. On explicit request, a separate consistency agent
checks a new scene only against user-confirmed facts and returns evidence-backed
diagnostics without changing the manuscript or memory.

The MVP stops at durable JSON snapshots. Neo4j, Cypher generation, and graph
projection are deferred. The JSON contract is intentionally suitable as the
input to a later deterministic Neo4j projector.

## Product Decisions

- Relationship and location extraction runs automatically after a successful
  scene save.
- Consistency validation runs only after an explicit user request.
- New characters, places, relationship events, and location events remain
  candidates until the user approves them.
- Relationships and locations are temporal events associated with a scene,
  not mutable latest-state edges.
- Editing a scene reanalyzes the complete scene rather than trying to patch
  individual sentences.
- Validation reports only contradictions with confirmed facts. It does not
  score style, entertainment value, prose quality, or emotional plausibility.
- The model provider is not selected. Pydantic AI test models and
  provider-independent ports define the initial behavior.
- Agent work runs in the backend process. Durable job state permits recovery
  after a restart; a distributed queue is deferred.
- System prompts are editable Markdown files under `backend/prompts/` and every
  rendered prompt and response is retained in a dedicated audit store.

## Scope

### Included

- Narrative Memory domain contract and backend package boundary.
- Scene analysis and consistency-validation agent ports.
- Pydantic AI adapters that return structured results.
- Fixed-width Unicode chunking with a maximum of 300 characters and 50
  characters of overlap.
- Per-chunk validated JSON artifacts.
- Scene-level and project-level relationship-memory JSON snapshots.
- Deterministic merge, replacement, deduplication, approval, and stale-evidence
  behavior.
- Character relationship events and character location events.
- An in-process async job executor with durable state and restart recovery.
- SQLite persistence for jobs, append-only agent audit records, prompt
  definitions, artifacts, decisions, and versioned JSON snapshots.
- A localhost-only internal HTML viewer for prompts, responses, artifacts,
  retries, jobs, snapshots, downloads, and snapshot differences.
- User-facing backend operations needed to list and decide candidates and to
  request consistency validation. Their consumer-facing contract must be
  authored through the repository OpenAPI workflow before implementation.

### Excluded

- Neo4j dependencies, migrations, Cypher, and graph projection.
- Redis, Celery, or another distributed job system.
- A production authentication system for the internal audit viewer.
- Automatic acceptance of any extracted fact.
- Automatic mutation of manuscript text.
- Vector search and embeddings.
- Prose, style, pacing, or emotional-quality evaluation.
- Selecting or configuring a production model provider.

## Domain Ownership

Memory is separated into three layers with different authority.

### Manuscript

Manuscript remains the sole owner and source of truth for scene text, scene
order, and manuscript revision. Analysis receives an immutable scene snapshot
after a successful save and never writes manuscript state.

### Narrative Memory

The new Narrative Memory supporting domain owns rebuildable information derived
from manuscripts:

- scene summaries;
- chunk metadata and extraction artifacts;
- unresolved character and place candidates;
- relationship and location-event candidates;
- analysis jobs and active analysis revisions;
- evidence links and candidate decision history;
- versioned scene and project memory snapshots.

Narrative Memory does not declare a candidate to be true and does not mutate
Story Bible or Manuscript state directly.

### Story Bible

Story Bible remains the authority for facts treated as true in the work. Its
model is extended to include confirmed characters, places, relationship events,
and location events. A cross-domain application use case promotes an approved
Narrative Memory candidate into confirmed Story Bible knowledge while recording
the decision in Narrative Memory.

### Writing Assistant

Writing Assistant continues to act only on an explicit request. Its consistency
validator reads the supplied scene text, confirmed Story Bible facts, and
relevant Narrative Memory summaries. It returns diagnostics and never applies
changes or writes memory.

### Required Domain Documentation

Implementation changes domain meaning and therefore must update these contracts
in the same change:

- create `docs/domains/narrative-memory.md`;
- update `docs/domains/story-bible.md` for confirmed relationship and location
  events;
- update `docs/domains/writing-assistant.md` for its confirmed-memory validation
  input;
- update `docs/domains/README.md` and its context map.

## Backend Package Boundaries

The intended structure is:

```text
backend/
├── application/
│   ├── jobs/
│   └── use_cases/
│       ├── analyze_saved_scene.py
│       ├── approve_memory_candidates.py
│       └── validate_scene_consistency.py
├── apps/
│   ├── narrative_memory/
│   │   ├── repository/
│   │   ├── router/
│   │   ├── schemas/
│   │   └── service/
│   ├── story_bible/
│   │   ├── repository/
│   │   └── service/
│   └── writing_assistant/
│       └── service/
├── infrastructure/
│   ├── audit/
│   ├── jobs/
│   └── llm/
├── prompts/
│   ├── README.md
│   ├── consistency-validation/system.md
│   └── scene-analysis/system.md
└── var/
    └── agent-audit.sqlite3
```

Cross-domain application use cases coordinate state changes. Agent adapters,
prompt loading, SQLite details, and process execution remain infrastructure
concerns. Domain and application services depend on narrow typed ports and do
not import Pydantic AI, FastAPI, or SQLite.

`backend/var/` is runtime state and must be ignored by Git. A configuration
value may override the database path for tests and deployments.

## Agent Responsibilities and Contracts

### Scene Analysis Agent

The Scene Analysis Agent accepts one chunk plus an explicit catalog of known
character and place identifiers, names, and aliases. It returns a Pydantic-
validated `ChunkAnalysisResult` containing:

- a local summary;
- entity candidates and mentions;
- place candidates and mentions;
- relationship-event candidates;
- location-event candidates;
- evidence offsets relative to the chunk;
- confidence for each candidate.

Relationship events contain a controlled broad category, a work-specific
description, subject and object references, and evidence. Broad categories are
initially romance, family, friendship, professional, antagonistic, and other.
The free-form description preserves distinctions that do not justify an
unbounded graph vocabulary.

Location events use the controlled types `arrived`, `present`, and `departed`.
Mentioning a place in narration or dialogue is not sufficient to create a
location event. The result must identify textual evidence that asserts the
character's physical presence or movement.

The agent cannot generate persistent identifiers, approve candidates, write
JSON snapshots, or emit Cypher.

### Consistency Validator Agent

The validator accepts:

- the complete new or changed scene;
- its scene sequence and manuscript revision;
- confirmed Story Bible characters, places, world rules, relationship events,
  and location events relevant to the scene;
- relevant earlier scene summaries and evidence excerpts.

It returns `ConsistencyValidationResult.diagnostics`. Every diagnostic contains
severity, category, a concise message, manuscript evidence, conflicting
confirmed fact identifiers, and an explanation. A result without both new-scene
evidence and a conflicting confirmed fact is invalid. Candidate facts never
serve as contradiction criteria.

The validator cannot change the manuscript, approve facts, write snapshots, or
evaluate subjective prose quality.

## Chunking

Python Unicode character indexes define chunk boundaries; byte length and model
token length do not. For non-empty text:

- maximum chunk length: 300 characters;
- overlap: 50 characters;
- stride: 250 characters;
- the last chunk may be shorter than 300 characters;
- empty text produces no LLM work and an empty successful scene result.

Every chunk records:

```json
{
  "chunk_id": "scene-08:r17:0003",
  "scene_id": "scene-08",
  "manuscript_revision": 17,
  "ordinal": 3,
  "start_offset": 750,
  "end_offset": 1050,
  "content_hash": "sha256:...",
  "text": "..."
}
```

Agent-relative evidence offsets are converted to absolute scene offsets before
merging. The merge rejects evidence outside its source chunk.

## JSON Artifact Pipeline

The required order is:

```text
scene snapshot
  -> chunks
  -> rendered prompts
  -> raw model responses
  -> validated ChunkAnalysis JSON
  -> merged SceneRelationshipSnapshot JSON
  -> merged ProjectRelationshipSnapshot JSON
  -> candidate review and decisions
```

No later stage runs unless the previous artifact has been durably stored. All
artifacts carry a schema version. Pydantic validates model results before they
are eligible for merge.

### Chunk Analysis Artifact

The validated artifact includes `schema_version`, chunk identity, entities,
places, relationship events, location events, evidence, and local summary.
Raw responses remain separately available for audit and are never treated as
valid artifacts.

### Scene Snapshot

The scene snapshot is a deterministic merge of all successful chunk artifacts
for one exact scene revision and analysis schema. It deduplicates overlap while
retaining all distinct evidence ranges.

### Project Snapshot

The project snapshot is a complete, immutable, versioned JSON document. It
contains current character and place candidates, temporal relationship and
location events, decisions, active scene analysis references, and snapshot
metadata. SQLite stores each version as JSON text; the internal viewer exposes
the exact document as a JSON download.

The current snapshot is the highest committed version for the project. A later
Neo4j integration will consume this JSON and must not change its business
meaning.

## Merge Semantics

The merge is deterministic and runs in one SQLite transaction.

1. Read the current project snapshot version.
2. Remove evidence and unconfirmed candidates contributed only by the old
   active revision of the changed scene.
3. Mark a confirmed event `needs_review` when its supporting evidence from the
   changed scene is absent or materially different. Never silently delete it.
4. Merge the new scene snapshot.
5. Deduplicate overlap results.
6. Validate all references and approval invariants.
7. Insert the complete next project snapshot with `version + 1`.
8. Atomically advance the current-version pointer.

Approved character and place IDs are identity keys. Unresolved candidates use a
project-scoped normalized name and aliases until the user resolves them.

Relationship events merge only when subject, object, broad category, normalized
description, scene, and overlapping evidence identify the same asserted event.
The same pair and category in different scenes remain separate temporal events.
Multiple independent evidence ranges accumulate on one event.

Location events merge only when character, place, event type, scene, and
overlapping evidence identify the same asserted movement or presence. A place
mention never merges into a location event.

The transaction uses optimistic concurrency on project ID and current snapshot
version. A conflict reloads the new current snapshot and reruns the deterministic
merge.

## Candidate Approval

Candidates support `pending`, `approved`, `rejected`, and `needs_review`.
Every decision is appended with actor, timestamp, source snapshot version, and
optional reason. Approval creates a new project snapshot; older snapshots are
never rewritten.

An event that references an unresolved character or place cannot be approved.
The user must first resolve or approve those entities. The backend supports
batch decisions for all candidates in a scene, but validates dependencies
before committing the batch.

Reanalyzing a scene replaces pending candidates from its previous revision.
Rejected decisions remain in audit history. Confirmed events whose evidence has
changed become `needs_review` and are excluded from strict validation until the
user reconfirms them.

## Hierarchical Validation Context

The validator does not receive the entire manuscript. The application use case
constructs context from:

1. the complete new scene;
2. confirmed characters and places mentioned in that scene;
3. confirmed relationship and location events for those entities up to the
   current scene sequence;
4. confirmed world rules selected from Story Bible;
5. related earlier scene summaries and bounded evidence excerpts.

The MVP performs deterministic filtering over JSON arrays and identifiers. It
does not introduce embeddings. Summaries may help locate context, but only
confirmed facts can support a contradiction diagnostic.

## In-Process Job Execution

A successful manuscript save calls `QueueSceneAnalysis` with an immutable scene
snapshot. The save response does not wait for analysis.

Job states are `pending`, `running`, `succeeded`, `failed`, and `superseded`.
The idempotency key is project ID, scene ID, manuscript revision, and analysis
schema version. Only one active job may exist for a key.

The process executor uses a bounded `asyncio` queue and configurable worker
count. A newer revision supersedes an older queued job for the same scene.
Startup recovery changes jobs left `running` by a terminated process back to
`pending` and queues all recoverable jobs. Persistent state, not the in-memory
queue, determines what work remains.

Each chunk receives at most two model attempts. If any chunk remains invalid or
fails, the job fails and no new scene or project snapshot is committed. A retry
may reuse already validated chunk artifacts with matching content, prompt,
model settings, and schema hashes.

## Prompt Management

System prompts are deliberately easy to find:

```text
backend/prompts/
├── README.md
├── consistency-validation/system.md
└── scene-analysis/system.md
```

Each prompt uses Markdown with front matter:

```markdown
---
prompt_id: scene-analysis
version: 1
result_schema: scene-analysis-v1
---

Prompt instructions...
```

The prompt registry reads the file for every new agent run so an edit applies
without a process restart. It validates required metadata and computes SHA-256
over the exact file bytes. Once a `prompt_id + version` has appeared in the
audit store, a different hash for the same pair is rejected; an editor must
increment the version. Unknown result schemas are rejected before a model call.

`backend/prompts/README.md` documents available variables, result schemas,
editing rules, local validation, and the versioning requirement. User messages
are built from typed inputs rather than ad hoc string concatenation.

## Audit Storage

Agent audit information is separate from application logs. SQLite stores:

- prompt definitions and hashes;
- jobs and append-only job transitions;
- agent runs and every attempt;
- fully rendered system and user messages;
- provider, model, settings, timestamps, latency, and token usage;
- raw responses and parsing failures;
- validated chunk artifacts;
- scene snapshots and project snapshots;
- candidate decisions and snapshot merge failures.

Mutable job and current-snapshot projections may be updated for efficient reads,
but every transition and complete snapshot version is append-only. Full prompts,
manuscript excerpts, and model responses never go to ordinary console logs. The
database file is created with owner-only read and write permissions.

## Internal Audit Viewer

The backend serves a small, server-rendered internal viewer:

- `/internal/agent-runs` lists runs and their status, agent, scene, model,
  prompt version, timing, and token use;
- `/internal/agent-runs/{run_id}` shows rendered messages, raw response,
  validated JSON, retries, and errors;
- `/internal/analysis-jobs/{job_id}` shows chunk progress and artifact state;
- `/internal/relationship-snapshots/{project_id}` lists versions and supports
  JSON download and version comparison.

The exact screen contract lives in
`frontend/docs/ui-plans/agent-audit-viewer.md`. Although documented with other
UI plans, it is an internal backend-rendered diagnostic interface and does not
become part of the product writing workspace.

The router accepts loopback clients only. Outside local development it is not
registered unless explicitly enabled. Templates escape manuscript and model
content, and JSON downloads use attachment responses. Production remote access
and authentication are separate future work.

## Failure Handling

- Missing or invalid prompt metadata fails before an LLM request.
- Every model attempt is stored, including validation errors and retry context.
- One terminal chunk failure prevents scene and project snapshot commits.
- A merge or invariant failure leaves the previous project snapshot current.
- A process restart recovers durable incomplete jobs.
- A newer scene revision supersedes stale queued work.
- A concurrent snapshot update causes a deterministic merge retry.
- Audit-write failure prevents the corresponding model call or state change;
  unlogged agent execution is not permitted.
- Invalid evidence offsets, unresolved event references, or unsupported enum
  values reject the artifact.

## API and Contract Boundary

The implementation needs consumer-facing operations to:

- list pending candidates for a scene or project;
- submit batch approval and rejection decisions;
- request consistency validation and retrieve its diagnostics;
- inspect analysis status when required by the product UI.

Exact paths, transport schemas, status codes, and error responses are not
invented in this design. Before implementation, the main agent must scope these
operations and assign `docs/api/openapi.yaml` exclusively to the OpenAPI agent.
The localhost-only internal viewer is a diagnostic interface and remains
separate from the consumer-facing contract.

## Verification Strategy

### Unit Tests

- Unicode chunk length, 50-character overlap, offsets, hashes, empty input, and
  final short chunk.
- Prompt metadata, same-version hash rejection, schema lookup, and reload.
- Pydantic validation of analysis and consistency results.
- Conversion from chunk-relative to scene-relative evidence offsets.
- Overlap deduplication without loss of independent evidence.
- Same-scene revision replacement and cross-scene event accumulation.
- Relationship and location-event merge identity.
- Confirmed-event transition to `needs_review` after evidence changes.
- Entity-before-event approval dependencies and atomic batch decisions.
- Hierarchical context exclusion of pending, rejected, and `needs_review`
  candidates.

### Use-Case and Persistence Tests

- A manuscript save queues analysis without waiting for model completion.
- Idempotent duplicate job requests and superseding newer revisions.
- All-or-nothing scene snapshot commit after chunk analysis.
- Append-only artifacts, runs, decisions, and snapshot versions.
- Optimistic concurrency and deterministic merge retry.
- Restart recovery of `pending` and abandoned `running` jobs.
- Consistency validation has no manuscript or memory write effects.

### Adapter and Viewer Tests

- Pydantic AI test models produce structured results without network access.
- Every model attempt persists its complete rendered prompt and response.
- SQLite file initialization and owner-only permissions.
- Internal routes reject non-loopback requests and stay disabled when configured
  off.
- HTML escapes prompt, manuscript, error, and response content.
- Snapshot JSON download is byte-for-byte the stored document.
- Snapshot diff distinguishes additions, removals, decisions, and stale facts.

### Full Backend Verification

Run from `backend/`:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

## Acceptance Criteria

1. Saving a changed scene returns without waiting for an LLM and leaves a
   durable recoverable analysis job.
2. Analysis uses at most 300 Unicode characters per chunk with exactly 50
   characters of overlap where another chunk follows.
3. Every LLM attempt is auditable with the exact prompt version, hash, rendered
   messages, response, parse result, timing, settings, and error.
4. Only validated JSON artifacts participate in merging.
5. New scene JSON merges into a versioned project JSON snapshot using the
   replacement, deduplication, and temporal-event rules in this design.
6. Characters, places, relationships, and location events remain unconfirmed
   until user approval.
7. Editing confirmed evidence marks the fact `needs_review` rather than deleting
   or silently retaining it as valid.
8. Explicit consistency validation uses only confirmed facts and returns
   evidence-backed diagnostics without changing manuscript or memory.
9. The localhost-only audit viewer exposes runs, jobs, artifacts, prompt data,
   snapshot downloads, and snapshot differences safely.
10. No Neo4j or Cypher implementation is introduced in this MVP.

## Future Neo4j Projection

A later feature may implement a deterministic projector that consumes an exact
`ProjectRelationshipSnapshot` schema version. It may create graph nodes and
relationships only from validated JSON, use parameterized Cypher, and record
the projected snapshot version. LLM-generated Cypher remains prohibited. This
future adapter must not become the authority for candidate approval or alter
the JSON merge semantics defined here.
