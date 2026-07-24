# LLM 호출 감사 로깅 공통 모듈 설계

## 목표

Narrative Analysis Agent와 Dialogue Generation Agent의 모든 실제 LLM 호출을 같은 공통
경계에서 감사한다. 개별 agent는 저장 구현을 소유하거나 복제하지 않고, 기존 공개 요청·응답,
프롬프트 본문, 재시도 없음, 검증 규칙을 그대로 유지한다.

감사 데이터는 일반 애플리케이션 로그 및 telemetry와 분리한다. 민감한 원고, 캐릭터 비밀,
공개 금지 정보와 provider 응답 원문은 기본적으로 기록하지 않으며 명시적으로 활성화한 제한적
감사 sink에만 암호화해 보존한다.

## 범위

### 포함

- `llm-agent` 공통 immutable audit event, port와 `AuditedAgentRunner`
- Narrative Analysis Agent와 Dialogue Generation Agent의 공통 runner 적용
- agent name, run ID, attempt ID, model/provider 설정, prompt 식별자·버전·SHA-256
- UTC 시작·종료 시각, 단조 시계 기반 소요 시간, 성공·실패·취소 상태
- provider가 제공하는 token usage와 정제된 오류
- 선택적 system/user prompt, raw response, validated output 원문
- backend 소유의 전용 JSONL audit logger/handler, 회전·보존·삭제·암호화·파일 권한 정책
- llm-agent/backend 테스트와 엔지니어링 문서 동기화

### 제외

- consumer-facing HTTP API 및 OpenAPI 변경
- frontend audit viewer
- 외부 telemetry 전송
- retry 추가 또는 agent별 audit 저장 구현
- 프롬프트 본문, 공개 요청·응답, 기존 도메인 검증 규칙 변경
- 키 관리 서비스, 키 회전 UI, 감사 로그 검색·다운로드 UI

## 현재 상태와 제약

- 두 agent는 같은 `run(user_prompt, instructions=...)` 형태의 injected runner를 사용하지만 각
  package에 동일한 protocol이 있고 감사 경계는 없다.
- Narrative Analysis Agent는 장면 하나를 여러 청크로 나누어 청크마다 정확히 한 번 호출한다.
  Dialogue Generation Agent는 요청 전체를 정확히 한 번 호출한다.
- Pydantic AI의 결과는 actual provider/model, usage, raw response message와 validated Pydantic
  output을 제공한다. 테스트의 `RecordingRunner`는 provider 호출 관찰용 최소 fake이며 운영 감사
  저장소가 아니다.
- 기존 agent 문서는 개별 agent의 audit storage를 금지한다. 공통 port/decorator는 허용하되 구체
  저장, 보존, 삭제, 암호화와 접근 정책은 실행 애플리케이션 소유로 문구를 고친다.
- 현재 기준선은 llm-agent 비-live 테스트 133개와 backend 테스트 305개, 양쪽 ruff lint/format이
  모두 통과한다.

## 선택한 접근

### 검토한 대안

1. backend 소유 전용 JSONL 감사 로그를 사용한다. 일반 logging과 격리하기 쉽고 운영 로그로
   순차 보존·회전할 수 있으며 이번 범위의 단순 조회 없는 감사 요구에 맞는다.
2. 별도 SQLite 감사 DB를 사용한다. 트랜잭션과 조회는 강하지만 사용자가 원하는 로깅 전용
   경계보다 저장소 성격이 강하고 현재 viewer/query 범위를 불필요하게 앞당긴다.
3. llm-agent가 파일 또는 DB를 직접 소유한다. 재사용 package가 실행 환경의 보존·암호화 정책을
   결정하게 되어 책임 경계를 위반한다.

1안을 채택한다.

## 아키텍처와 소유권

### llm-agent

새 공통 package는 다음을 소유한다.

- provider-independent immutable start/terminal event
- `AgentAuditSink` port
- `AuditedAgentRunner` decorator
- run/attempt ID, UTC clock와 monotonic clock의 injectable factory
- Pydantic AI 결과에서 actual model/provider, usage, raw response와 validated output을 안전하게
  추출하는 adapter
- prompt ID/version/hash와 비밀값을 받지 않는 sanitized model configuration

공통 package는 파일, SQLite, environment variable, retention, encryption key와 logging handler를
소유하지 않는다.

각 agent는 prompt 상수와 agent name을 제공하고 public invocation마다 run ID를 만든다.
Narrative Analysis의 청크 호출들은 같은 run ID와 서로 다른 attempt ID를 사용한다. Dialogue
Generation의 generation ID는 도메인 결과 식별자이고 audit attempt ID와 별도로 유지한다.

### backend

backend의 audit infrastructure는 다음을 소유한다.

- 일반 로그와 다른 metadata JSONL 및 sensitive JSONL 파일
- `propagate = False`인 전용 logger와 해당 파일만 쓰는 handler
- owner-only directory `0700`, 파일 `0600`
- 자정 기준 파일 회전 및 만료 파일 삭제
- AES-256-GCM sensitive payload 암호화와 key ID
- raw capture 활성화와 retention 구성

암호화 키 bytes와 key ID는 실행 애플리케이션이 명시적으로 주입한다. audit adapter는 환경
변수를 직접 읽지 않으며 키나 credential을 event 또는 로그에 기록하지 않는다.

## 감사 계약

한 provider 호출은 하나의 start event와 정확히 하나의 terminal event를 만든다.

공통 식별·설정 필드는 다음을 표현한다.

- schema version
- event type
- agent name
- run ID
- attempt ID
- requested model/provider와 actual model/provider
- 허용 목록을 통과한 비밀 없는 model settings
- prompt ID, prompt version, `sha256:<hex>` hash

시간과 결과 필드는 다음을 표현한다.

