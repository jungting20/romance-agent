# Chunk LLM Scene Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explicitly invoked asynchronous Narrative Memory workflow that chunks one scene, calls a provider-configurable structured LLM or scripted mock for each chunk, audits every attempt, and returns the existing validated scene relationship snapshot.

**Architecture:** Provider-independent frozen dataclasses and ports live in Narrative Memory; infrastructure adapters own Pydantic AI, prompt files, environment configuration, and SQLite. `SceneAnalysisService` serially renders and audits each canonical chunk call, translates validated relative extraction into existing `ChunkAnalysis` values, and delegates deterministic scene assembly to `merge_chunk_analyses()`.

**Tech Stack:** Python 3.13, Pydantic 2, Pydantic AI 2.9.1, standard-library dataclasses/hashlib/json/sqlite3/pathlib, pytest, Ruff

## Global Constraints

- Work only in the dedicated `feat/chunk-llm-extraction` worktree.
- Preserve Python compatibility at `>=3.13,<3.14` and add no dependency.
- Keep Narrative Memory service code independent of Pydantic, Pydantic AI, SQLite, environment variables, FastAPI, and provider SDKs.
- Use existing `chunk_scene()` and `merge_chunk_analyses()`; do not implement alternate chunking or merge rules.
- Use canonical maximum 300 Unicode characters, 50-character overlap, and 250-character stride.
- `NARRATIVE_LLM_MODEL=mock` is explicit; missing or blank configuration raises `ModelConfigurationError` only when analyzer composition is requested.
- The scripted mock defaults to an empty valid extraction and never invents story data.
- Run chunks serially by numeric ordinal; each chunk gets at most two provider attempts.
- Every extracted entity, place, relationship event, and location event becomes `pending`.
- Record prompt and attempt-start audit events before each model call; audit-start failure blocks the call.
- Store exact rendered prompts and Pydantic AI serialized messages, never API keys or provider-specific raw HTTP packets.
- Do not modify Manuscript, Story Bible, Writing Assistant, Projects, Worldbuilding, frontend, `main.py`, OpenAPI, background jobs, approval flows, project snapshot persistence, Neo4j, or Cypher.
- Update `docs/domains/narrative-memory.md` and backend engineering documentation in the same change as their behavior/rules.

---

## Planned File Structure

```text
backend/
├── apps/narrative_memory/
│   ├── repository/
│   │   └── analysis_audit.py
│   └── service/
│       ├── scene_analysis.py
│       ├── scene_analysis_ports.py
│       ├── scene_analysis_translation.py
│       └── scene_analysis_types.py
├── infrastructure/
│   ├── audit/
│   │   ├── __init__.py
│   │   └── sqlite_agent_audit.py
│   └── llm/
│       ├── pydantic_ai_scene_analysis.py
│       ├── scene_analysis_factory.py
│       ├── scene_analysis_schemas.py
│       ├── scripted_scene_analysis.py
│       └── prompt_registry.py
├── prompts/
│   ├── README.md
│   └── scene-analysis/system.md
└── tests/narrative_memory/
    ├── test_prompt_registry.py
    ├── test_scene_analysis_agents.py
    ├── test_scene_analysis_factory.py
    ├── test_scene_analysis_service.py
    ├── test_scene_analysis_translation.py
    └── test_sqlite_agent_audit.py
```

---

### Task 1: Define provider-independent extraction contracts and translation

**Files:**

- Create: `backend/apps/narrative_memory/service/scene_analysis_types.py`
- Create: `backend/apps/narrative_memory/service/scene_analysis_translation.py`
- Create: `backend/tests/narrative_memory/test_scene_analysis_translation.py`

**Interfaces:**

- Produces `KnownIdentity`, `AnalyzeSceneRequest`, `RelativeEvidence`, `ExtractedEntity`, `ExtractedPlace`, `ExtractedRelationshipEvent`, `ExtractedLocationEvent`, `SceneChunkExtraction`, `AgentUsage`, and `AgentInvocationResult` as frozen, slotted dataclasses.
- Produces `translate_chunk_extraction(chunk, scene_sequence, extraction, known_entities, known_places) -> ChunkAnalysis`.
- Consumes existing `SceneChunk`, `ChunkAnalysis`, candidate types, `CandidateStatus`, and `LocationEventType`.

- [ ] **Step 1: Write failing translation tests**

