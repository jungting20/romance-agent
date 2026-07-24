# 원고 자동 저장 재시도 포커스 복원 구현 계획

> 버그 보고서: [ManuscriptEditor 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1419-manuscript-editor.html#bug-001)
>
> 승인 설계: [원고 자동 저장 재시도 포커스 복원 설계](../specs/2026-07-24-manuscript-autosave-retry-focus-design.md)

## 목표

`원고 저장 다시 시도`가 성공해 조건부 버튼이 사라진 뒤에도 현재 활성 장면의
`원고 본문` textarea로 키보드 포커스를 복원하고, 본문·캐럿·선택 범위를 보존한다.

## 작업 1: 실패하는 포커스 회귀 테스트 추가

**대상**

- 수정: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

다음 두 사례를 사용자 관찰 기준으로 추가한다.

1. MSW 원고 PUT을 한 번 실패시켜 `저장 실패`와 이름 있는
   `원고 저장 다시 시도` 버튼을 표시한다.
2. 본문 끝에 고유 문자열을 입력하고 캐럿 위치를 기록한다.
3. 마우스 클릭으로 재시도를 성공시킨 뒤 `원고 본문`이 포커스를 가지며 값과 캐럿이
   보존되는지 검증한다.
4. 별도 사례에서 재시도 버튼까지 키보드로 이동하고 Enter로 실행한 뒤 같은 결과를 검증한다.
5. PUT 호출 횟수와 `자동 저장됨` 접근 가능한 상태를 함께 검증한다.

재시도가 다시 실패하는 기존 사례가 있으면 alert와 재시도 버튼이 유지되는지 회귀 단언을
추가한다. 없으면 동일 테스트 파일에 최소 사례를 추가한다.

집중 테스트를 실행해 현재 구현에서 포커스 단언이 실패하는지 확인한다.

```sh
cd frontend
mise exec -- pnpm vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
```

## 작업 2: 성공한 재시도 뒤 편집기 포커스 복원

**대상**

- 수정: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`
- 수정: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- 필요할 때만 수정: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`

`retry`가 호출자에게 저장 성공 여부를 전달하도록 기존 `saveCurrentDraft()`의 boolean 결과를
재사용한다. `LoadedWritingWorkspace`는 성공 결과를 받은 뒤 현재 활성 편집기의
`sceneNavigation.editorRef.current`에 포커스를 복원한다.

다음 제약을 지킨다.

- 재시도 요청 직렬화, revision, 충돌 판별과 상태 문자열은 변경하지 않는다.
- 성공한 재시도에서만 포커스를 복원한다.
- 본문 값이나 `selectionStart`/`selectionEnd`를 새 값으로 덮어쓰지 않는다.
- 조건부 버튼이 제거된 이후에도 최종 활성 요소가 textarea인지 테스트로 보장한다.
- 전역 selector, 지연 시간 상수, 새 의존성을 추가하지 않는다.

작업 1의 집중 테스트를 다시 실행한다.

```sh
cd frontend
mise exec -- pnpm vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
```

## 작업 3: 회귀와 실제 브라우저 검증

다음 범위를 확인한다.

- 일반 본문 입력과 800ms 자동 저장
- 선택 범위 교체와 캐럿 보존
- 저장 실패 뒤 마우스/Enter 재시도 성공 포커스
- 재시도 재실패와 충돌 상태
- 장면 추가 및 기존 장면 전환 후 편집기 포커스
- 긴 원고의 중앙 에디터 스크롤 경계

실제 브라우저에서는 `http://127.0.0.1:4173/projects/silver-garden/write`의 clean MSW
seed에서 실패를 재현하고, 재시도 성공 뒤 아래를 확인한다.

```js
document.activeElement === document.querySelector('textarea[aria-label="원고 본문"]')
```

프론트엔드 전체 검증을 실행한다.

```sh
cd frontend
mise exec -- pnpm check
mise exec -- pnpm build
```

## 완료 조건

- 설계의 수용 기준을 모두 만족한다.
- 포커스 회귀 테스트가 수정 전 실패, 수정 후 통과한다.
- 제품 코드 밖의 API, 도메인 계약, MSW 데이터 형식, 다른 편집기 흐름을 변경하지 않는다.
- 리뷰에서 발견된 이 결함 범위의 모든 수용된 finding을 해결하고 필요한 재검증을 마친다.
