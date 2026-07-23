# Character Memory Knowledge Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strict, independently persisted character memories to Narrative Memory scene analysis and v2 project knowledge graph snapshots without changing existing authority boundaries or consumer-facing APIs.

**Architecture:** Extend the public frozen Pydantic graph contract with `MemoryTarget` and `CharacterMemory`, then validate explicit extraction semantics at the agent boundary. Backend owns typed local-ID rewriting, overlap deduplication, scene replacement, project reconstruction, semantic integrity, and canonical v2-compatible persistence through the existing SQLite JSON BLOB transaction.

**Tech Stack:** Python 3.13, Pydantic 2, pydantic-ai, FastAPI backend composition, SQLite, pytest, Ruff, uv/mise.

## Global Constraints

- Implement ticket 10 only; do not change frontend, HTTP API, OpenAPI, Story Bible storage, Writing Assistant inputs, provider selection, retries, database tables, or background processing.
- Keep `project-knowledge-graph-snapshot-v2` and decode legacy v2 scene/project JSON that omits `character_memories` as an empty tuple.
- New canonical scene and project JSON always emits `character_memories`; stored historical bytes and hashes are never rewritten automatically.
- Public models remain strict, frozen, extra-field-forbidding Pydantic models and public collections remain tuples.
- General memory confidence is finite and in the closed range `0.8..1.0`; lower-confidence or ambiguous extraction goes to `unresolved_references`.
- Memory evidence is a non-empty verbatim substring of the current chunk at extraction and merge time.
- Only explicit remembering, forgetting, repression, uncertain recollection, or false-memory language creates a memory. Facts, participation, beliefs, perceptions, and retrospective narration alone do not.
- Character memories remain derived, non-authoritative Narrative Memory data and are never automatically promoted to Story Bible facts or Writing Assistant caller-selected prior memory.
- `llm-agent` never allocates durable IDs, merges chunks, writes storage, or changes retry behavior; backend remains the sole write and merge owner.
- Domain behavior and `docs/domains/narrative-memory.md` must agree in the same change.
- Commit messages must be written in Korean.

---

### Task 1: Public strict memory contract and additive v2 decoding

**Files:**
- Modify: `llm-agent/src/narrative_analysis_agent/models.py`
- Modify: `llm-agent/src/narrative_analysis_agent/__init__.py`
- Modify: `llm-agent/tests/unit/test_models.py`
- Modify: `llm-agent/tests/unit/test_project_graph_reader.py`

**Interfaces:**
- Consumes: existing `StrictModel`, `HighConfidence`, `KnowledgeGraphOutput`, and `ProjectKnowledgeGraphSnapshot`.
- Produces: public `MemoryTarget`, `CharacterMemory`, `MemoryState`, and `character_memories: tuple[CharacterMemory, ...] = ()` on chunk and project graphs.

- [ ] **Step 1: Add failing strict-schema and compatibility tests**

Add fixtures that construct this exact public value and verify all fields survive JSON validation:

```python
memory = CharacterMemory(
    id="memory_001",
    character_id="character_001",
    target=MemoryTarget(
        kind="event",
        reference_id="event_001",
        description="비 내리던 날의 약속",
    ),
    content="서윤은 비 내리던 날의 약속을 기억한다.",
    state="remembered",
    time_expression="10년 전",
    scene_sequence=4,
    evidence="그녀는 10년 전 비 내리던 날의 약속을 기억했다",
    confidence=0.94,
)
```

Cover each state, linked target kind, description-only target kind, unknown
fields, invalid ID prefixes, forbidden reference IDs on description-only
targets, missing references on linked targets, empty content/description/
evidence, non-finite or out-of-range confidence, negative scene sequence, and
frozen instances. Add a legacy v2 JSON fixture without `character_memories`
and assert both direct model validation and `ProjectGraphReader.read()` produce
`()`. Add a populated reader fixture and assert the memory round-trips.

- [ ] **Step 2: Run the model and reader tests and verify RED**

Run:

```sh
cd llm-agent
mise exec -- uv run pytest \
  tests/unit/test_models.py \
  tests/unit/test_project_graph_reader.py -v
```

Expected: collection/import tests fail because the new public types and fields
do not exist.

- [ ] **Step 3: Implement the strict public models**

Add these aliases and models in `models.py`, using a model validator to enforce
the linked/description-only invariant:

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

