# Narrative Memory JSON Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the provider-independent Narrative Memory core that chunks scenes into 300-character/50-overlap units, merges validated analysis data into immutable scene and project JSON snapshots, and persists versioned snapshots safely in SQLite.

**Architecture:** Pure frozen dataclasses and deterministic service functions own chunking and merge behavior under `apps/narrative_memory/service/`. A repository port hides SQLite, while a canonical JSON codec makes the stored bytes stable and suitable for audit download or a future Neo4j projector. This is the first independently testable subsystem from the approved design; separate follow-on plans cover Pydantic AI execution and prompts, background jobs and audit runs, approval/validation operations, and the internal HTML viewer.

**Tech Stack:** Python 3.13, standard-library dataclasses/json/hashlib/sqlite3, pytest, Ruff

## Global Constraints

- Preserve Python compatibility at `>=3.13,<3.14`.
- Use at most 300 Python Unicode characters per chunk, with 50 characters of overlap and a stride of 250.
- Treat `[start_offset, end_offset)` as absolute scene offsets.
- Store only validated domain objects; raw LLM responses are outside this plan.
- Keep service code independent of FastAPI, Pydantic, Pydantic AI, SQLite, and provider SDKs.
- Create immutable snapshot versions; never rewrite an older JSON snapshot.
- Use the project snapshot JSON as the durable derived-memory result.
- Do not add Neo4j, Cypher, embeddings, a model provider, an API route, or a background queue.
- Do not auto-approve extracted characters, places, relationships, or location events.
- Update domain documentation in the same change as the new domain behavior.
- Preserve unrelated user changes.

---

## Planned File Structure

```text
backend/
├── apps/
│   └── narrative_memory/
│       ├── __init__.py
│       ├── repository/
│       │   ├── __init__.py
│       │   ├── snapshot_repository.py
│       │   └── sqlite_snapshot_repository.py
│       └── service/
│           ├── __init__.py
│           ├── chunking.py
│           ├── merge.py
│           ├── models.py
│           └── snapshot_codec.py
├── tests/
│   └── narrative_memory/
│       ├── test_chunking.py
│       ├── test_merge.py
│       ├── test_snapshot_codec.py
│       └── test_sqlite_snapshot_repository.py
docs/domains/
├── README.md
├── narrative-memory.md
├── story-bible.md
└── writing-assistant.md
```

`models.py` defines vocabulary and immutable values. `chunking.py` performs
only source segmentation. `merge.py` contains pure scene/project merge rules.
`snapshot_codec.py` owns canonical JSON bytes. The repository protocol owns
the consumer-facing persistence contract; its SQLite implementation owns SQL,
transactions, file permissions, and optimistic concurrency.

---

### Task 1: Establish Narrative Memory vocabulary and contracts

**Files:**

- Create: `backend/apps/narrative_memory/__init__.py`
- Create: `backend/apps/narrative_memory/service/__init__.py`
- Create: `backend/apps/narrative_memory/service/models.py`
- Create: `backend/tests/narrative_memory/test_snapshot_codec.py`
- Create: `docs/domains/narrative-memory.md`
- Modify: `docs/domains/story-bible.md`
- Modify: `docs/domains/writing-assistant.md`
- Modify: `docs/domains/README.md`

**Interfaces:**

- Produces: `CandidateStatus`, `LocationEventType`, `Evidence`, `EntityCandidate`, `PlaceCandidate`, `RelationshipEventCandidate`, `LocationEventCandidate`, `ChunkAnalysis`, `SceneRelationshipSnapshot`, and `ProjectRelationshipSnapshot`.
- All collection fields are tuples so snapshots cannot be mutated after construction.
- `ProjectRelationshipSnapshot.empty(project_id: str)` returns version `0` with empty collections.

- [ ] **Step 1: Write the failing model and immutability test**

Create `backend/tests/narrative_memory/test_snapshot_codec.py` with:

```python
from dataclasses import FrozenInstanceError

import pytest

from apps.narrative_memory.service.models import (
    Evidence,
    ProjectRelationshipSnapshot,
)


def test_empty_project_snapshot_is_version_zero() -> None:
    snapshot = ProjectRelationshipSnapshot.empty("project-01")

    assert snapshot.project_id == "project-01"
    assert snapshot.snapshot_version == 0
    assert snapshot.relationship_events == ()
    assert snapshot.location_events == ()


def test_evidence_is_immutable() -> None:
    evidence = Evidence(
        chunk_id="scene-01:r1:0000",
        start_offset=0,
        end_offset=3,
        text="서연은",
    )

    with pytest.raises(FrozenInstanceError):
        evidence.text = "민준은"  # type: ignore[misc]
```

