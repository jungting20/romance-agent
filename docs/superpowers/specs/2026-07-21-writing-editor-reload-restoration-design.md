# 집필 에디터 새로고침 저장 복원 설계

> 버그 보고서: [집필 에디터 자동 저장 탐색 보고서](../../bug-reports/2026-07-21-1606-writing-editor-autosave.html#bug-001)

## 문제

개발 모드 MSW에서 `silver-garden` 원고 본문을 편집하면 800ms 유휴 뒤
`PUT /api/manuscripts/silver-garden-manuscript`가 `200`을 반환하고 화면도
`자동 저장됨`을 알린다. 그러나 같은 탭을 새로고침하면 방금 저장한 본문과
revision이 사라지고 revision 1의 seed 원고가 다시 표시된다.

현재 mock 저장소의 `projectWorkspaces`는 페이지 JavaScript 모듈의 메모리에만
있다. 저장 핸들러는 이 배열을 정상 갱신하지만 전체 페이지 reload가 모듈을
다시 평가하면서 seed를 복제해 초기화한다. 이는 확인된 원인이다.

## 사용자 영향과 심각도

심각도는 **High**다. 성공 응답과 `자동 저장됨` 안내를 신뢰한 사용자가
새로고침하면 편집 내용이 조용히 사라진다. 현재 프로젝트가 frontend/MSW
개발 실행을 제품 흐름의 기준으로 사용하므로 단순 테스트 편의 문제가 아니라
핵심 집필 흐름의 데이터 손실이다.

## 목표

- 같은 브라우저 탭에서 성공적으로 저장한 MSW 원고와 revision을 전체 페이지
  reload 뒤에도 `GET /api/projects/:projectId/workspace`로 복원한다.
- `편집 중` → `저장 중` → `자동 저장됨`의 800ms 자동 저장 동작, revision
  충돌, 실패 재시도, 최신 편집 직렬화를 보존한다.
- 새 browser context에는 기존 seed 데이터와 revision 1을 제공한다.
- production 애플리케이션 상태는 계속 TanStack Query와 API가 소유한다.
  브라우저 저장소를 production 원고의 두 번째 상태 소스로 만들지 않는다.

## 선택한 접근

MSW가 활성화된 개발 브라우저에서만 사용하는, 버전이 붙은
`sessionStorage` 기반 mock transport 저장소를 추가한다. mock 초기화 시 같은
탭의 저장된 snapshot을 검증해 hydrate하고, 성공한 manuscript 변경 뒤에는
원고, 원고 revision, 프로젝트 활동 시각만 원자적으로 다시 저장한다. Story
Bible과 concept는 seed 값을 보존한다.

`sessionStorage`를 선택한 이유는 reload에는 살아 있으면서 새 browser context와
새 탭에는 seed 상태를 제공하기 때문이다. 이 저장소는 `enableMocking()` 경계
안에서만 연결하고 production build의 query/domain 코드에서는 접근하지 않는다.

저장된 JSON에는 schema version을 포함한다. 누락, 파싱 오류, 구조 불일치,
지원하지 않는 version이면 해당 값을 제거하고 seed로 복구한다. 일부 필드만
복원해 서로 다른 revision과 본문을 조합하지 않는다.

## 상태와 책임 경계

- `project-workspaces.ts`는 mock workspace 상태 전이와 clone 규칙을 계속 소유한다.
- 새 persistence adapter는 serialize/parse/storage I/O만 소유한다.
- 브라우저 MSW bootstrap은 worker 시작 전에 한 번 hydrate하고 저장 성공 뒤
  snapshot을 기록하도록 adapter를 연결한다.
- Vitest의 `resetProjectWorkspaceMockData()`는 매 테스트 seed 메모리를 복구한다.
  테스트용 reset이 실제 browser session snapshot을 암묵적으로 남기지 않도록
  storage adapter는 명시적으로 주입하거나 해제한다.
- React 페이지, Manuscript 도메인, API request/response, OpenAPI는 바꾸지 않는다.

## 오류 및 경계 동작

- `PUT` 실패와 `409` 충돌은 persisted snapshot을 갱신하지 않는다.
- 성공 응답을 만들 상태 전이가 완료된 뒤에만 snapshot을 기록한다.
- 저장소 쓰기 실패는 mock API의 성공을 거짓 실패로 바꾸지 않되 개발 콘솔에
  원고 내용 없이 진단 가능한 경고를 남기고 메모리 상태는 유지한다.
- 빈 본문과 긴 본문은 문자열 그대로 round-trip한다.
- reload 복원 뒤 다음 저장은 복원된 revision을 `expectedRevision`으로 사용한다.

## 수용 기준

1. revision 1에서 고유 표식을 입력하고 800ms 유휴 뒤 PUT 200과
   `자동 저장됨`을 확인한 다음 reload하면 표식과 revision 2가 복원된다.
2. reload 후 다시 편집하면 `expectedRevision: 2`로 저장되고 revision 3이 된다.
3. 빈 본문과 여러 줄의 긴 본문도 reload 뒤 동일하게 복원된다.
4. 실패한 저장과 revision 충돌은 persisted snapshot을 변경하지 않는다.
5. 손상되거나 알 수 없는 version의 snapshot은 예외 없이 seed revision 1로
   복구된다.
6. 새 browser context는 seed 원고에서 시작한다.
7. 자동 저장 debounce, 단일 활성 요청, 최신 편집 직렬화, 실패 재시도가 기존과
   동일하게 동작한다.
8. production Query/domain/API 계약에는 브라우저 저장소 의존성이 추가되지 않는다.

## 검증

- mock 저장소의 hydrate/persist/손상 복구 focused test
- save 성공, 실패, 충돌, reload-equivalent rehydrate, 후속 revision 저장 focused test
- 집필 화면에서 실제 full reload를 수행하는 브라우저 회귀 검증
- `mise exec -- pnpm check`
- `mise exec -- pnpm build`

## 비목표

- production 백엔드 또는 OpenAPI 변경
- 집필 에디터 레이아웃과 ticket-worker #1의 스크롤 경계 수정
- Story Bible 편집 UX, AI 제안, 프로젝트 생성 흐름 변경
- 탭이나 browser context를 넘는 영구 보관
