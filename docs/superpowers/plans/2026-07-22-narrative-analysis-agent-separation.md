# Narrative Analysis Agent 분리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Narrative Memory의 장면 LLM 분석을 독립 `llm-agent` Python 패키지로 옮기고 backend가 provider-independent typed facade만 호출하게 한다.

**Architecture:** `narrative_analysis_agent` 패키지가 Pydantic AI 청크 추출, 프롬프트, 감사, 결정적 번역과 장면 청크 병합을 캡슐화한다. backend는 패키지의 공개 request/result/error와 `NarrativeAnalysisAgent.analyze_scene()`만 사용하며 프로젝트 스냅샷 저장과 장면-프로젝트 병합은 계속 소유한다.

**Tech Stack:** Python 3.13, uv, Pydantic AI 2.x, Pydantic 2.x, SQLite, pytest, Ruff

## Global Constraints

- Authoritative design: `docs/superpowers/specs/2026-07-22-narrative-analysis-agent-separation-design.md`.
- 새 프로젝트 디렉터리는 `llm-agent/`, 배포 이름은 `narrative-analysis-agent`, import 이름은 `narrative_analysis_agent`다.
- Pydantic AI는 청크별 구조화 추출에만 사용한다. 청크 분할, 번역, stable ID, `pending` 상태와 병합은 결정적 코드다.
- 청크는 최대 300자, 50자 중첩, 250자 stride이며 숫자 순서대로 직렬 분석한다.
- provider 호출 실패만 청크별 최대 두 번 시도한다. 스키마 또는 evidence 검증 실패는 재시도하지 않는다.
- 공개 계약은 Pydantic AI, Pydantic, FastAPI와 SQLite를 import하지 않는다.
- `llm-agent`가 프롬프트와 owner-only LLM 감사 SQLite를 소유한다.
- 한 청크가 최종 실패하거나 성공 감사 기록이 실패하면 부분 또는 성공 결과를 반환하지 않는다.
- backend는 프로젝트 스냅샷 저장, 재분석과 장면-프로젝트 병합을 계속 소유한다.
- consumer-facing HTTP API와 OpenAPI 변경은 없다.
- 기본 검증은 네트워크 없이 실행한다. 실제 모델 검증은 `RUN_LLM_LIVE_TESTS=1`인 `live` marker에서만 실행한다.
- 커밋 메시지는 한국어로 작성한다.
- 기존 사용자 변경을 보존하고 `AGENTS.md`, `input.txt`, `relationships.json`의 현재 내용을 덮어쓰지 않는다.

---

## File Structure

### 새 `llm-agent` 프로젝트

- `llm-agent/pyproject.toml`: 독립 runtime/dev dependency, pytest marker와 Ruff 설정.
- `llm-agent/uv.lock`: 독립 패키지 잠금 파일.
- `llm-agent/AGENTS.md`: 프로젝트 범위, 필수 문서, 검증과 소유권 지침.
- `llm-agent/docs/llm-agent-coding-rules.md`: provider 격리, 공개 계약, 감사와 테스트 규칙.
- `llm-agent/src/narrative_analysis_agent/contracts.py`: stdlib-only 공개 request/result/snapshot/error-safe DTO.
- `llm-agent/src/narrative_analysis_agent/errors.py`: 공개 오류 계층.
- `llm-agent/src/narrative_analysis_agent/config.py`: 모델, prompt root와 audit path 구성.
- `llm-agent/src/narrative_analysis_agent/facade.py`: 단일 공개 `NarrativeAnalysisAgent`.
- `llm-agent/src/narrative_analysis_agent/orchestrator.py`: run 생명주기, 직렬 청크 실행, 재시도와 원자성.
- `llm-agent/src/narrative_analysis_agent/chunking.py`: 정규 장면 청크.
- `llm-agent/src/narrative_analysis_agent/extraction/schemas.py`: 엄격한 Pydantic provider 출력.
- `llm-agent/src/narrative_analysis_agent/extraction/agent.py`: Pydantic AI와 scripted 청크 분석기.
- `llm-agent/src/narrative_analysis_agent/extraction/prompts.py`: prompt registry와 user prompt 렌더링.
- `llm-agent/src/narrative_analysis_agent/assembly/models.py`: provider-independent 내부 청크 분석 타입.
- `llm-agent/src/narrative_analysis_agent/assembly/translation.py`: 상대 evidence 번역과 stable ID.
- `llm-agent/src/narrative_analysis_agent/assembly/merge.py`: 청크 분석에서 장면 snapshot으로의 결정적 병합.
- `llm-agent/src/narrative_analysis_agent/assembly/validation.py`: 장면 분석 입력·출력 불변 조건.
- `llm-agent/src/narrative_analysis_agent/audit/ports.py`: prompt/run/attempt 감사 이벤트와 port.
- `llm-agent/src/narrative_analysis_agent/audit/sqlite.py`: owner-only append-only SQLite 구현.
- `llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md`: versioned system prompt.
- `llm-agent/tests/unit/`: 공개 계약, 청크, schema, 번역, 병합, prompt와 감사 테스트.
- `llm-agent/tests/integration/test_scene_analysis_offline.py`: 공개 facade 전체 오프라인 acceptance.
- `llm-agent/tests/live/test_scene_analysis_live.py`: opt-in 실제 모델 평가.

