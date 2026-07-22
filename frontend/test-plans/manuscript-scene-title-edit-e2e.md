# 원고 장면 제목 편집 E2E 테스트 계획

## 범위와 실행 계약

- 대상 route: `/projects/silver-garden/write` (일반형 `/projects/$projectId/write`).
- 생성 대상: `frontend/manuscript-scene-title-edit.spec.ts`.
- 정확한 실행 명령(각 테스트 공통): `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`를 `frontend/`에서 실행한다.
- 승인 기준: 장면 제목은 기존 `Scene.title`이며, 기존 `PUT /api/manuscripts/silver-garden-manuscript`의 전체 Manuscript 저장과 기존 `POST /api/manuscripts/silver-garden-manuscript/scene-diffs` 충돌 비교만 사용한다. OpenAPI는 변경하지 않는다.
- 제외: 장/부 계층, 제목 최대 길이, 장면 번호·순서·삭제·계획·상태, 프로젝트 제목, AI, 새 API, 장면 추가 자체만 검증하는 coverage.

## 공통 seed, setup, locator, 진단

`frontend/seed.spec.ts`는 placeholder라 seed로 재사용하지 않는다. 대신 Ticket #3의 `frontend/manuscript-scene-add.spec.ts` harness를 다음과 같이 재사용한다.

1. 각 테스트는 `serviceWorkers: "block"`인 새 BrowserContext/Page에서 시작하고 route interception을 탐색 전에 등록한다.
2. 테스트마다 깊은 복사하는 workspace fixture는 프로젝트 `silver-garden`, 원고 `silver-garden-manuscript`, revision 1이다. Scene 1은 ID `silver-garden-scene-1`, 제목 `비가 그친 뒤의 정원`, 장 번호 1, 기존 본문·인물/세계관 참조, active 상태다. Scene 2는 고정 ID, 제목 `두 번째 장면`, 장 번호 2, 구별되는 본문과 빈 참조를 갖는다. Scene 2는 장면 추가 UI coverage 없이 전환 검증만 위한 seed다.
3. 정상 PUT은 요청의 전체 Manuscript를 fixture에 저장하고 revision을 증가시키며, 이후 GET은 그 fixture를 반환한다. 요청 배열/waiter에 메서드, URL, `expectedRevision`, 전체 Manuscript를 기록한다.
4. 고정 sleep으로 성공을 판정하지 않는다. 실제 800ms debounce는 실제 시간으로 두되 PUT waiter와 `getByRole("status", { name: "자동 저장됨" })`을 종료 조건으로 사용한다.
5. 기본 accessible locator는 `button/장면 제목 수정`, `textbox/장면 제목`, `textbox/원고 본문`, `heading/<title>`, exact text `N장 · <title>`, `button/N장 <title>`, `status/자동 저장됨`, `alert`, `dialog/원고 저장 충돌 해결`이다. 활성 목차 항목은 `aria-current="true"`로 판정한다.
6. 모든 테스트는 예상 밖 API, console error, pageerror, 요청/응답 순서와 body를 수집한다. 실패 시 viewport, 현재 focus의 accessible name, 세 제목 표면, 입력의 value/disabled/ARIA, autosave/alert/dialog 상태, revision과 네트워크 기록을 첨부한다. screenshot은 실패 진단 때만 사용하고 trace/network 자료를 우선한다.

## Suite 1 — 핵심 인라인 편집과 접근성

### Test 1 — Enter 확정은 세 표면을 동기화하고 전체 원고를 저장·재접속 복원한다

**Seed/setup:** 공통 2장면 revision-1 fixture, viewport `1024x900`, 첫 PUT 성공 revision 2.

1. route로 이동해 `원고 본문`, heading `비가 그친 뒤의 정원`, active button `1장 비가 그친 뒤의 정원`, `자동 저장됨`을 확인한다.
2. `장면 제목 수정`을 클릭한다.
   - 예상: `장면 제목` 입력이 focused이고 기존 제목 전체가 선택된다.
3. 입력을 `  남겨진 편지  `로 바꾸고 Enter를 누른다.
   - 예상: heading `남겨진 편지`, exact header `1장 · 남겨진 편지`, active button `1장 남겨진 편지`가 같은 흐름에서 나타난다.
   - 예상: 상태 영역은 `장면 제목을 저장할 준비가 되었어요.`를 알리고 focus는 `장면 제목 수정`으로 돌아간다.