- [ ] **Step 2: Run the test and confirm the missing model failure**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/narrative_memory/test_snapshot_codec.py -v
```

Expected: collection fails with `ModuleNotFoundError` for
`apps.narrative_memory`.

- [ ] **Step 3: Implement the immutable model vocabulary**

Create package markers and implement `models.py` with frozen, slotted
dataclasses. Use these exact enum values and fields:

```python
from dataclasses import dataclass
from enum import StrEnum


class CandidateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class LocationEventType(StrEnum):
    ARRIVED = "arrived"
    PRESENT = "present"
    DEPARTED = "departed"


@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id: str
    start_offset: int
    end_offset: int
    text: str


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    candidate_id: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...]
    status: CandidateStatus
    scene_id: str
    scene_revision: int
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class PlaceCandidate:
    candidate_id: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...]
    status: CandidateStatus
    scene_id: str
    scene_revision: int
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class RelationshipEventCandidate:
    event_id: str
    subject_key: str
    object_key: str
    category: str
    description: str
    status: CandidateStatus
    scene_id: str
    scene_revision: int
    scene_sequence: int
    confidence: float
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class LocationEventCandidate:
    event_id: str
    character_key: str
    place_key: str
    event_type: LocationEventType
    description: str
    status: CandidateStatus
    scene_id: str
    scene_revision: int
    scene_sequence: int
    confidence: float
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class ChunkAnalysis:
    chunk_id: str
    scene_id: str
    scene_revision: int
    summary: str
    entities: tuple[EntityCandidate, ...]
    places: tuple[PlaceCandidate, ...]
    relationship_events: tuple[RelationshipEventCandidate, ...]
    location_events: tuple[LocationEventCandidate, ...]


@dataclass(frozen=True, slots=True)
class SceneRelationshipSnapshot:
    scene_id: str
    scene_revision: int
    scene_sequence: int
    schema_version: str
    summary: str
    entities: tuple[EntityCandidate, ...]
    places: tuple[PlaceCandidate, ...]
    relationship_events: tuple[RelationshipEventCandidate, ...]
    location_events: tuple[LocationEventCandidate, ...]


@dataclass(frozen=True, slots=True)
class ProjectRelationshipSnapshot:
    project_id: str
    snapshot_version: int
    schema_version: str
    active_scene_revisions: tuple[tuple[str, int], ...]
    entities: tuple[EntityCandidate, ...]
    places: tuple[PlaceCandidate, ...]
    relationship_events: tuple[RelationshipEventCandidate, ...]
    location_events: tuple[LocationEventCandidate, ...]

    @classmethod
    def empty(cls, project_id: str) -> "ProjectRelationshipSnapshot":
        return cls(
            project_id=project_id,
            snapshot_version=0,
            schema_version="project-relationship-snapshot-v1",
            active_scene_revisions=(),
            entities=(),
            places=(),
            relationship_events=(),
            location_events=(),
        )
```

- [ ] **Step 4: Run the focused tests**

Run:

```sh
mise exec -- uv run pytest tests/narrative_memory/test_snapshot_codec.py -v
```

Expected: two tests pass.

- [ ] **Step 5: Synchronize domain contracts**

Create `docs/domains/narrative-memory.md` with purpose, ubiquitous language,
models, invariants, use cases, inputs/outputs, and exclusions matching these
exact rules:

```text
Narrative Memory owns rebuildable scene summaries, evidence, extraction
candidates, analysis revisions, and versioned JSON snapshots. It never treats a
candidate as true, never mutates Manuscript, and never mutates Story Bible
directly. Reanalysis replaces the changed scene's pending candidates; confirmed
facts whose evidence disappears become needs_review. Relationships and
locations are temporal scene events.
```

Update `story-bible.md` so confirmed relationship and location events are Story
Bible facts and unresolved/`needs_review` candidates are not. Update
`writing-assistant.md` so consistency diagnostics may consume confirmed Story
Bible events and bounded Narrative Memory summaries but must cite confirmed
fact IDs. Update `README.md` to add Narrative Memory to the domain table and
context map as derived from Manuscript and read by the explicit Writing
Assistant validation workflow.

- [ ] **Step 6: Verify documentation and domain alignment**

Run from the repository root:

```sh
rg -n "Narrative Memory|needs_review|관계 사건|장소 사건" docs/domains
git diff --check -- docs/domains backend/apps/narrative_memory backend/tests/narrative_memory
```

Expected: all four domain documents contain the synchronized terms and
`git diff --check` is silent.

- [ ] **Step 7: Commit the vocabulary and contracts**

```sh
git add backend/apps/narrative_memory backend/tests/narrative_memory docs/domains
git commit -m "feat(backend): define narrative memory domain"
```

---

### Task 2: Implement deterministic 300/50 scene chunking

**Files:**

- Create: `backend/apps/narrative_memory/service/chunking.py`
- Create: `backend/tests/narrative_memory/test_chunking.py`

**Interfaces:**

- Produces: `SceneChunk` and `chunk_scene(scene_id: str, manuscript_revision: int, text: str) -> tuple[SceneChunk, ...]`.
- `SceneChunk.start_offset` is inclusive and `end_offset` is exclusive.
- `content_hash` is `sha256:` followed by the UTF-8 text digest.

- [ ] **Step 1: Write boundary, overlap, Unicode, and empty-input tests**

Create `test_chunking.py`:

```python
from apps.narrative_memory.service.chunking import chunk_scene