### backend 유지·변경 파일

- `backend/apps/narrative_memory/service/models.py`: 프로젝트 snapshot과 프로젝트 병합에 필요한 backend 도메인 타입 유지.
- `backend/apps/narrative_memory/service/merge.py`: `merge_scene_into_project`와 프로젝트 병합 helper만 유지.
- `backend/apps/narrative_memory/service/validation.py`: 프로젝트 snapshot 검증 유지.
- `backend/apps/narrative_memory/service/snapshot_codec.py`: 프로젝트 snapshot codec 유지.
- `backend/apps/narrative_memory/composition.py`: 공개 agent config/facade 조립만 담당.
- `backend/apps/narrative_memory/service/scene_analysis_result.py`: 공개 snapshot DTO를 기존 backend 프로젝트 병합 모델로 한 번 변환.
- `backend/pyproject.toml`, `backend/uv.lock`: 로컬 agent 패키지 의존성으로 전환하고 직접 `pydantic-ai` 제거.
- `backend/tests/narrative_memory/test_agent_composition.py`: backend의 얇은 소비 계약 검증.
- `backend/tests/narrative_memory/test_scene_analysis_result.py`: 공개 결과에서 backend 장면 모델로의 경계 변환 검증.
- `backend/tests/narrative_memory/test_merge.py`: 프로젝트 병합 테스트만 유지.
- `backend/tests/narrative_memory/test_snapshot_codec.py`, `test_sqlite_snapshot_repository.py`: backend persistence 회귀 유지.

### 제거되는 backend 소유 파일

- `backend/apps/narrative_memory/service/chunking.py`
- `backend/apps/narrative_memory/service/scene_analysis.py`
- `backend/apps/narrative_memory/service/scene_analysis_ports.py`
- `backend/apps/narrative_memory/service/scene_analysis_translation.py`
- `backend/apps/narrative_memory/service/scene_analysis_types.py`
- `backend/apps/narrative_memory/repository/analysis_audit.py`
- `backend/infrastructure/llm/`
- `backend/infrastructure/audit/sqlite_agent_audit.py`
- `backend/prompts/`
- 이동된 책임만 검증하던 `backend/tests/narrative_memory/test_chunking.py`, `test_prompt_registry.py`, `test_scene_analysis_agents.py`, `test_scene_analysis_factory.py`, `test_scene_analysis_service.py`, `test_scene_analysis_translation.py`, `test_sqlite_agent_audit.py`
- `backend/tests/writing_assistant/test_text_generation_port.py`의 Pydantic AI 설치 확인 테스트

---

### Task 1: 독립 패키지와 stdlib-only 공개 계약

**Files:**
- Create: `llm-agent/pyproject.toml`
- Create: `llm-agent/AGENTS.md`
- Create: `llm-agent/docs/llm-agent-coding-rules.md`
- Create: `llm-agent/src/narrative_analysis_agent/__init__.py`
- Create: `llm-agent/src/narrative_analysis_agent/contracts.py`
- Create: `llm-agent/src/narrative_analysis_agent/errors.py`
- Create: `llm-agent/src/narrative_analysis_agent/config.py`
- Test: `llm-agent/tests/unit/test_contracts.py`

**Interfaces:**
- Consumes: Python 3.13 stdlib only for public contracts.
- Produces: `KnownIdentity`, `SceneAnalysisRequest`, `Evidence`, candidate/event DTOs, `SceneRelationshipSnapshot`, `SceneAnalysisResult`, `NarrativeAnalysisConfig`, and the public error hierarchy.

- [ ] **Step 1: Write the failing public-contract test**

```python
from dataclasses import FrozenInstanceError

import pytest

from narrative_analysis_agent import (
    KnownIdentity,
    SceneAnalysisRequest,
    SceneAnalysisResult,
    SceneRelationshipSnapshot,
)


def test_public_contract_is_immutable_and_provider_independent() -> None:
    request = SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=7,
        text="서윤이 도착했다.",
        known_entities=(KnownIdentity("character:seoyun", "서윤", "서윤"),),
    )
    snapshot = SceneRelationshipSnapshot.empty("scene-01", 1, 7)
    result = SceneAnalysisResult(run_id="run-01", snapshot=snapshot)

    assert result.snapshot.schema_version == "scene-relationship-snapshot-v1"
    with pytest.raises(FrozenInstanceError):
        request.text = "changed"  # type: ignore[misc]
```

- [ ] **Step 2: Run the contract test and verify RED**

Run from `llm-agent/`:

```sh
mise exec -- uv run pytest tests/unit/test_contracts.py -v
```

Expected: FAIL during collection because `narrative_analysis_agent` does not exist.

