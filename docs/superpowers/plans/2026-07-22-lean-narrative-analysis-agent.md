# 경량 Narrative Analysis Agent 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `llm-agent`를 청킹, 단순 system prompt 로딩, 청크당 한 번의 구조화 LLM 호출과 청크별 결과 반환만 담당하는 600줄 이하의 Python 패키지로 축소한다.

**Architecture:** Pydantic 공개 모델을 provider 구조화 출력과 반환 계약에 함께 사용해 중복 변환을 제거한다. `NarrativeAnalysisAgent` 하나가 prompt를 읽고 청크를 순서대로 한 번씩 호출하며, backend는 이 청크별 분석 결과를 domain snapshot으로 변환하지 않고 그대로 반환한다.

**Tech Stack:** Python 3.13, Pydantic 2, Pydantic AI 2, pytest, Ruff, uv, mise

## Global Constraints

- 승인 설계는 `docs/superpowers/specs/2026-07-22-lean-narrative-analysis-agent-design.md`다.
- `llm-agent/src`의 최종 Python 소스는 600줄 이하여야 한다.
- 청크 크기는 최대 300자, 인접 중첩은 50자, stride는 250자다.
- 청크는 숫자 순서로 직렬 처리하고 각 청크를 정확히 한 번만 호출한다.
- 어느 청크든 실패하면 뒤 청크를 호출하거나 부분 결과를 반환하지 않는다.
- SQLite 감사, `run_id`, 재시도, prompt frontmatter/registry/version/hash, 결정적 ID, 후보 상태, 절대 evidence 변환과 청크 간 병합을 다시 도입하지 않는다.
- 기존 한국어 `system.md` 본문은 보존하고 YAML frontmatter만 제거한다.
- 기존 프로젝트 snapshot 모델·저장소·병합은 독립 기능으로 유지하며 LLM 분석 결과에 자동 연결하지 않는다.
- 현재 미커밋 상태인 `extraction/agent.py`, `orchestrator.py`, `system.md`, `test_config.py` 중 삭제 대상의 포맷 변경은 되돌리지 말고 삭제에 흡수하며, `system.md`의 한국어 본문은 보존한다.
- 커밋 메시지는 한글로 작성한다.

---

### Task 1: 단일 공개 분석 모델과 청킹 계약

**Files:**
- Create: `llm-agent/src/narrative_analysis_agent/models.py`
- Modify: `llm-agent/src/narrative_analysis_agent/chunking.py`
- Create: `llm-agent/tests/unit/test_models.py`
- Modify: `llm-agent/tests/unit/test_chunking.py`

**Interfaces:**
- Produces: `KnownIdentity`, `SceneAnalysisRequest`, `Evidence`, `Entity`, `Place`, `RelationshipEvent`, `LocationEvent`, `ChunkExtraction`, `AnalyzedChunk`, `SceneAnalysis`
- Produces: `chunk_scene(scene_id: str, scene_revision: int, text: str) -> tuple[SceneChunk, ...]`
- Consumes: 없음

- [ ] **Step 1: 공개 모델의 불변성과 strict 구조화 출력을 검증하는 실패 테스트 작성**

```python
from pydantic import ValidationError
import pytest

from narrative_analysis_agent.models import ChunkExtraction, SceneAnalysisRequest


def test_request_is_frozen_and_rejects_blank_identity() -> None:
    request = SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=2,
        text="본문",
    )
    with pytest.raises(ValidationError):
        request.scene_id = "changed"  # type: ignore[misc]


def test_chunk_extraction_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ChunkExtraction.model_validate({"summary": "요약", "unknown": True})
```

- [ ] **Step 2: 모델 테스트가 새 모듈 부재로 실패하는지 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_models.py -v`

Expected: FAIL with `ModuleNotFoundError: narrative_analysis_agent.models`.

- [ ] **Step 3: 중복 없는 Pydantic 공개 모델 구현**

`models.py`에 `ConfigDict(extra="forbid", frozen=True, strict=True)`를 공통 설정으로 사용한다.
요청의 식별 문자열은 `Field(min_length=1)`, revision과 sequence는 `Field(ge=0)`로 제한한다.
`Evidence`는 `start_offset >= 0`, `end_offset > start_offset`을 검증한다. 관계 범주는
`romance | family | friendship | professional | antagonistic | other`, 위치 사건은
`arrived | present | departed`, confidence는 유한한 `0.0..1.0`으로 제한한다.

모델 필드는 다음으로 고정한다.

```text
KnownIdentity: identity_key, normalized_name, display_name, aliases
SceneAnalysisRequest: project_id, scene_id, scene_revision, scene_sequence, text,
                      known_entities, known_places