The `MemoryTarget` validator must require prefixes `character_`, `location_`,
`event_`, or `relation_` for linked kinds and require `None` for
`described_event`, `described_relation`, and `other`. Add the default-empty
collection to both graph models and export the public types from `__init__.py`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: all selected tests pass, including the legacy
v2 payload without the new key.

- [ ] **Step 5: Commit the public contract**

```sh
git add llm-agent/src/narrative_analysis_agent/models.py \
  llm-agent/src/narrative_analysis_agent/__init__.py \
  llm-agent/tests/unit/test_models.py \
  llm-agent/tests/unit/test_project_graph_reader.py
git commit -m "기능: 인물 기억 공개 모델 추가"
```

### Task 2: Explicit-memory prompt and agent boundary validation

**Files:**
- Modify: `llm-agent/src/narrative_analysis_agent/agent.py`
- Modify: `llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md`
- Modify: `llm-agent/tests/unit/test_agent.py`
- Modify: `llm-agent/tests/integration/test_scene_analysis_offline.py`
- Modify: `llm-agent/tests/live/test_scene_analysis_live.py`

**Interfaces:**
- Consumes: Task 1 `CharacterMemory`, `MemoryTarget`, and project snapshot collections.
- Produces: prompt envelope containing `scene_id` and `scene_sequence`; typed local-or-existing memory reference validation; exact chunk evidence enforcement.

- [ ] **Step 1: Write failing agent-validation tests**

Extend the graph helper with `character_memories=()`. Add tests for:

```python
CharacterMemory(
    id="memory_001",
    character_id="character_001",
    target=MemoryTarget(
        kind="relation",
        reference_id="relation_001",
        description="두 사람의 약속",
    ),
    content="서윤은 약속을 기억한다.",
    state="remembered",
    time_expression=None,
    scene_sequence=3,
    evidence="서윤은 약속을 기억한다",
    confidence=0.9,
)
```

Verify acceptance for local and existing character/location/event/relation
targets. Verify rejection without retry for duplicate memory IDs, wrong-kind or
dangling subject/target, mismatched scene sequence, and absent evidence. Assert
the rendered JSON envelope has exact scene metadata and that every chunk still
receives the same unchanged existing snapshot. Add an offline integration case
that preserves a returned memory. Extend live assertions without requiring a
provider call in the default suite.

- [ ] **Step 2: Run agent tests and verify RED**

```sh
cd llm-agent
mise exec -- uv run pytest \
  tests/unit/test_agent.py \
  tests/integration/test_scene_analysis_offline.py -v
```

Expected: new prompt-envelope and memory validation assertions fail.

- [ ] **Step 3: Implement prompt rendering and semantic validation**

Change rendering to accept the request and include stable scene metadata:

```python
def _render_user_prompt(
    request: SceneAnalysisRequest,
    existing: ProjectKnowledgeGraphSnapshot,
    chunk: SceneChunk,
) -> str:
    envelope = {
        "scene": {
            "scene_id": request.scene_id,
            "scene_sequence": request.scene_sequence,
        },
        "existing_graph": existing.model_dump(mode="json"),
        "chunk": {
            "chunk_id": chunk.chunk_id,
            "ordinal": chunk.ordinal,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            "text": chunk.text,
        },
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
```

In `_validate_output`, collect local and existing relation IDs, validate unique
memory IDs, require the subject in the character set, dispatch target validation
by `target.kind`, require exact request scene sequence, and add memory evidence
to the chunk-substring list. Keep `analyze_scene()` step calls and their Korean
workflow comments synchronized.

- [ ] **Step 4: Update the system prompt**

Add explicit Korean instructions that:

- extract only source-explicit remembered, forgotten, repressed, uncertain, or
  false-memory statements;
- never infer memory from a fact, participation, knowledge, belief, perception,
  flashback, or retrospective narration alone;
- represent false/unverified propositions with description-only targets rather
  than world entities or relations;
- route ambiguous subject/target and confidence below `0.8` to
  `unresolved_references`;
- use current-chunk evidence only;
- preserve non-authoritative Story Bible and Writing Assistant boundaries.

- [ ] **Step 5: Run the complete llm-agent verification**

```sh
cd llm-agent
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit agent extraction behavior**

```sh
git add llm-agent/src/narrative_analysis_agent/agent.py \
  llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md \
  llm-agent/tests/unit/test_agent.py \
  llm-agent/tests/integration/test_scene_analysis_offline.py \
  llm-agent/tests/live/test_scene_analysis_live.py