- [ ] **Step 3: Create package metadata and public contracts**

Use this dependency boundary in `llm-agent/pyproject.toml`:

```toml
[project]
name = "narrative-analysis-agent"
version = "0.1.0"
requires-python = ">=3.13,<3.14"
dependencies = ["pydantic-ai>=2.9.1,<3"]

[dependency-groups]
dev = ["pytest>=8.4,<10", "ruff>=0.12,<1"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
markers = ["live: calls a configured external LLM provider"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Define immutable stdlib dataclasses in `contracts.py`. The required public signatures are:

```python
@dataclass(frozen=True, slots=True)
class KnownIdentity:
    identity_key: str
    normalized_name: str
    display_name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SceneAnalysisRequest:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    text: str
    known_entities: tuple[KnownIdentity, ...] = ()
    known_places: tuple[KnownIdentity, ...] = ()


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

    @classmethod
    def empty(cls, scene_id: str, revision: int, sequence: int) -> "SceneRelationshipSnapshot":
        return cls(
            scene_id=scene_id,
            scene_revision=revision,
            scene_sequence=sequence,
            schema_version="scene-relationship-snapshot-v1",
            summary="",
            entities=(),
            places=(),
            relationship_events=(),
            location_events=(),
        )


@dataclass(frozen=True, slots=True)
class SceneAnalysisResult:
    run_id: str
    snapshot: SceneRelationshipSnapshot
```

Define all nested DTOs with the exact fields from `scene-relationship-snapshot-v1`. Define `CandidateStatus` and `LocationEventType` as `StrEnum`. Export only public facade, config, contracts, and errors from `__init__.py`.

- [ ] **Step 4: Define public errors and configuration**

```python
class NarrativeAnalysisError(RuntimeError):
    def __init__(self, message: str, *, run_id: str | None = None) -> None:
        super().__init__(message)
        self.run_id = run_id


class AnalysisConfigurationError(NarrativeAnalysisError):
    pass


class PromptLoadError(NarrativeAnalysisError):
    pass


class ProviderUnavailableError(NarrativeAnalysisError):
    pass


class InvalidExtractionError(NarrativeAnalysisError):
    pass


class AnalysisAuditError(NarrativeAnalysisError):
    pass
```

```python
@dataclass(frozen=True, slots=True)
class NarrativeAnalysisConfig:
    model_name: str
    prompt_root: Path
    audit_path: Path
```

- [ ] **Step 5: Run package contract checks and verify GREEN**

```sh
mise exec -- uv lock
mise exec -- uv run pytest tests/unit/test_contracts.py -v
mise exec -- uv run ruff check src tests/unit/test_contracts.py
mise exec -- uv run ruff format --check src tests/unit/test_contracts.py
```

Expected: contract test passes; lint and format report no errors.

- [ ] **Step 6: Commit**

```sh
git add llm-agent
git commit -m "기능: 분석 에이전트 공개 계약 추가"
```

---

### Task 2: 결정적 청크·번역·장면 병합 코어 이동

**Files:**
- Create: `llm-agent/src/narrative_analysis_agent/chunking.py`
- Create: `llm-agent/src/narrative_analysis_agent/assembly/models.py`
- Create: `llm-agent/src/narrative_analysis_agent/assembly/translation.py`
- Create: `llm-agent/src/narrative_analysis_agent/assembly/merge.py`
- Create: `llm-agent/src/narrative_analysis_agent/assembly/validation.py`
- Create: `llm-agent/src/narrative_analysis_agent/assembly/__init__.py`
- Test: `llm-agent/tests/unit/test_chunking.py`
- Test: `llm-agent/tests/unit/test_translation.py`
- Test: `llm-agent/tests/unit/test_scene_merge.py`
- Reference: `backend/apps/narrative_memory/service/chunking.py`
- Reference: `backend/apps/narrative_memory/service/scene_analysis_translation.py`
- Reference: `backend/apps/narrative_memory/service/merge.py`
- Reference: `backend/tests/narrative_memory/test_chunking.py`
- Reference: `backend/tests/narrative_memory/test_scene_analysis_translation.py`
- Reference: scene-only cases in `backend/tests/narrative_memory/test_merge.py`

**Interfaces:**
- Consumes: `SceneAnalysisRequest` and provider-independent `SceneChunkExtraction`.
- Produces: `chunk_scene()`, `translate_chunk_extraction()`, `merge_chunk_analyses()`, and validated public `SceneRelationshipSnapshot`.

- [ ] **Step 1: Move focused tests first and verify RED**

Copy the existing chunking and translation tests into the new test paths, changing imports only to `narrative_analysis_agent`. Extract from `test_merge.py` only tests whose entry point is `merge_chunk_analyses`; leave every `merge_scene_into_project`, project snapshot and repository test in backend.

```sh
mise exec -- uv run pytest \
  tests/unit/test_chunking.py \
  tests/unit/test_translation.py \
  tests/unit/test_scene_merge.py -v
