# 지식 그래프 추출 v2 설계

## 배경

현재 `llm-agent`는 장면 본문 청킹, 일반 Markdown 시스템 프롬프트 로딩,
Pydantic AI 구조화 출력과 청크별 순차 호출만 소유하는 경량 패키지다. 공개 Pydantic
모델이 provider 출력과 공개 결과를 동시에 표현하며, 성공 결과는 병합된 장면
스냅샷이 아니라 순서가 보존된 `SceneAnalysis.chunks`다.

이번 변경은 이 경량 구조를 유지하면서 청크 출력 계약을 사용자가 제시한 소설 지식
그래프 JSON으로 교체한다. `llm-agent`는 기존 프로젝트 그래프를 SQLite에서 읽기
전용으로 조회해 각 청크 입력에 제공한다. 청크 간 ID 재매핑, 중복 제거, 프로젝트
병합과 저장은 backend가 소유한다.

## 목표

- 시스템 프롬프트의 JSON 출력 예시를 제거하고 출력 구조는 Pydantic AI 응답 모델로만
  정의한다.
- 인물, 장소, 일반 사건, 관계, 이동, 공통 참조, 미해결 참조와 모순을 추출한다.
- 명시적 사실과 문맥상 거의 확실한 정보만 일반 후보로 허용한다.
- 기존 프로젝트 그래프를 모든 청크에 동일한 문맥으로 제공한다.
- 현재의 300자/50자 중첩, 숫자 순서 직렬 처리와 청크당 단일 호출을 유지한다.
- `llm-agent`는 프로젝트 그래프를 읽기만 하고 backend가 병합과 저장을 계속 소유한다.
- v1 호환이나 데이터 마이그레이션 없이 v2 계약으로 교체한다.

## 비목표

- 청크 간 LLM 결과를 `llm-agent` 안에서 병합하거나 중복 제거하는 기능
- provider 재시도, 감사 저장소, run ID 또는 prompt registry 재도입
- durable ID, 후보 상태 또는 장면 절대 evidence offset을 `llm-agent`가 생성하는 기능
- 프로젝트 그래프를 `llm-agent`가 쓰거나 저장하는 기능
- HTTP API, OpenAPI 또는 frontend 변경
- v1 snapshot decoder, 자동 마이그레이션 또는 런타임 자동 DB 삭제

## 경계와 소유권

### llm-agent

- 장면 본문 청킹과 순차 모델 호출
- 일반 Markdown 시스템 프롬프트 로딩
- strict Pydantic 지식 그래프 응답 모델
- 프로젝트 그래프 SQLite의 단일 read-only 조회
- 기존 프로젝트 그래프를 포함한 안정적인 청크 사용자 JSON 구성
- 청크 원문에 대한 evidence 문자열과 참조 무결성 검증
- 입력 순서를 보존한 `SceneAnalysis.chunks` 반환

`llm-agent`는 SQLite URI read-only 모드로만 프로젝트 DB를 연다. 쓰기 연결, 테이블
생성, schema migration, 프로젝트 병합과 저장 코드를 포함하지 않는다.

### backend

- agent 구성 시 프로젝트 그래프 DB의 정확한 경로 전달
- 청크 로컬 ID의 프로젝트 ID 재매핑
- 청크 및 장면 간 엔티티 통합과 중복 제거
- 장면별 분석 결과 교체와 프로젝트 지식 그래프 재구성
- snapshot version 낙관적 동시성 검사
- v2 JSON codec, SQLite schema와 쓰기 트랜잭션
- agent를 호출하기 전에 v2 SQLite 파일과 필수 테이블 초기화

backend는 분석 전에 프로젝트 그래프를 조회해 agent 요청에 넣지 않는다. 조회는
`llm-agent`가 수행하고, backend는 agent가 반환한 조회 snapshot version을 저장 시점의
expected version으로 사용한다. 새 저장소에서는 backend가 먼저 빈 v2 schema를 생성한 뒤
그 정확한 DB 경로로 agent를 구성하므로 read-only reader가 초기 분석에서도 존재하는
파일을 열 수 있다.

## 데이터 흐름