4. PUT waiter로 800ms 자동 저장을 기다린다.
   - 예상: PUT은 정확히 1개, `expectedRevision: 1`, `scenes[0].title: "남겨진 편지"`다. 두 장면의 ID, 번호, 순서, 본문, 참조, `activeSceneId`는 seed와 같다.
   - 실패: 공백 미정규화, 부분/제목 전용 요청, 새 API, 다른 필드 변경, 중복 PUT.
5. 실제 `page.reload()` 후 revision-2 GET과 세 표면을 확인한다. 이어 기존 page를 닫고 같은 독립 context에 새 page를 연결해 route를 다시 연다.
   - 예상: reload와 reconnect 모두 제목, active 장면, 본문/참조, `자동 저장됨`을 복원한다.
6. 실패 진단에 PUT/GET body·revision, 세 표면, `aria-current`, focus/status, 오류 기록을 남긴다.

**성공 기준:** 정규화된 제목 하나만 기존 전체-Manuscript 계약으로 저장되고 reload/reconnect 뒤 동일하게 복원된다.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

### Test 2 — Escape는 초안을 취소하고 수정 버튼으로 focus를 복원한다

**Seed/setup:** 공통 fixture, `1024x900`, PUT 기록만 하고 응답 대기는 만들지 않는다.

1. 제목 편집을 열고 값을 `저장하면 안 되는 제목`으로 바꾸되 확정하지 않는다.
2. Escape를 누른다.
   - 예상: 입력이 닫히고 heading/header/active SceneTree가 모두 기존 제목이다.
   - 예상: 상태 영역은 `장면 제목 수정을 취소했어요.`를 포함하고 `장면 제목 수정` 버튼이 focused다.
3. 800ms를 지나도 취소 값이 포함된 PUT이 없음을 확인한다.
4. 실패 진단에 PUT count/body, active element, 세 표면과 상태 알림을 남긴다.

**실패 조건:** 취소 값이 Manuscript나 요청에 반영되거나 focus가 body로 빠진다.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

### Test 3 — 공백 Enter는 연결된 필드 오류를 유지하고 저장하지 않는다

**Seed/setup:** 공통 fixture, `1024x900`, PUT 기록.

1. 제목 편집을 열고 입력을 세 칸 공백으로 만든 뒤 Enter를 누른다.
   - 예상: `장면 제목` 입력은 focused 상태로 남고 `aria-invalid="true"`다.
   - 예상: accessible description과 `role="alert"`는 정확히 `장면 제목을 입력해 주세요.`이며 `aria-describedby` 연결이 유효하다.
2. 800ms 뒤에도 PUT이 없고 세 committed 표면은 기존 제목인지 확인한다.
3. 공백 뒤 한 글자를 입력한다.
   - 예상: 오류 연결이 해소되지만, 명시적 확정 전에는 committed 표면과 Manuscript가 바뀌지 않는다.
4. 실패 진단에 input value/ARIA/description, alert, PUT, 세 표면을 남긴다.

**실패 조건:** 공백이 저장되거나 입력이 닫히거나 max-length 동작을 추가로 가정한다.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

## Suite 2 — 저장 실패와 재시도

### Test 4 — 첫 저장 실패 뒤 제목을 유지하고 같은 최신 원고로 재시도한다

**Seed/setup:** 공통 fixture, `1024x900`; 첫 PUT은 `500 INTERNAL_ERROR`, 둘째 PUT은 성공 revision 2, 이후 GET은 성공 fixture.

1. `실패해도 남는 제목`을 Enter로 확정하고 첫 PUT을 기다린다.
   - 예상: `role="alert"`에 `저장 실패`, button `원고 저장 다시 시도`가 나타난다.
   - 예상: heading, exact header, active SceneTree 모두 로컬 제목을 유지하며 본문과 두 장면도 남는다.
2. `원고 저장 다시 시도`를 클릭하고 둘째 PUT 및 `자동 저장됨`을 기다린다.
   - 예상: 두 요청 모두 `expectedRevision: 1`; 재시도 body는 같은 제목과 최신 전체 Manuscript를 포함한다.
3. reload한다.
   - 예상: revision 2와 로컬 제목이 세 표면에 복원되며 conflict dialog는 없다.
4. 실패 진단에 두 PUT body/status 순서, revision, final GET, 세 표면과 alert/status를 남긴다.

**실패 조건:** 500 뒤 제목 소실, retry에서 seed 제목 회귀, 새 revision 오용, 새 API 호출.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

## Suite 3 — 409 충돌 해결

### Test 5 — 내 편집본 유지는 로컬 제목을 서버 revision 위에 보존한다