```

Expected: FAIL because the new modules and functions do not exist.

- [ ] **Step 2: Move the canonical chunk implementation**

Preserve these exact constants and move the current `chunk_scene` body without semantic changes:

```python
MAX_CHUNK_CHARACTERS = 300
CHUNK_OVERLAP_CHARACTERS = 50
CHUNK_STRIDE_CHARACTERS = 250
```

Keep chunk IDs as `{scene_id}:r{revision}:{ordinal:04d}` and the existing SHA-256 content hash.

- [ ] **Step 3: Move provider-independent extraction and translation types**

Move `RelativeEvidence`, extracted entity/place/event types, `SceneChunkExtraction`, `ChunkAnalysis`, and their enums into `assembly/models.py`. They must import neither Pydantic nor Pydantic AI.

Preserve this translation interface and move the complete existing implementation plus its private helpers:

```python
def translate_chunk_extraction(
    chunk: SceneChunk,
    scene_sequence: int,
    extraction: SceneChunkExtraction,
    known_entities: tuple[KnownIdentity, ...],
    known_places: tuple[KnownIdentity, ...],
) -> ChunkAnalysis
```

Translation must validate relative ranges against the immutable chunk, convert them to absolute offsets, assign `pending`, and retain the current SHA-256 stable-ID payload.

- [ ] **Step 4: Extract scene-only merge and validation**

Move only the chunk-to-scene path and helpers needed by it. Preserve the public entry-point name, parameters, and return type shown below, and move its complete existing body:

```python
def merge_chunk_analyses(
    scene_id: str,
    scene_revision: int,
    scene_sequence: int,
    analyses: Iterable[ChunkAnalysis],
) -> SceneRelationshipSnapshot
```

Do not move `ProjectRelationshipSnapshot`, `merge_scene_into_project`, approval downgrade rules, project identity clustering or project persistence validation. Move the complete `merge_chunk_analyses` implementation and only the private helpers reachable from it. Convert the internal scene result to the public contract DTO before returning it.

- [ ] **Step 5: Run deterministic core tests and compare backend regression**

```sh
mise exec -- uv run pytest \
  tests/unit/test_chunking.py \
  tests/unit/test_translation.py \
  tests/unit/test_scene_merge.py -v
cd ../backend
mise exec -- uv run pytest \
  tests/narrative_memory/test_chunking.py \
  tests/narrative_memory/test_scene_analysis_translation.py \
  tests/narrative_memory/test_merge.py -q
```

Expected: new package tests pass and original backend tests remain green before cleanup.

- [ ] **Step 6: Commit**

```sh
git add llm-agent
git commit -m "리팩터: 결정적 장면 분석 코어 분리"
```

---

### Task 3: Pydantic 청크 분석기와 hot-loaded prompt 이동

**Files:**
- Create: `llm-agent/src/narrative_analysis_agent/extraction/__init__.py`
- Create: `llm-agent/src/narrative_analysis_agent/extraction/schemas.py`
- Create: `llm-agent/src/narrative_analysis_agent/extraction/agent.py`
- Create: `llm-agent/src/narrative_analysis_agent/extraction/prompts.py`
- Create: `llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md`
- Test: `llm-agent/tests/unit/test_extraction_agent.py`
- Test: `llm-agent/tests/unit/test_prompts.py`
- Reference: `backend/infrastructure/llm/scene_analysis_schemas.py`
- Reference: `backend/infrastructure/llm/pydantic_ai_scene_analysis.py`
- Reference: `backend/infrastructure/llm/scripted_scene_analysis.py`
- Reference: `backend/infrastructure/llm/prompt_registry.py`
- Reference: `backend/prompts/scene-analysis/system.md`

**Interfaces:**
- Consumes: internal `ChunkAnalysisCall(system_prompt, user_prompt, chunk_id)`.
- Produces: `ChunkAnalyzerPort.analyze() -> ChunkInvocationResult`, strict `ChunkExtractionOutput`, `PydanticAIChunkAnalyzer`, `ScriptedChunkAnalyzer`, and `FilePromptRegistry`.

- [ ] **Step 1: Move provider schema and adapter tests first**

Port current schema, `TestModel`, scripted sequence and sanitized provider-error cases into `test_extraction_agent.py`. Port prompt metadata, traversal, hot-load and stable JSON rendering cases into `test_prompts.py`.

```sh
mise exec -- uv run pytest tests/unit/test_extraction_agent.py tests/unit/test_prompts.py -v
```

Expected: FAIL because extraction modules do not exist.

- [ ] **Step 2: Implement strict provider schema without domain imports**

Keep the exact provider output fields:

```python
class ChunkExtractionOutput(StrictOutputModel):
    summary: str
    entities: list[EntityOutput] = Field(default_factory=list)
    places: list[PlaceOutput] = Field(default_factory=list)
    relationship_events: list[RelationshipEventOutput] = Field(default_factory=list)
    location_events: list[LocationEventOutput] = Field(default_factory=list)
