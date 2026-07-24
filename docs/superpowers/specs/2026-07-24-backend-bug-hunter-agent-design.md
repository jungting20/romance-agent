# Backend 버그 탐색 전용 에이전트 설계

## 목적

프로젝트에 하나의 소비자 API operation 또는 명시적인 backend use case를
격리된 fixture와 임시 저장소에서 반복 실행해 객관적인 backend 결함을 찾는
`backend-bug-hunter` custom agent를 추가한다. 확정된 신규 결함만
`ticket-worker`에 등록하고, 탐색 전체 결과와 정제된 실행 증거를 한글 HTML
보고서로 남긴다.

이 agent는 실행 중인 화면을 탐색하는 기존 `bug-hunter`와 완료된 Python
구현을 읽기 전용으로 검토하는 `backend-review` 사이의 중간 역할이 아니다.
`backend-bug-hunter`는 구현 리뷰나 브라우저 조작 없이, 할당된 operation 또는
use case의 관찰 가능한 동작을 능동적으로 실행하고 결함을 재현하는 별도 역할이다.

## 선택한 접근

전용 agent, 전용 보고서 템플릿, 전용 validator를 각각 추가하고 루트
`AGENTS.md`에 독립적인 위임 정책을 둔다.

- `.codex/agents/backend-bug-hunter.toml`은 실행 범위, 안전 제약, 탐색 순서,
  등록 게이트와 handoff 계약을 정의한다.
- `docs/bug-reports/backend-report-template.html`은 backend 실행 증거에 맞는
  한글 보고서 구조를 제공한다.
- `.codex/agents/tests/validate-backend-bug-hunter.sh`은 agent·정책·템플릿의
  정적 계약과 안전 관련 양성·음성 fixture를 검증한다.
- 루트 `AGENTS.md`는 메인 agent가 제공해야 할 입력, 쓰기 소유권, 실패 처리,
  티켓 등록과 최종 검토 책임을 정의한다.

기존 `bug-hunter` 보고서와 validator를 재사용하는 방식은 채택하지 않는다.
그 계약은 route, viewport, 브라우저 조작, 스크린샷을 중심으로 하므로 요청·응답,
transaction rollback, 임시 DB와 정제 로그를 중심으로 하는 backend 증거와 맞지
않는다. agent와 루트 정책만 추가하는 최소 방식도 채택하지 않는다. 실행 주체가
LLM인 만큼 fixture 격리, 민감정보 제거와 partial handoff를 독립 validator로
검증할 필요가 있다.

## 역할과 경계

`backend-bug-hunter`는 할당마다 다음 중 정확히 하나만 탐색한다.

1. 승인된 OpenAPI baseline에 존재하는 하나의 `operationId`
2. HTTP로 노출되지 않은 하나의 명시적 backend application use case

operation과 use case를 동시에 묶거나 여러 operation을 한 번에 탐색하지 않는다.
entry point에서 직접 도달하는 schema 또는 입력 모델, application service, domain
logic, repository 또는 provider port, 오류 매핑과 관련 테스트 fixture까지만 탐색
경계에 포함한다. 공유 코드가 호출 경로에 있더라도 다른 operation이나 다른 use
case를 독립적으로 감사하지 않는다. 대상이 둘 이상이거나 경계가 모호하면 실행을
시작하지 않고 메인 agent에 분할 또는 명확화를 요청한다.

기존 역할은 다음처럼 보존한다.

- `bug-hunter`: 지정 route와 사용자 흐름의 실제 브라우저 UI·UX 탐색
- `backend-review`: 완료된 backend 구현의 읽기 전용 계약·아키텍처 검토
- `backend-bug-hunter`: 기존 backend 동작을 격리 실행해 새로운 결함을 발견·재현

`backend-bug-hunter`는 결함을 수정하거나 구현을 승인하지 않는다. 제품 코드,
테스트, `.codex/agents/bug-hunter.toml`, `.codex/agents/backend-review.toml`,
`backend/AGENTS.md`, `docs/api/openapi.yaml`, `docs/domains/**`, package 또는 lock
파일을 수정하지 않는다.

## 호출 입력 계약