**Seed/setup:** 공통 fixture, `1024x900`; 첫 PUT 409, 기존 scene-diffs POST는 server revision 7 및 제목 `서버 최신 제목`/본문 `서버 최신 본문`을 포함한 authoritative 전체 원고, 해결 PUT은 revision 8 성공.

1. `내가 유지할 제목`을 Enter 확정하고 409 및 scene-diffs 완료를 기다린다.
   - 예상: dialog `원고 저장 충돌 해결`과 `내 편집본 유지`, `서버 최신본 적용`이 나타난다.
   - 예상: 배경의 `장면 제목 수정`은 disabled이며 제목 전용 conflict API는 없다.
2. `내 편집본 유지`를 선택한다.
   - 예상: 해결 PUT은 `expectedRevision: 7`; active scene 제목은 로컬 값이고 비교의 로컬 content를 유지하며 unrelated 서버 원고 필드를 보존한다.
   - 예상: dialog가 닫히고 세 표면의 로컬 제목, enabled 수정 버튼, `자동 저장됨`이 보인다.
3. reload해 revision 8과 같은 결과를 확인한다.
4. 실패 진단에 첫/해결 PUT, scene-diffs request/response, revision, dialog/button 상태, 세 표면과 final GET을 남긴다.

**실패 조건:** 로컬 제목 소실, 서버의 unrelated 변경 덮어쓰기, revision 1 재사용, 새 API 호출.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

### Test 6 — 서버 최신본 적용은 로컬 제목을 버리고 재저장하지 않는다

**Seed/setup:** Test 5와 같지만 해결 PUT은 허용하지 않고 authoritative server revision은 7이다.

1. `버려질 로컬 제목`을 확정해 409 dialog를 연다.
2. `서버 최신본 적용`을 선택한다.
   - 예상: 세 표면이 `서버 최신 제목`으로 일치하고 서버 본문/active 원고를 채택하며 수정 버튼은 enabled다.
   - 예상: 최초 conflicting PUT 외 추가 PUT은 없고, 800ms 뒤에도 버린 로컬 제목이 다시 저장되지 않는다.
3. reload해 revision 7 서버 원고만 복원되는지 확인한다.
4. 실패 진단에 PUT count/body, authoritative fixture, scene-diffs, 세 표면과 dialog/status를 남긴다.

**실패 조건:** 로컬 제목 재등장·자동 저장, resolution PUT 발생, 서버 원고 일부만 채택.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

### Test 7 — 이전 저장이 충돌하는 동안 입력 중 제목은 잠기지만 초안은 보존된다

**Seed/setup:** 공통 fixture, `1024x900`; body edit로 시작하는 첫 PUT을 barrier로 보류했다가 409 반환, scene-diffs는 기존 committed 제목과 server revision을 반환, `내 편집본 유지` 해결 PUT 성공.

1. `원고 본문`을 변경해 autosave PUT을 시작하고 응답을 보류한다.
2. PUT 대기 중 제목 편집을 열어 `충돌 중 보존할 제목`을 입력하되 Enter/blur하지 않는다.
3. 보류 PUT을 409로 해제한다.
   - 예상: conflict dialog가 열리고 배경 `장면 제목` locator의 value는 그대로이며 disabled다(모달 배경이 inert여도 locator state/value로 관찰).
   - 예상: Enter로 확정할 수 없고 어떤 PUT/scene-diffs body에도 uncommitted 제목은 없다.
4. `내 편집본 유지`로 body 충돌을 해결한다.
   - 예상: 같은 active scene이면 dialog 뒤 제목 입력이 enabled로 돌아오고 초안 값은 남지만 세 committed 표면은 아직 기존 제목이다.
5. 이제 Enter를 눌러 명시적으로 확정하고 다음 800ms PUT을 기다린다.
   - 예상: focus가 수정 버튼으로 돌아오고 세 표면/전체 Manuscript가 보존 제목으로 동기화된다.
6. 실패 진단에 barrier event 순서, 모든 request body, input value/disabled/focus의 단계별 상태와 revision을 남긴다.

**실패 조건:** 충돌 전에 입력값 자동 확정, conflict 진입 때 초안 소실, disabled 중 확정, 해결 뒤 조용한 자동 적용.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

## Suite 4 — 장면 전환과 반응형 동등성

### Test 8 — 장면 전환은 이전 장면의 미확정 제목 초안을 폐기한다

**Seed/setup:** 공통 2장면 fixture, `1024x900`, 모든 PUT 기록.

