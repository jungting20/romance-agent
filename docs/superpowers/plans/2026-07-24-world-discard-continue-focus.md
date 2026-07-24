# 세계관 폐기 취소 후 편집기 포커스 복원 구현 계획

> 버그 보고서: [WorldEditorSheet 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1439-world-editor-sheet.html#bug-001)

## 목표

WorldEditorSheet의 폐기 확인을 취소했을 때 초안과 URL을 보존하면서 포커스를 편집기 내부로 확실히 되돌린다.

## 작업

1. `frontend/src/features/edit-world-entries/ui/world-discard-dialog.tsx`와 호출부의 현재 dialog close lifecycle을 확인한다.
2. close intent뿐 아니라 `reload-latest` intent의 취소에도 적용되는 focus restoration 계약을 추가한다. dialog를 열기 직전의 enabled control을 우선하고, 사용할 수 없으면 현재 WorldEditorSheet의 첫 분류 field 또는 명확한 fallback을 사용한다.
3. `frontend/src/features/edit-world-entries/ui/world-editor-sheet.tsx` 또는 page 조합부에는 필요한 ref/callback만 최소 추가한다. 공용 `Dialog` 동작은 이 결함 해결에 반드시 필요하다는 증거가 없으면 변경하지 않는다.
4. focused test에서 다음을 검증한다.
   - dirty close → `계속 편집` click/Enter → draft·URL 보존과 Sheet control focus.
   - conflict latest reload → `계속 편집` → draft 보존과 Sheet control focus.
   - discard 승인, latest reload 승인, clean close, save success focus 회귀.
5. 실제 브라우저에서 1280×800과 375×800으로 keyboard visible focus를 확인한다.

## 정확한 검증 명령

`frontend/`에서:

```sh
mise exec -- pnpm vitest run src/features/edit-world-entries/ui/world-editor-sheet.test.tsx src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

브라우저 검증:

```text
http://127.0.0.1:4173/projects/silver-garden/write?tab=world
1280x800, 375x800
세계관 수정 및 추가 → 제목 수정 → Escape → 계속 편집(Enter) → active element와 visible focus 확인
409 conflict → 최신 세계관 불러오기 → 계속 편집 → 동일 확인
```

## 완료 조건

- 설계 문서의 수용 기준을 모두 충족한다.
- WorldEditorSheet 외 dialog 소비자의 동작을 변경하지 않는다.
- API, domain contract, package/lockfile 변경이 없다.

