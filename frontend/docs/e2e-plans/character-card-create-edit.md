# 인물 카드 등록·수정 E2E 테스트 계획

## Application Overview

대상은 인증이 없는 로컬 개발 MSW 환경의 /projects/silver-garden/write?tab=characters 이다. 승인 기준은 UI plan blob ed5812bd7e9b036b46d850b7e4053cfc00a8c6cd의 REQ-01..REQ-10, OpenAPI blob 634f780054304f1b383f4b2a0d4844b41927fff0의 createStoryBibleCharacter/updateStoryBibleCharacter, 현재 Story Bible/Narrative Memory 도메인 계약이다.

모든 테스트는 새 browser context와 MSW 초기 seed(서윤 ID silver-garden-character-1, 도현 ID silver-garden-character-2)에서 독립 실행하고 인증은 사용하지 않는다. 기본 desktop viewport는 1280x800, mobile은 375x800이다. 각 테스트는 실행 순서에 의존하지 않고, 필요한 실패/권위 응답만 page.route로 해당 테스트 안에서 가로채며 종료 시 unroute 또는 context 폐기로 정리한다. 스크린샷 비교와 waitForTimeout은 사용하지 않고 role/name, URL, focus, live region, 요청 body, 응답 후 카드로 판정한다.

권장 생성 파일은 frontend/e2e/character-card-create-edit.spec.ts와 frontend/e2e/character-card-resilience-navigation.spec.ts이다. frontend/seed.spec.ts는 setup placeholder일 뿐 재사용·수정하지 않는다. 첫 파일은 등록/수정/검증, 둘째 파일은 실패/이탈/history/mobile을 소유한다. 앱 구현, MSW source, Playwright config는 변경하지 않는다.

REQ 추적: 테스트 1=REQ-01,02,03,05,07,10; 테스트 2=REQ-01,02,03,05,06,07,10; 테스트 3=REQ-04,09; 테스트 4=REQ-05,07,09; 테스트 5=REQ-07,09; 테스트 6=REQ-08,09; 테스트 7=REQ-08; 테스트 8=REQ-08,09; 테스트 9=REQ-01,02,07,08,09. 삭제·conflict/merge/force-save·Narrative Memory·장면 상태 UI가 없다는 것은 테스트 1/2의 editor와 request assertions에서 최소 확인하고 별도 탐색 테스트로 중복하지 않는다.

실행 전 terminal A에서 frontend/ 기준 mise exec -- pnpm dev --host 127.0.0.1 --port 4173 을 유지한다. terminal B에서 mise exec -- pnpm exec playwright test e2e/character-card-create-edit.spec.ts e2e/character-card-resilience-navigation.spec.ts, 이어서 mise exec -- pnpm check, mise exec -- pnpm build를 실행하며 모두 exit 0이어야 한다.

## Test Scenarios

### 1. 인물 카드 핵심 등록·수정

**Seed:** `frontend/seed.spec.ts`

#### 1.1. desktop에서 모든 필드로 인물을 등록하고 서버 권위 snapshot만 반영한다

**File:** `frontend/e2e/character-card-create-edit.spec.ts`

**Steps:**