```text
backend
  │ SceneAnalysisRequest(project/scene identity, immutable text)
  ▼
llm-agent
  ├─ configured project graph SQLite를 read-only로 한 번 조회
  ├─ project record가 없으면 empty v2 graph 사용
  ├─ 본문을 300자/50자 중첩 청크로 분할
  ├─ 각 청크에 동일한 existing graph와 청크 원문 전달
  ├─ 각 청크를 정확히 한 번 호출
  ├─ KnowledgeGraphOutput strict validation
  └─ SceneAnalysis(source_snapshot_version, ordered chunks) 반환
  ▼
backend
  ├─ 청크 로컬 ID를 기존 또는 신규 프로젝트 ID로 재매핑
  ├─ 해당 scene graph 교체
  ├─ 전체 active scene graph에서 project graph 재구성
  ├─ source_snapshot_version 동시성 검사
  └─ v2 snapshot을 SQLite에 저장
```

한 분석 실행은 시작 시 읽은 하나의 프로젝트 snapshot을 모든 청크에 동일하게 사용한다.
같은 실행에서 앞 청크의 출력을 뒤 청크 입력에 누적하지 않는다.

## Pydantic AI 응답 계약

현재 `ChunkExtraction`을 사용자가 제시한 JSON과 같은 최상위 구조의
`KnowledgeGraphOutput`으로 교체한다. 모든 모델은 `extra="forbid"`, `frozen=True`,
`strict=True`이며 모음은 tuple로 표현한다.

```text
KnowledgeGraphOutput
├─ document: Document
├─ entities
│  ├─ characters: tuple[Character, ...]
│  ├─ locations: tuple[Location, ...]
│  └─ events: tuple[Event, ...]
├─ relations: tuple[Relation, ...]
├─ movements: tuple[Movement, ...]
├─ coreferences: tuple[Coreference, ...]
├─ unresolved_references: tuple[UnresolvedReference, ...]
└─ contradictions: tuple[Contradiction, ...]
```

필드 이름과 중첩 구조는 제시된 출력 형식을 유지한다.

- `Document`: `chapter_id`, `summary`, `narrative_time`
- `Character`: `id`, `canonical_name`, `aliases`, `description`, `gender`, `age`,
  `occupation`, `affiliation`, `status`, `first_mention`, `confidence`
- `Location`: `id`, `canonical_name`, `aliases`, `location_type`,
  `parent_location_id`, `description`, `first_mention`, `confidence`
- `Event`: `id`, `event_type`, `name`, `summary`, `participant_ids`,
  `location_ids`, `time_expression`, `narrative_time`, `sequence`, `evidence`,
  `confidence`
- `Relation`: `id`, `source_id`, `relation_type`, `target_id`, `state`,
  `directed`, `start_event_id`, `end_event_id`, `time_expression`,
  `scene_sequence`, `evidence`, `inference`, `confidence`
- `Movement`: `character_id`, `from_location_id`, `to_location_id`,
  `movement_type`, `event_id`, `time_expression`, `sequence`, `evidence`,
  `confidence`
- `Coreference`: `expression`, `resolved_entity_id`, `evidence`, `confidence`
- `UnresolvedReference`: `expression`, `possible_entity_ids`, `reason`
- `Contradiction`: `subject_id`, `field_or_relation`, `existing_value`,
  `new_value`, `evidence`, `possible_explanation`

`age`는 정확한 나이와 연령대 표현을 모두 보존할 수 있도록 `int | str | None`으로 둔다.
예시에서 null을 허용한 다른 속성과 참조도 nullable로 정의한다.

## 응답 검증

- `document.chapter_id`는 요청의 `scene_id`와 정확히 같아야 한다.
- `narrative_time`, `gender`, character `status`, relation `state`와
  `location_type`은 제시된 값만 허용한다.
- relation, event와 movement type은 표준 유형을 우선하되 새 유형은
  `UPPER_SNAKE_CASE` 정규식을 만족해야 한다.
- 모든 confidence는 유한한 `0.0..1.0` 값이어야 한다.
- 일반 엔티티, 사건, 관계와 이동은 `confidence >= 0.8`이어야 한다.
- 대상이 확정되지 않거나 confidence가 0.8보다 낮은 참조는 일반 후보가 아니라
  `unresolved_references`에만 기록한다.
- ID는 청크 결과 안에서 종류별로 유일해야 한다.
- 관계, 이동, 사건 참여자와 공통 참조는 같은 청크 출력 또는 기존 프로젝트 그래프의
  호환되는 ID만 참조할 수 있다.
- `evidence`와 `first_mention`은 해당 청크 원문에 그대로 포함되어야 한다.
- 잘못된 참조, confidence 정책 위반과 원문에 없는 근거는 유효하지 않은 청크 출력이다.

Pydantic AI가 JSON 구조와 기본 타입을 검증하고, 요청 및 청크 문맥이 필요한 검증은
`agent.py`의 작은 후검증 함수가 담당한다. 별도 내부 모델이나 translation 계층을 만들지
않는다.