메인 agent는 다음 입력을 모두 제공한다.

- 대상 종류와 식별자: 하나의 `operationId` 또는 하나의 backend use case 이름
- 정확한 backend entry point: route handler, service method 또는 use-case symbol
- consumer-facing operation인 경우 main-agent-approved OpenAPI baseline의 path,
  revision 또는 diff identity와 해당 `operationId`
- 관련 `docs/domains/*.md` 계약과 적용할 요구사항 또는 수용 기준
- 시작 fixture의 경로 또는 생성 명령, fixture 내용의 의미와 expected revision
- 인증 상태, principal 또는 권한 fixture와 인증 우회 금지 조건
- 실행별 전용 임시 DB·파일 경로, 허용된 임시 상위 경로, 격리·초기화·정리 방식
- 허용된 server, test, fixture, inspection 및 verification 명령
- 제외할 handler, operation, use case, domain, provider, 데이터와 동작
- 허용되는 데이터 변경과 금지되는 데이터 변경
- 확인할 오류 주입, 동시성, 재시도 시나리오

operation 대상인데 승인된 OpenAPI baseline 또는 `operationId`가 없거나, 관련
domain contract가 지정되지 않았거나, fixture·인증·임시 저장소·허용 명령·제외
범위·데이터 변경 제한 가운데 하나라도 빠지면 setup 전에 중단한다. HTTP가 아닌
use case에는 OpenAPI baseline을 요구하지 않으며 그 부재를 정상적인 비적용으로
기록한다.

## 격리와 데이터 안전

탐색은 실제 운영 데이터, 외부 provider, 공유 DB 또는 다른 실행과 공유하는 파일을
사용하지 않는다. 메인 agent가 승인한 임시 상위 경로 아래에 실행별 고유 디렉터리를
만들고, resolve한 경로가 승인된 상위 경로 안에 있으며 production/shared 경로와
다름을 확인한 후에만 fixture를 배치한다.

각 재현 run은 다음 규칙을 따른다.

1. 변경 불가능한 시작 fixture에서 새 run 디렉터리로 복제하거나 결정적으로 다시
   생성한다.
2. DB, lock, journal, temporary replacement file과 provider stub 상태를 run 사이에
   공유하지 않는다.
3. 해당 run이 소유한 디렉터리만 정리한다. 저장소 루트, 사용자 홈, 넓은 glob,
   unresolved 환경 변수 또는 공유 임시 디렉터리를 삭제 대상으로 사용하지 않는다.
4. fixture 원본과 제품 저장소의 tracked 파일은 수정하지 않는다.
5. 정리 전후 경로와 잔여 파일을 기록하고, 정리에 실패하면 partial handoff에
   남긴다.

provider failure는 외부 네트워크나 실제 credential로 만들지 않는다. 할당된
boundary가 provider를 직접 사용하면 fake, stub 또는 승인된 failure adapter만
사용한다. provider가 호출 경로에 없으면 비적용 근거를 기록한다.

## 탐색 절차

1. 루트 `AGENTS.md`, `backend/README.md`, `backend/AGENTS.md`, backend coding
   rules, 관련 domain contract, 수용 기준과 승인된 OpenAPI baseline을 읽는다.
2. `.codegraph/`가 있으면 entry point와 직접 호출 경로를 CodeGraph로 먼저
   확인한다. 현재 Git 상태와 실행 revision을 기록한다.
3. backend setup 전에 `zellij-agent ticket-worker list --json`을 실행해 기존
   티켓의 제목, 관찰 가능한 증상, 영향과 수정 경계를 중복 기준선으로 보존한다.
   목록이 명시적으로 미초기화라고 보고할 때만 `ticket-worker init`을 한 번 실행한다.
4. 입력 계약과 임시 경로를 검증하고 첫 번째 clean run 저장소를 만든다.
5. 정상 경로와 경계값을 확인한 다음 validation failure를 확인한다.
6. HTTP operation이면 계약과 실제 호출 경로에 적용되는 404, 409, 422, 500을
   확인한다. use case이면 같은 실패 원인을 소유하는 typed application error 또는
   domain/application failure를 확인한다. 도달 불가능한 status나 오류는 억지로
   만들지 않고 근거와 함께 비적용으로 기록한다.
