# 세계관 편집기 stale validation 피드백 수정 계획

## 입력

- 설계: `docs/superpowers/specs/2026-07-24-world-editor-stale-validation-feedback-design.md`
- 증거: `docs/bug-reports/2026-07-24-1502-world-editor-feedback.html#bug-001`
- 요구사항: `REQ-WORLD-004`, `REQ-WORLD-005`, `REQ-WORLD-010`

## 구현 단계

1. `frontend/src/features/edit-world-entries/world-entry-editor-state.test.ts`에 validation 오류 두 개를 만든 뒤 제목과 설명을 차례로 고치는 reducer 테스트를 추가한다. 각 단계에서 해결된 field 오류만 제거되고 다른 오류는 유지되며 최종적으로 `errors`와 stale `firstInvalidField`가 정리되는지 검증한다.
2. `frontend/src/features/edit-world-entries/world-entry-editor-state.ts`의 `change-field` 처리를 최소 범위로 수정한다. affected field의 현재 validation 결과 또는 submitted-value identity에 따라 해결된 오류만 제거하고, 변경하지 않은 row/field 오류는 보존한다.
3. `frontend/src/features/edit-world-entries/ui/world-editor-sheet.test.tsx`에 실제 제목·설명 입력 흐름을 추가한다. `2 → 1 → 0` 요약, inline 오류, `aria-invalid`, `aria-describedby`, alert 제거를 사용자 관찰 결과로 검증한다.
4. 기존 validation submit/first-focus, 저장 성공, retryable retry, conflict/reload, unavailable/return 테스트를 실행해 오류 우선순위와 복구 흐름이 유지되는지 확인한다.
5. `375x800`과 `1280x800`의 MSW `silver-garden` 상태에서 보고서의 최소 재현 절차를 반복하고, 해결된 오류가 입력 즉시 접근성 트리에서 사라지는지 확인한다.

## 제약

- `WorldEditorFeedback` 결함 밖의 제품 동작, API, OpenAPI, Story Bible 도메인 계약을 변경하지 않는다.
- 공용 Alert, Sheet, Dialog primitive를 재설계하지 않는다.
- 기존 티켓 #15의 discard-cancel focus와 #16의 desktop width를 이 작업에 포함하지 않는다.
- 오류 전체를 field change마다 무조건 초기화하지 않는다. 변경하지 않은 field의 유효한 오류를 보존한다.

## 검증 명령

`frontend/`에서 순서대로 실행한다.

```sh
mise exec -- pnpm vitest run src/features/edit-world-entries/world-entry-editor-state.test.ts src/features/edit-world-entries/ui/world-editor-sheet.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

## 완료 조건

- 설계의 모든 수용 기준에 대한 테스트와 실제 브라우저 증거가 있다.
- 집중 테스트, `pnpm check`, `pnpm build`가 모두 통과한다.
- 변경 파일이 이 결함의 reducer, Sheet 테스트 및 필요 시 직접 관련된 UI 파일로 제한된다.
