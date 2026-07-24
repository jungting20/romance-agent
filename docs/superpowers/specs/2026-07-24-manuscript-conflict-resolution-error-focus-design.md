# 원고 충돌 해결 실패 후 포커스 이탈 결함 설계

## 결함과 근거

scene-content 충돌에서 `내 편집본 유지` 저장이 1회 실패하면 dialog와 활성 재시도 버튼은 남지만 `document.activeElement`가 `BODY`가 된다. 최신 MSW revision에서 시작한 두 번의 독립 재현 모두 `dialog.contains(activeElement) === false`였다.

- 보고서: [bug-003](../../bug-reports/2026-07-24-1520-manuscript-conflict-dialog.html#bug-003)
- 심각도: Medium
- 영향: 키보드와 보조기술 사용자가 실패 발생 위치와 다음 동작을 잃고 modal focus containment가 깨진다.

## 목표와 범위

- 해결 저장 중 클릭/키보드로 실행한 control의 의미 있는 후속 focus를 보존한다.
- 실패 시 `내 편집본 저장 다시 시도` 또는 합리적인 dialog 내부 fallback에 visible focus를 둔다.
- 성공 시 기존 textarea focus restore와 초안·revision 의미를 유지한다.
- 수정 범위는 `ManuscriptConflictDialog`의 resolving→resolve-error focus 전환과 집중 테스트다. 공용 Dialog, 자동 저장 retry, 다른 modal, API와 도메인 규칙은 제외한다.

## 수용 기준

1. 마우스, Enter, Space로 local keep을 시작한 뒤 실패하면 focus가 활성 재시도 버튼 또는 명시한 dialog 내부 fallback에 있다.
2. 실패 상태에서 Tab/Shift+Tab이 dialog 안에서 순환한다.
3. 재시도 성공 시 dialog가 닫히고 원고 textarea로 focus가 복원된다.
4. pending 중 Escape 차단, compare retry, apply server, direct keep local, 초안/selection/revision 의미가 유지된다.

## 검증

```sh
cd frontend
mise exec -- pnpm vitest run src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

실제 브라우저에서 MSW revision conflict 뒤 1회 PUT failure를 주입해 failure와 retry success 각각의 `activeElement`를 확인한다.
