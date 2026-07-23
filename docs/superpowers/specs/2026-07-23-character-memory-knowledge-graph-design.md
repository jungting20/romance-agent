# Character Memory Knowledge Graph Design

## Status

- Ticket: `10` (`feature/인물-기억-그래프`)
- Approved implementation brief: 2026-07-23
- Mode: FULL
- Consumer-facing API impact: none
- Frontend impact: none

## Goal

Narrative Memory scene analysis and project knowledge graph snapshots will
preserve explicit character memories as a strict public model and an independent
collection. A memory remains derived, non-authoritative Narrative Memory data;
it is never encoded as a relation attribute, prompt-only prose, Story Bible
fact, or automatically selected Writing Assistant context.

## Scope

This feature changes only:

- the public strict schema, prompt, validation, and read-only graph loading in
  `llm-agent/src/narrative_analysis_agent/`;
- backend chunk-local ID remapping, scene merging, project reconstruction,
  semantic validation, canonical JSON persistence, and SQLite compatibility in
  `backend/apps/narrative_memory/`;
- corresponding deterministic unit and integration tests;
- `docs/domains/narrative-memory.md`.

It does not change frontend code, HTTP routes, OpenAPI, Story Bible storage,
Writing Assistant inputs, provider selection, retry behavior, database tables,
or background processing.

## Requirements

- `NM-MEM-001`: The public schema exposes a frozen, strict
  `CharacterMemory` model and an independent top-level
  `character_memories` tuple on both `KnowledgeGraphOutput` and
  `ProjectKnowledgeGraphSnapshot`.
- `NM-MEM-002`: Each memory preserves a local or durable memory ID, the subject
  character ID, structured target, remembered content, memory state, optional
  source time expression, project scene sequence, verbatim current-chunk
  evidence, and finite `0.8..1.0` confidence.
- `NM-MEM-003`: Memory state distinguishes `remembered`, `forgotten`,
  `repressed`, `uncertain`, and `false_memory`. It does not encode a general
  belief, perception, or Story Bible verification state.
- `NM-MEM-004`: Ordinary memory extraction requires explicit source language
  that a character remembers, forgot, repressed, is uncertain about remembering,
  or holds a false memory. Mere participation, knowledge, belief, perception,
  or retrospective narration is insufficient.
- `NM-MEM-005`: An ambiguous subject or target, a target that cannot be safely
  categorized, or an extraction below confidence `0.8` produces an
  `unresolved_references` entry instead of a general memory.
- `NM-MEM-006`: Backend remaps every local memory subject and linked target to
  the correct project ID kind, merges only deterministically identical overlap
  extractions, and preserves all memory fields exactly.
- `NM-MEM-007`: Scene replacement removes the previous revision's memories,
  preserves other current scenes, and rebuilds the project memory collection in
  scene order without losing scene provenance at the scene-record boundary.
- `NM-MEM-008`: Model, merge, codec, repository, and read boundaries reject
  dangling or wrong-kind linked memory references and invalid confidence,
  evidence, state, or scene sequence values.
- `NM-MEM-009`: Existing v2 scene and project payloads that omit
  `character_memories` remain readable as an empty collection. New canonical
  JSON always writes the collection. No automatic migration changes stored
  immutable payload bytes.
- `NM-MEM-010`: Character memories remain non-authoritative Narrative Memory
  data and are not automatically promoted to Story Bible confirmed facts or to
  the caller-selected prior-memory input of Writing Assistant.

## Public Model

The public model follows the existing `StrictModel` contract: unknown fields
are forbidden, instances are frozen, strict type validation is enabled, and
collections are tuples.

```python
MemoryState = Literal[
    "remembered",
    "forgotten",
    "repressed",
    "uncertain",
    "false_memory",
]

MemoryTargetKind = Literal[
    "character",
    "location",
    "event",
    "relation",
    "described_event",
    "described_relation",
    "other",
]

class MemoryTarget(StrictModel):
    kind: MemoryTargetKind
    reference_id: str | None
    description: str = Field(min_length=1)

class CharacterMemory(StrictModel):
    id: str = Field(pattern=r"^memory_[0-9]+$")
    character_id: str
    target: MemoryTarget
    content: str = Field(min_length=1)
    state: MemoryState
    time_expression: str | None
    scene_sequence: int = Field(ge=0)
    evidence: str = Field(min_length=1)
    confidence: HighConfidence
```

Linked target kinds (`character`, `location`, `event`, and `relation`) require a
non-null `reference_id` with the matching ID prefix. Description-only target
kinds require `reference_id=None`:

- `described_event` and `described_relation` preserve an explicit remembered
  proposition that must not be promoted into a world event or relation, notably
  the content of a false memory;
- `other` is limited to an explicit, unambiguous memory object that has no
  first-class graph ID kind;
- ambiguity about what the target is does not use a description-only target and
  instead routes to `unresolved_references`.

`KnowledgeGraphOutput.character_memories` and
`ProjectKnowledgeGraphSnapshot.character_memories` both default to `()`. The
collection is independent of `Entities` and `Relation`.

## Extraction Semantics

The system prompt will make four layers explicit:

1. Story-world facts and extracted events or relations.
2. A character's belief or perception, which is not automatically a memory.
3. Retrospective narration, which is not automatically attributed to a
   character.
4. Explicit character memory state, which alone may create a
   `CharacterMemory`.

The model must not create a memory merely because a character participated in
an event, knows a fact, thinks something, or appears in a flashback. A false
memory is represented by `state="false_memory"`; its unverified proposition is
kept in a description-only target rather than creating a world event or
relation. Existing project graph evidence is context only and cannot become
current-chunk evidence.