def test_chunk_scene_uses_300_characters_with_50_overlap() -> None:
    text = "가" * 250 + "나" * 100

    chunks = chunk_scene("scene-01", 7, text)

    assert [(chunk.start_offset, chunk.end_offset) for chunk in chunks] == [
        (0, 300),
        (250, 350),
    ]
    assert chunks[0].text[-50:] == chunks[1].text[:50]
    assert chunks[0].chunk_id == "scene-01:r7:0000"
    assert chunks[1].chunk_id == "scene-01:r7:0001"


def test_chunk_scene_counts_unicode_characters_not_utf8_bytes() -> None:
    chunks = chunk_scene("scene-01", 1, "서연" * 150)

    assert len(chunks) == 1
    assert chunks[0].end_offset == 300


def test_chunk_scene_returns_no_chunks_for_empty_text() -> None:
    assert chunk_scene("scene-01", 1, "") == ()
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run:

```sh
mise exec -- uv run pytest tests/narrative_memory/test_chunking.py -v
```

Expected: collection fails because `chunking.py` does not exist.

- [ ] **Step 3: Implement the chunker**

Create `chunking.py`:

```python
from dataclasses import dataclass
from hashlib import sha256

MAX_CHUNK_CHARACTERS = 300
CHUNK_OVERLAP_CHARACTERS = 50
CHUNK_STRIDE_CHARACTERS = MAX_CHUNK_CHARACTERS - CHUNK_OVERLAP_CHARACTERS


@dataclass(frozen=True, slots=True)
class SceneChunk:
    chunk_id: str
    scene_id: str
    manuscript_revision: int
    ordinal: int
    start_offset: int
    end_offset: int
    content_hash: str
    text: str


def chunk_scene(
    scene_id: str,
    manuscript_revision: int,
    text: str,
) -> tuple[SceneChunk, ...]:
    chunks: list[SceneChunk] = []
    for ordinal, start in enumerate(range(0, len(text), CHUNK_STRIDE_CHARACTERS)):
        end = min(start + MAX_CHUNK_CHARACTERS, len(text))
        chunk_text = text[start:end]
        chunks.append(
            SceneChunk(
                chunk_id=f"{scene_id}:r{manuscript_revision}:{ordinal:04d}",
                scene_id=scene_id,
                manuscript_revision=manuscript_revision,
                ordinal=ordinal,
                start_offset=start,
                end_offset=end,
                content_hash=f"sha256:{sha256(chunk_text.encode('utf-8')).hexdigest()}",
                text=chunk_text,
            )
        )
        if end == len(text):
            break
    return tuple(chunks)
```

- [ ] **Step 4: Run focused tests and lint**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_chunking.py -v
mise exec -- uv run ruff check apps/narrative_memory/service/chunking.py tests/narrative_memory/test_chunking.py
```

Expected: three tests pass and Ruff is silent.

- [ ] **Step 5: Commit the chunker**

```sh
git add backend/apps/narrative_memory/service/chunking.py backend/tests/narrative_memory/test_chunking.py
git commit -m "feat(backend): chunk narrative scenes"
```

---

### Task 3: Build canonical JSON encoding and strict decoding

**Files:**

- Create: `backend/apps/narrative_memory/service/snapshot_codec.py`
- Modify: `backend/tests/narrative_memory/test_snapshot_codec.py`

**Interfaces:**

- Produces: `encode_project_snapshot(snapshot) -> bytes` and `decode_project_snapshot(payload: bytes) -> ProjectRelationshipSnapshot`.
- JSON is UTF-8, sorted by key, indented by two spaces, ends with one newline, and preserves Korean text.
- Decoding rejects missing fields, unknown fields, invalid enum values, and a payload that is not a JSON object.

- [ ] **Step 1: Add round-trip, stable-byte, and unknown-field tests**

Append tests that construct one pending relationship event and assert:

```python
import json

import pytest

from apps.narrative_memory.service.snapshot_codec import (
    SnapshotDecodeError,
    decode_project_snapshot,
    encode_project_snapshot,
)


def test_project_snapshot_codec_is_stable_and_round_trips() -> None:
    snapshot = ProjectRelationshipSnapshot.empty("project-01")
    payload = encode_project_snapshot(snapshot)

    assert payload.endswith(b"\n")
    assert "project-01" in payload.decode("utf-8")
    assert decode_project_snapshot(payload) == snapshot
    assert encode_project_snapshot(decode_project_snapshot(payload)) == payload