## 청크 결과와 ID 의미

`character_001`, `location_001`, `event_001`, `relation_001`은 LLM 응답에서는 청크 로컬
ID다. `llm-agent`는 이 값을 durable identity로 해석하거나 청크 간 재작성하지 않는다.

`AnalyzedChunk`는 현재와 같이 chunk ID, ordinal, 장면 기준 시작·끝 위치, 원문과
`KnowledgeGraphOutput`을 가진다. `SceneAnalysis`는 장면 식별 정보, 기존 프로젝트
그래프에서 읽은 `source_snapshot_version`과 순서가 보존된 청크 튜플을 반환한다.

backend는 다음 순서로 최종 ID를 결정한다.

1. 기존 프로젝트의 대표 이름과 별칭에 명확히 일치하면 기존 ID를 재사용한다.
2. 여러 새 청크가 명확히 같은 대상을 나타내면 하나로 통합한다.
3. 애매하면 별도 엔티티로 유지하고 `POSSIBLE_SAME_AS` 관계를 보존한다.
4. 신규 ID는 원문 최초 등장 순서와 정규화 이름을 기준으로 결정적으로 할당한다.
5. 관계, 사건, 이동, 공통 참조와 미해결 참조의 모든 ID를 최종 ID로 재매핑한다.

동일 이름만으로 서로 다른 인물을 자동 병합하지 않는다. 관계 변화는 기존 관계를
덮어쓰지 않고 종료 상태와 새 관계 기록을 함께 유지한다.

## 프로젝트 그래프 읽기

`llm-agent`에는 작은 `ProjectGraphReader`를 추가한다. 생성 시 명시적인 DB 경로를 받고,
분석 시작 시 `project_id`의 current v2 snapshot payload와 version을 읽는다.

- DB 경로가 없거나 열 수 없으면 provider 호출 전에 실패한다.
- DB 파일은 존재하지만 프로젝트 current record가 없으면 empty graph와 version `0`을
  반환한다.
- 손상된 JSON, v1 또는 알 수 없는 schema version은 provider 호출 전에 실패한다.
- 조회 연결은 URI `mode=ro`를 사용하고 분석이 끝나기 전에 닫는다.
- DB payload, 시스템 프롬프트와 원고는 일반 로그나 공개 오류에 포함하지 않는다.

backend는 DB 경로를 agent 구성에 전달하지만 프로젝트 그래프를 대신 조회하거나
`SceneAnalysisRequest`에 그래프 객체를 넣지 않는다. backend가 소유한 초기화 절차가
DB 파일과 v2 테이블의 존재를 보장하며, `llm-agent` reader는 schema 생성이나 복구를
시도하지 않는다.

## 프로젝트 저장

backend는 장면별 `KnowledgeGraphOutput`과 집계된 `ProjectKnowledgeGraphSnapshot`을 같은
Narrative Memory SQLite 파일에 저장한다. 정확한 장면 교체와 provenance 보존을 위해
장면별 그래프 레코드를 별도로 유지하고 프로젝트 snapshot은 모든 active 장면 그래프에서
재구성한다.

프로젝트 snapshot v2는 다음 정보를 가진다.

- `project_id`, `snapshot_version`, `schema_version`
- 장면별 `documents`
- 통합된 characters, locations와 events
- 통합된 relations, movements와 coreferences
- 장면 출처를 보존한 unresolved references와 contradictions

저장 트랜잭션은 agent가 읽은 `source_snapshot_version`과 current version이 정확히 같을
때만 새 version을 기록한다. 다르면 동시성 충돌로 거부하고 새 snapshot을 덮어쓰지 않는다.

## 프롬프트

패키지 `system.md`는 사용자가 제공한 한국어 지식 그래프 추출 지침을 기준으로 교체한다.
다음 내용은 프롬프트에서 제거한다.

- `## 출력 형식` 아래 JSON 예시 전체
- `{{CHAPTER_ID}}`, `{{EXISTING_GRAPH_DATA}}`, `{{NOVEL_TEXT}}` 입력 템플릿

프롬프트에는 분석 목표, 근거 원칙, 동일 대상 통합, 관계 방향, 사실과 인식 구분,
관계 변화, 엔티티와 관계 의미, 시간 처리, confidence 기준, evidence 의미와 기존 그래프
재사용 규칙만 둔다. 실제 출력 구조는 `output_type=KnowledgeGraphOutput`이 제공한다.