Create tests that construct a `SceneChunk` with absolute range `250..350` and a
`SceneChunkExtraction` with relative evidence `10..14`. Assert:

```python
analysis = translate_chunk_extraction(
    chunk=chunk,
    scene_sequence=3,
    extraction=extraction,
    known_entities=(),
    known_places=(),
)

assert analysis.chunk_id == "scene-01:r7:0001"
assert analysis.entities[0].status is CandidateStatus.PENDING
assert analysis.entities[0].evidence[0] == Evidence(
    chunk_id="scene-01:r7:0001",
    scene_id="scene-01",
    scene_revision=7,
    start_offset=260,
    end_offset=264,
    text=chunk.text[10:14],
)
assert analysis.relationship_events[0].subject_key == analysis.entities[0].candidate_id
assert analysis.location_events[0].place_key == analysis.places[0].candidate_id
```

Add focused cases proving:

```python
assert translate(first_input) == translate(first_input)
assert first_entity_id != first_place_id

bad_entity = replace(
    extraction.entities[0],
    evidence=(RelativeEvidence(10, 14, "wrong"),),
)
with pytest.raises(ExtractionTranslationError, match="evidence text"):
    translate_chunk_extraction(
        chunk,
        3,
        replace(extraction, entities=(bad_entity,)),
        (),
        (),
    )

with pytest.raises(ExtractionTranslationError, match="unknown entity reference"):
    bad_relationship = replace(extraction.relationship_events[0], subject_ref="missing")
    translate_chunk_extraction(
        chunk,
        3,
        replace(extraction, relationship_events=(bad_relationship,)),
        (),
        (),
    )

with pytest.raises(ExtractionTranslationError, match="ambiguous local reference"):
    duplicate = replace(extraction.entities[0], display_name="Duplicate")
    translate_chunk_extraction(
        chunk,
        3,
        replace(extraction, entities=(*extraction.entities, duplicate)),
        (),
        (),
    )
```

Also cover known stable entity/place references, wrong-kind references,
relative bounds outside the chunk, every relationship category, all three
location event types, and non-finite/out-of-range confidence.

- [ ] **Step 2: Run the tests and verify RED**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_translation.py -v
```

Expected: collection fails because `scene_analysis_types` and
`scene_analysis_translation` do not exist.

- [ ] **Step 3: Implement immutable extraction types**

Create `scene_analysis_types.py` with these public shapes:

```python
from dataclasses import dataclass
from typing import Literal

type RelationshipCategory = Literal[
    "romance", "family", "friendship", "professional", "antagonistic", "other"
]


@dataclass(frozen=True, slots=True)
class KnownIdentity:
    identity_key: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalyzeSceneRequest:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    text: str
    known_entities: tuple[KnownIdentity, ...] = ()
    known_places: tuple[KnownIdentity, ...] = ()


@dataclass(frozen=True, slots=True)
class RelativeEvidence:
    start_offset: int
    end_offset: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedEntity:
    local_ref: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...]
    evidence: tuple[RelativeEvidence, ...]


@dataclass(frozen=True, slots=True)
class ExtractedPlace:
    local_ref: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...]
    evidence: tuple[RelativeEvidence, ...]


@dataclass(frozen=True, slots=True)
class ExtractedRelationshipEvent:
    subject_ref: str
    object_ref: str
    category: RelationshipCategory
    description: str
    confidence: float
    evidence: tuple[RelativeEvidence, ...]


@dataclass(frozen=True, slots=True)
class ExtractedLocationEvent:
    character_ref: str
    place_ref: str
    event_type: str
    description: str
    confidence: float
    evidence: tuple[RelativeEvidence, ...]