Evidence: start_offset, end_offset, text
Entity/Place: local_ref, normalized_name, display_name, aliases, evidence
RelationshipEvent: subject_ref, object_ref, category, description, confidence, evidence
LocationEvent: character_ref, place_ref, event_type, description, confidence, evidence
```

```python
class ChunkExtraction(StrictModel):
    summary: str
    entities: tuple[Entity, ...] = ()
    places: tuple[Place, ...] = ()
    relationship_events: tuple[RelationshipEvent, ...] = ()
    location_events: tuple[LocationEvent, ...] = ()


class AnalyzedChunk(StrictModel):
    chunk_id: str
    ordinal: int
    start_offset: int
    end_offset: int
    text: str
    extraction: ChunkExtraction


class SceneAnalysis(StrictModel):
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    chunks: tuple[AnalyzedChunk, ...]
```

- [ ] **Step 4: 청킹에서 사용하지 않는 content hash를 제거하고 경계 테스트 정리**

`SceneChunk`는 `chunk_id`, `ordinal`, `start_offset`, `end_offset`, `text`만 가진다. 기존
300자/50자 규칙과 빈 입력이 빈 튜플을 반환하는 동작은 유지한다.

```python
assert chunk_scene("scene", 1, "") == ()
chunks = chunk_scene("scene", 1, "가" * 551)
assert [(chunk.start_offset, chunk.end_offset) for chunk in chunks] == [
    (0, 300),
    (250, 550),
    (500, 551),
]
```

- [ ] **Step 5: 모델과 청킹 테스트 통과 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_models.py tests/unit/test_chunking.py -v`

Expected: PASS.

- [ ] **Step 6: 작업 커밋**

```bash
git add llm-agent/src/narrative_analysis_agent/models.py \
  llm-agent/src/narrative_analysis_agent/chunking.py \
  llm-agent/tests/unit/test_models.py \
  llm-agent/tests/unit/test_chunking.py
git commit -m "리팩터: 장면 분석 공개 모델 단순화"
```

### Task 2: 단일 호출 분석 파이프라인

**Files:**
- Create: `llm-agent/src/narrative_analysis_agent/agent.py`
- Modify: `llm-agent/src/narrative_analysis_agent/__init__.py`
- Modify: `llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md`
- Create: `llm-agent/tests/unit/test_agent.py`
- Modify: `llm-agent/tests/integration/test_scene_analysis_offline.py`

**Interfaces:**
- Consumes: Task 1의 `SceneAnalysisRequest`, `ChunkExtraction`, `AnalyzedChunk`, `SceneAnalysis`, `chunk_scene`
- Produces: `NarrativeAnalysisAgent(model: Model | str, *, prompt_path: Path | None = None, runner: AgentRunner | None = None)`
- Produces: `NarrativeAnalysisAgent.analyze_scene(request: SceneAnalysisRequest) -> SceneAnalysis`
- Produces: `NarrativeAnalysisError`
- Produces: `packaged_prompt_path() -> Path`

- [ ] **Step 1: 청크당 한 번 호출과 실패 중단 테스트 작성**

가짜 runner는 `run(user_prompt, *, instructions)` 호출을 기록하고 `output: ChunkExtraction`을
가진 결과를 반환한다. 551자 입력에 대해 세 번만 호출되는지 검증한다.

```python
analysis = asyncio.run(agent.analyze_scene(request_with_551_characters))
assert len(runner.calls) == 3
assert [chunk.ordinal for chunk in analysis.chunks] == [0, 1, 2]
```

두 번째 호출에서 `AgentRunError`를 발생시키는 runner로 재시도와 부분 반환이 없음을 검증한다.

```python
with pytest.raises(NarrativeAnalysisError, match="scene analysis failed"):
    asyncio.run(agent.analyze_scene(request_with_551_characters))
assert len(runner.calls) == 2
```

- [ ] **Step 2: 새 agent 모듈이 없어 테스트가 실패하는지 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_agent.py -v`

Expected: FAIL with `ModuleNotFoundError: narrative_analysis_agent.agent`.

- [ ] **Step 3: 단일 파이프라인 구현**

`agent.py`는 다음 흐름만 구현한다.

```python
async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis:
    try:
        instructions = self.prompt_path.read_text(encoding="utf-8")
    except OSError:
        raise NarrativeAnalysisError("unable to load scene analysis prompt") from None

    analyzed: list[AnalyzedChunk] = []
    for chunk in chunk_scene(request.scene_id, request.scene_revision, request.text):
        try:
            result = await self._runner.run(
                render_user_prompt(request, chunk),
                instructions=instructions,
            )
        except asyncio.CancelledError:
            raise
        except AgentRunError:
            raise NarrativeAnalysisError("scene analysis failed") from None
        analyzed.append(
            AnalyzedChunk(
                chunk_id=chunk.chunk_id,
                ordinal=chunk.ordinal,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                text=chunk.text,
                extraction=result.output,
            )
        )
    return SceneAnalysis(
        project_id=request.project_id,
        scene_id=request.scene_id,
        scene_revision=request.scene_revision,
        scene_sequence=request.scene_sequence,
        chunks=tuple(analyzed),
    )