현재 경량 prompt 정책을 유지하므로 YAML frontmatter, prompt version, schema metadata와
registry를 다시 도입하지 않는다. 입력 값은 `agent.py`가 JSON 사용자 메시지로 구성한다.

## 오류 처리

- prompt 읽기, 프로젝트 그래프 조회, provider 호출과 구조화 출력 실패는 내부 내용을
  숨긴 `NarrativeAnalysisError`로 변환한다.
- 프로젝트 record 부재만 empty graph로 취급한다. 파일 접근 실패, schema 불일치와 손상은
  분석 실패다.
- 각 청크를 정확히 한 번 호출하며 실패한 청크를 재시도하지 않는다.
- 한 청크 실패 시 뒤 청크를 호출하지 않고 앞 청크의 부분 결과도 반환하지 않는다.
- `asyncio.CancelledError`는 변환하지 않고 그대로 전파한다.
- backend 병합 또는 저장 실패는 agent 성공으로 위장하지 않고 application error로
  전달한다.

## v1 데이터 처리

v1 decoder, 자동 migration과 호환 계층은 만들지 않는다. 구현 시 먼저 설정으로 정확한
Narrative Memory SQLite 파일 경로를 확인하고, 사용자가 삭제를 승인한 그 파일만 한 번
삭제한다. 삭제 결과와 복구 가능 여부를 보고한다.

애플리케이션 실행 중 schema 불일치를 이유로 DB 파일이나 레코드를 자동 삭제하는 코드는
추가하지 않는다.

## 문서 변경

- `docs/domains/narrative-memory.md`를 v2 지식 그래프 의미, read/write 소유권과 새 불변
  조건에 맞춘다.
- `llm-agent/docs/llm-agent-coding-rules.md`는 프로젝트 graph read-only 조회만 허용하고
  DB 쓰기, 청크 병합과 durable ID 생성을 계속 금지하도록 갱신한다.
- `llm-agent/AGENTS.md`의 소유권과 필수 검증을 새 read-only 경계에 맞춘다.
- `backend/docs/backend-coding-rules.md`는 청크 그래프 병합과 v2 저장 책임을 기록한다.
- backend README의 agent 구성과 DB 경로를 갱신한다.

## 테스트 전략

### llm-agent

- 모든 strict Pydantic 응답 타입, enum, nullable 필드와 unknown field 거부
- UPPER_SNAKE_CASE, confidence와 청크 문맥 후검증
- 프로젝트 그래프 read-only 조회, empty project, 접근 실패, v1 및 손상 payload 거부
- 기존 그래프가 모든 청크 user JSON에 동일하게 포함되는지 확인
- 300/50 청크, 숫자 순서와 청크당 단일 호출 회귀
- provider와 구조화 출력 실패 시 즉시 중단 및 부분 결과 미반환
- 네트워크 없는 offline 전체 흐름
- opt-in live 모델의 추출 의미와 근거 검증

### backend

- 청크 로컬 ID 재매핑과 기존 ID 재사용
- 별칭 통합, 애매한 동명이인 분리와 `POSSIBLE_SAME_AS`
- 사건, 관계, 이동, 공통 참조, 미해결 참조와 모순 병합
- 장면 재분석 교체와 다른 장면 데이터 보존
- v2 codec 안정적 round-trip과 invalid payload 거부
- SQLite 장면 그래프 및 프로젝트 snapshot 저장·재조회
- snapshot version 동시성 충돌
- agent 공개 계약 소비와 오류 정제

전체 검증은 다음 명령을 사용한다.

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

## 완료 조건

- 시스템 프롬프트에 출력 JSON 예시와 입력 placeholder가 없다.
- Pydantic AI `output_type`이 제시된 지식 그래프 구조 전체를 strict하게 정의한다.
- 장면은 반드시 300자/50자 중첩 청크로 숫자 순서대로 분석되고 각 청크는 한 번만 호출된다.
- `llm-agent`는 프로젝트 그래프를 read-only로 한 번 조회하고 모든 청크에 동일하게
  전달한다.
- `llm-agent`는 청크 간 병합, durable ID 생성 또는 프로젝트 DB 쓰기를 하지 않는다.
- backend가 청크 로컬 ID를 결정적으로 재매핑하고 장면별 결과와 프로젝트 v2 snapshot을
  저장한다.
- v1 호환이나 자동 migration 없이 승인된 기존 DB만 한 번 삭제된다.
- `llm-agent`와 backend 전체 비-live 테스트, lint와 format 검사가 통과한다.
- domain 및 프로젝트 코딩 문서가 구현과 같은 소유권과 불변 조건을 설명한다.