def test_project_snapshot_decoder_rejects_unknown_fields() -> None:
    data = json.loads(
        encode_project_snapshot(ProjectRelationshipSnapshot.empty("project-01"))
    )
    data["unexpected"] = True

    with pytest.raises(SnapshotDecodeError, match="unexpected"):
        decode_project_snapshot(json.dumps(data).encode("utf-8"))
```

- [ ] **Step 2: Run the codec tests and confirm import failure**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_snapshot_codec.py -v
```

Expected: collection fails because `snapshot_codec.py` does not exist.

- [ ] **Step 3: Implement an explicit codec**

Implement `snapshot_codec.py` with these exact public names:

```python
import json
from dataclasses import asdict
from typing import Any

from apps.narrative_memory.service.models import (
    CandidateStatus,
    EntityCandidate,
    Evidence,
    LocationEventCandidate,
    LocationEventType,
    PlaceCandidate,
    ProjectRelationshipSnapshot,
    RelationshipEventCandidate,
)


class SnapshotDecodeError(ValueError):
    pass


def encode_project_snapshot(snapshot: ProjectRelationshipSnapshot) -> bytes:
    data = asdict(snapshot)
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")


def decode_project_snapshot(payload: bytes) -> ProjectRelationshipSnapshot:
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SnapshotDecodeError("snapshot is not valid UTF-8 JSON") from error
    if not isinstance(data, dict):
        raise SnapshotDecodeError("snapshot root must be an object")
    return _project_from_dict(data)


def _project_from_dict(data: dict[str, Any]) -> ProjectRelationshipSnapshot:
    allowed = {
        "project_id",
        "snapshot_version",
        "schema_version",
        "active_scene_revisions",
        "entities",
        "places",
        "relationship_events",
        "location_events",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise SnapshotDecodeError(f"unexpected fields: {', '.join(unknown)}")
    try:
        return _decode_nested_project_fields(data)
    except (IndexError, KeyError, TypeError, ValueError) as error:
        raise SnapshotDecodeError(f"invalid project snapshot: {error}") from error


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _require_keys(
    data: dict[str, Any],
    allowed: set[str],
    required: set[str],
    label: str,
) -> None:
    unknown = sorted(set(data) - allowed)
    missing = sorted(required - set(data))
    if unknown:
        raise ValueError(f"{label} has unexpected fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(missing)}")


def _items(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    return value


def _evidence(value: Any) -> Evidence:
    data = _require_object(value, "evidence")
    keys = {"chunk_id", "start_offset", "end_offset", "text"}
    _require_keys(data, keys, keys, "evidence")
    return Evidence(
        chunk_id=str(data["chunk_id"]),
        start_offset=int(data["start_offset"]),
        end_offset=int(data["end_offset"]),
        text=str(data["text"]),
    )


def _entity(value: Any) -> EntityCandidate:
    data = _require_object(value, "entity")
    keys = {
        "candidate_id", "normalized_name", "display_name", "aliases", "status",
        "scene_id", "scene_revision", "evidence",
    }
    _require_keys(data, keys, keys, "entity")
    return EntityCandidate(
        candidate_id=str(data["candidate_id"]),
        normalized_name=str(data["normalized_name"]),
        display_name=str(data["display_name"]),
        aliases=tuple(str(item) for item in _items(data["aliases"], "aliases")),
        status=CandidateStatus(str(data["status"])),
        scene_id=str(data["scene_id"]),
        scene_revision=int(data["scene_revision"]),
        evidence=tuple(_evidence(item) for item in _items(data["evidence"], "evidence")),
    )


def _place(value: Any) -> PlaceCandidate:
    data = _require_object(value, "place")
    keys = {
        "candidate_id", "normalized_name", "display_name", "aliases", "status",
        "scene_id", "scene_revision", "evidence",
    }
    _require_keys(data, keys, keys, "place")
    return PlaceCandidate(
        candidate_id=str(data["candidate_id"]),
        normalized_name=str(data["normalized_name"]),
        display_name=str(data["display_name"]),
        aliases=tuple(str(item) for item in _items(data["aliases"], "aliases")),
        status=CandidateStatus(str(data["status"])),
        scene_id=str(data["scene_id"]),
        scene_revision=int(data["scene_revision"]),
        evidence=tuple(_evidence(item) for item in _items(data["evidence"], "evidence")),
    )


def _relationship(value: Any) -> RelationshipEventCandidate:
    data = _require_object(value, "relationship event")
    keys = {
        "event_id", "subject_key", "object_key", "category", "description", "status",
        "scene_id", "scene_revision", "scene_sequence", "confidence", "evidence",
    }
    _require_keys(data, keys, keys, "relationship event")
    return RelationshipEventCandidate(
        event_id=str(data["event_id"]),
        subject_key=str(data["subject_key"]),
        object_key=str(data["object_key"]),
        category=str(data["category"]),
        description=str(data["description"]),
        status=CandidateStatus(str(data["status"])),
        scene_id=str(data["scene_id"]),
        scene_revision=int(data["scene_revision"]),
        scene_sequence=int(data["scene_sequence"]),
        confidence=float(data["confidence"]),
        evidence=tuple(_evidence(item) for item in _items(data["evidence"], "evidence")),
    )


def _location(value: Any) -> LocationEventCandidate:
    data = _require_object(value, "location event")
    keys = {
        "event_id", "character_key", "place_key", "event_type", "description", "status",
        "scene_id", "scene_revision", "scene_sequence", "confidence", "evidence",
    }
    _require_keys(data, keys, keys, "location event")
    return LocationEventCandidate(
        event_id=str(data["event_id"]),
        character_key=str(data["character_key"]),
        place_key=str(data["place_key"]),
        event_type=LocationEventType(str(data["event_type"])),
        description=str(data["description"]),
        status=CandidateStatus(str(data["status"])),
        scene_id=str(data["scene_id"]),
        scene_revision=int(data["scene_revision"]),
        scene_sequence=int(data["scene_sequence"]),
        confidence=float(data["confidence"]),
        evidence=tuple(_evidence(item) for item in _items(data["evidence"], "evidence")),
    )


def _decode_nested_project_fields(data: dict[str, Any]) -> ProjectRelationshipSnapshot:
    required = {
        "project_id", "snapshot_version", "schema_version", "active_scene_revisions",
        "entities", "places", "relationship_events", "location_events",
    }
    _require_keys(data, required, required, "project snapshot")
    revisions = _items(data["active_scene_revisions"], "active_scene_revisions")
    return ProjectRelationshipSnapshot(
        project_id=str(data["project_id"]),
        snapshot_version=int(data["snapshot_version"]),
        schema_version=str(data["schema_version"]),
        active_scene_revisions=tuple((str(item[0]), int(item[1])) for item in revisions),
        entities=tuple(_entity(item) for item in _items(data["entities"], "entities")),
        places=tuple(_place(item) for item in _items(data["places"], "places")),
        relationship_events=tuple(
            _relationship(item)
            for item in _items(data["relationship_events"], "relationship_events")
        ),
        location_events=tuple(
            _location(item) for item in _items(data["location_events"], "location_events")
        ),
    )
```