git commit -m "기능: 명시적 인물 기억 추출 검증"
```

### Task 3: Backend typed relation and character-memory merge

**Files:**
- Modify: `backend/apps/narrative_memory/service/merge.py`
- Modify: `backend/tests/narrative_memory/test_merge.py`

**Interfaces:**
- Consumes: Task 1 public memory contract and existing character/location/event maps.
- Produces: a relation result carrying local-to-project IDs; deterministic memory rewriting, overlap deduplication, dependency closure, and scene/project aggregation.

- [ ] **Step 1: Write failing merge tests**

Create helpers for `MemoryTarget` and `CharacterMemory`. Add focused tests that
prove:

- subject and character/location/event/relation target IDs are rewritten;
- described targets retain `reference_id=None` and exact text;
- overlap copies with the same absolute evidence position and semantic fields
  collapse to one memory while distinct state/time/content remains distinct;
- reversed chunk input order produces the same memory IDs and values;
- evidence missing from the source chunk is rejected;
- references to existing project relations pull relation/entity/event
  dependencies into the scene closure;
- project reconstruction orders memories by scene, replaces an older scene
  revision, and preserves other scenes.

The core assertion for a rewritten relation target is:

```python
assert graph.character_memories == (
    source_memory.model_copy(
        update={
            "id": "memory_001",
            "character_id": "character_007",
            "target": source_memory.target.model_copy(
                update={"reference_id": "relation_010"}
            ),
        }
    ),
)
```

- [ ] **Step 2: Run merge tests and verify RED**

```sh
cd backend
mise exec -- uv sync --dev
mise exec -- uv run pytest tests/narrative_memory/test_merge.py -v
```

Expected: new memory collection and relation mapping assertions fail.

- [ ] **Step 3: Separate relation mapping from relation materialization**

Introduce a cohesive result or pair with these interfaces:

```python
@dataclass(frozen=True, slots=True)
class RelationMerge:
    items: tuple[Relation, ...]
    id_map: IdMap
```

Keep `_merge_relations(chunks, existing, entity_map, event_map) ->
RelationMerge`. While allocating each durable relation, assign
`id_map[(chunk.ordinal, relation.id)] = durable_id` before deduplicating the
materialized value, then return
`RelationMerge(items=tuple(merged), id_map=id_map)` using the existing sorted
`merged` list.
Preserve all existing relation ordering and change-history
behavior.

- [ ] **Step 4: Implement deterministic memory rewriting and aggregation**

Add `_merge_character_memories(chunks, existing, character_map, location_map,
event_map, relation_map) -> tuple[CharacterMemory, ...]`. Use this concrete
typed target rewrite helper:

```python
def _rewrite_memory_target(
    ordinal: int,
    target: MemoryTarget,
    target_maps: dict[str, IdMap],
) -> MemoryTarget:
    if target.reference_id is None:
        return target
    durable_id = _resolve_reference(
        ordinal,
        target.reference_id,
        target_maps[target.kind],
    )
    return target.model_copy(update={"reference_id": durable_id})
```

For linked targets select the map by kind; described targets are copied
unchanged. Build the duplicate key from absolute evidence position, rewritten
subject/target, normalized content, state, normalized time expression, scene
sequence, normalized evidence, and confidence. Allocate `memory_NNN` after the
highest existing memory ID in deterministic key order. Add memories to the
scene graph and project reconstruction aggregation.

Extend dependency closure to include memory subjects and linked targets. When
the target is an existing relation, copy that relation and enqueue its source,
target, start-event, and end-event dependencies.

- [ ] **Step 5: Run merge verification and commit**

```sh
cd backend
mise exec -- uv run pytest tests/narrative_memory/test_merge.py -v
cd ..
git add backend/apps/narrative_memory/service/merge.py \
  backend/tests/narrative_memory/test_merge.py
