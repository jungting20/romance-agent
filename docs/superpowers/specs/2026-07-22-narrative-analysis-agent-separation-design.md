# Narrative Analysis Agent 분리 설계

## 배경

현재 backend의 Narrative Memory 장면 분석은 애플리케이션 포트 뒤에 Pydantic AI
어댑터를 두고 있지만, 청크 분할, 프롬프트 로딩, 에이전트 호출, 감사, 번역과 병합이
`backend/` 안에 함께 있다. 서비스 코드는 Pydantic AI를 직접 알지 않지만 backend
프로젝트가 Pydantic AI 의존성과 에이전트 구현·테스트를 함께 소유한다.

이 변경은 장면 분석 전체를 독립 Python 패키지로 분리한다. backend는 버전 있는 공개
계약과 단일 facade만 사용하고, Pydantic AI 및 분석 내부 구현을 알지 않는다.

## 목표

- 저장소 루트에 독립적인 `llm-agent/` Python 프로젝트를 둔다.
- backend가 `NarrativeAnalysisAgent.analyze_scene()`만 호출하게 한다.
- Pydantic AI는 청크별 구조화 추출에만 사용한다.
- 청크 분할, 번역, stable ID 생성, 후보 상태 부여와 병합은 결정적 코드로 유지한다.
- 프롬프트와 LLM 감사 저장을 `llm-agent`가 소유한다.
- 공개 request/result DTO는 Pydantic AI, FastAPI와 SQLite에 의존하지 않는다.
- 기본 테스트는 오프라인·결정적으로 실행하고 실제 모델 검증은 명시적 opt-in으로 둔다.

## 비목표

- 상위 LLM이 하위 에이전트를 도구로 호출하는 multi-agent 추론 구조
- LLM을 사용한 청크 분할, 번역, stable ID 생성 또는 최종 병합
- 별도 HTTP/RPC 서비스나 독립 배포 프로세스 도입
- 장면 분석 HTTP API 추가
- 분석 결과의 자동 backend 저장
- Story Bible이나 Manuscript 상태의 직접 조회·변경
- Writing Assistant 기능 구현

## 패키지 경계

독립 프로젝트 디렉터리 이름은 `llm-agent/`, 배포 및 import 패키지 이름은 각각
`narrative-analysis-agent`, `narrative_analysis_agent`로 한다.

```text
llm-agent/
├── pyproject.toml
├── uv.lock
├── src/narrative_analysis_agent/
│   ├── __init__.py
│   ├── contracts.py
│   ├── facade.py
│   ├── orchestrator.py
│   ├── chunking.py
│   ├── extraction/
│   │   ├── agent.py
│   │   └── schemas.py
│   ├── assembly/
│   │   ├── translation.py
│   │   ├── merge.py
│   │   ├── models.py
│   │   └── validation.py
│   ├── audit/
│   │   ├── ports.py
│   │   └── sqlite.py
│   └── prompts/
│       └── scene-analysis/system.md
└── tests/
    ├── unit/
    ├── integration/
    └── live/
```

`llm-agent`는 다음을 소유한다.

- 장면 분석 공개 계약과 facade
- 프롬프트 파일, 버전 검증과 hot loading
- 정규 청크 분할
- Pydantic AI 모델 어댑터와 엄격한 provider 출력 스키마
- 청크별 재시도와 실행 오케스트레이션
- provider 출력의 내부 모델 번역
- evidence 절대 offset, 결정적 stable ID와 `pending` 상태 부여
- 청크 결과 병합과 최종 불변 조건 검증
- LLM prompt/run/attempt 감사 SQLite

backend는 다음만 소유한다.

- 애플리케이션 입력에서 공개 `SceneAnalysisRequest` 구성
- `NarrativeAnalysisAgent.analyze_scene()` 호출
- 공개 성공 결과 사용과 공개 오류 변환
- 반환된 결과를 저장할지 결정하는 애플리케이션 유스케이스

Narrative Memory의 도메인 의미와 계약 소유권은 계속 `docs/domains/narrative-memory.md`에
남는다. 독립 패키지는 그 계약의 장면 분석 구현체이며 별도 도메인이 아니다.

## 공개 계약

공개 타입은 표준 라이브러리 dataclass, enum과 기본 타입으로 작성한다. 공개 계약 모듈은
Pydantic AI, Pydantic, FastAPI, SQLite를 import하지 않는다.