Import every referenced model type from `models.py`. Keep the explicit enum
construction, list-to-tuple conversion, object checks, and unknown-key checks;
do not replace these helpers with unchecked `ClassName(**data)` construction.

- [ ] **Step 4: Run codec tests and full focused package tests**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_snapshot_codec.py -v
mise exec -- uv run pytest tests/narrative_memory -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit the codec**

```sh
git add backend/apps/narrative_memory/service/snapshot_codec.py backend/tests/narrative_memory/test_snapshot_codec.py
git commit -m "feat(backend): encode narrative memory snapshots"
```

---

### Task 4: Merge overlapping chunk analyses into one scene snapshot

**Files:**

- Create: `backend/apps/narrative_memory/service/merge.py`
- Create: `backend/tests/narrative_memory/test_merge.py`

**Interfaces:**

- Produces: `merge_chunk_analyses(scene_id, scene_revision, scene_sequence, analyses) -> SceneRelationshipSnapshot`.
- Raises `MergeInvariantError` for mismatched scene/revision or invalid evidence.
- Deduplicates overlap events while retaining distinct evidence ranges.

- [ ] **Step 1: Write tests for overlap deduplication and invalid evidence**

Build two `ChunkAnalysis` values for `scene-01:r1:0000` and
`scene-01:r1:0001`. Give both the same normalized relationship identity and
overlapping absolute evidence; assert one event with the union of evidence.
Also add:

```python
import pytest

from apps.narrative_memory.service.merge import (
    MergeInvariantError,
    merge_chunk_analyses,
)


def test_merge_rejects_an_analysis_from_another_revision(
    chunk_analysis_for_revision_one: ChunkAnalysis,
) -> None:
    with pytest.raises(MergeInvariantError, match="revision"):
        merge_chunk_analyses(
            scene_id="scene-01",
            scene_revision=2,
            scene_sequence=1,
            analyses=(chunk_analysis_for_revision_one,),
        )
```

Define fixtures in the same test module with concrete dataclass constructors;
do not add a shared fixture module for this one consumer.

- [ ] **Step 2: Run the merge tests and confirm the missing module failure**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_merge.py -v
```

Expected: collection fails because `merge.py` does not exist.

- [ ] **Step 3: Implement deterministic scene merging**

Implement these exact helpers in `merge.py`:

```python
import re
from collections.abc import Iterable
from dataclasses import replace

