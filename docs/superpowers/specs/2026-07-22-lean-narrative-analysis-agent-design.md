# 경량 Narrative Analysis Agent 설계

## 목적

`llm-agent`를 장면 본문 청킹, 단순 system prompt 로딩, 청크별 구조화 LLM 호출만
담당하는 작은 패키지로 축소한다. 코드를 다른 프로젝트로 이동해 전체 복잡도를 유지하지
않고, 현재의 감사·재시도·결정적 번역·청크 병합 요구 자체를 제거한다.

완료 시 `llm-agent/src`의 Python 소스는 600줄 이하여야 한다. 최종 검증에서 실제 파일 수와
줄 수를 함께 보고한다.

## 범위

### 유지하는 동작

- 장면 본문을 최대 300자, 50자 중첩 청크로 분할한다.
- 청크를 숫자 순서대로 직렬 처리한다.
- 패키지 기본 prompt 또는 호출자가 지정한 prompt 파일을 UTF-8 텍스트로 읽는다.
- 각 청크를 LLM에 정확히 한 번 전달한다.
- Pydantic AI의 구조화 출력 검증을 사용한다.
- 청크별 요약, 인물, 장소, 관계 사건, 위치 사건과 청크 기준 상대 evidence offset을
  입력 순서대로 반환한다.
- 어느 청크든 실패하면 즉시 중단하고 부분 결과를 반환하지 않는다.
- 비동기 취소는 변환하지 않고 그대로 전파한다.

### 제거하는 동작

- SQLite 분석 감사 저장소와 모든 run/attempt 이벤트
- `run_id` 생성, 반환 및 오류 전파
- provider 실패 재시도
- prompt registry, YAML frontmatter, prompt ID, 버전, hash 및 결과 스키마 등록
- provider 출력에서 별도의 내부 모델과 공개 dataclass로 이어지는 다단계 변환
- 결정적 candidate/event ID 생성
- 후보에 `pending` 상태 부여
- evidence를 장면 절대 offset으로 변환하고 원문과 다시 대조하는 처리
- 알려진 정체성과 로컬 참조의 결정적 해석
- 청크 간 후보 병합, 중복 제거 및 장면 요약 병합
- 완성된 `SceneRelationshipSnapshot` 생성과 관련 불변조건 검증
- LLM 분석 결과를 backend 프로젝트 snapshot 흐름에 자동 연결하는 처리

## 아키텍처

최종 패키지는 다음 구조를 목표로 한다.

```text
narrative_analysis_agent/
├── __init__.py
├── agent.py
├── chunking.py
├── models.py
└── prompts/
    └── scene-analysis/
        └── system.md
```

`models.py`는 입력과 구조화 출력, 청크별 결과를 위한 하나의 Pydantic 모델 집합을
소유한다. Pydantic 모델을 공개 결과로 직접 사용하여 provider 출력과 내부 모델, 공개
dataclass 사이의 중복 표현을 만들지 않는다.

`agent.py`는 모델 구성, prompt 읽기, 청크 순회, 구조화 호출과 최종 결과 조립을 담당한다.
별도 facade와 orchestrator, port, registry 계층을 두지 않는다. 테스트는 Pydantic AI의 모델
주입 경계를 이용해 실제 네트워크 없이 호출을 제어한다.

`chunking.py`는 300자/50자 중첩 규칙과 청크 메타데이터 생성만 담당한다.

`system.md`는 현재 작성 중인 한국어 지시문 본문을 유지하되 YAML frontmatter를 제거한
일반 UTF-8 Markdown 파일이 된다.

## 공개 인터페이스

공개 사용 형태는 다음과 같다.

```python
agent = NarrativeAnalysisAgent(model_name, prompt_path=optional_path)
analysis = await agent.analyze_scene(request)
```

`SceneAnalysisRequest`는 장면 식별 정보, 원문과 선택적 known identity catalog를 받는다.
known identity는 prompt 문맥으로만 전달하며, 반환 참조를 durable domain identity로
해석하거나 검증하지 않는다.

`SceneAnalysis`는 장면 식별 정보와 `AnalyzedChunk` 튜플을 반환한다. 각 청크는 청크 ID,
순번, 시작·끝 위치, 원문과 구조화된 `ChunkExtraction`을 가진다. 추출물의 evidence offset은
청크 원문 기준이며 장면 절대 위치로 변환하지 않는다. 여러 청크에 같은 대상이 나오면 각
청크 결과에 그대로 남는다.