```python
result = await agent.analyze_scene(
    SceneAnalysisRequest(
        project_id=project_id,
        scene_id=scene_id,
        scene_revision=scene_revision,
        scene_sequence=scene_sequence,
        text=text,
        known_entities=known_entities,
        known_places=known_places,
    )
)

snapshot = result.snapshot
run_id = result.run_id
```

`SceneAnalysisRequest`는 현재 분석 입력의 의미를 보존한다.

- project ID
- scene ID, revision, sequence와 불변 본문
- 선택적 알려진 인물·장소 정체성 카탈로그

`SceneAnalysisResult`는 감사 조회용 `run_id`와
`scene-relationship-snapshot-v1` 구조의 typed snapshot을 가진다. snapshot은 JSON
직렬화를 지원하되 backend에 Pydantic 모델을 노출하지 않는다.

## 실행 흐름

```text
backend
  │ SceneAnalysisRequest
  ▼
NarrativeAnalysisAgent
  ├─ 모델 설정과 프롬프트 로드·버전 검증
  ├─ 감사 prompt 등록과 run 시작
  ├─ 본문 정규 청크 분할
  ├─ 숫자 청크 순서대로 ChunkAnalysisAgent 호출
  │    ├─ attempt 시작 감사
  │    ├─ Pydantic AI 구조화 출력 호출
  │    ├─ ChunkExtractionOutput 검증
  │    └─ attempt 성공·실패와 사용량 감사
  ├─ 검증된 출력을 내부 분석 모델로 번역
  ├─ evidence 절대 offset, stable ID와 pending 상태 부여
  ├─ 청크 분석을 결정적으로 병합
  ├─ 최종 snapshot 불변 조건 검증
  ├─ run 성공 감사
  ▼
SceneAnalysisResult(run_id, snapshot)
```

청크는 기존 계약과 같이 최대 300자, 50자 중첩, 250자 stride로 생성하고 숫자 순서대로
직렬 분석한다. Pydantic provider 출력은 local/known reference와 상대 evidence만 만들 수
있으며 stable ID, 영속 candidate ID 또는 후보 상태를 만들 수 없다.

번역 경계는 상대 evidence가 청크 원문과 일치하는지 검증한 뒤 절대 offset으로 변환한다.
번역·병합은 같은 입력과 provider 출력에 대해 항상 같은 결과를 생성해야 한다.

한 청크가 최종 실패하면 부분 snapshot을 반환하지 않는다. 성공 결과도 감사 run 성공
기록까지 완료된 뒤에만 반환한다. 결과는 자동 저장하지 않으며 `llm-agent`는 backend의
Narrative Memory, Manuscript 또는 Story Bible 저장소를 호출하지 않는다.

## 오류 계약

공개 오류는 다음 패키지 전용 계층으로 제한한다.

```text
NarrativeAnalysisError
├── AnalysisConfigurationError
├── PromptLoadError
├── ProviderUnavailableError
├── InvalidExtractionError
└── AnalysisAuditError
```

- 모델 설정 또는 프롬프트 검증 실패 시 provider를 호출하지 않는다.
- prompt 등록과 run/attempt 시작 감사 실패는 provider 호출을 차단한다.
- provider 호출 실패만 청크별 최대 두 번 시도한다.
- 구조화 출력 및 evidence 검증 실패는 재시도하지 않는다.
- 어느 청크든 최종 실패하면 run 실패를 감사하고 결과를 반환하지 않는다.
- 취소는 best-effort 실패 감사를 기록하고 `asyncio.CancelledError`를 그대로 전파한다.
- provider 본문, 프롬프트와 원고는 공개 오류나 일반 로그에 포함하지 않는다.
- 공개 오류는 가능한 경우 감사 조회용 `run_id`만 제공한다.
- backend는 공개 오류 타입을 애플리케이션 또는 API 오류로 변환하고 내부 원인을 해석하지
  않는다.

## 감사 저장

`llm-agent`가 별도 SQLite 감사 저장소를 소유한다. 기존 보장을 그대로 유지한다.

- 프롬프트 원본 bytes, ID, version, result schema와 content hash
- run 시작·성공·실패
- 청크별 attempt 시작·성공·실패
- provider/model identity, latency와 token usage
- 원본 모델 메시지와 검증된 extraction JSON
- 같은 run, chunk와 attempt 번호에 최대 하나의 terminal event
- 감사 DB 파일의 owner-only 권한