from apps.narrative_memory.service.models import (
    ChunkAnalysis,
    Evidence,
    RelationshipEventCandidate,
    SceneRelationshipSnapshot,
)


class MergeInvariantError(ValueError):
    pass


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def evidence_key(evidence: Evidence) -> tuple[int, int, str]:
    return (
        evidence.start_offset,
        evidence.end_offset,
        normalize_text(evidence.text),
    )


def relationship_key(
    event: RelationshipEventCandidate,
) -> tuple[str, str, str, str, str]:
    return (
        event.subject_key,
        event.object_key,
        normalize_text(event.category),
        normalize_text(event.description),
        event.scene_id,
    )


def entity_key(candidate: EntityCandidate) -> tuple[str, str]:
    return (candidate.scene_id, candidate.normalized_name)


def place_key(candidate: PlaceCandidate) -> tuple[str, str]:
    return (candidate.scene_id, candidate.normalized_name)


def location_key(
    event: LocationEventCandidate,
) -> tuple[str, str, str, str, str]:
    return (
        event.character_key,
        event.place_key,
        event.event_type.value,
        normalize_text(event.description),
        event.scene_id,
    )


def _merge_evidence(values: Iterable[Evidence]) -> tuple[Evidence, ...]:
    by_key = {evidence_key(value): value for value in values}
    return tuple(by_key[key] for key in sorted(by_key))
```

Validate that every analysis matches the requested scene and revision, every
evidence range has `0 <= start < end`, and every relationship/location event
belongs to that scene/revision. Sort every output collection by its identity
key. Join non-empty unique chunk summaries in chunk order with `"\n"`.

- [ ] **Step 4: Run merge and package tests**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_merge.py -v
mise exec -- uv run pytest tests/narrative_memory -v
```

Expected: overlap collapses to one event, invalid inputs are rejected, and all
Narrative Memory tests pass.

- [ ] **Step 5: Commit scene merging**

```sh
git add backend/apps/narrative_memory/service/merge.py backend/tests/narrative_memory/test_merge.py
git commit -m "feat(backend): merge scene analysis JSON"
```

---

### Task 5: Merge scene replacements into immutable project snapshots

**Files:**

- Modify: `backend/apps/narrative_memory/service/merge.py`
- Modify: `backend/tests/narrative_memory/test_merge.py`

**Interfaces:**

- Produces: `merge_scene_into_project(project, scene) -> ProjectRelationshipSnapshot`.
- The result version is exactly the input version plus one.
- Pending candidates from the previous active revision of the scene disappear.
- Approved events unsupported by the replacement scene become `needs_review`.
- Events from other scenes remain unchanged.

- [ ] **Step 1: Add replacement and temporal accumulation tests**

Add three explicit tests:

```python
def test_project_merge_replaces_pending_candidates_from_same_scene() -> None:
    current = project_snapshot_with_pending_scene_one_revision_one()
    replacement = scene_snapshot_for_scene_one_revision_two_without_events()

    result = merge_scene_into_project(current, replacement)

    assert result.snapshot_version == current.snapshot_version + 1
    assert result.relationship_events == ()
    assert dict(result.active_scene_revisions) == {"scene-01": 2}


def test_project_merge_marks_unsupported_approved_event_needs_review() -> None:
    current = project_snapshot_with_approved_scene_one_event()
    replacement = scene_snapshot_for_scene_one_revision_two_without_events()

    result = merge_scene_into_project(current, replacement)

    assert result.relationship_events[0].status is CandidateStatus.NEEDS_REVIEW


def test_project_merge_preserves_events_from_other_scenes() -> None:
    current = project_snapshot_with_scene_one_and_scene_two_events()
    replacement = scene_snapshot_for_scene_one_revision_two_without_events()

    result = merge_scene_into_project(current, replacement)

    assert [event.scene_id for event in result.relationship_events] == ["scene-02"]
```

Implement the named test builders in the same module using concrete domain
constructors.

- [ ] **Step 2: Run the new tests and confirm behavioral failures**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_merge.py -v
```

Expected: the three new tests fail because
`merge_scene_into_project` does not exist.

- [ ] **Step 3: Implement project merge semantics**

Add `merge_scene_into_project` with this processing order:

```python
def merge_scene_into_project(
    project: ProjectRelationshipSnapshot,
    scene: SceneRelationshipSnapshot,
) -> ProjectRelationshipSnapshot:
    active_revisions = dict(project.active_scene_revisions)
    previous_revision = active_revisions.get(scene.scene_id)
    if previous_revision is not None and scene.scene_revision <= previous_revision:
        raise MergeInvariantError("scene revision must advance")

    relationships = _replace_scene_relationships(project.relationship_events, scene)
    locations = _replace_scene_locations(project.location_events, scene)
    entities = _merge_entities_after_scene_replacement(project.entities, scene.entities, scene)
    places = _merge_places_after_scene_replacement(project.places, scene.places, scene)
    active_revisions[scene.scene_id] = scene.scene_revision

    return ProjectRelationshipSnapshot(
        project_id=project.project_id,
        snapshot_version=project.snapshot_version + 1,
        schema_version=project.schema_version,
        active_scene_revisions=tuple(sorted(active_revisions.items())),
        entities=entities,
        places=places,
        relationship_events=relationships,
        location_events=locations,
    )