The user prompt envelope will include `scene_id` and `scene_sequence` alongside
the chunk metadata. Agent validation requires every memory's `scene_sequence`
to equal the request value and every memory evidence string to occur verbatim
in the current chunk.

## LLM-Agent Validation

For each chunk, `NarrativeAnalysisAgent` will:

- reject duplicate local memory IDs;
- require the subject to resolve to a local or existing character;
- validate linked target references against the local-or-existing collection
  for the declared kind, including relations;
- validate the target's linked/description-only shape;
- require the memory scene sequence to match the analysis request;
- require evidence to be a non-empty substring of the current chunk;
- rely on the strict public model for states, content, confidence, and extra
  field rejection.

The same project snapshot continues to be read exactly once and supplied to
every chunk. No earlier chunk memory is accumulated into a later chunk prompt.

## Backend Merge

`assemble_scene_graph()` will use this order:

1. Build character, location, and event local-to-project ID maps.
2. Build a relation local-to-project ID map and the merged relation collection.
3. Rewrite each memory subject and linked target through the correct typed map.
4. Verify current-chunk evidence defensively while the source chunk is still
   available.
5. Cluster overlap duplicates using absolute evidence position plus subject,
   target, content, state, time expression, scene sequence, and confidence.
6. Allocate deterministic `memory_NNN` project IDs after the highest existing
   memory ID and preserve the earliest ordered duplicate.

Different scenes do not share memory IDs merely because their content is equal.
This preserves separate acts of remembering and their scene provenance. A scene
reanalysis may allocate replacement IDs; stable identity across revisions is
not promised by the existing derived-graph contract.

When a memory links to an existing project character, location, event, or
relation, the scene dependency closure includes the referenced item. A copied
relation also brings the entities and event anchors required for its own
integrity. This closure is referential support, not new current-chunk evidence
or authority promotion.

## Project Reconstruction and Integrity

`rebuild_project_graph()` aggregates `character_memories` from the current
scene records after ordering them by `(scene_sequence, scene_id)`. Replacing a
scene record therefore removes the old revision's memories while retaining all
other current scene records.

Semantic validation at scene encode/decode, project encode/decode, and
repository storage boundaries will enforce:

- globally unique character, location, event, relation, and memory IDs;
- subject references to characters only;
- linked target references to the exact declared kind;
- no reference ID on description-only targets;
- finite high confidence and non-empty evidence/content/description;
- valid non-negative scene sequence and declared state through exact public
  model revalidation.

Snapshot validation cannot prove substring inclusion because snapshots do not
store full chunk text. The agent and backend merge boundary own that invariant;
later persistence boundaries preserve the already validated evidence exactly.

## Persistence and v2 Compatibility

The schema identifier remains
`project-knowledge-graph-snapshot-v2`. This is an additive v2 extension:

- legacy v2 scene and project payloads without `character_memories` decode to
  an empty tuple through the public model default;
- current records retain their original payload and hash; reading does not
  rewrite or rehash immutable historical bytes;
- newly encoded scene and project payloads always include
  `"character_memories": []` or the populated collection;
- canonical encoding remains UTF-8, sorted, indented JSON with a trailing
  newline and no NaN values;
- decode-encode-encode remains stable for newly canonicalized values;
- v1 and unknown schema identifiers remain rejected;
- SQLite tables and transaction structure do not change, and no migration or
  automatic database deletion is introduced.

A hard v3 cutover was rejected because it would make current v2 projects
unreadable. A dual-reader v2-to-v3 migration was rejected because it adds
storage migration behavior without user value for this additive collection.

## Authority Boundaries

Character memories are explicit but still derived Narrative Memory analysis.
They do not establish world truth. In particular:

- `false_memory` does not create a Story Bible fact or confirmed world event;
- `uncertain` describes memory state, not Story Bible review state;
- the collection is not automatically passed to Writing Assistant;
- Writing Assistant dialogue generation continues to receive only prior
  memories explicitly selected by its caller and treats them as
  non-authoritative context;
- Story Bible confirmed facts remain independently owned and are not changed by
  Narrative Memory extraction or persistence.

## Testing Strategy

### LLM agent

- strict model acceptance and rejection for target shapes, states, confidence,
  evidence, tuple immutability, and unknown fields;
- duplicate memory ID, wrong-kind/dangling subject or target, mismatched scene
  sequence, and evidence absent from the chunk;
- linked references to the existing snapshot;
- prompt separation of facts, beliefs, narration, and explicit memories;
- legacy v2 project payloads without the collection and populated v2 payloads;
- offline integration preservation through `SceneAnalysis`.

### Backend

- character, location, event, and relation target remapping;
- deterministic overlap deduplication and reversed chunk input order;
- exact state, time, sequence, evidence, content, and confidence preservation;
- existing-project dependency closure, including relation dependencies;
- scene replacement, other-scene preservation, and scene-ordered project
  reconstruction;
- canonical project and scene round trips and legacy v2 payload compatibility;
- dangling/wrong-kind references, invalid copied models, and corrupt stored
  payload rejection;
- SQLite scene/project persistence, current pointer, hash, history, concurrency,
  and rollback behavior with memories present;
- use-case integration proving no partial publish on merge, persistence, or
  version failure.

## Verification

From `llm-agent/`:

```sh
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

From `backend/`:

```sh
mise exec -- uv run pytest \
  tests/narrative_memory/test_merge.py \
  tests/narrative_memory/test_snapshot_codec.py \
  tests/narrative_memory/test_sqlite_snapshot_repository.py \
  tests/narrative_memory/test_scene_analysis_use_case.py -v
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

The main agent will compare the implementation diff with
`docs/domains/narrative-memory.md`, review the complete llm-agent boundary,
dispatch the read-only backend reviewer after backend editing stops, resolve all
accepted findings, and rerun fresh full verification before completion.