7. 범위에 맞게 persistence rollback, 동시 실행, retry 또는 idempotency,
   provider failure, 오류 로그의 민감정보 노출을 확인한다. 요구사항이나 호출
   경로에 없는 항목은 비적용 근거를 남긴다.
8. 의심 결함마다 최소 재현 절차, 기대 결과, 실제 결과, 영향과 authoritative
   requirement를 정리한다.
9. 첫 run의 변경된 저장소를 재사용하지 않고 fixture 원본에서 두 번째 clean run을
   만든다. 같은 관찰 가능한 실패가 두 번 발생해야 확정 결함이다.
10. 등록 직전에 `zellij-agent ticket-worker list --json`을 다시 실행한다. 기존
    티켓과 target, trigger, observable failure, impact, repair boundary를 비교한다.
11. 확정·신규·범위 내·독립 수정 가능한 결함만 한 번 등록하고 fresh JSON에서
    command, ID, title, summary, prompt, evidence paths와 반환 상태를 검증한다.
12. 한글 HTML 보고서를 작성하고 전용 validator를 실행한다. 생성한 bug 문서,
    보고서와 evidence asset만 명시적으로 커밋할 수 있다.
13. 임시 자원을 정리하고 보고서, 티켓, 중복, 제외, 두 run 증거, 명령 결과,
    제한과 preserved changes를 handoff한다.

## 시나리오 매트릭스

모든 항목을 무조건 발생시키는 것이 아니라 할당된 operation/use case와 계약에
적용되는 항목을 확인한다. 비적용 항목은 보고서에서 생략하지 않고 이유를 기록한다.

| 분류 | 확인 내용 |
| --- | --- |
| 정상 | 승인된 요청 또는 입력이 성공하고 계약된 결과와 상태를 만든다. |
| 경계 | 빈 값, 최소·최대, revision 경계 등 reachable boundary를 확인한다. |
| Validation | transport 또는 application owner가 잘못된 입력을 거부하며 저장을 변경하지 않는다. |
| 404 | 대상 resource 부재가 계약된 응답 또는 typed failure로 변환된다. |
| 409 | revision, state 또는 concurrency 충돌이 부분 저장 없이 반환된다. |
| 422 | transport shape 또는 semantic validation의 승인된 오류가 반환된다. |
| 500 | 예상하지 못한 내부 실패가 내부 원인과 비밀을 노출하지 않는다. |
| Rollback | write 중 실패가 canonical state와 관련 레코드에 부분 변경을 남기지 않는다. |
| Concurrency | 동시에 시작한 요청의 결과가 lock/version/idempotency 계약을 지킨다. |
| Retry | retry가 중복 write 또는 손실을 만들지 않고 정의된 결과를 반환한다. |
| Provider failure | fake/stub 실패가 안전한 application/transport error로 변환된다. |
| 로그 | 요청, 오류, provider cause와 stack output에 민감정보가 남지 않는다. |

## 결함 판정과 티켓 등록

다음 조건을 모두 충족해야 신규 티켓을 등록한다.

- 할당된 operation 또는 use case 경계 안에서 발생한다.
- authoritative OpenAPI, domain contract, 수용 기준 또는 안정된 명시적 동작이
  기대 결과를 뒷받침한다.
- 독립된 두 clean run에서 동일하게 재현된다.
- 실제 결과, 영향, 저장 상태와 최소 재현 절차가 구체적이다.
- 기존 티켓과 target, trigger, observable failure, impact, repair boundary가
  중복되지 않는다.
- 하나의 독립된 수정과 검증 단위로 좁힐 수 있다.

성능 선호, 구조 개선 아이디어, 재현되지 않은 현상, 제품 결정이 필요한 모호한
기대, 허용되지 않은 명령이나 외부 자원으로만 재현되는 현상은 등록하지 않는다.

심각도는 `Blocking`, `High`, `Medium`, `Low`를 사용한다. 현재 프로젝트의
등록 정책과 맞춰 다음처럼 분기한다.