```

In `_replace_scene_relationships` and `_replace_scene_locations`, retain all
other scenes. For the changed scene, discard pending/rejected prior candidates;
retain approved candidates only when the replacement contains matching
identity and evidence, otherwise use `dataclasses.replace` to set
`NEEDS_REVIEW`. Add new replacement candidates as pending unless they match a
retained approved event. Apply the same rule to entities and places based on
their evidence. Sort all results deterministically.

- [ ] **Step 4: Run all Narrative Memory tests**

```sh
mise exec -- uv run pytest tests/narrative_memory -v
```

Expected: all tests pass, including changed-scene replacement and cross-scene
accumulation.

- [ ] **Step 5: Commit project merging**

```sh
git add backend/apps/narrative_memory/service/merge.py backend/tests/narrative_memory/test_merge.py
git commit -m "feat(backend): merge project relationship snapshots"
```

---

### Task 6: Persist immutable snapshot versions in SQLite

**Files:**

- Create: `backend/apps/narrative_memory/repository/__init__.py`
- Create: `backend/apps/narrative_memory/repository/snapshot_repository.py`
- Create: `backend/apps/narrative_memory/repository/sqlite_snapshot_repository.py`
- Create: `backend/tests/narrative_memory/test_sqlite_snapshot_repository.py`
- Modify: `backend/README.md`

**Interfaces:**

- Produces protocol methods `initialize()`, `get_current(project_id)`, `get_version(project_id, version)`, and `commit(expected_version, snapshot)`.
- Produces `SnapshotVersionConflict` for stale expected versions.
- Stored `payload` is exactly `encode_project_snapshot(snapshot)`.

- [ ] **Step 1: Write persistence, exact-byte, permissions, and conflict tests**

Create a temporary database per test and assert:

```python
import stat

import pytest

from apps.narrative_memory.repository.snapshot_repository import SnapshotVersionConflict
from apps.narrative_memory.repository.sqlite_snapshot_repository import (
    SQLiteSnapshotRepository,
)
from apps.narrative_memory.service.models import ProjectRelationshipSnapshot
from apps.narrative_memory.service.snapshot_codec import encode_project_snapshot


def test_repository_commits_and_reads_exact_snapshot_bytes(tmp_path) -> None:
    path = tmp_path / "agent-audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()
    snapshot = ProjectRelationshipSnapshot.empty("project-01")

    repository.commit(expected_version=None, snapshot=snapshot)

    stored = repository.get_version("project-01", 0)
    assert stored is not None
    assert stored.snapshot == snapshot
    assert stored.payload == encode_project_snapshot(snapshot)


def test_repository_rejects_stale_expected_version(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "audit.sqlite3")
    repository.initialize()
    repository.commit(None, ProjectRelationshipSnapshot.empty("project-01"))

    with pytest.raises(SnapshotVersionConflict):
        repository.commit(None, ProjectRelationshipSnapshot.empty("project-01"))


def test_repository_file_is_owner_read_write_only(tmp_path) -> None:
    path = tmp_path / "audit.sqlite3"
    repository = SQLiteSnapshotRepository(path)
    repository.initialize()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
```

- [ ] **Step 2: Run the repository tests and confirm missing imports**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_sqlite_snapshot_repository.py -v
```

Expected: collection fails because the repository modules do not exist.

- [ ] **Step 3: Define the repository contract**

Create `snapshot_repository.py` with:

```python
from dataclasses import dataclass
from typing import Protocol

from apps.narrative_memory.service.models import ProjectRelationshipSnapshot


class SnapshotVersionConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoredProjectSnapshot:
    snapshot: ProjectRelationshipSnapshot
    payload: bytes
    content_hash: str


class SnapshotRepository(Protocol):
    def initialize(self) -> None:
        raise NotImplementedError

    def get_current(self, project_id: str) -> StoredProjectSnapshot | None:
        raise NotImplementedError

    def get_version(self, project_id: str, version: int) -> StoredProjectSnapshot | None:
        raise NotImplementedError

    def commit(
        self,
        expected_version: int | None,
        snapshot: ProjectRelationshipSnapshot,
    ) -> StoredProjectSnapshot:
        raise NotImplementedError
```

- [ ] **Step 4: Implement SQLite transactions and immutable rows**

Create `sqlite_snapshot_repository.py`. `initialize()` must create the parent
directory, touch the database with mode `0o600`, and create:

