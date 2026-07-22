# Knowledge Graph Extraction v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 경량 `llm-agent`가 기존 프로젝트 그래프를 읽기 전용으로 참조해 청크별 지식 그래프를 구조화 출력하고, backend가 이를 결정적으로 병합해 v2 프로젝트 그래프로 저장하게 한다.

**Architecture:** `llm-agent`는 strict Pydantic 응답 모델, 300/50 청킹, 프로젝트 그래프 단일 read-only 조회와 청크당 한 번의 순차 모델 호출만 소유한다. backend는 반환된 청크 로컬 ID를 프로젝트 ID로 재매핑하고 장면별 그래프에서 v2 프로젝트 snapshot을 재구성한 뒤 낙관적 버전 검사와 함께 SQLite에 저장한다. v1 호환과 자동 migration은 제공하지 않는다.

**Tech Stack:** Python 3.13, Pydantic 2, Pydantic AI 2.x, stdlib `sqlite3`, pytest, Ruff, uv/mise

## Global Constraints

- 설계 기준은 `docs/superpowers/specs/2026-07-22-knowledge-graph-extraction-v2-design.md`다.
- 장면은 최대 300자, 50자 중첩 청크로 나누고 숫자 순서대로 직렬 처리한다.
- 각 청크는 정확히 한 번 호출하며 재시도와 부분 결과 반환을 금지한다.
- Pydantic AI 응답 구조는 사용자가 제시한 JSON 필드와 중첩 구조를 유지한다.
- 일반 엔티티, 사건, 관계, 이동과 해소된 공통 참조는 `confidence >= 0.8`만 허용한다.
- `llm-agent`는 프로젝트 SQLite를 URI read-only 모드로 한 번만 읽고 쓰기, schema 생성, 청크 병합과 durable ID 생성을 하지 않는다.
- backend는 LLM 입력용 그래프를 조회하지 않으며, 분석 후 ID 재매핑·장면 교체·프로젝트 병합·저장만 소유한다.
- v1 decoder, 자동 migration, 런타임 자동 DB 삭제를 추가하지 않는다.
- HTTP API, OpenAPI와 frontend는 변경하지 않는다.
- 현재 작업 트리의 사용자 변경을 보존하고 관련 없는 리팩터링을 하지 않는다.
- 커밋 메시지는 한글로 작성한다.

---

## File Structure

### llm-agent

- `llm-agent/src/narrative_analysis_agent/models.py`: 입력, exact 지식 그래프 출력, 프로젝트 snapshot과 청크 결과를 표현하는 단일 strict Pydantic 모델 집합
- `llm-agent/src/narrative_analysis_agent/project_graph_reader.py`: 프로젝트 snapshot의 SQLite read-only 조회와 content hash 검증
- `llm-agent/src/narrative_analysis_agent/agent.py`: prompt 로딩, 그래프 조회, 안정적 사용자 JSON, 청크 호출과 문맥 후검증
- `llm-agent/src/narrative_analysis_agent/__init__.py`: 새 공개 계약과 reader 오류 export
- `llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md`: 출력 예시가 없는 한국어 의미 지침
- `llm-agent/tests/unit/test_models.py`: strict schema와 field validation
- `llm-agent/tests/unit/test_project_graph_reader.py`: read-only SQLite 경계
- `llm-agent/tests/unit/test_agent.py`: 호출 순서, existing graph 전달과 후검증
- `llm-agent/tests/integration/test_scene_analysis_offline.py`: 네트워크 없는 전체 공개 흐름
- `llm-agent/tests/live/conftest.py`, `llm-agent/tests/live/test_scene_analysis_live.py`: 새 live 의미 검증

### backend

- `backend/apps/narrative_memory/service/models.py`: 장면 그래프 저장 레코드와 v2 schema 상수
- `backend/apps/narrative_memory/service/snapshot_codec.py`: public Pydantic v2 project snapshot canonical JSON codec
- `backend/apps/narrative_memory/service/validation.py`: 집계 그래프의 ID, 참조, 문서와 confidence 불변 조건
- `backend/apps/narrative_memory/service/merge.py`: 청크 로컬 ID 재매핑, 장면 그래프 조립과 프로젝트 재구성
- `backend/apps/narrative_memory/repository/snapshot_repository.py`: 장면 조회와 원자적 scene/project commit port
- `backend/apps/narrative_memory/repository/sqlite_snapshot_repository.py`: v2 schema 초기화, scene graph 저장, project snapshot version commit
- `backend/apps/narrative_memory/service/scene_analysis_use_case.py`: agent 호출 후 merge와 저장을 조정하는 application workflow
- `backend/apps/narrative_memory/composition.py`: 동일한 DB 경로로 reader와 writer 구성
- `backend/tests/narrative_memory/test_snapshot_codec.py`: v2 codec
- `backend/tests/narrative_memory/test_merge.py`: 결정적 병합
- `backend/tests/narrative_memory/test_sqlite_snapshot_repository.py`: 저장·조회·충돌
- `backend/tests/narrative_memory/test_scene_analysis_use_case.py`: 전체 backend workflow
- `backend/tests/narrative_memory/test_agent_composition.py`: 경로 공유 구성

### documentation

- `docs/domains/narrative-memory.md`: v2 보편 언어, read/write 소유권과 불변 조건
- `llm-agent/AGENTS.md`: read-only project graph scope
- `llm-agent/docs/llm-agent-coding-rules.md`: 경량 agent 규칙 갱신
- `backend/docs/backend-coding-rules.md`: merge와 persistence 책임
- `backend/README.md`: 구성 예시와 v2 저장 흐름

---

### Task 1: 지식 그래프 Pydantic 공개 계약

**Files:**
- Modify: `llm-agent/src/narrative_analysis_agent/models.py`
- Modify: `llm-agent/src/narrative_analysis_agent/__init__.py`
- Modify: `llm-agent/tests/unit/test_models.py`