```

실제 runner는 `Agent(model, output_type=ChunkExtraction, retries=0,
defer_model_check=True)`로 한 번 구성한다. user prompt는 JSON으로 장면 메타데이터, known
identity catalog, 청크 메타데이터와 원문을 직렬화한다. provider 예외 원문은 공개 오류에
포함하지 않는다.

- [ ] **Step 4: system prompt frontmatter 제거 및 공개 export 교체**

`system.md`의 첫 `---`부터 두 번째 `---`까지 다섯 줄만 제거하고 한국어 본문은 그대로 둔다.
`__init__.py`는 새 agent와 `models.py`의 공개 이름만 export한다.

- [ ] **Step 5: offline 통합 테스트를 새 반환 계약으로 교체**

네트워크 없는 runner를 주입해 `SceneAnalysis.chunks`가 입력 순서와 구조화 출력을 보존하는지
공개 import만으로 검증한다. audit 파일, `run_id`, snapshot 단언은 모두 제거한다.

- [ ] **Step 6: agent 단위·통합 테스트 통과 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_agent.py tests/integration/test_scene_analysis_offline.py -v`

Expected: PASS and the fake runner call count equals the chunk count.

- [ ] **Step 7: 작업 커밋**

```bash
git add llm-agent/src/narrative_analysis_agent/agent.py \
  llm-agent/src/narrative_analysis_agent/__init__.py \
  llm-agent/src/narrative_analysis_agent/prompts/scene-analysis/system.md \
  llm-agent/tests/unit/test_agent.py \
  llm-agent/tests/integration/test_scene_analysis_offline.py
git commit -m "리팩터: 장면 분석을 단일 호출 파이프라인으로 축소"
```

### Task 3: 구형 계층과 구현 세부 테스트 제거

**Files:**
- Delete: `llm-agent/src/narrative_analysis_agent/audit/`
- Delete: `llm-agent/src/narrative_analysis_agent/assembly/`
- Delete: `llm-agent/src/narrative_analysis_agent/extraction/`
- Delete: `llm-agent/src/narrative_analysis_agent/config.py`
- Delete: `llm-agent/src/narrative_analysis_agent/contracts.py`
- Delete: `llm-agent/src/narrative_analysis_agent/errors.py`
- Delete: `llm-agent/src/narrative_analysis_agent/facade.py`
- Delete: `llm-agent/src/narrative_analysis_agent/orchestrator.py`
- Delete: `llm-agent/tests/unit/test_config.py`
- Delete: `llm-agent/tests/unit/test_contracts.py`
- Delete: `llm-agent/tests/unit/test_extraction_agent.py`
- Delete: `llm-agent/tests/unit/test_orchestrator.py`
- Delete: `llm-agent/tests/unit/test_prompts.py`
- Delete: `llm-agent/tests/unit/test_scene_merge.py`
- Delete: `llm-agent/tests/unit/test_sqlite_audit.py`
- Delete: `llm-agent/tests/unit/test_translation.py`
- Modify: `llm-agent/tests/live/conftest.py`
- Modify: `llm-agent/tests/live/test_scene_analysis_live.py`
- Modify: `llm-agent/docs/llm-agent-coding-rules.md`
- Modify: `llm-agent/AGENTS.md`

**Interfaces:**
- Consumes: Task 2의 공개 API
- Produces: 과거 package-private 모듈 없이 import 가능한 경량 패키지

- [ ] **Step 1: 전체 비-live 테스트를 실행해 구형 계약 의존 실패 목록 확인**

Run: `cd llm-agent && mise exec -- uv run pytest -m "not live" -v`

Expected: old audit, snapshot, translation, orchestrator tests fail against the intentionally removed contract.

- [ ] **Step 2: 구형 구현과 전용 테스트 삭제**

위 Delete 목록을 제거한다. 다른 위치로 코드를 이동하지 않는다. Task 2의 `agent.py`와
`models.py`가 실제로 사용하는 코드만 남긴다.