```sql
CREATE TABLE IF NOT EXISTS project_snapshots (
    project_id TEXT NOT NULL,
    snapshot_version INTEGER NOT NULL,
    schema_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload BLOB NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (project_id, snapshot_version)
);

CREATE TABLE IF NOT EXISTS current_project_snapshots (
    project_id TEXT PRIMARY KEY,
    snapshot_version INTEGER NOT NULL
);
```

`commit()` must use `BEGIN IMMEDIATE`, query the current version, compare it to
`expected_version`, assert `snapshot.snapshot_version` is `0` for a new project
or `expected_version + 1` otherwise, insert the immutable payload and SHA-256,
upsert the current pointer, and commit. Roll back on every exception. Set
`created_at` with `datetime.now(timezone.utc).isoformat()`.

- [ ] **Step 5: Run repository and package tests**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_sqlite_snapshot_repository.py -v
mise exec -- uv run pytest tests/narrative_memory -v
```

Expected: exact bytes round-trip, stale commits fail, mode is `0600`, and all
Narrative Memory tests pass.

- [ ] **Step 6: Update the backend structure map**

Add `narrative_memory` to `backend/README.md` and state that its repository
persists immutable versioned JSON snapshots in SQLite. Do not list individual
files in the structure map.

- [ ] **Step 7: Commit SQLite snapshot persistence**

```sh
git add backend/apps/narrative_memory/repository backend/tests/narrative_memory/test_sqlite_snapshot_repository.py backend/README.md
git commit -m "feat(backend): persist narrative memory snapshots"
```

---

### Task 7: Verify the JSON core as an independently usable subsystem

**Files:**

- Modify: files introduced in Tasks 1–6 only when a failing verification test
  demonstrates a defect

**Interfaces:**

- Consumes: all public interfaces from Tasks 1–6.
- Produces: a verified provider-independent JSON core ready for the agent/job plan.

- [ ] **Step 1: Add one end-to-end core test**

Add to `test_sqlite_snapshot_repository.py` a test that:

1. chunks a 350-character Korean scene into `[0, 300)` and `[250, 350)`;
2. constructs validated `ChunkAnalysis` objects with one duplicated overlap
   relationship and one location event;
3. merges them into one scene snapshot;
4. merges that scene into `ProjectRelationshipSnapshot.empty("project-01")`;
5. commits version `1` with `expected_version=0` after first committing the
   empty version `0` snapshot;
6. reads version `1` and asserts one relationship event, one location event,
   exact JSON bytes, and active scene revision `1`.

Name the test
`test_scene_analysis_json_reaches_immutable_project_snapshot` and use only
public interfaces.

- [ ] **Step 2: Run the focused end-to-end test**

```sh
mise exec -- uv run pytest tests/narrative_memory/test_sqlite_snapshot_repository.py::test_scene_analysis_json_reaches_immutable_project_snapshot -v
```

Expected: one test passes.

- [ ] **Step 3: Run full backend verification**

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: all tests pass, Ruff reports no lint violations, and formatting is
already correct.

- [ ] **Step 4: Compare implementation and domain documentation**

Run from the repository root:

```sh
git diff -- backend docs/domains
git status --short
```

Confirm explicitly that chunk constants are `300/50`, snapshots are immutable
JSON, same-scene pending data is replaced, approved stale evidence becomes
`needs_review`, Story Bible owns confirmed facts, and no Neo4j/Cypher/model/API
code was introduced.

- [ ] **Step 5: Commit any verification-only test or repair**

If Step 1 changed the tree, commit it with:

```sh
git add backend/tests/narrative_memory backend/apps/narrative_memory docs/domains backend/README.md
git commit -m "test(backend): verify narrative memory JSON core"
```

If the end-to-end test was already committed as part of a repair commit, verify
`git status --short` is clean and do not create an empty commit.

---

## Follow-on Plan Boundaries

After this plan passes review, create separate implementation plans in this
order:

1. **Agent prompts and audit runs:** `backend/prompts/`, prompt ID/version/hash
   registry, Pydantic AI structured adapters, exact rendered-message logging,
   raw responses, validated chunk artifacts, and model-request blocking in
   tests.
2. **Durable in-process analysis jobs:** job transitions, bounded `asyncio`
   executor, restart recovery, superseding revisions, two-attempt policy, and
   all-or-nothing scene/project snapshot commit.
3. **Candidate decisions and explicit validation:** dependency-checked batch
   decisions, confirmed-context selection, consistency validator, and
   consumer-facing operations through the repository OpenAPI workflow.
4. **Internal audit viewer:** the approved
   `frontend/docs/ui-plans/agent-audit-viewer.md` implemented as localhost-only
   backend-rendered Jinja templates with exact snapshot download and diff.

Each follow-on plan consumes the stable public types and repository contract
produced here; none may change the JSON schema or merge semantics silently.