**Interfaces:**
- Consumes: Python 3.13, Pydantic `BaseModel`, `ConfigDict`, `Field`, `StringConstraints`
- Produces: `KnowledgeGraphOutput`, `ProjectKnowledgeGraphSnapshot`, `SceneAnalysisRequest`, `AnalyzedChunk`, `SceneAnalysis`, `PROJECT_GRAPH_SCHEMA_VERSION`

- [ ] **Step 1: exact JSON 구조와 strict validation의 실패 테스트 작성**

`test_models.py`에서 최소 유효 그래프 factory를 만들고 unknown field, 잘못된 enum,
`confidence=0.79`, non-finite confidence, 소문자 custom type과 nullable 필드를 각각 검증한다.

```python
def graph_payload() -> dict[str, object]:
    return {
        "document": {
            "chapter_id": "scene-01",
            "summary": "서윤은 온실에 도착한다.",
            "narrative_time": "present",
        },
        "entities": {"characters": [], "locations": [], "events": []},
        "relations": [],
        "movements": [],
        "coreferences": [],
        "unresolved_references": [],
        "contradictions": [],
    }


def test_knowledge_graph_rejects_general_confidence_below_point_eight() -> None:
    payload = graph_payload()
    payload["entities"]["characters"] = [
        {
            "id": "character_001",
            "canonical_name": "서윤",
            "aliases": [],
            "description": "",
            "gender": "unknown",
            "age": None,
            "occupation": None,
            "affiliation": None,
            "status": "unknown",
            "first_mention": "서윤",
            "confidence": 0.79,
        }
    ]

    with pytest.raises(ValidationError):
        KnowledgeGraphOutput.model_validate(payload)
```