1. 1280x800 새 context에서 http://127.0.0.1:4173/projects/silver-garden/write?tab=characters 로 이동하고 등장인물 heading, 새 인물 등록, 서윤/도현 수정 action을 기다린다. - expect: 초기 두 주인공 카드가 모두 보이고 새 인물 등록 action이 키보드로 접근 가능하다.
2. POST **/api/projects/silver-garden/story-bible/characters를 한 번 가로채 요청 JSON을 기록하고, 기존 두 인물과 server-character-3(이름 서버 민서 및 입력과 일부 다른 authoritative 값), 기존 world entry, 증가한 revision을 담은 201 응답을 반환한다. - expect: interception은 이 테스트에만 적용되며 실제 MSW 초기 상태를 변형하지 않는다.
3. 새 인물 등록을 클릭하고 dialog 이름을 확인한 뒤 초기 focus를 검사한다. 인물 ID 필드가 없는지 확인하고 이름, 성별, 나이(스물아홉), 역할, 성격, 문체, 대사 스타일, 기본 욕망, 숨은 감정 9개 필드에 고정 값을 입력한다. - expect: 이름 textbox가 최초 focus를 받고 나이는 text input이며 모든 label이 접근 가능하다. - expect: 삭제, 충돌/덮어쓰기, 이전 기억, 현재 욕망·의도·known/unknown/forbidden UI가 없다.
4. 저장을 클릭하고 POST 완료를 기다린다. - expect: 요청은 id/expectedRevision/scene/memory 필드 없이 9개 mutable 문자열만 포함한다. - expect: 중복 POST는 발생하지 않는다.
5. Sheet가 닫히고 URL이 ?tab=characters로 replace 정규화된 뒤 목록을 검사한다. - expect: server-character-3의 권위 이름 '서버 민서' 카드가 보이고 서윤/도현과 기존 world-backed workspace가 보존된다. - expect: polite status가 '서버 민서 인물을 저장했어요.'를 알리고 생성 launch 또는 갱신 카드로 유효한 focus가 돌아간다.

#### 1.2. 초기 주인공의 불변 ID를 유지하고 연속 수정의 마지막 서버 응답을 표시한다

**File:** `frontend/e2e/character-card-create-edit.spec.ts`

**Steps:**

1. 1280x800 새 context에서 characterId=silver-garden-character-1을 포함한 direct URL로 이동한다. - expect: URL이 tab=characters&panel=character-editor&characterId=silver-garden-character-1로 canonicalize되고 '서윤 수정' dialog가 열린다. - expect: 인물 ID는 silver-garden-character-1인 readonly input이고 모든 9개 필드가 seed 값으로 채워져 있다.
2. PATCH endpoint를 가로채 호출 순서별 request를 기록한다. 첫 응답은 동일 ID와 이름 '서버 서윤 1', 둘째 응답은 동일 ID와 이름 '서버 서윤 2' 및 다른 hiddenFeeling을 담되 도현과 world entries를 그대로 포함한다. - expect: 두 응답 모두 완전한 authoritative Story Bible snapshot이다.
3. 첫 저장에서 이름과 숨은 감정을 변경해 저장하고 목록에서 첫 authoritative 값을 확인한다. 같은 카드 편집기를 다시 열고 다시 이름/숨은 감정을 변경해 두 번째 저장한다. - expect: 각 save 후 Sheet가 닫히고 해당 서버 응답의 카드 값이 표시된다. - expect: 두 번째 저장 후 '서버 서윤 2'와 두 번째 hiddenFeeling만 최신 표시값이다.
4. 기록한 두 PATCH를 검사한다. - expect: 두 요청 모두 URL path의 characterId가 silver-garden-character-1이고 body에 id, revision, conflict 필드가 없다. - expect: 변경한 필드만 전송되고 도현 ID/값과 카드 순서가 보존된다. - expect: conflict 비교·force-save·삭제 UI가 나타나지 않는다.

#### 1.3. trim 후 빈 이름을 product validation으로 막고 이름에 focus한다

**File:** `frontend/e2e/character-card-create-edit.spec.ts`

**Steps:**

1. 1280x800 새 context에서 create Sheet를 열고 POST 요청 counter interception을 설치한다. 이름을 공백 세 칸으로 입력하고 저장한다. - expect: 브라우저 기본 required bubble 대신 visible alert summary와 inline '이름을 입력해 주세요.'가 표시된다. - expect: 이름은 aria-invalid이며 focus를 가진다. - expect: POST counter는 0이다.
2. 공백을 지우고 유효한 이름을 입력한다. - expect: 이름 validation error가 해제되고 선택 필드에 형식/길이 제약 메시지가 생기지 않는다.