감사 저장 위치는 facade 구성에서 명시적으로 주입한다. backend는 감사 port나 event 타입을
구현하지 않는다.

## 테스트 전략

### 단위 테스트

- 청크 경계와 중첩
- provider 출력 strict validation
- provider 출력에서 내부 모델로의 변환
- evidence 원문·offset 검증
- 결정적 ID, 상태 부여와 병합
- 분석 불변 조건
- prompt version/hot-load 검증
- 감사 스키마와 terminal event 유일성
- 공개 오류의 비밀정보 제거

### 오프라인 통합 테스트

Pydantic AI `TestModel` 또는 scripted model로 공개 facade 전체를 실행한다. 저장소 루트의
`input.txt`와 `relationships.json`을 acceptance fixture로 유지한다. scripted 청크 출력이
최종적으로 `relationships.json`과 정확히 같은 typed snapshot을 만드는지 검증한다.

### 실제 모델 테스트

실제 모델 테스트는 `live` marker와 `RUN_LLM_LIVE_TESTS=1`이 모두 있을 때만 실행한다.
기본 pytest와 CI에서는 제외한다. 실제 결과는 비결정적 문장과 confidence를 정확 비교하지
않고 다음을 검증한다.

- 공개 result schema 유효성
- 기대 인물 pair와 relationship category의 검출
- evidence가 원문 및 offset과 정확히 일치함
- 명시되지 않은 관계·장소 사실을 추론하지 않음

### backend 계약 테스트

backend는 fake `NarrativeAnalysisAgent`를 주입해 요청 변환, 성공 결과 사용과 공개 오류
변환만 검증한다. Pydantic AI, 실제 모델과 agent 감사 DB를 backend 테스트에서 사용하지
않는다.

## 검증 명령

`llm-agent/`에서:

```sh
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

실제 모델 opt-in 검증:

```sh
NARRATIVE_LLM_MODEL=<model> \
RUN_LLM_LIVE_TESTS=1 \
mise exec -- uv run pytest -m live -v
```

`backend/`에서:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

## 마이그레이션

1. `llm-agent` 프로젝트와 provider-independent 공개 계약을 만든다.
2. 현재 backend 장면 분석의 순수 모델, 청크, 번역, 병합과 검증 테스트를 이동한다.
3. Pydantic AI 어댑터, prompt registry, 프롬프트와 감사 저장을 이동한다.
4. 공개 facade와 오프라인 acceptance 테스트를 완성한다.
5. backend에 로컬 패키지 의존성을 추가하고 현재 분석 포트를 facade 호출로 교체한다.
6. backend에서 Pydantic AI 직접 dependency와 이동된 구현·테스트를 제거한다.
7. 두 프로젝트의 전체 검증과 opt-in 실제 모델 테스트를 실행한다.
8. `backend/README.md`, backend coding rules와 저장소 구조 문서를 새 소유권에 맞춘다.
9. 도메인 의미가 유지됨을 `docs/domains/narrative-memory.md`와 구현 diff로 확인한다. 구현
   과정에서 책임 또는 불변 조건이 달라지면 같은 변경에서 도메인 문서를 갱신한다.

마이그레이션 중에는 같은 구현의 backend 사본과 `llm-agent` 사본을 장기간 병행하지 않는다.
facade acceptance가 통과한 뒤 backend 소비자를 전환하고 이전 구현을 같은 변경에서 제거한다.

## 완료 조건

- backend production code와 테스트에 `pydantic_ai` import가 없다.
- backend는 공개 request/result/error와 facade만 import한다.
- 장면 분석의 provider 호출, 감사, 번역과 병합이 모두 `llm-agent`에 있다.
- 공개 facade 오프라인 통합 테스트가 최종 snapshot까지 통과한다.
- backend fake-agent 계약 테스트가 통과한다.
- 기존 청크, 재시도, 감사, 보안, 번역, 병합과 snapshot 불변 조건이 보존된다.
- `llm-agent`와 backend의 전체 pytest, lint와 format 검사가 통과한다.
- live 테스트는 기본 검사에서 제외되고 명시적으로 실행 가능하다.
- 구조 및 소유권 문서가 구현과 일치한다.