- `Blocking`, `High`, `Medium`: 보고서 anchor를 먼저 예약하고 한글 bug-specific
  design과 implementation plan을 만든다. 두 문서가 보고서 경로와 정확한
  `#bug-NNN` anchor를 상대 링크로 참조하는지 자체 검토한 뒤
  `zellij-agent ticket-worker add`로 등록한다.
- `Low`: 별도 design과 plan을 만들지 않는다. 보고서 경로와 정확한
  `#bug-NNN` anchor를 implementation evidence로 사용해
  `zellij-agent ticket-worker fast-add`로 등록하며 prompt에 정확히
  `FAST 모드로 처리한다`를 포함한다.

모든 실행 prompt는 `feature-development` 사용, `brainstorming`과
`writing-plans` 생략, 결함 범위 밖 변경 금지를 요구한다. 등록 실패, duplicate
판정 또는 post-registration 검증 실패를 ticket DB 직접 편집이나 추측성 재등록으로
복구하지 않는다.

## 민감정보 제거와 증거 계약

보고서와 ticket에는 원시 credential, Authorization 값, cookie, session ID,
access/refresh token, provider secret, private key, 전체 환경 변수 또는 작품의
비공개 원문을 저장하지 않는다. request, response와 로그는 허용된 필드만 남기고
나머지를 `[REDACTED]`로 치환한다. secret의 존재를 입증해야 할 때도 값 대신 필드
이름, 분류와 redaction 결과만 기록한다.

저장 전후 증거는 해당 결함을 입증하는 최소 레코드, revision, row count, canonical
hash, 파일 존재 여부와 정제된 diff로 제한한다. SQLite journal이나 원본 binary,
전체 DB dump, 전체 작품 snapshot을 보고서에 넣지 않는다.

각 확정 결함의 보고서 evidence는 두 clean run 각각에 대해 다음을 포함한다.

- 정제된 요청 또는 use-case 입력
- status와 정제된 응답 또는 application result/error
- 정제된 관련 로그
- 실행 전 저장 상태
- 실행 후 저장 상태
- 사용한 fixture identity와 고유 임시 경로의 정제된 식별자
- 실행 명령, 종료 코드와 관찰 시각

validator의 음성 fixture는 raw bearer token, authorization secret, cookie와
provider credential이 포함된 보고서를 거부한다. 값이 `[REDACTED]`로 치환된
양성 fixture와 민감정보 없는 0건 보고서는 통과해야 한다.

## 한글 HTML 보고서

매 실행은 다음 형식의 보고서 하나를 생성한다.

```text
docs/bug-reports/YYYY-MM-DD-HHmm-backend-<scope-slug>.html
```

보고서는 `lang="ko"`, UTF-8, viewport metadata, 의미 있는 heading 구조,
반응형 inline CSS, visible focus와 print style을 포함하고 JavaScript, CDN 또는
외부 resource를 사용하지 않는다. 사용자 대상 문장은 한글로 작성하고 정확한
operationId, symbol, path, 명령과 status만 원문을 유지한다.

필수 섹션은 다음과 같다.

1. 탐색 범위와 제외 범위
2. 실행 계약: target, entry point, OpenAPI baseline, domain contract, revision
3. 격리 환경: fixture, 인증 상태, 임시 DB·파일, 초기화·정리 방식
4. 시나리오 매트릭스 결과와 비적용 근거
5. 결과 요약과 등록한 버그
6. 버그별 두 clean run의 요청·응답, 정제 로그, 저장 전후 상태
7. 기존 티켓과 중복된 관찰 및 제외한 관찰
8. 수행 명령과 validator 결과
9. 실패, partial state, 정리 결과, 제약과 미확인 항목

각 버그에는 `bug-001` 형식의 안정적인 anchor를 부여한다. 확정 결함이 없어도
보고서를 만들되, 제한된 범위에서 등록할 결함이 없었다고만 기술하고 backend
전체에 버그가 없다고 일반화하지 않는다.

## 쓰기 소유권과 Git 규칙

agent가 소유할 수 있는 쓰기는 다음으로 제한한다.