### 2. 저장 실패·이탈·history 복원력

**Seed:** `frontend/seed.spec.ts`

#### 2.1. 500 저장 실패에서 exact draft를 보존하고 한 번만 재시도한다

**File:** `frontend/e2e/character-card-resilience-navigation.spec.ts`

**Steps:**

1. 1280x800 새 context에서 서윤 편집기를 열고 PATCH route를 호출 순서별로 가로챈다. 첫 호출은 짧은 지연 뒤 500 INTERNAL_ERROR, 두 번째는 입력한 변경을 반영한 authoritative 200 snapshot을 반환한다. - expect: route handler와 request count는 테스트 로컬이다.
2. 숨은 감정을 '실패 뒤에도 남는 초안'으로 바꾸고 저장 버튼을 빠르게 두 번 클릭한다. - expect: 저장 중 status가 polite하게 노출되고 form/닫기/저장 control이 disabled 된다. - expect: 500 뒤 request count는 1이고 error alert는 입력 내용 보존을 알리며 textbox 값과 immutable ID가 그대로다. - expect: 버튼 이름이 '다시 저장'으로 바뀐다.
3. 다시 저장을 한 번 클릭하고 성공을 기다린다. - expect: 총 PATCH count는 정확히 2이며 두 요청의 draft가 같다. - expect: 성공 후 Sheet가 닫히고 authoritative 카드 및 polite success status가 보인다.

#### 2.2. PATCH 404를 unavailable 상태로 전환하고 draft를 보존한다

**File:** `frontend/e2e/character-card-resilience-navigation.spec.ts`

**Steps:**

1. 1280x800 새 context에서 서윤 편집기를 열고 PATCH를 CHARACTER_NOT_FOUND 404로 가로챈다. 숨은 감정을 '404 뒤에도 남는 초안'으로 바꾸고 저장한다. - expect: alert가 '이 인물을 더 이상 편집할 수 없어요.'와 목록 복귀 안내를 보여준다. - expect: draft와 readonly ID가 보존되고 모든 field 및 다시 저장이 disabled 된다. - expect: conflict/merge/force-save UI는 없다.
2. 등장인물 목록으로 돌아가기를 클릭한다. - expect: dirty draft에 REQ-08이 적용되어 '저장하지 않은 변경사항을 버릴까요?' discard dialog가 열린다.
3. 변경사항 버리기를 한 번 클릭한다. - expect: discard dialog와 Sheet가 닫히고 URL은 ?tab=characters로 canonicalize되며 서윤/도현 seed 카드는 계속 보인다. - expect: 추가 discard dialog가 다시 열리지 않는다.

#### 2.3. dirty 명시적 닫기·Escape·overlay가 각각 단 한 번의 discard 확인을 거친다

**File:** `frontend/e2e/character-card-resilience-navigation.spec.ts`

**Steps:**

1. 명시적 닫기 버튼, Escape, sheet overlay click 세 method를 test.describe 또는 반복 helper의 독립 새 context로 실행한다. 각 run에서 서윤 편집기를 열고 성격에 고정 suffix를 추가한다. - expect: 각 method 전 editor URL과 dirty draft가 동일한 기준 상태다.
2. 해당 close method를 수행하고 discard dialog에서 계속 편집을 선택한다. - expect: editor가 열린 채 URL과 exact draft가 보존되고 focus가 editor로 돌아간다.
3. 같은 method를 다시 수행하고 변경사항 버리기를 한 번 클릭한다. - expect: discard dialog와 character Sheet가 모두 닫히고 재확인 dialog가 다시 열리지 않는다. - expect: URL이 ?tab=characters이고 authoritative seed 카드로 돌아가며 launch action에 focus가 복귀한다.

#### 2.4. clean Back·Forward를 재생하고 dirty Back은 확인 전까지 막는다

**File:** `frontend/e2e/character-card-resilience-navigation.spec.ts`