git commit -m "기능: 인물 기억 재매핑과 장면 병합"
```

Expected: focused merge tests exit 0.

### Task 4: Snapshot integrity, canonical codec, and SQLite compatibility

**Files:**
- Modify: `backend/apps/narrative_memory/service/validation.py`
- Modify: `backend/apps/narrative_memory/service/snapshot_codec.py` only if the tests expose a codec-specific gap
- Modify: `backend/apps/narrative_memory/repository/sqlite_snapshot_repository.py` only if the tests expose a repository-boundary gap
- Modify: `backend/tests/narrative_memory/test_snapshot_codec.py`
- Modify: `backend/tests/narrative_memory/test_sqlite_snapshot_repository.py`

**Interfaces:**
- Consumes: Task 3 merged scene and project graphs.
- Produces: typed memory referential validation and legacy/new v2 canonical persistence guarantees through existing repository APIs.

- [ ] **Step 1: Add failing semantic and persistence tests**

Add tests for:

- canonical JSON containing `"character_memories"` and stable
  encode-decode-encode bytes;
- legacy v2 project and scene payloads without the key decoding as `()`;
- dangling/wrong-kind memory subject and each linked target kind;
- a description-only target carrying a reference ID;
- invalid model copies for state, sequence, evidence, content, description, and
  confidence rejected before storage;
- stored scene/project memory round-trip and correct hashes;
- corrupt memory payload rejection;
- scene replacement and project history with memories;
- transaction rollback and current pointer preservation on a memory invariant,
  stale version, or write failure.

Use exact canonical output with the collection positioned by sorted JSON keys;
do not relax existing byte assertions.

- [ ] **Step 2: Run codec and repository tests and verify RED**

```sh
cd backend
mise exec -- uv run pytest \
  tests/narrative_memory/test_snapshot_codec.py \
  tests/narrative_memory/test_sqlite_snapshot_repository.py -v
```

Expected: semantic reference and canonical collection assertions fail.

- [ ] **Step 3: Extend graph semantic validation**

Add memory IDs to global uniqueness. For every memory:

```python
_require_reference(memory.character_id, character_ids, "memory character")
if memory.target.kind == "character":
    _require_reference(memory.target.reference_id, character_ids, "memory target")
elif memory.target.kind == "location":
    _require_reference(memory.target.reference_id, location_ids, "memory target")
elif memory.target.kind == "event":
    _require_reference(memory.target.reference_id, event_ids, "memory target")
elif memory.target.kind == "relation":
    _require_reference(memory.target.reference_id, relation_ids, "memory target")
```

Include memory confidence and evidence in the existing validation sequences.
Rely on exact strict model revalidation for enum, target-shape, content,
description, and scene-sequence constraints. Keep codec and repository logic
unchanged when the existing generic model dump/load already meets the test;
change those files only for an observed boundary gap.

- [ ] **Step 4: Run focused persistence verification**

Run the Step 2 command. Expected: all selected tests pass, including untouched
historical payload/hash behavior.

- [ ] **Step 5: Commit persistence integrity**

```sh
git add backend/apps/narrative_memory/service/validation.py \
  backend/apps/narrative_memory/service/snapshot_codec.py \
  backend/apps/narrative_memory/repository/sqlite_snapshot_repository.py \
  backend/tests/narrative_memory/test_snapshot_codec.py \
  backend/tests/narrative_memory/test_sqlite_snapshot_repository.py
git commit -m "기능: 인물 기억 스냅샷 무결성 보장"
```

Do not stage unchanged production files.

### Task 5: Use-case integration and domain synchronization

**Files:**
- Modify: `backend/tests/narrative_memory/test_scene_analysis_use_case.py`
- Modify: `docs/domains/narrative-memory.md`
- Modify: `backend/README.md` only if implementation changes the documented package responsibilities
- Modify: `llm-agent/docs/llm-agent-coding-rules.md` only if implementation establishes a reusable agent engineering rule not already documented
- Modify: `backend/docs/backend-coding-rules.md` only if implementation establishes a reusable backend engineering rule not already documented

**Interfaces:**
- Consumes: completed public schema, agent validation, backend merge, and persistence.
- Produces: end-to-end application proof and synchronized authoritative Narrative Memory domain language.

- [ ] **Step 1: Add failing use-case integration tests**

Construct a `SceneAnalysis` with one explicit memory and verify
`AnalyzeSceneUseCase.execute()` returns the exact analysis only after the
repository contains both the memory-bearing scene record and rebuilt project
snapshot. Add a failure case proving a stale version or rejected memory merge
publishes neither scene nor project state.

- [ ] **Step 2: Run the integration test and verify RED or existing coverage gap**

```sh
cd backend
mise exec -- uv run pytest \
  tests/narrative_memory/test_scene_analysis_use_case.py -v