```

Use local `Literal` values for relationship category and location event type. Move conversion into a mapper function in `assembly/translation.py`; `schemas.py` must not import public or internal domain models.

- [ ] **Step 3: Implement chunk analyzer port and adapters**

```python
class ChunkAnalyzerPort(Protocol):
    @property
    def model_name(self) -> str:
        raise NotImplementedError

    async def analyze(self, call: ChunkAnalysisCall) -> ChunkInvocationResult:
        raise NotImplementedError
```

Construct Pydantic AI with `output_type=ChunkExtractionOutput`, `retries=0`, and `defer_model_check=True`. Translate `AgentRunError` to a private provider-call error without chaining or provider body. Preserve response message bytes, provider/model identity and token usage.

- [ ] **Step 4: Move and validate prompt registry**

Keep exact front matter keys `prompt_id`, `version`, `result_schema`, supported schema `chunk-analysis-extraction-v1`, UTF-8 validation, root containment and hot loading. Copy the approved prompt bytes without changing version 1.

- [ ] **Step 5: Run extraction checks and verify GREEN**

```sh
mise exec -- uv run pytest tests/unit/test_extraction_agent.py tests/unit/test_prompts.py -v
mise exec -- uv run ruff check src/narrative_analysis_agent/extraction tests/unit
mise exec -- uv run ruff format --check src/narrative_analysis_agent/extraction tests/unit
```

Expected: all moved schema, adapter and prompt tests pass.

- [ ] **Step 6: Commit**

```sh
git add llm-agent
git commit -m "리팩터: 청크 분석기와 프롬프트 분리"
```

---

### Task 4: 에이전트 소유 감사 SQLite 이동

**Files:**
- Create: `llm-agent/src/narrative_analysis_agent/audit/__init__.py`
- Create: `llm-agent/src/narrative_analysis_agent/audit/ports.py`
- Create: `llm-agent/src/narrative_analysis_agent/audit/sqlite.py`
- Test: `llm-agent/tests/unit/test_sqlite_audit.py`
- Reference: `backend/apps/narrative_memory/repository/analysis_audit.py`
- Reference: `backend/infrastructure/audit/sqlite_agent_audit.py`
- Reference: `backend/tests/narrative_memory/test_sqlite_agent_audit.py`

**Interfaces:**
- Consumes: versioned prompt definitions and run/attempt events.
- Produces: `AgentAuditPort` and `SQLiteAgentAudit` with append-only terminal uniqueness.

- [ ] **Step 1: Move audit tests and verify RED**

Port all schema, owner-only mode, prompt byte idempotency/version conflict, run/attempt event and terminal-index validation cases.

```sh
mise exec -- uv run pytest tests/unit/test_sqlite_audit.py -v
```

Expected: FAIL because the package audit implementation does not exist.

- [ ] **Step 2: Move audit events and port**

Preserve event identity and safe payload fields. The port must expose:

```python
class AgentAuditPort(Protocol):
    def register_prompt(self, prompt: PromptDefinition) -> None:
        raise NotImplementedError

    def append_run_event(self, event: RunEvent) -> None:
        raise NotImplementedError

    def append_attempt_event(self, event: AttemptEvent) -> None:
        raise NotImplementedError
```

- [ ] **Step 3: Move SQLite implementation and security constraints**

Preserve file mode `0o600`, transaction behavior, exact prompt-byte conflict, binary/case-sensitive identity, partial unique terminal index and existing-index metadata validation. Do not add update or delete repair behavior.

- [ ] **Step 4: Run audit checks and verify GREEN**

```sh
mise exec -- uv run pytest tests/unit/test_sqlite_audit.py -v
mise exec -- uv run ruff check src/narrative_analysis_agent/audit tests/unit/test_sqlite_audit.py
mise exec -- uv run ruff format --check src/narrative_analysis_agent/audit tests/unit/test_sqlite_audit.py
```

Expected: audit tests pass without accessing backend modules.

- [ ] **Step 5: Commit**

```sh
git add llm-agent
git commit -m "리팩터: 분석 감사 저장소 분리"
```

---

### Task 5: 통합 orchestrator와 단일 facade 완성

**Files:**
- Create: `llm-agent/src/narrative_analysis_agent/orchestrator.py`
- Create: `llm-agent/src/narrative_analysis_agent/facade.py`
- Modify: `llm-agent/src/narrative_analysis_agent/__init__.py`
- Test: `llm-agent/tests/unit/test_orchestrator.py`
- Test: `llm-agent/tests/integration/test_scene_analysis_offline.py`
- Modify: `input.txt`
- Modify: `relationships.json`
- Reference: `backend/apps/narrative_memory/service/scene_analysis.py`
- Reference: `backend/tests/narrative_memory/test_scene_analysis_service.py`

**Interfaces:**
- Consumes: `NarrativeAnalysisConfig`, `SceneAnalysisRequest`, chunk analyzer, prompt registry and audit dependencies.
- Produces: `NarrativeAnalysisAgent.analyze_scene(request) -> SceneAnalysisResult`.

- [ ] **Step 1: Port orchestration tests and write facade acceptance test**

Keep current cases for input validation, serial chunk call order, provider-only two-attempt retry, no retry for invalid extraction, cancellation, audit-start call blocking, terminal audit failures, sanitized errors and empty text.

The acceptance assertion must use repository-root fixtures:

```python
ROOT = Path(__file__).parents[3]
input_text = ROOT.joinpath("input.txt").read_text().rstrip("\n")
expected = json.loads(ROOT.joinpath("relationships.json").read_text())