**Steps:**

1. 1280x800 새 context의 characters 목록에서 서윤 수정 action으로 clean Sheet를 열고 page.goBack(), page.goForward()를 순서대로 실행한다. - expect: Back은 Sheet를 닫고 ?tab=characters를 복원하며 Forward는 같은 characterId의 서윤 수정 Sheet와 seed draft를 복원한다.
2. 성격을 변경한 뒤 page.goBack()을 실행하고 discard dialog에서 계속 편집을 선택한다. - expect: navigation은 완료되지 않고 editor URL 및 exact draft가 유지된다.
3. 다시 page.goBack() 후 변경사항 버리기를 선택한다. - expect: Back이 한 번만 완료되어 목록 URL로 이동하고 Sheet가 닫힌다. - expect: 추가 discard dialog나 stale draft가 없다.

#### 2.5. confirmed route 이탈 뒤 manuscript flush가 실패하면 character draft를 복원한다

**File:** `frontend/e2e/character-card-resilience-navigation.spec.ts`

**Steps:**

1. 1280x800 새 context에서 characters 목록 URL로 이동한 뒤 서윤 수정 action으로 편집기를 열어 browser history에 목록 entry와 editor entry를 순서대로 만든다. - expect: 현재 URL은 character editor를 가리키고 바로 이전 history entry는 ?tab=characters 목록이다.
2. 원고 본문을 변경해 unsaved 상태로 만들고 서윤 성격도 변경한다. PUT **/api/manuscripts/**를 500 INTERNAL_ERROR로 가로챈다. - expect: 원고와 character 두 draft가 모두 dirty이다.
3. background header link를 force-click하지 않고 page.goBack()을 실행한 뒤 character discard dialog에서 변경사항 버리기를 선택한다. - expect: manuscript flush가 시도되고 실패한다. - expect: route 이탈은 취소되어 현재 workspace에 남고 저장 실패 표시가 보인다. - expect: character editor가 동일 URL과 exact character draft로 다시 열려 있다.

### 3. 모바일 중첩 Sheet와 focus

**Seed:** `frontend/seed.spec.ts`

#### 3.1. 375px Context Sheet 위에서 character Sheet를 열고 닫아 focus를 복원한다

**File:** `frontend/e2e/character-card-resilience-navigation.spec.ts`

**Steps:**

1. 375x800 새 context에서 /projects/silver-garden/write 로 이동하고 인물 보기 tab을 클릭한다. - expect: 왼쪽 '인물 보기' dialog가 열리고 등장인물 heading, 새 인물 등록, 서윤/도현 수정 action이 보인다.
2. 서윤 인물 수정을 클릭한다. - expect: 오른쪽 full-width '서윤 수정' dialog가 Context Sheet 위에 열리고 DOM의 sheet-content가 2개다. - expect: 이름 input이 focus를 가지며 readonly 인물 ID와 모든 field가 viewport 안에서 scroll 가능한 form으로 제공된다. - expect: body scroll은 잠겨 있다.
3. Tab과 Shift+Tab을 사용해 character Sheet의 닫기, form, 취소, 저장 범위 안에서 focus가 trap되는지 확인한다. clean 취소를 클릭한다. - expect: 배경 원고나 Context control로 focus가 탈출하지 않는다. - expect: character Sheet만 닫히고 underlying '인물 보기' dialog는 남으며 '서윤 인물 수정' launch action에 focus가 돌아간다.
4. 새 인물 등록을 열어 이름에 값을 입력하고 Escape를 누른 뒤 discard dialog의 계속 편집, 다시 Escape 후 변경사항 버리기를 수행한다. - expect: discard dialog가 character Sheet 위에서 focus trap되고 계속 편집은 이름 draft와 focus context를 보존한다. - expect: 확정 후 create Sheet만 닫히고 Context Sheet와 새 인물 등록 launch focus가 복원된다.