## 데이터 흐름

1. `analyze_scene()`이 필수 장면 입력과 모델 이름을 검증한다.
2. 지정된 prompt 파일 또는 패키지 기본 `system.md`를 `Path.read_text(encoding="utf-8")`로
   읽는다.
3. 장면 원문을 정규 청크로 나눈다.
4. 각 청크에 장면 메타데이터, known identity catalog와 청크 원문을 담은 user prompt를
   구성한다.
5. Pydantic AI agent를 청크당 한 번 호출하고 `ChunkExtraction`으로 검증한다.
6. 검증된 출력을 해당 `AnalyzedChunk`에 담는다.
7. 모든 청크가 성공하면 순서가 보존된 `SceneAnalysis`를 반환한다.

추가 LLM 병합 호출이나 규칙 기반 청크 병합은 수행하지 않는다.

## 오류 처리

- 빈 모델 이름이나 잘못된 요청 값은 `ValueError`로 거부한다.
- prompt 읽기, provider 호출 또는 구조화 출력 검증 실패는 메시지를 정제한
  `NarrativeAnalysisError`로 변환한다.
- `NarrativeAnalysisError`는 `run_id`나 provider 원문 오류를 포함하지 않는다.
- 실패한 청크를 재호출하지 않는다.
- 한 청크 실패 시 뒤 청크를 호출하지 않고, 이미 성공한 청크도 결과로 반환하지 않는다.
- `asyncio.CancelledError`는 잡거나 변환하지 않는다.

## Backend 영향

- 분석 agent 조합에서 `audit_path`와 `NarrativeAnalysisConfig`를 제거한다.
- `SceneAnalysisResult`, `run_id`, run ID 보존 오류 처리를 제거한다.
- `AnalyzeSceneUseCase`는 단순 `SceneAnalysis`를 반환한다.
- agent 결과를 backend `SceneRelationshipSnapshot`으로 변환하던 어댑터를 삭제한다.
- 기존 프로젝트 snapshot 모델, 저장소와 병합 로직은 독립 기능으로 유지한다.
- 단순 분석 결과를 프로젝트 snapshot이나 Story Bible에 자동 반영하지 않는다.
- 현재 소비자 대상 장면 분석 API가 없으므로 OpenAPI 변경은 없다.

## 문서 동기화

`docs/domains/narrative-memory.md`는 장면 분석 결과를 청크별 미확정 추출물로 정의하도록
수정한다. 결정적 ID, `pending` 상태, 절대 evidence offset과 청크 병합은 더 이상 장면 분석
에이전트의 보장이 아니다. 프로젝트 snapshot의 기존 의미와 검증 규칙은 유지한다.

`llm-agent`와 backend의 코딩 규칙 및 README에서 삭제된 감사 저장소, run ID, config 및
변환 경계 규칙을 제거한다. 과거 `docs/superpowers/` 설계·구현 기록은 당시 결정의 기록이므로
수정하지 않는다.

## 삭제 대상

- `llm-agent/src/narrative_analysis_agent/audit/`
- `llm-agent/src/narrative_analysis_agent/assembly/`
- 기존 `config.py`, `contracts.py`, `errors.py`, `facade.py`, `orchestrator.py`
- 기존 `extraction/`의 책임을 `agent.py`와 `models.py`로 흡수한 뒤 디렉터리 삭제
- audit, translation, merge, orchestrator 구현 세부사항만 검증하는 테스트
- backend의 분석 결과 domain snapshot 변환 어댑터와 해당 전용 테스트

## 테스트 및 검증

남기는 테스트는 공개 동작을 검증한다.

- 300자/50자 중첩과 청크 순서
- 빈 입력과 마지막 짧은 청크
- 기본 prompt 및 사용자 지정 prompt의 단순 로딩
- 청크당 정확히 한 번 호출
- 구조화 결과와 청크 순서 보존
- 한 청크 실패 시 즉시 중단 및 부분 결과 미반환
- provider 및 구조화 출력 오류 정제
- 네트워크 없는 전체 offline 흐름
- 명시적 opt-in live provider 평가

구현 후 다음 검증을 수행한다.

```sh
cd llm-agent
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .

cd ../backend
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

마지막으로 `llm-agent/src`의 Python 파일 수와 전체 줄 수가 이 설계의 축소 목표를 만족하는지
측정한다.