- [ ] **Step 2: 모델 테스트가 현재 계약에서 실패하는지 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_models.py -v`

Expected: 새 `KnowledgeGraphOutput` import 또는 validation assertion에서 FAIL.

- [ ] **Step 3: exact 응답 모델과 public wrapper 구현**

`models.py`에서 기존 `Entity`, `Place`, `RelationshipEvent`, `LocationEvent`,
`ChunkExtraction`을 제거하고 다음 공개 계약을 정의한다. 각 나열 필드는 tuple default를
사용하고 모든 nullable 필드는 예시와 같은 `None`을 허용한다.

```python
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PROJECT_GRAPH_SCHEMA_VERSION = "project-knowledge-graph-snapshot-v2"
UpperSnake = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$"),
]
HighConfidence = Annotated[float, Field(ge=0.8, le=1.0, allow_inf_nan=False)]
NarrativeTime = Literal["present", "flashback", "flashforward", "mixed", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Document(StrictModel):
    chapter_id: str = Field(min_length=1)
    summary: str
    narrative_time: NarrativeTime


class Character(StrictModel):
    id: str = Field(pattern=r"^character_[0-9]+$")
    canonical_name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    description: str
    gender: Literal["male", "female", "nonbinary", "unknown"]
    age: int | str | None
    occupation: str | None
    affiliation: str | None
    status: Literal["alive", "dead", "missing", "unknown"]
    first_mention: str
    confidence: HighConfidence


class Location(StrictModel):
    id: str = Field(pattern=r"^location_[0-9]+$")
    canonical_name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    location_type: Literal[
        "country", "city", "village", "building", "room", "school",
        "company", "hospital", "street", "nature", "vehicle", "virtual", "other",
    ]
    parent_location_id: str | None
    description: str
    first_mention: str
    confidence: HighConfidence


class Event(StrictModel):
    id: str = Field(pattern=r"^event_[0-9]+$")
    event_type: UpperSnake
    name: str
    summary: str
    participant_ids: tuple[str, ...] = ()
    location_ids: tuple[str, ...] = ()
    time_expression: str | None
    narrative_time: Literal["present", "flashback", "flashforward", "unknown"]
    sequence: int = Field(ge=0)
    evidence: str
    confidence: HighConfidence


class Entities(StrictModel):
    characters: tuple[Character, ...] = ()
    locations: tuple[Location, ...] = ()
    events: tuple[Event, ...] = ()


class Relation(StrictModel):
    id: str = Field(pattern=r"^relation_[0-9]+$")
    source_id: str
    relation_type: UpperSnake
    target_id: str
    state: Literal["active", "ended", "uncertain", "perceived"]
    directed: bool
    start_event_id: str | None
    end_event_id: str | None
    time_expression: str | None
    scene_sequence: int = Field(ge=0)
    evidence: str
    inference: bool
    confidence: HighConfidence


class Movement(StrictModel):
    character_id: str
    from_location_id: str | None
    to_location_id: str | None
    movement_type: UpperSnake
    event_id: str | None
    time_expression: str | None
    sequence: int = Field(ge=0)
    evidence: str
    confidence: HighConfidence


class Coreference(StrictModel):
    expression: str
    resolved_entity_id: str
    evidence: str
    confidence: HighConfidence


class UnresolvedReference(StrictModel):
    expression: str
    possible_entity_ids: tuple[str, ...] = ()
    reason: str


class Contradiction(StrictModel):
    subject_id: str
    field_or_relation: str
    existing_value: str
    new_value: str
    evidence: str
    possible_explanation: str


class KnowledgeGraphOutput(StrictModel):
    document: Document
    entities: Entities
    relations: tuple[Relation, ...] = ()
    movements: tuple[Movement, ...] = ()
    coreferences: tuple[Coreference, ...] = ()
    unresolved_references: tuple[UnresolvedReference, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()


class ProjectKnowledgeGraphSnapshot(StrictModel):
    project_id: str = Field(min_length=1)
    snapshot_version: int = Field(ge=0)
    schema_version: Literal["project-knowledge-graph-snapshot-v2"]
    documents: tuple[Document, ...] = ()
    entities: Entities = Entities()
    relations: tuple[Relation, ...] = ()
    movements: tuple[Movement, ...] = ()
    coreferences: tuple[Coreference, ...] = ()
    unresolved_references: tuple[UnresolvedReference, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()

    @classmethod
    def empty(cls, project_id: str) -> "ProjectKnowledgeGraphSnapshot":
        return cls(
            project_id=project_id,
            snapshot_version=0,
            schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        )


class SceneAnalysisRequest(StrictModel):
    project_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    scene_revision: int = Field(ge=0)
    scene_sequence: int = Field(ge=0)
    text: str


class AnalyzedChunk(StrictModel):
    chunk_id: str
    ordinal: int = Field(ge=0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    text: str
    extraction: KnowledgeGraphOutput


class SceneAnalysis(StrictModel):
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    source_snapshot_version: int = Field(ge=0)
    chunks: tuple[AnalyzedChunk, ...]
```

`__init__.py`는 위 공개 타입만 export하고 제거된 v1 추출 타입을 export하지 않는다.

- [ ] **Step 4: 모델 테스트 통과 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_models.py -v`

Expected: PASS.

- [ ] **Step 5: 공개 계약 커밋**

```sh
git add llm-agent/src/narrative_analysis_agent/models.py \
  llm-agent/src/narrative_analysis_agent/__init__.py \
  llm-agent/tests/unit/test_models.py
git commit -m "기능: 지식 그래프 응답 계약 추가"
```

---

### Task 2: 프로젝트 그래프 SQLite read-only reader

**Files:**
- Create: `llm-agent/src/narrative_analysis_agent/project_graph_reader.py`
- Modify: `llm-agent/src/narrative_analysis_agent/__init__.py`
- Create: `llm-agent/tests/unit/test_project_graph_reader.py`

**Interfaces:**
- Consumes: `ProjectKnowledgeGraphSnapshot`, backend v2 tables `project_snapshots`와 `current_project_snapshots`
- Produces: `ProjectGraphReader(path: Path).read(project_id: str) -> ProjectKnowledgeGraphSnapshot`, `ProjectGraphReadError`

- [ ] **Step 1: read-only reader 실패 테스트 작성**

임시 SQLite에 v2 tables와 canonical payload를 직접 넣어 정상 조회, current record 부재,
missing DB, hash mismatch, v1 schema와 malformed JSON을 각각 검증한다.

```python
def test_reader_returns_empty_v2_graph_when_project_has_no_current_record(tmp_path: Path) -> None:
    path = tmp_path / "narrative-memory.sqlite3"
    initialize_v2_tables(path)

    result = ProjectGraphReader(path).read("project-01")

    assert result == ProjectKnowledgeGraphSnapshot.empty("project-01")


def test_reader_does_not_create_a_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"

    with pytest.raises(ProjectGraphReadError, match="unable to read project graph"):
        ProjectGraphReader(path).read("project-01")

    assert not path.exists()
```

- [ ] **Step 2: reader 테스트가 import 실패하는지 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_project_graph_reader.py -v`

Expected: `project_graph_reader` import에서 FAIL.

- [ ] **Step 3: read-only reader 구현**

reader는 `Path.resolve().as_uri() + "?mode=ro"`로 연결하고 hash와 metadata를 검증한다.

```python
class ProjectGraphReadError(RuntimeError):
    pass


class ProjectGraphReader:
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self, project_id: str) -> ProjectKnowledgeGraphSnapshot:
        try:
            uri = f"{self._path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(uri, uri=True) as connection:
                pointer = connection.execute(
                    "SELECT snapshot_version FROM current_project_snapshots WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
                if pointer is None:
                    return ProjectKnowledgeGraphSnapshot.empty(project_id)
                row = connection.execute(
                    """
                    SELECT schema_version, content_hash, payload
                    FROM project_snapshots
                    WHERE project_id = ? AND snapshot_version = ?
                    """,
                    (project_id, pointer[0]),
                ).fetchone()
            if row is None:
                raise ValueError("current snapshot is missing")
            schema_version, content_hash, raw_payload = row
            payload = bytes(raw_payload)
            calculated = f"sha256:{sha256(payload).hexdigest()}"
            if content_hash != calculated:
                raise ValueError("snapshot hash mismatch")
            snapshot = ProjectKnowledgeGraphSnapshot.model_validate_json(payload)
            if (
                snapshot.project_id != project_id
                or snapshot.snapshot_version != pointer[0]
                or snapshot.schema_version != schema_version
            ):
                raise ValueError("snapshot metadata mismatch")
            return snapshot
        except (OSError, sqlite3.Error, ValidationError, ValueError):
            raise ProjectGraphReadError("unable to read project graph") from None
```

- [ ] **Step 4: reader와 전체 모델 테스트 통과 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_project_graph_reader.py tests/unit/test_models.py -v`

Expected: PASS.

- [ ] **Step 5: reader 커밋**

```sh
git add llm-agent/src/narrative_analysis_agent/project_graph_reader.py \
  llm-agent/src/narrative_analysis_agent/__init__.py \
  llm-agent/tests/unit/test_project_graph_reader.py
git commit -m "기능: 프로젝트 그래프 읽기 전용 조회 추가"
```

---

### Task 3: 경량 agent의 새 prompt와 지식 그래프 호출

**Files:**
- Modify: `llm-agent/src/narrative_analysis_agent/agent.py`
- Modify: `llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md`
- Modify: `llm-agent/tests/unit/test_agent.py`
- Modify: `llm-agent/tests/integration/test_scene_analysis_offline.py`
- Modify: `llm-agent/tests/live/conftest.py`
- Modify: `llm-agent/tests/live/test_scene_analysis_live.py`

**Interfaces:**
- Consumes: `KnowledgeGraphOutput`, `ProjectGraphReader`, `SceneAnalysisRequest`, `chunk_scene()`
- Produces: `NarrativeAnalysisAgent(model, project_graph_path, prompt_path=None, runner=None)`, `analyze_scene() -> SceneAnalysis`

- [ ] **Step 1: 그래프 조회와 모든 청크 전달 테스트 작성**

fake reader는 한 번만 호출되어야 하고 fake runner의 모든 `user_prompt`에 같은
`existing_graph`가 들어가야 한다. `document.chapter_id` mismatch, 원문에 없는 evidence와
잘못된 ID 참조는 provider 재호출 없이 실패해야 한다.

```python
def test_analyze_scene_reads_graph_once_and_sends_it_to_every_chunk() -> None:
    reader = RecordingGraphReader(ProjectKnowledgeGraphSnapshot.empty("project-01"))
    runner = GraphRunner()
    agent = NarrativeAnalysisAgent("test", graph_reader=reader, runner=runner)

    result = asyncio.run(agent.analyze_scene(request("가" * 551)))

    assert reader.project_ids == ["project-01"]
    assert len(runner.calls) == 3
    graphs = [json.loads(call[0])["existing_graph"] for call in runner.calls]
    expected = ProjectKnowledgeGraphSnapshot.empty("project-01").model_dump(mode="json")
    assert graphs == [expected] * 3
    assert result.source_snapshot_version == 0
```

backend는 저장 직전에 current snapshot을 다시 읽고 `source_snapshot_version`과 정확히
일치할 때만 그 snapshot을 병합 기준으로 사용한다. 따라서 `SceneAnalysis`에는 전체 source
graph를 중복 반환하지 않는다.

- [ ] **Step 2: agent 테스트 실패 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_agent.py tests/integration/test_scene_analysis_offline.py -v`

Expected: 기존 `ChunkExtraction` 계약 또는 새 constructor 인자에서 FAIL.

- [ ] **Step 3: agent와 문맥 후검증 구현**

runner output을 `KnowledgeGraphOutput`으로 바꾸고, 분석 시작 시 reader를 한 번 호출한 뒤
각 청크에 동일 객체를 직렬화한다.

```python
class AgentResult(Protocol):
    output: KnowledgeGraphOutput


def _validate_output(
    output: KnowledgeGraphOutput,
    request: SceneAnalysisRequest,
    chunk: SceneChunk,
    existing: ProjectKnowledgeGraphSnapshot,
) -> None:
    if output.document.chapter_id != request.scene_id:
        raise ValueError("chapter ID does not match the scene")
    local_characters = {item.id for item in output.entities.characters}
    local_locations = {item.id for item in output.entities.locations}
    local_events = {item.id for item in output.entities.events}
    known_characters = {item.id for item in existing.entities.characters}
    known_locations = {item.id for item in existing.entities.locations}
    known_events = {item.id for item in existing.entities.events}
    characters = local_characters | known_characters
    locations = local_locations | known_locations
    events = local_events | known_events
    for event in output.entities.events:
        if not set(event.participant_ids) <= characters:
            raise ValueError("event references an unknown character")
        if not set(event.location_ids) <= locations:
            raise ValueError("event references an unknown location")
    for relation in output.relations:
        if relation.source_id not in characters | locations | events:
            raise ValueError("relation source is unknown")
        if relation.target_id not in characters | locations | events:
            raise ValueError("relation target is unknown")
    evidence_values = [
        *(item.first_mention for item in output.entities.characters),
        *(item.first_mention for item in output.entities.locations),
        *(item.evidence for item in output.entities.events),
        *(item.evidence for item in output.relations),
        *(item.evidence for item in output.movements),
        *(item.evidence for item in output.coreferences),
        *(item.evidence for item in output.contradictions),
    ]
    if any(value and value not in chunk.text for value in evidence_values):
        raise ValueError("evidence is not present in the chunk")
```

`analyze_scene()`은 `ProjectGraphReadError`, `AgentRunError`, `ValidationError`, 후검증
`ValueError`를 원인 없는 `NarrativeAnalysisError`로 정제하고 `CancelledError`만 그대로
전파한다. 사용자 JSON은 `existing_graph`와 현재 `chunk`를 포함하며 환경변수나 다른
프로젝트 데이터는 포함하지 않는다.

- [ ] **Step 4: 시스템 프롬프트 교체**

사용자가 제공한 한국어 프롬프트에서 `## 출력 형식` JSON 전체와 마지막 `## 입력` 템플릿을
제거한 본문을 `system.md`에 넣는다. 다음 회귀 assertion을 추가한다.

```python
def test_packaged_prompt_contains_semantics_without_json_template() -> None:
    content = packaged_prompt_path().read_text(encoding="utf-8")

    assert "## 분석 목표" in content
    assert "## confidence 기준" in content
    assert "## 출력 형식" not in content
    assert "{{CHAPTER_ID}}" not in content
    assert '"document"' not in content
```

- [ ] **Step 5: agent focused tests 통과 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_agent.py tests/integration/test_scene_analysis_offline.py -v`

Expected: PASS.

- [ ] **Step 6: live fixture와 assertion 갱신**

live 테스트는 새 top-level 컬렉션 존재, `confidence >= 0.8`, evidence substring, 알려지지 않은
참조 부재를 검사하고 생성 문장이나 전체 그래프를 exact 비교하지 않는다. 실행은 opt-in으로
유지한다.

- [ ] **Step 7: agent 변경 커밋**

```sh
git add llm-agent/src/narrative_analysis_agent/agent.py \
  llm-agent/src/narrative_analysis_agent/models.py \
  llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md \
  llm-agent/tests/unit/test_agent.py \
  llm-agent/tests/integration/test_scene_analysis_offline.py \
  llm-agent/tests/live/conftest.py llm-agent/tests/live/test_scene_analysis_live.py
git commit -m "기능: 청크별 지식 그래프 분석 적용"
```

---

### Task 4: backend v2 snapshot 계약과 codec

**Files:**
- Modify: `backend/apps/narrative_memory/service/models.py`
- Modify: `backend/apps/narrative_memory/service/snapshot_codec.py`
- Modify: `backend/apps/narrative_memory/service/validation.py`
- Modify: `backend/tests/narrative_memory/test_snapshot_codec.py`

**Interfaces:**
- Consumes: public `KnowledgeGraphOutput`, `ProjectKnowledgeGraphSnapshot`
- Produces: `SceneGraphRecord`, `encode_project_snapshot()`, `decode_project_snapshot()`, `validate_project_snapshot()`

- [ ] **Step 1: v2 codec와 불변 조건 실패 테스트 작성**

v2 empty/semantic snapshot canonical round-trip, v1 거부, unknown field, dangling relation,
duplicate ID와 non-finite confidence를 테스트한다.

```python
def test_v2_project_snapshot_codec_is_canonical_and_round_trips() -> None:
    snapshot = ProjectKnowledgeGraphSnapshot.empty("project-01")

    payload = encode_project_snapshot(snapshot)

    assert payload.endswith(b"\n")
    assert decode_project_snapshot(payload) == snapshot
    assert encode_project_snapshot(decode_project_snapshot(payload)) == payload


def test_decoder_rejects_v1_snapshot() -> None:
    payload = b'{"schema_version":"project-relationship-snapshot-v1"}'

    with pytest.raises(SnapshotDecodeError):
        decode_project_snapshot(payload)
```

- [ ] **Step 2: 기존 v1 codec 테스트에서 실패 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_snapshot_codec.py -v`

Expected: v1 fixture와 새 v2 기대값 불일치로 FAIL.

- [ ] **Step 3: backend 모델과 codec 교체**

`models.py`에서 v1 candidate/status dataclass를 제거하고 장면 저장 단위를 정의한다.

```python
from dataclasses import dataclass

from narrative_analysis_agent import KnowledgeGraphOutput


@dataclass(frozen=True, slots=True)
class SceneGraphRecord:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    graph: KnowledgeGraphOutput
```

codec은 Pydantic public model을 canonical JSON으로 encode하고 strict validate한다.

```python
def encode_project_snapshot(snapshot: ProjectKnowledgeGraphSnapshot) -> bytes:
    validate_project_snapshot(snapshot)
    data = snapshot.model_dump(mode="json")
    return (
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def decode_project_snapshot(payload: bytes) -> ProjectKnowledgeGraphSnapshot:
    try:
        snapshot = ProjectKnowledgeGraphSnapshot.model_validate_json(payload, strict=True)
        validate_project_snapshot(snapshot)
        return snapshot
    except (UnicodeDecodeError, ValidationError, ValueError) as error:
        raise SnapshotDecodeError("invalid project knowledge graph snapshot") from error
```

`validate_project_snapshot()`은 project ID, document chapter ID 유일성, 전체 character/location/
event/relation ID 유일성, parent/reference 존재와 올바른 종류, relation/movement/coreference
참조, snapshot version과 confidence를 하나의 함수에서 검증한다.

- [ ] **Step 4: codec tests 통과 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_snapshot_codec.py -v`

Expected: PASS.

- [ ] **Step 5: v2 contract 커밋**

```sh
git add backend/apps/narrative_memory/service/models.py \
  backend/apps/narrative_memory/service/snapshot_codec.py \
  backend/apps/narrative_memory/service/validation.py \
  backend/tests/narrative_memory/test_snapshot_codec.py
git commit -m "기능: 프로젝트 지식 그래프 v2 계약 추가"
```

---

### Task 5: backend 결정적 청크·장면·프로젝트 병합

**Files:**
- Modify: `backend/apps/narrative_memory/service/merge.py`
- Modify: `backend/tests/narrative_memory/test_merge.py`

**Interfaces:**
- Consumes: `SceneAnalysis`, existing `ProjectKnowledgeGraphSnapshot`, tuple of existing `SceneGraphRecord`
- Produces: `assemble_scene_graph(analysis, existing) -> SceneGraphRecord`, `rebuild_project_graph(project_id, version, scenes) -> ProjectKnowledgeGraphSnapshot`

- [ ] **Step 1: 결정적 병합 실패 테스트 작성**

다음 독립 사례를 테스트한다.

- 두 청크의 같은 canonical name/alias가 하나의 character로 합쳐짐
- 기존 프로젝트 character ID 재사용
- 동일 이름이지만 alias/evidence 연결이 불충분하면 분리되고 `POSSIBLE_SAME_AS` 유지
- relation, event, movement와 coreference의 모든 로컬 참조 재매핑
- 같은 scene 재분석은 기존 `SceneGraphRecord`를 교체하고 다른 scene은 유지
- 입력 청크/컬렉션 순서를 바꿔도 최종 canonical project snapshot이 동일
- 관계 `active`/`ended` 기록이 함께 보존

```python
def test_scene_merge_reuses_existing_character_id_and_rewrites_references() -> None:
    existing = project_with_character("character_007", "서윤", aliases=("한서윤",))
    analysis = analysis_with_local_character_and_relation(
        local_id="character_001",
        canonical_name="한서윤",
        relation_target="character_002",
    )

    scene = assemble_scene_graph(analysis, existing)

    assert scene.graph.entities.characters[0].id == "character_007"
    assert scene.graph.relations[0].source_id == "character_007"
```

- [ ] **Step 2: 기존 v1 merge에서 실패 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_merge.py -v`

Expected: 새 public graph 타입 또는 새 merge function import에서 FAIL.

- [ ] **Step 3: 장면 병합 구현**

`merge.py`의 v1 후보 상태·absolute evidence 알고리즘을 제거한다. 다음 공개 함수와 작은
pure helper로 교체한다.

```python
def assemble_scene_graph(
    analysis: SceneAnalysis,
    existing: ProjectKnowledgeGraphSnapshot,
) -> SceneGraphRecord:
    character_map = _character_id_map(analysis.chunks, existing)
    location_map = _location_id_map(analysis.chunks, existing)
    event_map = _event_id_map(analysis.chunks, existing, character_map, location_map)
    graph = KnowledgeGraphOutput(
        document=_merge_documents(analysis.scene_id, analysis.chunks),
        entities=Entities(
            characters=_merge_characters(analysis.chunks, character_map),
            locations=_merge_locations(analysis.chunks, location_map),
            events=_merge_events(analysis.chunks, event_map, character_map, location_map),
        ),
        relations=_merge_relations(analysis.chunks, character_map, location_map, event_map),
        movements=_merge_movements(analysis.chunks, character_map, location_map, event_map),
        coreferences=_merge_coreferences(analysis.chunks, character_map, location_map),
        unresolved_references=_merge_unresolved(analysis.chunks, character_map, location_map),
        contradictions=_merge_contradictions(analysis.chunks, character_map, location_map),
    )
    return SceneGraphRecord(
        project_id=analysis.project_id,
        scene_id=analysis.scene_id,
        scene_revision=analysis.scene_revision,
        scene_sequence=analysis.scene_sequence,
        graph=graph,
    )
```

ID helper는 기존 graph의 normalized canonical name과 aliases가 유일하게 교차할 때 기존 ID를
재사용한다. 신규 ID는 evidence가 처음 발견되는 `(chunk.ordinal, chunk.text.find(evidence),
normalized_name)` 순서로 정렬하고 종류별 기존 최대 숫자 다음 번호를 3자리 zero padding으로
할당한다. 청크 로컬 ID map의 key는 반드시 `(chunk.ordinal, local_id)`로 두어 서로 다른
청크가 같은 `character_001` 값을 사용해도 충돌하지 않게 한다. 기존 프로젝트 ID는 local
map을 거치지 않고 그대로 보존한다. 같은 토큰이 여러 기존 ID와 연결되면 자동 병합하지
않는다.

`_merge_documents()`는 청크 순서대로 summary 문장을 중복 제거해 최대 4문장으로 제한한다.
narrative time이 모두 같으면 그 값, 다르면 `mixed`, 값이 없으면 `unknown`을 사용한다.

- [ ] **Step 4: 프로젝트 재구성 구현**

```python
def rebuild_project_graph(
    project_id: str,
    snapshot_version: int,
    scenes: tuple[SceneGraphRecord, ...],
) -> ProjectKnowledgeGraphSnapshot:
    ordered = tuple(sorted(scenes, key=lambda item: (item.scene_sequence, item.scene_id)))
    snapshot = ProjectKnowledgeGraphSnapshot(
        project_id=project_id,
        snapshot_version=snapshot_version,
        schema_version=PROJECT_GRAPH_SCHEMA_VERSION,
        documents=tuple(item.graph.document for item in ordered),
        entities=_aggregate_entities(ordered),
        relations=_aggregate_relations(ordered),
        movements=_aggregate_movements(ordered),
        coreferences=_aggregate_coreferences(ordered),
        unresolved_references=_aggregate_unresolved(ordered),
        contradictions=_aggregate_contradictions(ordered),
    )
    validate_project_snapshot(snapshot)
    return snapshot
```

집계 helper는 최종 ID와 의미 필드 전체를 key로 사용해 exact duplicate만 제거하고 scene
순서를 보존한다. 장면 provenance는 repository의 `SceneGraphRecord`로 유지한다.

- [ ] **Step 5: merge tests 통과 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_merge.py -v`

Expected: PASS.

- [ ] **Step 6: merge 커밋**

```sh
git add backend/apps/narrative_memory/service/merge.py \
  backend/tests/narrative_memory/test_merge.py
git commit -m "기능: 청크 지식 그래프 결정적 병합 추가"
```

---

### Task 6: v2 장면·프로젝트 SQLite 원자적 저장

**Files:**
- Modify: `backend/apps/narrative_memory/repository/snapshot_repository.py`
- Modify: `backend/apps/narrative_memory/repository/sqlite_snapshot_repository.py`
- Modify: `backend/tests/narrative_memory/test_sqlite_snapshot_repository.py`

**Interfaces:**
- Consumes: `SceneGraphRecord`, `ProjectKnowledgeGraphSnapshot`, v2 codec
- Produces: `get_scene_graphs(project_id)`, `commit_scene(expected_version, scene, snapshot)`, 기존 `get_current()` read contract

- [ ] **Step 1: v2 schema와 원자성 실패 테스트 작성**

초기화가 `scene_knowledge_graphs`, `project_snapshots`, `current_project_snapshots`를 만들고,
scene/project가 한 transaction에서 저장되는지 검증한다. expected version mismatch, scene
payload/hash 손상, project payload/hash 손상과 중간 INSERT 실패 rollback도 검증한다.

```python
def test_commit_scene_writes_scene_and_project_atomically(tmp_path: Path) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    scene = scene_record("project-01", "scene-01", revision=1)
    snapshot = project_snapshot("project-01", version=0, scenes=(scene,))

    stored = repository.commit_scene(None, scene, snapshot)

    assert stored.snapshot == snapshot
    assert repository.get_scene_graphs("project-01") == (scene,)
    assert repository.get_current("project-01").snapshot == snapshot
```

- [ ] **Step 2: repository tests 실패 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_sqlite_snapshot_repository.py -v`

Expected: `commit_scene` 또는 v2 schema assertion에서 FAIL.

- [ ] **Step 3: repository port 갱신**

```python
class SnapshotRepository(Protocol):
    def initialize(self) -> None:
        raise NotImplementedError

    def get_current(self, project_id: str) -> StoredProjectSnapshot | None:
        raise NotImplementedError

    def get_scene_graphs(self, project_id: str) -> tuple[SceneGraphRecord, ...]:
        raise NotImplementedError

    def commit_scene(
        self,
        expected_version: int | None,
        scene: SceneGraphRecord,
        snapshot: ProjectKnowledgeGraphSnapshot,
    ) -> StoredProjectSnapshot:
        raise NotImplementedError
```

- [ ] **Step 4: SQLite v2 schema와 atomic commit 구현**

기존 v1 DB가 삭제된 전제에서 `initialize()`는 다음 v2 table을 생성한다.

```sql
CREATE TABLE IF NOT EXISTS scene_knowledge_graphs (
    project_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    scene_revision INTEGER NOT NULL,
    scene_sequence INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    payload BLOB NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, scene_id)
);
```

기존 `project_snapshots`와 `current_project_snapshots` table 이름은 유지하되 payload는 v2만
허용한다. `commit_scene()`은 `BEGIN IMMEDIATE`, current version 비교, scene upsert,
project snapshot insert, pointer upsert를 하나의 transaction에서 수행한다. scene revision이
기존보다 크지 않으면 rollback하고 `SnapshotVersionConflict`를 발생시킨다.

- [ ] **Step 5: repository focused tests 통과 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_sqlite_snapshot_repository.py -v`

Expected: PASS.

- [ ] **Step 6: repository 커밋**

```sh
git add backend/apps/narrative_memory/repository/snapshot_repository.py \
  backend/apps/narrative_memory/repository/sqlite_snapshot_repository.py \
  backend/tests/narrative_memory/test_sqlite_snapshot_repository.py
git commit -m "기능: 지식 그래프 v2 원자적 저장 추가"
```

---

### Task 7: backend 분석·병합·저장 workflow와 구성

**Files:**
- Modify: `backend/apps/narrative_memory/service/scene_analysis_use_case.py`
- Modify: `backend/apps/narrative_memory/composition.py`
- Modify: `backend/tests/narrative_memory/test_scene_analysis_use_case.py`
- Modify: `backend/tests/narrative_memory/test_agent_composition.py`

**Interfaces:**
- Consumes: `NarrativeAnalysisAgent`, `SnapshotRepository`, `assemble_scene_graph()`, `rebuild_project_graph()`
- Produces: `AnalyzeSceneUseCase.execute(input) -> SceneAnalysis`, configured reader/writer using one DB path

- [ ] **Step 1: 저장 workflow 실패 테스트 작성**

agent 성공 후 repository current version이 `analysis.source_snapshot_version`과 일치할 때 scene과
project가 저장되는지 검증한다. mismatch, merge failure와 commit failure는 sanitized
`SceneAnalysisApplicationError`이고 commit을 남기지 않아야 한다.

```python
def test_use_case_persists_scene_and_project_after_successful_analysis() -> None:
    analysis = scene_analysis(source_snapshot_version=0)
    repository = RecordingSnapshotRepository(current=None, scenes=())
    use_case = AnalyzeSceneUseCase(RecordingAgent(analysis), repository)

    result = asyncio.run(use_case.execute(analyze_input()))

    assert result is analysis
    assert len(repository.commits) == 1
    expected_version, scene, project = repository.commits[0]
    assert expected_version is None
    assert scene.scene_id == "scene-01"
    assert project.snapshot_version == 0
```

- [ ] **Step 2: workflow tests 실패 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_use_case.py tests/narrative_memory/test_agent_composition.py -v`

Expected: 새 repository dependency 또는 graph path argument에서 FAIL.

- [ ] **Step 3: use case 구현**

known identity 입력을 제거하고 agent 성공 후에만 저장 경계를 호출한다.

```python
class AnalyzeSceneUseCase:
    def __init__(self, agent: SceneAnalysisFacade, repository: SnapshotRepository) -> None:
        self._agent = agent
        self._repository = repository

    async def execute(self, input_value: AnalyzeSceneInput) -> SceneAnalysis:
        try:
            analysis = await self._agent.analyze_scene(
                SceneAnalysisRequest(
                    project_id=input_value.project_id,
                    scene_id=input_value.scene_id,
                    scene_revision=input_value.scene_revision,
                    scene_sequence=input_value.scene_sequence,
                    text=input_value.text,
                )
            )
            current = self._repository.get_current(input_value.project_id)
            current_version = None if current is None else current.snapshot.snapshot_version
            if (0 if current_version is None else current_version) != analysis.source_snapshot_version:
                raise SnapshotVersionConflict("analysis used a stale project graph")
            existing = (
                ProjectKnowledgeGraphSnapshot.empty(input_value.project_id)
                if current is None
                else current.snapshot
            )
            scene = assemble_scene_graph(analysis, existing)
            scenes = tuple(
                item for item in self._repository.get_scene_graphs(input_value.project_id)
                if item.scene_id != scene.scene_id
            ) + (scene,)
            next_version = 0 if current_version is None else current_version + 1
            project = rebuild_project_graph(input_value.project_id, next_version, scenes)
            self._repository.commit_scene(current_version, scene, project)
            return analysis
        except asyncio.CancelledError:
            raise
        except (NarrativeAnalysisError, MergeInvariantError, SnapshotVersionConflict):
            raise SceneAnalysisApplicationError("scene analysis failed") from None
```

- [ ] **Step 4: 동일 DB 경로 구성 구현**

```python
def build_narrative_analysis_agent(
    *, model_name: str, prompt_path: Path, project_graph_path: Path
) -> NarrativeAnalysisAgent:
    return NarrativeAnalysisAgent(
        model_name,
        prompt_path=prompt_path,
        project_graph_path=project_graph_path,
    )


def build_analyze_scene_use_case(
    *, model_name: str, prompt_path: Path, project_graph_path: Path
) -> AnalyzeSceneUseCase:
    repository = SQLiteSnapshotRepository(project_graph_path)
    repository.initialize()
    agent = build_narrative_analysis_agent(
        model_name=model_name,
        prompt_path=prompt_path,
        project_graph_path=project_graph_path,
    )
    return AnalyzeSceneUseCase(agent, repository)
```

초기화는 backend가 먼저 수행하고 agent는 같은 path를 read-only로만 연다.

- [ ] **Step 5: workflow와 composition tests 통과 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_use_case.py tests/narrative_memory/test_agent_composition.py -v`

Expected: PASS.

- [ ] **Step 6: workflow 커밋**

```sh
git add backend/apps/narrative_memory/service/scene_analysis_use_case.py \
  backend/apps/narrative_memory/composition.py \
  backend/tests/narrative_memory/test_scene_analysis_use_case.py \
  backend/tests/narrative_memory/test_agent_composition.py
git commit -m "기능: 장면 분석 결과 프로젝트 저장 연결"
```

---

### Task 8: v1 reset, 문서 동기화와 전체 검증

**Files:**
- Modify: `docs/domains/narrative-memory.md`
- Modify: `llm-agent/AGENTS.md`
- Modify: `llm-agent/docs/llm-agent-coding-rules.md`
- Modify: `backend/docs/backend-coding-rules.md`
- Modify: `backend/README.md`

**Interfaces:**
- Consumes: Tasks 1-7의 최종 public/ownership contracts
- Produces: 구현과 일치하는 domain 및 engineering documentation, 검증 evidence

- [ ] **Step 1: 삭제 대상 DB를 읽기 전용으로 확인**

Run:

```sh
rg -n "SQLiteSnapshotRepository|project_graph_path|narrative-memory.*sqlite" \
  backend llm-agent -g '*.py' -g '*.md'
```

Expected: 테스트 `tmp_path` 외의 실제 configured 파일이 있으면 정확한 절대 경로가 한 개로
식별된다. 실제 configured 파일이 없으면 삭제 대상 없음으로 기록하고 임의의 DB나 테스트
fixture를 삭제하지 않는다.

- [ ] **Step 2: 승인된 기존 DB만 한 번 삭제**

실제 configured 파일이 확인된 경우에만 경로가 workspace root, home 또는 광범위한 디렉터리가
아닌 단일 SQLite 파일인지 검증한 뒤 복구 불가능한 삭제임을 기록하고 그 파일만 삭제한다.
파일이 없으면 이 단계는 no-op으로 기록한다. 런타임 삭제 코드는 작성하지 않는다.

- [ ] **Step 3: domain 및 프로젝트 문서 갱신**

`docs/domains/narrative-memory.md`에 다음 v2 의미를 명시한다.

- 분석 결과는 exact 지식 그래프를 담은 순서 보존 청크 튜플
- 일반 후보 confidence 최소 0.8과 unresolved 분리
- agent는 project graph read-only, backend는 ID/merge/write owner
- 300/50, 단일 호출, no partial result
- v1 후보 상태·absolute evidence 계약 제거
- backend의 장면별 provenance와 versioned project snapshot

`llm-agent` 문서는 read-only 조회만 예외로 허용하고 audit, retry, write, durable ID,
cross-chunk merge 금지를 유지한다. backend 문서는 v2 merge/codec/repository와 동일 path 구성,
README는 다음 호출 예시를 제공한다.

```python
use_case = build_analyze_scene_use_case(
    model_name="provider:model",
    prompt_path=packaged_prompt_path(),
    project_graph_path=data_root / "narrative-memory.sqlite3",
)
```

- [ ] **Step 4: 제거된 v1 계약 잔존 참조 검사**

Run:

```sh
rg -n "CandidateStatus|SceneRelationshipSnapshot|ProjectRelationshipSnapshot|ChunkExtraction|known_entities|known_places" \
  llm-agent/src backend/apps/narrative_memory llm-agent/tests backend/tests/narrative_memory
```

Expected: 의도적으로 남긴 과거 `docs/superpowers/` 기록 외 production/test 참조 0건.

- [ ] **Step 5: llm-agent 전체 검증**

Run:

```sh
cd llm-agent
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: 모든 명령 exit 0, live 테스트만 deselected.

- [ ] **Step 6: backend 전체 검증**

Run:

```sh
cd backend
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: 모든 명령 exit 0.

- [ ] **Step 7: domain diff와 구현 일치 확인**

Run:

```sh
git diff -- docs/domains/narrative-memory.md \
  llm-agent/src/narrative_analysis_agent \
  backend/apps/narrative_memory
```

Expected: 문서의 read/write 소유권, confidence, chunk, ID와 snapshot 불변 조건이 구현과
동일하고 v1 의미가 남아 있지 않음.

- [ ] **Step 8: 문서와 최종 동기화 커밋**

```sh
git add docs/domains/narrative-memory.md llm-agent/AGENTS.md \
  llm-agent/docs/llm-agent-coding-rules.md \
  backend/docs/backend-coding-rules.md backend/README.md
git commit -m "문서: 지식 그래프 v2 소유권 동기화"
```

- [ ] **Step 9: feature-development review와 최종 검증 handoff 준비**

구현자는 affected llm-agent entry point `NarrativeAnalysisAgent.analyze_scene`, backend entry
point `AnalyzeSceneUseCase.execute`, spec/plan revision, 모든 verification output과 DB reset
결과를 main agent에 전달한다. main agent는 substantial backend review를 실행하고 accepted
finding을 모두 해결한 뒤 같은 전체 명령을 다시 실행한다. frontend와 OpenAPI review는
영향이 없으므로 실행하지 않는다.