- [ ] **Step 3: live 테스트를 청크별 결과 계약으로 축소**

fixture는 `NarrativeAnalysisAgent(model_name, prompt_path=packaged_prompt_path())`를 생성한다.
live 테스트는 모든 청크의 extraction을 평탄화해 필수 관계 범주가 존재하는지 확인하고,
각 evidence가 `chunk.text[start_offset:end_offset]`와 같은지만 검증한다. audit 경로, 절대
offset, stable ID와 snapshot 단언은 제거한다.

- [ ] **Step 4: 패키지 지침과 코딩 규칙 동기화**

`llm-agent/AGENTS.md`와 코딩 규칙을 다음 책임으로 제한한다.

```text
- package owns chunking, the editable prompt, structured extraction, and sequential calls
- each chunk is called once; one failure returns no partial analysis
- public Pydantic models are the single extraction/result representation
- no audit storage, retries, durable IDs, candidate status, scene snapshot assembly, or cross-chunk merge
```

- [ ] **Step 5: 잔존 import와 비-live 테스트 검증**

Run: `rg -n "audit|run_id|SceneAnalysisResult|SceneRelationshipSnapshot|assembly|orchestrator|PromptRegistry|retry" llm-agent/src llm-agent/tests llm-agent/AGENTS.md llm-agent/docs`

Expected: no obsolete implementation reference; generic prose such as “no retries”만 허용한다.

Run: `cd llm-agent && mise exec -- uv run pytest -m "not live" && mise exec -- uv run ruff check . && mise exec -- uv run ruff format --check .`

Expected: all commands PASS.

- [ ] **Step 6: 작업 커밋**

```bash
git add -A llm-agent
git commit -m "리팩터: 분석 감사와 조립 계층 제거"
```

### Task 4: Backend 소비 경계 단순화

**Files:**
- Modify: `backend/apps/narrative_memory/composition.py`
- Modify: `backend/apps/narrative_memory/service/scene_analysis_use_case.py`
- Delete: `backend/apps/narrative_memory/service/scene_analysis_result.py`
- Modify: `backend/tests/narrative_memory/test_agent_composition.py`
- Modify: `backend/tests/narrative_memory/test_scene_analysis_use_case.py`
- Delete: `backend/tests/narrative_memory/test_scene_analysis_result.py`
- Modify: `backend/README.md`
- Modify: `backend/docs/backend-coding-rules.md`

**Interfaces:**
- Consumes: `NarrativeAnalysisAgent`, `SceneAnalysisRequest`, `SceneAnalysis`, `NarrativeAnalysisError`, `packaged_prompt_path`
- Produces: `build_narrative_analysis_agent(*, model_name: str, prompt_path: Path) -> NarrativeAnalysisAgent`
- Produces: `AnalyzeSceneUseCase.execute(input_value: AnalyzeSceneInput) -> SceneAnalysis`

- [ ] **Step 1: 새 backend 소비 계약의 실패 테스트 작성**

```python
agent = build_narrative_analysis_agent(
    model_name="test",
    prompt_path=packaged_prompt_path(),
)
assert isinstance(agent, NarrativeAnalysisAgent)
```

use case 테스트의 가짜 facade는 `SceneAnalysis`를 직접 반환한다.

```python
result = asyncio.run(use_case.execute(input_value))
assert result is agent_result
```

오류 테스트는 `NarrativeAnalysisError("secret")`를 던지고
`SceneAnalysisApplicationError("scene analysis failed")`로 정제되는지만 확인한다. `run_id`는
어느 타입에도 존재하지 않아야 한다.

- [ ] **Step 2: focused 테스트가 구형 config와 result 계약으로 실패하는지 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_agent_composition.py tests/narrative_memory/test_scene_analysis_use_case.py -v`

Expected: FAIL on removed `audit_path`, `NarrativeAnalysisConfig`, or `SceneAnalysisResult` references.

- [ ] **Step 3: composition과 use case를 직접 결과 계약으로 변경**

```python
def build_narrative_analysis_agent(
    *, model_name: str, prompt_path: Path
) -> NarrativeAnalysisAgent:
    return NarrativeAnalysisAgent(model_name, prompt_path=prompt_path)
```

```python
class SceneAnalysisFacade(Protocol):
    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis: ...


async def execute(self, input_value: AnalyzeSceneInput) -> SceneAnalysis:
    try:
        return await self._agent.analyze_scene(
            SceneAnalysisRequest(
                project_id=input_value.project_id,
                scene_id=input_value.scene_id,
                scene_revision=input_value.scene_revision,
                scene_sequence=input_value.scene_sequence,
                text=input_value.text,
                known_entities=input_value.known_entities,
                known_places=input_value.known_places,
            )
        )
    except NarrativeAnalysisError:
        raise SceneAnalysisApplicationError("scene analysis failed") from None