result = asyncio.run(agent.analyze_scene(request_for(input_text)))

assert asdict(result.snapshot) == expected
assert result.run_id == "run-acceptance"
```

- [ ] **Step 2: Run orchestrator tests and verify RED**

```sh
mise exec -- uv run pytest \
  tests/unit/test_orchestrator.py \
  tests/integration/test_scene_analysis_offline.py -v
```

Expected: FAIL because facade/orchestrator are absent.

- [ ] **Step 3: Implement deterministic orchestrator**

Required constructor and method:

```python
class SceneAnalysisOrchestrator:
    def __init__(
        self,
        analyzer: ChunkAnalyzerPort,
        prompt_registry: PromptRegistryPort,
        audit: AgentAuditPort,
        run_id_factory: Callable[[], str],
        clock: Callable[[], datetime],
        monotonic: Callable[[], float],
    ) -> None:
        self._analyzer = analyzer
        self._prompt_registry = prompt_registry
        self._audit = audit
        self._run_id_factory = run_id_factory
        self._clock = clock
        self._monotonic = monotonic
```

Implement `async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysisResult` by moving the complete control flow from the current `SceneAnalysisService.analyze_scene` and `_analyze_chunk`. Load and register prompt before provider calls, append run/attempt start before each provider call, analyze chunks serially, retry only private provider-call errors once, translate and merge validated outputs, append run success with canonical snapshot JSON, then return `SceneAnalysisResult`.

- [ ] **Step 4: Implement facade composition**

```python
class NarrativeAnalysisAgent:
    def __init__(self, config: NarrativeAnalysisConfig) -> None:
        self.config = config
        self._orchestrator = build_orchestrator(config)

    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysisResult:
        return await self._orchestrator.analyze_scene(request)
```

Define private `build_orchestrator(config: NarrativeAnalysisConfig) -> SceneAnalysisOrchestrator` in `facade.py`. `model_name == "mock"` selects the scripted analyzer; every other nonblank value constructs the Pydantic AI analyzer. The builder creates and initializes its package-owned prompt registry and SQLite audit from config. Blank model names raise `AnalysisConfigurationError` without initializing a provider.

- [ ] **Step 5: Align acceptance fixtures with the exact public snapshot**

Keep `input.txt` as the immutable 1,194-character scene. Keep `relationships.json` limited to the exact `SceneRelationshipSnapshot` keys and validate every evidence range against `input.txt`. If public dataclass field names differ from the fixture, fix the contract or fixture before GREEN; do not add an ad-hoc comparison adapter.

- [ ] **Step 6: Run facade and acceptance checks and verify GREEN**

```sh
mise exec -- uv run pytest \
  tests/unit/test_orchestrator.py \
  tests/integration/test_scene_analysis_offline.py -v
mise exec -- uv run pytest -m "not live"
```

Expected: full package offline suite passes and no network provider is contacted.

- [ ] **Step 7: Commit**

```sh
git add llm-agent input.txt relationships.json
git commit -m "기능: 통합 장면 분석 facade 추가"
```

---

### Task 6: 실제 모델 opt-in 평가 추가

**Files:**
- Create: `llm-agent/tests/live/test_scene_analysis_live.py`
- Create: `llm-agent/tests/live/conftest.py`
- Modify: `llm-agent/docs/llm-agent-coding-rules.md`

**Interfaces:**
- Consumes: `NARRATIVE_LLM_MODEL`, provider credential variables, root `input.txt` and expected semantic relationships.
- Produces: explicit opt-in live evaluation without affecting default tests.

- [ ] **Step 1: Write the skipped-by-default live test**

```python
pytestmark = pytest.mark.live


def test_live_scene_analysis_matches_required_relationships(live_agent) -> None:
    if os.environ.get("RUN_LLM_LIVE_TESTS") != "1":
        pytest.skip("set RUN_LLM_LIVE_TESTS=1 to run live provider tests")
    result = asyncio.run(live_agent.analyze_scene(scene_request()))
    actual = {
        (event.subject_key, event.object_key, event.category)
        for event in result.snapshot.relationship_events
    }
    assert REQUIRED_RELATIONSHIPS <= actual
    assert_evidence_matches_source(result.snapshot, scene_request().text)