- UTC started/ended timestamp
- monotonic duration milliseconds
- `success`, `failure`, `cancelled`
- input/output/cache read/cache write token과 provider가 제공한 추가 정수 usage
- 정제된 안정적 error type/code와 message

provider URL, provider details, headers, credential, API key, environment 값과 예외 repr/traceback은
계약에 포함하지 않는다. usage가 provider에서 제공되지 않으면 `null`을 기록하며 값을 추측하지
않는다.

## 민감 원문 처리

원문 기록은 기본 비활성화한다. 이때 metadata JSONL에는 원고, prompt 원문, response 원문,
validated output이 들어가지 않는다.

명시적으로 활성화하면 다음 값을 하나의 sensitive payload로 canonical JSON 직렬화한다.

- 렌더링된 system prompt
- 렌더링된 user prompt
- provider가 반환한 raw response message
- agent-specific semantic validation까지 통과한 validated output

payload는 AES-256-GCM으로 암호화한 뒤 sensitive JSONL에 base64 nonce/ciphertext, key ID와 audit
식별자만 기록한다. AAD에는 schema version, agent name, run ID와 attempt ID를 포함해 다른 레코드로
암호문을 옮길 수 없게 한다. 실패가 semantic validation 이전에 발생하면 validated output은
기록하지 않는다. provider가 raw response를 제공하지 못하면 해당 필드는 `null`이다.

metadata는 원문이 없으므로 암호화하지 않는다. 민감 파일이 일반 logger/telemetry로 전달되지
않도록 전용 handler 외의 handler를 연결하지 않고 propagation을 금지한다.

## 보존 정책

- metadata JSONL: 30일
- encrypted sensitive JSONL: 7일

각 stream은 자정에 회전하며 backup count를 넘긴 회전 파일을 실행 애플리케이션의 handler가
삭제한다. 현재 활성 파일은 다음 회전 시 만료 판단 대상이 된다. 별도 scheduler, archive 또는
external log shipper는 이번 범위에 포함하지 않는다.

## 호출 흐름과 오류 처리

1. agent가 기존 방식으로 system/user prompt를 렌더링한다.
2. `AuditedAgentRunner`가 start event를 전용 sink에 기록한다.
3. start 기록이 성공한 경우에만 wrapped runner를 한 번 호출한다.
4. runner 결과를 agent 고유 validator가 검증한다.
5. decorator가 usage와 선택적 원문을 추출하고 terminal event를 기록한다.
6. terminal 기록 성공 후에만 validated output을 agent에 반환한다.

감사 로깅은 활성 sink가 주입된 경우 fail-closed다. start 기록 실패는 provider 호출을 막고,
terminal 기록 실패는 성공 결과를 반환하지 않는다. 두 agent는 이 실패를 기존의 정제된 공개
오류 타입과 메시지로 번역하므로 public error 의미를 확장하지 않는다.

provider 또는 validation 실패는 원래 예외 세부정보를 저장하지 않고 분류된 정제 오류만 기록한
뒤 기존 공개 오류로 번역한다. cancellation은 terminal cancelled 기록을 best-effort로 시도하고
`asyncio.CancelledError`를 그대로 전파한다. raw capture가 꺼진 기본 구성은 예외 객체나 prompt를
어떤 로그에도 전달하지 않는다.

## 호환성과 도메인 영향

- 두 agent의 공개 request/result model과 exception type/message는 유지한다.
- system prompt 파일의 bytes와 user prompt envelope 의미는 유지한다.
- provider 호출 횟수와 순서, retry 없음, cancellation, 부분 결과 없음 규칙을 유지한다.
- `RecordingRunner`와 offline runner는 호출 관찰용 test double로 유지하고 audit sink 테스트에는
  별도 recording sink를 사용한다.
- 감사 로깅은 cross-cutting engineering concern이며 Narrative Memory와 Writing Assistant의
  책임, 보편 언어, 불변 조건 또는 컨텍스트 맵을 바꾸지 않는다. 따라서 `docs/domains/*`는
  수정하지 않는다.

## 테스트와 검증

llm-agent focused tests는 다음을 검증한다.

- 두 agent가 동일한 `AuditedAgentRunner` 경계를 사용한다.
- run/attempt ID, prompt metadata, 시간, 상태와 usage가 정확하다.
- success, provider failure, semantic validation failure와 cancellation terminal event가 정확하다.
- audit start 실패는 provider 호출을 막고 terminal 실패는 결과를 차단한다.
- raw capture 기본값에서는 민감 원문이 event에 없다.
- raw capture 활성화 시에만 result inspector가 원문 payload를 sink에 전달한다.
- 기존 prompt, output, validation과 호출 횟수 테스트가 그대로 통과한다.

backend focused tests는 다음을 검증한다.

- metadata/sensitive stream 분리와 logger non-propagation
- directory/file owner-only mode
- JSONL 한 줄 canonical record와 midnight rotation/30일·7일 보존 구성
- raw disabled 시 sensitive 파일 미생성
- raw enabled 시 plaintext 부재, AES-GCM envelope와 key ID
- credential 또는 일반 logger 노출 부재
- Narrative Analysis composition의 공통 sink 주입

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

구현 편집이 끝나면 complete affected Python boundary에 대해 read-only backend review를 수행한다.
모든 accepted finding을 수정하고 필요한 re-review 뒤 동일한 전체 검증을 다시 실행한다.

## 승인된 결정 요약

- persistence: backend 소유 전용 JSONL audit logging
- raw capture default: disabled
- metadata retention: 30일
- encrypted content retention: 7일
- encryption: raw sensitive payload 전체 AES-256-GCM, metadata는 plaintext
- failure mode: configured audit sink에 대해 fail-closed, cancellation audit는 best-effort
- API/UI/domain: 변경 없음
