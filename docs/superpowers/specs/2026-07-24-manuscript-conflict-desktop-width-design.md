# 원고 충돌 대화상자 데스크톱 폭 결함 설계

## 결함과 근거

1280px viewport에서 `ManuscriptConflictDialog`가 선언한 `max-w-5xl` 대신 384px로 계산된다. 두 번의 최신 revision 재시작에서 dialog width와 computed max-width가 모두 384px였고, 두 diff column은 각각 172px로 축소됐다.

- 보고서: [bug-002](../../bug-reports/2026-07-24-1520-manuscript-conflict-dialog.html#bug-002)
- 심각도: Medium
- 영향: side-by-side 원고 비교가 데스크톱에서도 모바일 폭으로 압축돼 줄바꿈이 과도하고 변경 판단이 어렵다.

## 목표와 범위

`ManuscriptConflictDialog`에 한정해 데스크톱에서 의도한 넓은 비교 폭을 적용하고, 모바일에서는 viewport 여백을 유지한다. 공용 `DialogContent`와 다른 dialog 소비자는 변경하지 않는다. 높이·스크롤 문제는 bug-001, focus 문제는 bug-003/004 범위다.

## 수용 기준

1. 1280×800에서 dialog가 384px보다 넓고 기존 `max-w-5xl` 의도 범위 안에서 두 열 비교 공간을 제공한다.
2. 375×800에서는 좌우 1rem 여백 안에 맞고 수평 viewport overflow가 없다.
3. scene-content/scene-structure, loading/error/retry, footer, 긴 diff 스크롤과 keyboard 동작이 유지된다.

## 검증

```sh
cd frontend
mise exec -- pnpm vitest run src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

Playwright로 1280×800과 375×800에서 dialog/column bounding box 및 수평 overflow를 기록한다.