```

- [ ] **Step 2: Verify the default suite skips live calls**

```sh
mise exec -- uv run pytest -m "not live" -q
mise exec -- uv run pytest tests/live/test_scene_analysis_live.py -q
```

Expected: offline suite passes; direct live file reports one skipped test when the opt-in variable is absent.

- [ ] **Step 3: Document the explicit live command and safety boundary**

Document that live tests cost money, require provider credentials, compare semantic pairs/categories rather than exact prose/confidence, and never run in the default suite.

- [ ] **Step 4: Run a live test only when credentials are already configured**

```sh
: "${NARRATIVE_LLM_MODEL:?configure NARRATIVE_LLM_MODEL before live tests}"
RUN_LLM_LIVE_TESTS=1 \
mise exec -- uv run pytest -m live -v
```

Expected: PASS when a supported provider and credentials are available. If credentials are absent, retain the skipped default proof and report the live test as not executed rather than failed or passed.

- [ ] **Step 5: Commit**

```sh
git add llm-agent
git commit -m "테스트: 실제 모델 선택 검증 추가"
```

---

### Task 7: backend를 얇은 facade 소비자로 전환하고 이전 구현 제거

**Files:**
- Create: `backend/apps/narrative_memory/composition.py`
- Create: `backend/apps/narrative_memory/service/scene_analysis_result.py`
- Create: `backend/tests/narrative_memory/test_agent_composition.py`
- Create: `backend/tests/narrative_memory/test_scene_analysis_result.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `backend/apps/narrative_memory/service/models.py`
- Modify: `backend/apps/narrative_memory/service/merge.py`
- Modify: `backend/tests/narrative_memory/test_merge.py`
- Delete: backend 분석·LLM·감사 파일과 이동된 테스트 중 File Structure에 열거한 경로

**Interfaces:**
- Consumes: `NarrativeAnalysisConfig`, `NarrativeAnalysisAgent`, public request/result/errors.
- Produces: backend composition boundary with no Pydantic AI or agent-internal imports.

- [ ] **Step 1: Write backend composition contract test**

```python
from narrative_analysis_agent import NarrativeAnalysisAgent, NarrativeAnalysisConfig

from apps.narrative_memory.composition import build_narrative_analysis_agent


def test_backend_builds_only_the_public_agent_facade(tmp_path) -> None:
    agent = build_narrative_analysis_agent(
        model_name="mock",
        prompt_root=tmp_path / "prompts",
        audit_path=tmp_path / "audit.sqlite3",
    )
    assert isinstance(agent, NarrativeAnalysisAgent)
    assert isinstance(agent.config, NarrativeAnalysisConfig)
```

Add a separate boundary test that builds a public snapshot containing one entity, place, relationship and location event, calls `to_domain_scene_snapshot()`, and asserts exact equality with the corresponding existing backend `SceneRelationshipSnapshot` and nested model types.

- [ ] **Step 2: Run backend test and verify RED**

```sh
mise exec -- uv run pytest \
  tests/narrative_memory/test_agent_composition.py \
  tests/narrative_memory/test_scene_analysis_result.py -v
```

Expected: FAIL because the local dependency and composition module are absent.

- [ ] **Step 3: Replace direct dependency and add thin composition**

Replace `pydantic-ai>=2.9.1,<3` in backend dependencies with the repository-local package using uv's supported path/workspace source configuration. Regenerate `backend/uv.lock` with `mise exec -- uv lock`.

```python
def build_narrative_analysis_agent(
    *, model_name: str, prompt_root: Path, audit_path: Path
) -> NarrativeAnalysisAgent:
    return NarrativeAnalysisAgent(
        NarrativeAnalysisConfig(
            model_name=model_name,
            prompt_root=prompt_root,
            audit_path=audit_path,
        )
    )
```

- [ ] **Step 4: Add the single public-result to backend-domain mapping boundary**

Keep backend project snapshot, project merge, snapshot codec and repository behavior unchanged. Implement this exact boundary and map every nested tuple field explicitly without Pydantic:

```python
from narrative_analysis_agent import SceneRelationshipSnapshot as AgentSceneSnapshot

from apps.narrative_memory.service.models import SceneRelationshipSnapshot


def to_domain_scene_snapshot(snapshot: AgentSceneSnapshot) -> SceneRelationshipSnapshot:
    return SceneRelationshipSnapshot(
        scene_id=snapshot.scene_id,
        scene_revision=snapshot.scene_revision,
        scene_sequence=snapshot.scene_sequence,
        schema_version=snapshot.schema_version,
        summary=snapshot.summary,
        entities=tuple(to_domain_entity(item) for item in snapshot.entities),
        places=tuple(to_domain_place(item) for item in snapshot.places),
        relationship_events=tuple(
            to_domain_relationship(item) for item in snapshot.relationship_events
        ),
        location_events=tuple(to_domain_location(item) for item in snapshot.location_events),
    )
```

Define the four named private mappers in the same file with complete field-for-field construction into existing backend model types. This is the only agent-result translation in backend; do not duplicate chunking, provider schema, audit, stable-ID or scene-merge logic.

- [ ] **Step 5: Remove moved implementation and tests**