- 새 `docs/bug-reports/YYYY-MM-DD-HHmm-backend-<scope-slug>.html`
- 그 보고서의 새 evidence asset
- `Blocking`, `High`, `Medium` 결함을 위한 새 `docs/superpowers/specs/**`와
  `docs/superpowers/plans/**`
- `ticket-worker` 명령을 통한 프로젝트 로컬 티켓 데이터
- 할당된 임시 상위 경로 아래의 현재 실행 전용 fixture 사본과 임시 저장소

기존 파일을 덮어쓰지 않고, pre-existing change를 stage, commit, restore 또는
delete하지 않는다. 커밋할 때는 agent가 새로 만든 bug 문서, 보고서와 evidence
asset만 정확한 pathspec으로 stage한다. 임시 fixture와 DB는 커밋하지 않는다.

## 실패와 partial handoff

필수 입력 누락, baseline 불명확, target이 둘 이상인 경우, 경로 격리 실패,
허용되지 않은 명령 필요, fixture 생성 실패가 발생하면 탐색을 시작하지 않는다.
실행 도중 실패하면 그 실패에 의존하는 재현, 문서 작성 또는 티켓 등록을 성공으로
표시하지 않는다.

partial handoff는 다음을 명시한다.

- target과 실패한 phase
- 완료한 phase와 실행하지 않은 phase
- 실행한 명령, 종료 코드와 정제된 오류
- 생성·검증·커밋한 artifact와 아직 검증하지 못한 artifact
- 등록된 ticket ID와 post-registration 검증 상태 또는 등록하지 않은 이유
- 생성한 임시 경로와 cleanup 성공·실패·잔여 파일
- 제품 파일, 계약과 pre-existing change가 보존됐는지 여부
- 재개에 필요한 정확한 입력 또는 안전 조치

ticket 등록이 성공한 뒤 보고서 또는 cleanup이 실패한 경우 ticket 존재를 숨기지
않고 partial handoff에 ID와 실제 상태를 남긴다. 생성하거나 확인하지 않은 artifact,
두 번 재현하지 못한 결함 또는 실행하지 않은 검사를 완료했다고 주장하지 않는다.

## 루트 정책 동기화

루트 `AGENTS.md`에 `Backend Bug-Hunting Subagent` 섹션을 별도로 추가한다. 이
섹션은 호출 조건, 필수 입력, 단일 target 규칙, 소유 경계, 격리와 금지 자원,
시나리오 매트릭스, 두 clean run, duplicate/registration gate, 보고서 evidence,
실패와 partial handoff, main-agent 최종 검토 책임을 정의한다.

기존 `Browser Bug-Hunting Subagent` 섹션의 의미나 등록 규칙은 수정하지 않는다.
`backend/AGENTS.md`는 backend 구현 agent의 정책이므로 이번 변경에서는 읽기
기준으로만 사용하고 수정하지 않는다. 프로젝트별 세부 코딩 규칙이나 domain
의미도 바뀌지 않으므로 backend engineering 문서와 `docs/domains/**`를 수정하지
않는다.

## Validator 설계

`validate-backend-bug-hunter.sh`은 Python 3.11 이상의 표준 `tomllib`과
`html.parser`를 사용한다. 저장소 toolchain으로 실행하며 다음을 확인한다.

- agent TOML의 name, description, sandbox와 developer instructions
- 단일 operationId 또는 use-case target, entry point와 모든 필수 입력
- setup 전 중단 조건과 승인된 OpenAPI baseline의 조건부 요구
- 실행별 고유 임시 저장소, fixture reset, 운영/shared 데이터와 외부 provider 금지
- 정상, 경계, validation, 404/409/422/500, rollback, concurrency, retry,
  provider failure와 log sensitivity의 적용성 기반 검사
- clean state 두 번 재현, setup 전과 등록 직전 fresh duplicate query
- severity별 `add`/`fast-add`, post-registration 검증과 ticket DB 직접 편집 금지
- 제품·OpenAPI·domain·기존 agent 수정 금지와 정확한 쓰기 소유권
- partial handoff 필수 필드와 허위 완료 금지
- backend report template과 생성 보고서의 한국어·HTML·외부 resource 계약
- 요청·응답, 정제 로그, 저장 전후 상태와 두 run evidence