1. scene 1 제목에 `저장하면 안 되는 제목`을 입력하되 확정하지 않는다.
2. SceneTree button `2장 두 번째 장면`을 클릭한다.
   - 예상: scene 2가 `aria-current="true"`; heading/header/body가 scene 2 값이고 scene-1 제목 input/draft는 없다.
   - 예상: selection autosave가 발생해도 scene-1 title은 기존 값이며 미확정 문자열이 요청에 없다.
3. scene 1 button을 다시 클릭한다.
   - 예상: 세 표면은 원래 제목이고 초안이 부활하지 않는다.
4. 실패 진단에 PUT별 `activeSceneId`/scene titles, `aria-current`, 전환별 표면과 input 존재 여부를 남긴다.

**실패 조건:** 전환이 blur commit으로 미확정 제목을 저장하거나 다른 scene에 초안이 누출된다.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

### Test 9 — 375px와 1024px에서 같은 accessible 키보드 상호작용을 제공한다

**Seed/setup:** `test.each`로 정확히 `375x812`, `1024x900`을 각각 fresh fixture/context에서 실행한다.

1. 각 viewport에서 `장면 제목 수정`과 heading의 bounding box가 겹쳐 동작을 가리지 않는지 확인한다. 버튼을 클릭해 같은 `장면 제목` input이 focused이고 현재 제목 전체가 선택됐는지 확인한다.
2. viewport별 고유 제목을 Enter 확정한다.
   - 예상: 두 viewport 모두 focus가 수정 버튼으로 복원되고 heading 및 exact header가 동기화되며 1개의 expectedRevision-1 전체-Manuscript PUT 뒤 `자동 저장됨`이다.
3. `1024px`에서는 inline active SceneTree button을 확인한다. `375px`에서는 확정 뒤 tab `원고 보기`를 열고 dialog `원고 보기` 안에서 같은 active button을 확인한 뒤 Escape로 Sheet를 닫는다.
   - 예상: 모바일도 데스크톱 전용 selector 없이 같은 제목 편집 interaction을 사용하고 Sheet close가 committed 제목을 바꾸지 않는다.
4. 실패 진단에 viewport, bounding boxes, focus/selection, Sheet state, 세 표면과 PUT body를 남긴다.

**실패 조건:** 모바일에서 제목/버튼 겹침, 다른 accessible name, pointer-only 동작, SceneTree 확인을 위해 제목을 재편집해야 함.

**File/run:** `frontend/manuscript-scene-title-edit.spec.ts`; `mise exec -- pnpm exec playwright test manuscript-scene-title-edit.spec.ts`.

## Traceability

| 요구                                                     | Tests     |
| -------------------------------------------------------- | --------- |
| Enter 확정, trim, focus 복원                             | 1, 9      |
| Escape 취소                                              | 2         |
| 공백 validation과 연결 오류                              | 3         |
| editor heading / `N장 · title` / active SceneTree 동기화 | 1, 4–6, 9 |
| 800ms 전체 원고 autosave, reload/reconnect 복원          | 1         |
| 첫 실패 + retry 제목 유지                                | 4         |
| 409 + keep-local                                         | 5         |
| 409 + server-latest                                      | 6         |
| conflict lock 중 in-progress draft 보존                  | 7         |
| scene 전환 시 미확정 초안 폐기                           | 8         |
| mobile 375 / desktop 1024 접근성 동등성                  | 9         |
| 기존 saveManuscript·scene-diffs만 사용                   | 1, 4–7    |

## 위험과 제약

- repo Playwright config는 named `chromium` project가 없어 planner setup의 해당 project 선택은 실패한다. 실제 spec은 config의 기본 project로 위 exact 명령을 실행한다.
- 개발 MSW Service Worker가 `page.route`보다 먼저 응답하지 않도록 Ticket #3와 동일하게 `serviceWorkers: "block"`을 강제한다. placeholder `seed.spec.ts`에 의존하지 않는다.
- 제목 편집 중 이전 PUT 충돌(Test 7)은 응답 barrier가 필수다. modal이 background를 inert 처리하므로 value/disabled는 locator property로 관찰하고 visibility assertion으로 잘못 모델링하지 않는다.
- 모바일 SceneTree는 inline이 아니라 `원고 보기` Sheet 안에 있다. 제목 편집 자체는 Sheet를 열지 않고 같은 접근 가능한 control로 수행한다.
- 800ms는 제품 경계값 자체를 재정의하지 않는다. PUT waiter/상태를 종료 조건으로 쓰고 CI timeout에는 충분한 여유를 둔다.