Delete the paths listed under “제거되는 backend 소유 파일”. Trim `backend/apps/narrative_memory/service/merge.py` and `test_merge.py` to project merge behavior. Confirm no backend production or test Python file imports `pydantic_ai`, `infrastructure.llm`, `SQLiteAgentAudit`, `SceneAnalysisOrchestrator`, or package-private agent modules.

Remove only `test_pydantic_ai_is_available` and its `pydantic_ai.Agent` import from `backend/tests/writing_assistant/test_text_generation_port.py`; retain the `TextGenerationPort` contract test.

```sh
if rg -n "pydantic_ai|infrastructure\.llm|SQLiteAgentAudit" . -g '*.py'; then
  exit 1
fi
```

Expected: no matches under `backend/`.

- [ ] **Step 6: Run focused and full backend checks**

```sh
mise exec -- uv run pytest \
  tests/narrative_memory/test_agent_composition.py \
  tests/narrative_memory/test_scene_analysis_result.py \
  tests/narrative_memory/test_merge.py \
  tests/narrative_memory/test_snapshot_codec.py \
  tests/narrative_memory/test_sqlite_snapshot_repository.py -q
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: focused and full backend suites pass with no Pydantic AI imports.

- [ ] **Step 7: Commit**

```sh
git add backend
git commit -m "리팩터: 백엔드를 분석 facade 소비자로 전환"
```

---

### Task 8: 구조·소유권 문서 동기화와 최종 검증

**Files:**
- Modify: `AGENTS.md`
- Modify: `backend/README.md`
- Modify: `backend/docs/backend-coding-rules.md`
- Modify: `docs/domains/narrative-memory.md` only if implementation changes domain meaning or boundaries
- Modify: `docs/domains/README.md` only if domain dependency direction changes
- Modify: `llm-agent/AGENTS.md`
- Modify: `llm-agent/docs/llm-agent-coding-rules.md`

**Interfaces:**
- Consumes: final implementation and verification evidence.
- Produces: discoverable ownership rules and a verified cross-project migration.

- [ ] **Step 1: Update repository and project maps**

Add `llm-agent/` to the root repository map without overwriting the existing Mandatory Feature Ticket Registration change. Update backend's structure map to show only the public package composition boundary and project snapshot persistence. Move detailed prompt/provider/audit rules from backend coding rules into `llm-agent/docs/llm-agent-coding-rules.md`, leaving a link and consumer-boundary rule in backend docs.

- [ ] **Step 2: Compare implementation with domain contracts**

Verify that chunk size/overlap/order, retry semantics, `pending`, stable IDs, evidence, snapshot schema, explicit invocation and no automatic persistence still match `docs/domains/narrative-memory.md`. If all meaning is preserved, record that no domain document edit is required. If any responsibility, invariant, input or output changed, update the domain document and context map in this same task.

- [ ] **Step 3: Run full independent package verification**

From `llm-agent/`:

```sh
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: all commands exit 0; no live provider call occurs.

- [ ] **Step 4: Run full backend verification**

From `backend/`:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: all commands exit 0.

- [ ] **Step 5: Verify dependency and ownership boundaries**

From repository root:

```sh
test -z "$(rg -l 'pydantic_ai|from pydantic_ai' backend -g '*.py')"
test -z "$(rg -l 'apps\.|backend\.' llm-agent/src -g '*.py')"
git diff --check
```

Expected: both dependency scans are empty and diff check passes.

- [ ] **Step 6: Run required read-only review and resolve findings**

Assign the complete package extraction and backend consumption boundary to the backend reviewer after all implementation writers stop. Review acceptance criteria include provider isolation, deterministic semantics, audit preservation, no backend Pydantic imports, fixture traceability and all checks above. Resolve every accepted finding; re-review blocking/high or material repairs.

- [ ] **Step 7: Commit documentation and final corrections**

```sh
git add AGENTS.md backend/README.md backend/docs llm-agent/AGENTS.md llm-agent/docs docs/domains
git commit -m "문서: 분석 에이전트 소유권 정리"
```

---

## Final Acceptance Checklist

- [ ] `NarrativeAnalysisAgent.analyze_scene()` is the only backend-facing analysis entry point.
- [ ] Public contracts import no Pydantic, Pydantic AI, FastAPI or SQLite.
- [ ] Pydantic AI exists only under `llm-agent/src/narrative_analysis_agent/extraction/`.
- [ ] Chunking, translation, stable IDs, `pending` status and scene merge are deterministic.
- [ ] Project snapshot persistence and scene-to-project merge remain in backend.
- [ ] Prompt and audit storage are owned by `llm-agent`.
- [ ] Provider failures retry once; invalid extraction does not retry.
- [ ] Partial snapshots are never returned.
- [ ] Root acceptance fixtures produce the exact typed snapshot offline.
- [ ] Default tests are network-free and live evaluation is explicit opt-in.
- [ ] backend contains no `pydantic_ai` import.
- [ ] No consumer-facing API or OpenAPI operation changed.
- [ ] `llm-agent` and backend pytest, Ruff lint and Ruff format checks all pass.
- [ ] Implementation and relevant documentation describe the same ownership and behavior.