validator 내부 fixture는 다음 결과를 보장한다.

- 정제된 두-run evidence가 있는 결함 보고서 통과
- 범위 내 0건 보고서 통과
- raw authorization/bearer token, cookie 또는 provider credential 거부
- unresolved template token 거부
- 필수 evidence나 안정적인 bug anchor 누락 거부
- 운영/shared DB 표기가 있거나 isolation 설명이 없는 보고서 거부
- 실패가 있는데 partial state와 cleanup 결과가 없는 보고서 거부

기존 browser validator에는 backend 검사 로직을 넣지 않는다. browser agent와
backend-review 파일이 변경되지 않았음은 별도의 read-only Git diff 검사로
확인한다.

## 검증 명령

worktree의 `mise.toml`을 신뢰한 뒤 저장소 Python을 사용한다.

```sh
mise trust mise.toml
mise exec -- bash .codex/agents/tests/validate-backend-bug-hunter.sh
git diff --check
git diff --exit-code HEAD -- \
  .codex/agents/bug-hunter.toml \
  .codex/agents/backend-review.toml \
  backend/AGENTS.md \
  docs/api/openapi.yaml \
  docs/domains
```

기존 `.codex/agents/tests/validate-bug-hunter.sh`도 저장소 Python으로 실행해
결과를 별도로 기록한다. 현재 승인 전 baseline에서는 HEAD의
`.codex/agents/bug-hunter.toml`에 validator가 요구하는 정확한
`zellij-agent ticket-worker list --json` 문구가 없어 실패한다. 이 선행 실패를
이번 backend agent 변경으로 고치거나 browser agent 책임과 혼합하지 않는다.

제품 backend Python을 변경하지 않으므로 backend pytest, Ruff와 format 전체 검사는
필수 변경 검사가 아니다. 최종 diff가 backend 제품 경계를 건드렸다면 그 시점에는
`backend/AGENTS.md`의 전체 검사를 추가하고 해당 변경을 별도 검토한다.

## 수용 기준

1. 메인 agent가 완전한 입력 계약으로 하나의 operationId 또는 backend use case를
   `backend-bug-hunter`에 위임할 수 있다.
2. agent는 운영 데이터, 외부 provider와 공유 저장소 없이 고유 임시 fixture에서만
   실행한다.
3. 정상과 적용 가능한 실패·rollback·concurrency·retry·provider·로그 시나리오를
   확인하고 비적용 항목의 근거를 남긴다.
4. 결함은 서로 독립된 두 clean run에서 재현되고 fresh duplicate 검사에 통과해야만
   등록된다.
5. 한글 HTML 보고서가 정제된 요청·응답, 로그, 저장 전후 상태와 두 run 증거를
   포함하며 raw secret을 거부한다.
6. 등록 실패 또는 실행 중단 시 실제 artifact, ticket, cleanup과 미완료 단계를
   partial handoff로 정확히 반환한다.
7. 제품 코드, 테스트, OpenAPI, domain contract, 기존 browser `bug-hunter`,
   `backend-review`와 `backend/AGENTS.md`는 변경되지 않는다.
8. 전용 validator의 양성·음성 fixture와 Git diff 검사가 통과한다.

## 승인된 결정과 알려진 제약

- UI 변경과 consumer-facing API 변경은 없으므로 UI plan과 OpenAPI drafting을
  수행하지 않는다.
- domain 의미와 backend 구현 규칙은 변경되지 않으므로 domain 문서와 backend
  coding rules를 수정하지 않는다.
- agent·template·validator·루트 위임 정책은 서로 강하게 연결되어 있어 메인
  thread가 한 변경 단위로 소유한다. `backend-review`를 이 작업의 reviewer로
  사용하면 그 역할을 구현 검토 밖으로 확장하게 되므로 사용하지 않는다.
- primary checkout의 `AGENTS.md`와 `.codex/agents/bug-hunter.toml`에는 다른 작업의
  미커밋 변경이 있다. 이 worktree는 그 변경을 복사하거나 덮어쓰지 않으며, 최종
  통합 시 루트 문서의 인접 변경을 보존하도록 별도 충돌 검토가 필요하다.