```

`AnalyzedScene`, `run_id`, `to_domain_scene_snapshot`과 변환 모듈을 제거한다.

- [ ] **Step 4: backend README와 코딩 규칙 동기화**

README 예시는 `model_name`과 `prompt_path` 두 값만 전달하도록 수정한다. 코딩 규칙은 backend가
청크별 분석 결과를 그대로 반환하며 provider SDK를 직접 import하지 않는다는 경계만 남긴다.
agent audit, snapshot 변환, run ID 보존 규칙을 삭제한다.

- [ ] **Step 5: focused 및 backend 전체 검증**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_agent_composition.py tests/narrative_memory/test_scene_analysis_use_case.py -v`

Expected: PASS.

Run: `cd backend && mise exec -- uv run pytest && mise exec -- uv run ruff check . && mise exec -- uv run ruff format --check .`

Expected: all commands PASS.

- [ ] **Step 6: 작업 커밋**

```bash
git add -A backend/apps/narrative_memory backend/tests/narrative_memory \
  backend/README.md backend/docs/backend-coding-rules.md
git commit -m "리팩터: 백엔드 장면 분석 소비 경계 단순화"
```

### Task 5: Narrative Memory 계약 동기화와 최종 축소 검증

**Files:**
- Modify: `docs/domains/narrative-memory.md`

**Interfaces:**
- Consumes: Task 1~4의 최종 동작
- Produces: 구현과 일치하는 Narrative Memory 장면 분석 계약

- [ ] **Step 1: 도메인 계약의 구형 보장 위치 확인**

Run: `rg -n "감사|재시도|결정적|절대 문자|청크 병합|장면 관계 스냅샷을 반환|pending" docs/domains/narrative-memory.md`

Expected: agent에서 제거할 보장과 프로젝트 snapshot에 계속 남길 보장이 함께 표시된다.

- [ ] **Step 2: 장면 분석 계약을 청크별 미확정 추출물로 수정**

장면 분석 유스케이스와 불변조건은 다음 의미를 명시한다.

```text
장면 분석은 본문을 300자/50자 중첩 청크로 나누어 숫자 순서대로 직렬 처리하고 각 청크를
모델에 한 번만 전달한다. 성공 시 청크별 구조화 추출물과 청크 기준 상대 근거를 순서대로
반환한다. 추출물은 사실, durable candidate, scene snapshot이 아니며 자동 저장·병합·승인하지
않는다. 어느 청크든 실패하면 부분 결과를 반환하지 않는다.
```

프로젝트 snapshot 구성, 승인 상태, 재분석 병합, 저장소 검증 규칙은 유지하되 단순 agent
결과가 이를 직접 만족하거나 생성한다는 문장을 제거한다.

- [ ] **Step 3: 구현과 문서의 제거 항목 일치 검사**

Run: `rg -n "audit_path|run_id|SceneAnalysisResult|PromptRegistry|SQLiteAgentAudit|merge_chunk_analyses|translate_chunk_extraction" llm-agent/src backend/apps backend/README.md backend/docs llm-agent/docs docs/domains/narrative-memory.md`

Expected: no matches.

- [ ] **Step 4: 양쪽 애플리케이션 최종 검증**

Run: `cd llm-agent && mise exec -- uv run pytest -m "not live" && mise exec -- uv run ruff check . && mise exec -- uv run ruff format --check .`

Expected: all commands PASS.

Run: `cd backend && mise exec -- uv run pytest && mise exec -- uv run ruff check . && mise exec -- uv run ruff format --check .`

Expected: all commands PASS.

- [ ] **Step 5: 소스 축소 수치 확인**

Run: `find llm-agent/src -type f -name '*.py' -print0 | sort -z | xargs -0 wc -l`

Expected: four Python files and total line count at or below 600.

Run: `git diff --check 9e54db7..HEAD`

Expected: no whitespace errors.

- [ ] **Step 6: 도메인 문서 커밋**

```bash
git add docs/domains/narrative-memory.md
git commit -m "문서: 경량 장면 분석 계약 동기화"
```

- [ ] **Step 7: 최종 handoff 기록**

최종 보고에는 삭제·변경 파일, 공개 계약 파괴 변경, domain 계약 영향, `llm-agent/src` 파일 수와
줄 수, 모든 검증 명령의 실제 결과, live 테스트 미실행 여부를 포함한다.
