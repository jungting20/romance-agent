# 세계관 편집기 validation 피드백 갱신 설계

## 목적

세계관 편집기에서 빈 필드 제출 뒤 사용자가 해당 필드를 유효한 값으로 고쳤을 때, 이미 해결된 오류와 validation 요약을 즉시 현재 draft에 맞게 갱신한다.

근거 보고서는 `docs/bug-reports/2026-07-24-1502-world-editor-feedback.html#bug-001`이다.

## 확정 결함

`/projects/silver-garden/write?tab=world`의 `WorldEditorFeedback` 흐름에서 기존 항목의 제목과 설명을 비운 뒤 저장하면 두 필드 오류와 “입력하지 않은 항목이 2개 있어요.” alert가 나타난다. 이후 두 필드에 유효한 값을 입력해도 다음 저장 전까지 다음 상태가 그대로 남는다.

- validation alert가 계속 오류 2개를 알린다.
- 두 필드의 inline 오류가 계속 표시된다.
- 두 필드가 계속 `aria-invalid="true"`이고 이전 오류 설명을 참조한다.

두 번의 clean-state MSW 실행에서 같은 결과를 확인했다. 다시 저장하면 성공하므로 값 자체는 유효하지만, 화면과 접근성 트리가 현재 draft와 모순된다.

## 요구사항 근거

- `REQ-WORLD-004`는 저장 시 모든 blank 필드를 노출하고 제목·설명을 trim한 뒤 비어 있지 않은지 검증한다.
- `REQ-WORLD-010`은 키보드 조작, visible focus, label, announced validation/request error를 요구한다.
- `frontend/docs/frontend-coding-rules.md`는 오류 표시를 affected field 또는 submitted-value snapshot에 결부하고, 변경하지 않은 필드의 서버 오류를 지우지 않도록 요구한다.
- `frontend/docs/ui-plans/worldbuilding-edit-add.md`는 `WorldEditorFeedback`가 현재 오류 상태와 오류 개수로 정확히 하나의 우선 피드백을 렌더링하도록 정한다.

## 원인 확인

확정 뒤 CodeGraph로 확인한 결과, `worldEditorReducer`의 `change-field` 분기는 draft와 phase만 갱신하고 `errors`와 `firstInvalidField`를 그대로 보존한다. `WorldEditorFeedback`는 보존된 `state.errors`에서 개수를 계산하므로 해결된 필드도 계속 오류로 계산한다.

## 승인된 동작

1. 오류가 표시된 필드를 변경하면 그 필드의 현재 값을 다시 검증하거나 제출 당시 값과 비교해, 해결된 affected-field 오류만 제거한다.
2. 같은 row의 다른 필드와 다른 row에서 아직 해결되지 않은 오류는 유지한다.
3. 오류 2개 중 제목만 해결하면 요약은 1개가 되고 설명 오류는 유지된다.
4. 마지막 오류까지 해결하면 validation alert, inline 오류, `aria-invalid`, 해당 오류용 `aria-describedby`가 사라진다.
5. 다시 invalid 값으로 저장하면 기존처럼 모든 blank 오류가 표시되고 첫 invalid 필드로 focus가 이동한다.
6. 저장 성공, retryable error/retry, revision conflict/reload latest, unavailable/return, dirty discard 동작은 변경하지 않는다.

## 범위

### 포함

- `WorldEditorFeedback`가 소비하는 validation 오류 상태 갱신
- field별 오류 유지·제거 규칙
- reducer와 Sheet 관찰 동작에 대한 집중 회귀 테스트
- 데스크톱과 모바일의 동일한 피드백 의미 검증

### 제외

- API와 Story Bible 도메인 규칙 변경
- 오류 문구나 Alert 공용 primitive 재설계
- conflict, retryable, unavailable, discard 동작 변경
- WorldEditorSheet 폭 및 레이아웃 변경
- 인물 편집기와 원고 편집기 변경

## 수용 기준

- 제목·설명 오류를 각각 해결할 때 오류 개수가 `2 → 1 → 0`으로 갱신된다.
- 해결된 필드만 inline 오류와 invalid 접근성 속성이 제거된다.
- 변경하지 않은 invalid 필드의 오류는 유지된다.
- 마지막 오류 해결 뒤 validation alert가 더 이상 접근성 트리에 없다.
- 유효 값으로 저장하면 기존 성공 흐름이 완료되고 authoritative 목록이 갱신된다.
- retryable, conflict, unavailable 피드백과 복구 action의 기존 테스트가 통과한다.

## 검증 명령

`frontend/`에서 실행한다.

```sh
mise exec -- pnpm vitest run src/features/edit-world-entries/world-entry-editor-state.test.ts src/features/edit-world-entries/ui/world-editor-sheet.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

브라우저에서는 `375x800`과 `1280x800`에서 보고서의 최소 재현 절차와 retryable/conflict/unavailable 회귀를 MSW로 확인한다.