@dataclass(frozen=True, slots=True)
class SceneChunkExtraction:
    summary: str
    entities: tuple[ExtractedEntity, ...] = ()
    places: tuple[ExtractedPlace, ...] = ()
    relationship_events: tuple[ExtractedRelationshipEvent, ...] = ()
    location_events: tuple[ExtractedLocationEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentUsage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class AgentInvocationResult:
    extraction: SceneChunkExtraction
    response_messages_json: bytes
    usage: AgentUsage
    provider_name: str
    model_name: str
```

Use `LocationEventType` instead of a free string in the final implementation
when constructing `ExtractedLocationEvent`; the plan shows `str` only to make
the dependency visible. The actual annotation must be
`event_type: LocationEventType` imported from `models.py`.

- [ ] **Step 4: Implement strict translation**

In `scene_analysis_translation.py`:

```python
class ExtractionTranslationError(ValueError):
    pass


def translate_chunk_extraction(
    chunk: SceneChunk,
    scene_sequence: int,
    extraction: SceneChunkExtraction,
    known_entities: tuple[KnownIdentity, ...],
    known_places: tuple[KnownIdentity, ...],
) -> ChunkAnalysis: ...
```

Implement the body with these exact rules:

1. Reject duplicate or blank local refs independently for entities and places.
2. Build local-ref maps to deterministic IDs and known-key sets; a local ref
   shadows nothing and any collision with a known key is ambiguous.
3. Validate evidence with
   `0 <= start < end <= len(chunk.text)` and exact source-slice equality.
4. Convert evidence to absolute `Evidence` using `chunk.start_offset`.
5. Create IDs as `sha256:<hex>` from a UTF-8 JSON array encoded with
   `ensure_ascii=False` and compact separators. Include schema, scene, revision,
   kind, normalized semantic fields, and sorted absolute evidence ranges.
6. Force `CandidateStatus.PENDING` on all four candidate types.
7. Resolve local refs to generated IDs and known refs to their stable keys;
   reject missing, ambiguous, and wrong-kind refs.
8. Require finite confidence in `0.0..1.0` before constructing events.
9. Populate all authoritative chunk metadata from `SceneChunk`, never from the
   extraction.

Construct every `ChunkAnalysis` field explicitly: schema constant, chunk ID,
ordinal, start, end, source text, scene ID, revision, normalized summary, and
the four translated candidate tuples. Let existing merge validation remain
authoritative for canonical chunk layout.

- [ ] **Step 5: Run focused and existing merge tests**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_translation.py -v
mise exec -- uv run pytest tests/narrative_memory/test_merge.py -q
mise exec -- uv run ruff check apps/narrative_memory/service/scene_analysis_types.py apps/narrative_memory/service/scene_analysis_translation.py tests/narrative_memory/test_scene_analysis_translation.py
```

Expected: all pass.

- [ ] **Step 6: Commit Task 1**

```sh
git add backend/apps/narrative_memory/service/scene_analysis_types.py backend/apps/narrative_memory/service/scene_analysis_translation.py backend/tests/narrative_memory/test_scene_analysis_translation.py
git commit -m "feat(backend): translate structured scene extraction"
```

---

### Task 2: Add versioned hot-reloaded prompt registry and renderer

**Files:**

- Create: `backend/apps/narrative_memory/service/scene_analysis_ports.py`
- Create: `backend/infrastructure/llm/prompt_registry.py`
- Create: `backend/prompts/README.md`
- Create: `backend/prompts/scene-analysis/system.md`
- Create: `backend/tests/narrative_memory/test_prompt_registry.py`

**Interfaces:**

- Produces `PromptDefinition` and `PromptRegistryPort.load(prompt_id) -> PromptDefinition`.
- Produces `FilePromptRegistry(root: Path)` and `render_scene_analysis_user_prompt(request, chunk) -> str`.
- Later tasks consume exact UTF-8 prompt bytes, metadata, SHA-256, body, and stable JSON user messages.

- [ ] **Step 1: Write failing prompt tests**

Use `tmp_path` to write one prompt file and assert:

```python
prompt = FilePromptRegistry(tmp_path).load("scene-analysis")
assert prompt.prompt_id == "scene-analysis"
assert prompt.version == 1
assert prompt.result_schema == "chunk-analysis-extraction-v1"
assert prompt.body == "Extract only asserted facts.\n"
assert prompt.content_hash == f"sha256:{sha256(raw_bytes).hexdigest()}"
assert prompt.raw_bytes == raw_bytes
```

Overwrite the file and call `load()` again to prove hot reload. Add separate
tests for invalid UTF-8, missing delimiter, missing/extra/duplicate metadata,
non-positive integer version, path traversal prompt ID, and an unsupported
result schema.

For rendering, deserialize the output with `json.loads()` and assert exact
keys and values for chunk metadata, text, and sorted known catalogs. Prove the
same typed input produces byte-for-byte equal text and contains no environment
variables.

- [ ] **Step 2: Run prompt tests and verify RED**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_prompt_registry.py -v
```

Expected: import failure for `prompt_registry` and `scene_analysis_ports`.

- [ ] **Step 3: Define prompt port and value**

Add to `scene_analysis_ports.py`:

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    prompt_id: str
    version: int
    result_schema: str
    content_hash: str
    raw_bytes: bytes
    body: str


class PromptRegistryPort(Protocol):
    def load(self, prompt_id: str) -> PromptDefinition: pass
```

- [ ] **Step 4: Implement file parsing and stable rendering**

Create `prompt_registry.py` with:

```python
SUPPORTED_RESULT_SCHEMAS = {"chunk-analysis-extraction-v1"}


class PromptDefinitionError(ValueError):
    pass


class FilePromptRegistry:
    def __init__(self, root: Path) -> None:
        self._root = root

    def load(self, prompt_id: str) -> PromptDefinition:
        if not prompt_id or any(part in {"", ".", ".."} for part in prompt_id.split("/")):
            raise PromptDefinitionError("invalid prompt ID")
        path = self._root / prompt_id / "system.md"
        raw = path.read_bytes()
        return _parse_prompt_definition(prompt_id, raw)
```

Parse only `prompt_id`, `version`, and `result_schema` between the first two
standalone `---` lines. Reject every other key and duplicate. Decode exact bytes
as UTF-8, require metadata prompt ID to equal the requested path ID, require a
positive integer version, validate the schema constant, preserve the body after
the closing delimiter, and hash complete raw bytes.

Implement rendering with `json.dumps(envelope, ensure_ascii=False,
sort_keys=True, separators=(",", ":"))`. Sort known identities by
`identity_key`; retain the chunk text exactly.

- [ ] **Step 5: Add the production prompt files**

`backend/prompts/scene-analysis/system.md` must use version `1` and instruct the
model to return only asserted characters, places, temporal relationship events,
and physical location events; use relative evidence offsets; use controlled
enums; avoid IDs/status; and never infer physical presence from a mention.

`backend/prompts/README.md` must document:

- `NARRATIVE_LLM_MODEL` and explicit `mock`;
- the stable JSON user-message fields;
- `chunk-analysis-extraction-v1`;
- edit-without-restart behavior;
- the mandatory version increment when exact bytes change;
- the command `mise exec -- uv run pytest tests/narrative_memory/test_prompt_registry.py -v`.

- [ ] **Step 6: Run focused tests and commit Task 2**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_prompt_registry.py -v
mise exec -- uv run ruff check apps/narrative_memory/service/scene_analysis_ports.py infrastructure/llm/prompt_registry.py tests/narrative_memory/test_prompt_registry.py
git add backend/apps/narrative_memory/service/scene_analysis_ports.py backend/infrastructure/llm/prompt_registry.py backend/prompts backend/tests/narrative_memory/test_prompt_registry.py
git commit -m "feat(backend): load versioned scene prompts"
```

Expected: tests and Ruff pass; commit succeeds.

---

### Task 3: Build append-only SQLite agent audit storage

**Files:**

- Create: `backend/apps/narrative_memory/repository/analysis_audit.py`
- Create: `backend/infrastructure/audit/__init__.py`
- Create: `backend/infrastructure/audit/sqlite_agent_audit.py`
- Create: `backend/tests/narrative_memory/test_sqlite_agent_audit.py`

**Interfaces:**

- Produces frozen event types `RunStarted`, `RunSucceeded`, `RunFailed`, `AttemptStarted`, `AttemptSucceeded`, `AttemptFailed` and `AgentAuditPort`.
- Produces `SQLiteAgentAudit(path: Path)` with `initialize()`, `register_prompt()`, `append_run_event()`, and `append_attempt_event()`.
- The scene service uses only the port and event types, not SQLite.

- [ ] **Step 1: Write failing audit tests**

Tests must prove:

```python
audit = SQLiteAgentAudit(tmp_path / "private" / "agent-audit.sqlite3")
audit.initialize()
assert stat.S_IMODE(audit_path.stat().st_mode) == 0o600

audit.register_prompt(prompt)
audit.register_prompt(prompt)  # idempotent exact bytes

with pytest.raises(PromptVersionConflict):
    audit.register_prompt(replace(prompt, content_hash="sha256:different"))
```

Append started/succeeded and started/failed events, query SQLite directly, and
assert insertion order and exact prompt, user message, response bytes,
validated JSON, usage JSON, latency, and errors. Assert there are no `UPDATE`
or mutable status columns in the schema. Simulate an invalid event payload and
transaction error to prove no partial row is committed.

- [ ] **Step 2: Run audit tests and verify RED**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_sqlite_agent_audit.py -v
```

Expected: import failure for audit port/adapter.

- [ ] **Step 3: Define typed audit events and port**

In `analysis_audit.py`, define separate frozen dataclasses rather than optional
field bags. Required shapes:

```python
type RunEvent = RunStarted | RunSucceeded | RunFailed
type AttemptEvent = AttemptStarted | AttemptSucceeded | AttemptFailed


class AgentAuditPort(Protocol):
    def register_prompt(self, prompt: PromptDefinition) -> None: pass
    def append_run_event(self, event: RunEvent) -> None: pass
    def append_attempt_event(self, event: AttemptEvent) -> None: pass
```

`RunStarted` contains run/project/scene/revision/sequence/model/prompt/time.
`RunSucceeded` contains run/time and canonical scene snapshot JSON bytes.
`RunFailed` contains run/time, error type, and error message.
`AttemptStarted` contains run/chunk/attempt/time and exact system/user messages.
`AttemptSucceeded` contains run/chunk/attempt/time/latency, response message
bytes, canonical validated extraction JSON bytes, provider/model, and
`AgentUsage`. `AttemptFailed` contains the same identity/time/latency plus error
type/message and response bytes when available.

- [ ] **Step 4: Implement SQLite append-only adapter**

Create tables:

```sql
CREATE TABLE prompt_definitions (
  prompt_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  result_schema TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  raw_bytes BLOB NOT NULL,
  PRIMARY KEY (prompt_id, version)
);
CREATE TABLE run_events (
  event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  payload_json BLOB NOT NULL
);
CREATE TABLE attempt_events (
  event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  chunk_id TEXT NOT NULL,
  attempt_number INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  payload_json BLOB NOT NULL
);
```

Create the database with
`os.open(path, os.O_CREAT | os.O_RDWR, 0o600)` and enforce `chmod(0o600)` like
the existing snapshot repository. Serialize event payloads as canonical UTF-8
JSON bytes with Korean preserved and bytes fields encoded as decoded UTF-8 JSON
strings, not base64. Use one transaction per public method; rollback and rethrow
on failure. `register_prompt()` accepts an exact existing row and raises
`PromptVersionConflict` for any differing schema/hash/raw bytes.

- [ ] **Step 5: Run audit and repository regressions**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_sqlite_agent_audit.py -v
mise exec -- uv run pytest tests/narrative_memory/test_sqlite_snapshot_repository.py -q
mise exec -- uv run ruff check apps/narrative_memory/repository/analysis_audit.py infrastructure/audit tests/narrative_memory/test_sqlite_agent_audit.py
```

Expected: all pass.

- [ ] **Step 6: Commit Task 3**

```sh
git add backend/apps/narrative_memory/repository/analysis_audit.py backend/infrastructure/audit backend/tests/narrative_memory/test_sqlite_agent_audit.py
git commit -m "feat(backend): audit scene analysis attempts"
```

---

### Task 4: Implement strict Pydantic AI and scripted mock adapters

**Files:**

- Create: `backend/infrastructure/llm/scene_analysis_schemas.py`
- Create: `backend/infrastructure/llm/pydantic_ai_scene_analysis.py`
- Create: `backend/infrastructure/llm/scripted_scene_analysis.py`
- Create: `backend/infrastructure/llm/scene_analysis_factory.py`
- Create: `backend/tests/narrative_memory/test_scene_analysis_agents.py`
- Create: `backend/tests/narrative_memory/test_scene_analysis_factory.py`

**Interfaces:**

- Extends `scene_analysis_ports.py` with `SceneAnalysisAgentPort.analyze(call) -> AgentInvocationResult` and frozen `SceneAnalysisCall`.
- Produces `PydanticAISceneAnalysisAgent`, `ScriptedSceneAnalysisAgent`, `ModelConfigurationError`, and `create_scene_analysis_agent(model_name=None, environ=os.environ)`.

- [ ] **Step 1: Write failing strict-schema and mock tests**

Pydantic schema tests must reject unknown fields, invalid relationship/location
enums, `nan`, confidence outside `0..1`, and invalid evidence bounds. A valid
schema must convert exactly to `SceneChunkExtraction`.

Scripted mock tests:

```python
agent = ScriptedSceneAnalysisAgent(
    scripts={"scene-01:r1:0000": [first_result, ProviderCallError("retry"), second_result]}
)
assert (await agent.analyze(call)).extraction == first_result
assert len(agent.calls) == 1

empty = await ScriptedSceneAnalysisAgent().analyze(call)
assert empty.extraction == SceneChunkExtraction(summary="")
```

Use a Pydantic AI local custom/test model to assert the production adapter
returns validated extraction, `all_messages_json()` bytes, usage counters, and
model identity without network access.

- [ ] **Step 2: Run agent tests and verify RED**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_agents.py -v
```

Expected: imports fail for the four new infrastructure modules.

- [ ] **Step 3: Implement strict Pydantic output models**

Use one base class:

```python
class StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

Define `EvidenceOutput`, `EntityOutput`, `PlaceOutput`,
`RelationshipEventOutput`, `LocationEventOutput`, and `ChunkExtractionOutput`.
Use `Field(ge=0)`, `Field(gt=0)`, and `Field(ge=0.0, le=1.0,
allow_inf_nan=False)` as appropriate. Add a model validator to evidence for
`end_offset > start_offset`; chunk-length and source-text checks remain in the
provider-independent translator. Convert lists to tuples and enums into the
Task 1 dataclasses in one explicit `to_domain()` method.

- [ ] **Step 4: Implement the two agent adapters**

Extend `scene_analysis_ports.py`:

```python
@dataclass(frozen=True, slots=True)
class SceneAnalysisCall:
    chunk_id: str
    system_prompt: str
    user_prompt: str


class SceneAnalysisAgentPort(Protocol):
    async def analyze(self, call: SceneAnalysisCall) -> AgentInvocationResult: pass
```

`PydanticAISceneAnalysisAgent.analyze()` creates or uses an injected
`Agent[None, ChunkExtractionOutput]` configured with `retries=0`; call
`agent.run(call.user_prompt, instructions=call.system_prompt)`. Return
`result.output.to_domain()`, `result.all_messages_json()`, and usage copied from
`result.usage.requests/input_tokens/output_tokens`. Convert provider exceptions
and Pydantic AI structured-output exhaustion into a typed `ProviderCallError`
without logging message bodies.

`ScriptedSceneAnalysisAgent` stores an immutable input script copied into
per-chunk deques, appends every call to `calls`, pops the next extraction or
exception, and otherwise returns an empty extraction with canonical empty
response messages `b"[]"` and zero usage.

- [ ] **Step 5: Write failing factory tests**

```python
with pytest.raises(ModelConfigurationError, match="NARRATIVE_LLM_MODEL"):
    create_scene_analysis_agent(environ={})
with pytest.raises(ModelConfigurationError):
    create_scene_analysis_agent(environ={"NARRATIVE_LLM_MODEL": "   "})
assert isinstance(create_scene_analysis_agent(environ={"NARRATIVE_LLM_MODEL": "mock"}), ScriptedSceneAnalysisAgent)
assert isinstance(create_scene_analysis_agent(model_name="openai:example", environ={}), PydanticAISceneAnalysisAgent)
```

Patch the Pydantic AI `Agent` constructor in the final case so no provider
credential or network is needed; assert the exact string and
`defer_model_check=True` are forwarded.

- [ ] **Step 6: Implement lazy model factory and run checks**

The factory resolves explicit `model_name` first, then
`environ.get("NARRATIVE_LLM_MODEL")`, strips whitespace, rejects absence, uses
the exact sentinel `mock`, and otherwise constructs the production adapter.
It must not be imported or called by `main.py`.

```sh
mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_agents.py tests/narrative_memory/test_scene_analysis_factory.py -v
mise exec -- uv run ruff check infrastructure/llm tests/narrative_memory/test_scene_analysis_agents.py tests/narrative_memory/test_scene_analysis_factory.py
```

Expected: all pass and no network access occurs.

- [ ] **Step 7: Commit Task 4**

```sh
git add backend/apps/narrative_memory/service/scene_analysis_ports.py backend/infrastructure/llm backend/tests/narrative_memory/test_scene_analysis_agents.py backend/tests/narrative_memory/test_scene_analysis_factory.py
git commit -m "feat(backend): add structured scene analysis agents"
```

---

### Task 5: Orchestrate serial audited chunk analysis

**Files:**

- Create: `backend/apps/narrative_memory/service/scene_analysis.py`
- Create: `backend/tests/narrative_memory/test_scene_analysis_service.py`
- Modify: `backend/apps/narrative_memory/repository/analysis_audit.py`
- Modify: `backend/apps/narrative_memory/service/scene_analysis_ports.py`

**Interfaces:**

- Produces `SceneAnalysisService(agent, prompt_registry, audit, run_id_factory, clock, monotonic)` and async `analyze_scene(request) -> SceneRelationshipSnapshot`.
- Produces typed `SceneAnalysisError`, `SceneAnalysisProviderError`, and `SceneAnalysisAuditError`.
- Consumes all prior tasks and existing chunk/merge/codec functions.

- [ ] **Step 1: Write failing empty and successful service tests**

Use fixed clock/run ID, in-memory recording audit, file/stub prompt registry, and
scripted mock. Assert empty text performs zero agent calls, writes run
started/succeeded, and returns an empty valid scene snapshot.

For a 350-character scene, script two extractions and assert:

```python
result = await service.analyze_scene(request)
assert [call.chunk_id for call in agent.calls] == [
    "scene-01:r1:0000",
    "scene-01:r1:0001",
]
assert result.scene_id == "scene-01"
assert result.scene_revision == 1
assert result.scene_sequence == 4
assert len(result.entities) == 1  # overlap deduplicated by existing merge
assert audit.event_types == [
    "run_started",
    "attempt_started", "attempt_succeeded",
    "attempt_started", "attempt_succeeded",
    "run_succeeded",
]
```

Assert each `AttemptStarted` contains the exact loaded system body and stable
rendered user JSON, while each success contains canonical extraction JSON and
serialized response messages.

- [ ] **Step 2: Write failing retry and failure tests**

Cover:

- provider failure then success produces exactly two attempts;
- two provider failures append failed attempt/run events and raise;
- a deterministic `ExtractionTranslationError` is not retried;
- no later chunk runs after terminal failure;
- `audit.register_prompt`, run-start, or attempt-start failure prevents the
  associated model call;
- attempt-terminal or run-terminal audit failure is surfaced and no snapshot is
  claimed;
- prompt load and prompt-version conflict occur before model calls;
- cancellation is appended when the audit is available and re-raised.

- [ ] **Step 3: Run service tests and verify RED**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_service.py -v
```

Expected: import failure because `scene_analysis.py` does not exist.

- [ ] **Step 4: Implement orchestration in strict order**

Constructor dependencies are explicit and typed. `analyze_scene()` must:

1. Validate nonblank project/scene IDs, nonnegative revision/sequence, and known
   identity key uniqueness before loading a prompt.
2. Load `scene-analysis`; resolve the agent's exposed provider/model identity;
   create a run ID and append the registered prompt plus `RunStarted`.
3. Call `chunk_scene()` once.
4. For each chunk in returned numeric order, render the user prompt, append
   `AttemptStarted`, call the agent, append success/failure, and translate.
5. Retry only `ProviderCallError`, with attempt numbers `1` and `2` and no sleep.
6. Serialize validated extraction through a provider-independent canonical JSON
   helper in `scene_analysis_types.py`; do not import Pydantic.
7. Merge all successful analyses with existing `merge_chunk_analyses()`.
8. Serialize the scene snapshot by an explicit canonical helper added beside
   the service (do not misuse the project snapshot codec), append
   `RunSucceeded`, and return.
9. On terminal expected errors, append `RunFailed` and raise a typed service
   error chained from the cause. Never include prompt/manuscript/response in the
   exception message.

Use `clock() -> datetime`, `monotonic() -> float`, and `run_id_factory() -> str`
for deterministic audit values. The service must not read environment variables
or acquire global clients/repositories.

- [ ] **Step 5: Run service plus Narrative Memory tests**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_service.py -v
mise exec -- uv run pytest tests/narrative_memory -q
mise exec -- uv run ruff check apps/narrative_memory tests/narrative_memory/test_scene_analysis_service.py
```

Expected: all pass.

- [ ] **Step 6: Commit Task 5**

```sh
git add backend/apps/narrative_memory backend/tests/narrative_memory/test_scene_analysis_service.py
git commit -m "feat(backend): analyze narrative scenes by LLM chunk"
```

---

### Task 6: Synchronize contracts and verify the backend slice

**Files:**

- Modify: `docs/domains/narrative-memory.md`
- Modify: `backend/docs/backend-coding-rules.md`
- Modify: `backend/README.md`
- Modify: `backend/tests/narrative_memory/test_scene_analysis_service.py`

**Interfaces:**

- Documents the implemented domain use case, provider/prompt/audit engineering rules, configuration, package structure, exclusions, and verification.
- Produces one public end-to-end test from request through mock, audit, translation, existing merge, and returned snapshot.

- [ ] **Step 1: Add a failing public end-to-end test**

Construct real `FilePromptRegistry`, `SQLiteAgentAudit`, and
`ScriptedSceneAnalysisAgent`; call `SceneAnalysisService.analyze_scene()` on a
350-character Korean scene with scripted entity/place/relationship/location
results. Assert:

- two calls in ordinal order;
- absolute evidence in the returned scene snapshot;
- all statuses pending;
- overlap deduplication;
- exact prompt registration and attempt event counts in SQLite;
- exact validated JSON and response messages persisted;
- no project snapshot row or other domain file/state is created.

Run the single test before editing docs:

```sh
mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_service.py::test_analyze_scene_with_mock_and_sqlite_audit_end_to_end -v
```

Expected: FAIL until any remaining composition or audit integration gap is
completed; if it passes immediately, retain it as the public acceptance test.

- [ ] **Step 2: Complete only the integration needed by the test**

Wire the existing public constructors directly in the test. If a tiny
composition function is necessary, add it to
`infrastructure/llm/scene_analysis_factory.py`; it must accept explicit prompt
root and audit path and must not touch FastAPI or globals beyond the model
environment lookup already approved.

- [ ] **Step 3: Synchronize Narrative Memory domain contract**

Add the explicit scene-analysis use case and invariants:

- caller supplies immutable scene text and optional known identity catalogs;
- canonical chunks are analyzed serially;
- structured output cannot contain status or durable IDs;
- backend assigns pending status, deterministic IDs, and absolute verified
  evidence;
- terminal chunk failure returns no scene snapshot;
- provider, prompt, and audit mechanics remain infrastructure and no other
  domain is read or mutated.

Do not add background-save behavior, approval semantics, or API operations.

- [ ] **Step 4: Document reusable backend engineering rules**

Update `backend/docs/backend-coding-rules.md` with a focused "LLM Agent Audit"
section requiring:

- provider clients behind typed ports;
- model selection only at composition boundaries;
- versioned hot-loaded prompt files under `backend/prompts`;
- pre-call audit persistence and no sensitive content in console logs;
- structured validation before domain translation;
- scripted network-free test adapters.

Update `backend/README.md` structure for `prompts/`, `infrastructure/llm/`, and
`infrastructure/audit/`, and document `NARRATIVE_LLM_MODEL=mock` plus the focused
test command. Do not imply automatic manuscript-save execution.

- [ ] **Step 5: Run focused and full verification**

From `backend/`:

```sh
mise exec -- uv run pytest tests/narrative_memory -v
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

From repository root:

```sh
git diff --check
rg -n "NARRATIVE_LLM_MODEL|scene-analysis|pending|audit|다른 도메인" backend/README.md backend/docs/backend-coding-rules.md docs/domains/narrative-memory.md backend/prompts
git diff --name-only HEAD~1..HEAD
```

Expected: all tests pass, Ruff is clean, diff check is silent, and no path from
another domain, frontend, OpenAPI, `main.py`, jobs, Neo4j, or Cypher appears in
the feature diff.

- [ ] **Step 6: Commit Task 6**

```sh
git add backend/README.md backend/docs/backend-coding-rules.md backend/tests/narrative_memory/test_scene_analysis_service.py docs/domains/narrative-memory.md
git commit -m "docs(backend): document audited scene analysis"
```

---

## Review and Completion Gates

1. Stop implementation editing and dispatch the repository `backend-review`
   agent with base `0677d75`, final head, the focused design/spec, this plan,
   affected entry point `SceneAnalysisService.analyze_scene`, owned paths,
   acceptance criteria, and verification evidence.
2. Triage every finding. Resolve every accepted finding; mandatory re-review
   applies to High/Important findings and behavior-changing repairs.
3. Main agent reviews the complete diff, confirms only Narrative Memory plus
   approved infrastructure/prompt/docs paths changed, and compares the domain
   contract with implementation behavior.
4. Main agent freshly runs full backend pytest, Ruff lint, Ruff format, and
   `git diff --check` before any completion claim.
5. No OpenAPI or frontend review is required because this slice exposes no
   consumer-facing operation and changes no UI.
