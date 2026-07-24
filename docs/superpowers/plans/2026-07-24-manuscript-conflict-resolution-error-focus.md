# 원고 충돌 해결 실패 후 포커스 이탈 구현 계획

근거 보고서: [bug-003](../../bug-reports/2026-07-24-1520-manuscript-conflict-dialog.html#bug-003)

## 작업

1. resolving 동안 활성 버튼이 disabled 되며 browser focus가 사라지는 전환을 집중 테스트로 재현한다.
2. resolve-error 진입 뒤 재시도 control 또는 명시적 dialog fallback으로 focus를 복원하되 성공 닫힘의 textarea return-focus와 경쟁하지 않게 구현한다.
3. mouse/Enter/Space, Tab/Shift+Tab trap, Escape pending 차단, retry success를 검증한다.
4. 초안, caret/selection, revision, apply-server 및 compare-retry 의미가 바뀌지 않았는지 회귀 테스트한다.

## 검증 명령

```sh
cd frontend
mise exec -- pnpm vitest run src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

## 제한

공용 `Dialog`, 다른 modal 소비자, 자동 저장 일반 실패 UI, API/OpenAPI, 원고 도메인 계약은 수정하지 않는다.
