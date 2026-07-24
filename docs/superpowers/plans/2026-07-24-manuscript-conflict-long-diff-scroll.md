# 원고 충돌 긴 diff 스크롤 구현 계획

근거 보고서: [bug-001](../../bug-reports/2026-07-24-1520-manuscript-conflict-dialog.html#bug-001)

## 작업

1. `ManuscriptConflictDialog`의 max-height grid에서 diff row가 남은 높이로 축소될 수 있도록 명시적인 row 구성과 필요한 `min-h-0` 경계를 적용한다.
2. diff wrapper만 세로 스크롤을 소유하게 하고 header·설명·안내·오류·footer가 dialog 안에 항상 남도록 한다.
3. 40개 이상 row fixture로 내부 스크롤 가능, footer 노출, sticky header, 짧은 diff 및 scene-structure 회귀를 집중 테스트한다.
4. loading, compare error/retry, resolution error/retry, Escape, focus trap/restore 테스트를 유지한다.
5. 아래 명령과 1280×800/375×800 실제 브라우저 MSW 충돌로 검증한다.

## 검증 명령

```sh
cd frontend
mise exec -- pnpm vitest run src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

## 제한

공용 `Dialog`, API/OpenAPI, 도메인 계약, 원고 병합 의미, 다른 화면의 스크롤은 수정하지 않는다.