```

Expected before the new assertion is satisfied: failure because the memory is
not present in stored scene/project output.

- [ ] **Step 3: Synchronize the domain contract**

Update `docs/domains/narrative-memory.md` to define:

- character memory, memory subject, structured linked/description target, and
  the five memory states in ubiquitous language;
- the independent collection in `KnowledgeGraphOutput`, `SceneGraphRecord`, and
  `ProjectKnowledgeGraphSnapshot`;
- explicit-only extraction and separation from fact, belief/perception,
  flashback narration, unresolved references, Story Bible authority, and
  Writing Assistant caller-selected non-authoritative memories;
- typed local-ID remapping, evidence/scene-sequence preservation, overlap merge,
  scene replacement, project reconstruction, and referential integrity;
- additive v2 compatibility, new canonical emission, immutable historical
  bytes/hashes, and no migration.

Do not change `docs/domains/README.md` because dependency directions do not
change.

- [ ] **Step 4: Run all affected application checks**

```sh
cd llm-agent
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .

cd ../backend
mise exec -- uv sync --dev
mise exec -- uv run pytest \
  tests/narrative_memory/test_merge.py \
  tests/narrative_memory/test_snapshot_codec.py \
  tests/narrative_memory/test_sqlite_snapshot_repository.py \
  tests/narrative_memory/test_scene_analysis_use_case.py -v
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: every command exits 0. Confirm `git diff --check` is clean and compare
the implementation diff with the Narrative Memory domain diff requirement by
requirement.

- [ ] **Step 5: Commit integration and domain documentation**

```sh
git add backend/tests/narrative_memory/test_scene_analysis_use_case.py \
  docs/domains/narrative-memory.md backend/README.md \
  llm-agent/docs/llm-agent-coding-rules.md \
  backend/docs/backend-coding-rules.md
git commit -m "문서: 인물 기억 도메인 계약 동기화"
```

Stage only files actually changed.

### Task 6: Read-only review, remediation, and final verification

**Files:**
- Review only: complete branch diff from merge-base with `main`
- Review only: all changed `llm-agent/`, `backend/`, and `docs/domains/narrative-memory.md` paths

**Interfaces:**
- Consumes: Tasks 1-5 implementation and verification evidence.
- Produces: resolved task reviews, backend-review conclusion and normalized verdict, whole-branch review, and fresh final verification evidence.

- [ ] **Step 1: Review each implementation task**

After each implementer stops editing, generate an exact base/head review package
and run a read-only task review for spec compliance and code quality. Resolve
every accepted finding. Re-run focused tests after every fix and re-review all
Blocking/High findings or material behavior changes.

- [ ] **Step 2: Dispatch the project backend reviewer**

Review these backend entry points and boundaries:

- `assemble_scene_graph()` and `rebuild_project_graph()`;
- `validate_scene_graph()` and `validate_project_snapshot()`;
- `encode_project_snapshot()` and `decode_project_snapshot()`;
- `SQLiteSnapshotRepository.get_scene_graphs()`, `get_current()`, and
  `commit_scene()`;
- `AnalyzeSceneUseCase.execute()` integration.

Provide the approved design, this plan, complete implementer handoff, exact
diff boundary, tests, domain contract, exclusions, and explicit read-only
ownership. Record every native finding, disposition, native conclusion, and
normalized verdict.

- [ ] **Step 3: Run whole-branch review and resolve findings**

Generate a review package from `git merge-base main HEAD` to `HEAD`. Review the
complete llm-agent public boundary, backend integration, additive v2 policy,
authority separation, and test evidence. Send one consolidated fix assignment
for validated findings and re-review material corrections.

- [ ] **Step 4: Run fresh final verification**

```sh
cd llm-agent
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .

cd ../backend
mise exec -- uv sync --dev
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .

cd ..
git diff --check main...HEAD
git status --short --untracked-files=all
```

Expected: every check exits 0 and the status contains no unintended files.

- [ ] **Step 5: Finalize the branch result**

Confirm all `NM-MEM-001` through `NM-MEM-010` requirements are implemented and
verified, every accepted finding is resolved, and no frontend/API/OpenAPI files
changed. Report commits, changed paths, exact commands/results, additive v2
policy, review conclusions/dispositions, and remaining risks. Only after the
objective is genuinely complete emit the ticket completion marker requested by
the user.
