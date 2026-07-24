# 원고 충돌 대화상자 데스크톱 폭 구현 계획

근거 보고서: [bug-002](../../bug-reports/2026-07-24-1520-manuscript-conflict-dialog.html#bug-002)

## 작업

1. `ManuscriptConflictDialog` 로컬 class의 breakpoint max-width 우선순위를 확인하고 데스크톱에서 넓은 비교 폭이 확실히 적용되도록 수정한다.
2. 공용 `DialogContent` 기본 폭과 다른 소비자를 변경하지 않는다.
3. 1280px에서 384px 회귀 방지와 375px viewport containment를 집중 테스트한다.
4. scene-content/scene-structure, 긴 diff, loading/error/retry 및 focus 동작 회귀를 검증한다.

## 검증 명령

```sh
cd frontend
mise exec -- pnpm vitest run src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```
