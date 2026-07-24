# 원고 충돌 긴 diff 스크롤 결함 설계

## 결함과 근거

`ManuscriptConflictDialog`의 scene-content 비교가 길어지면 내부 `overflow-auto` 영역이 축소되지 않고 표 높이만큼 팽창한다. 20행 로컬 본문과 20행 서버 본문을 비교한 두 번의 깨끗한 MSW 재현에서 대화상자는 높이 688px로 제한됐지만 비교 영역은 각각 2,397px와 3,197px였고 `scrollTop`은 0에서 움직이지 않았다. 두 번째 재현에서 `서버 최신본 적용` 버튼의 상단은 3,430px로 대화상자 하단 704px 밖에 있었다.

- 보고서: [bug-001](../../bug-reports/2026-07-24-1520-manuscript-conflict-dialog.html#bug-001)
- 심각도: High
- 영향: 긴 충돌에서 사용자가 전체 diff와 해결 동작을 포인터로 확인·실행할 수 없다.

## 목표

- 대화상자 전체는 viewport 안에 유지한다.
- header, 설명, 안내, alert, footer는 고정된 레이아웃 흐름을 유지하고 diff 영역만 남은 높이를 소유해 세로 스크롤한다.
- 긴 diff에서도 sticky column header와 두 해결 버튼이 항상 접근 가능해야 한다.
- 짧은 diff, scene-structure, loading, compare error, resolution error 의미는 바꾸지 않는다.

## 범위와 비범위

수정 범위는 `frontend/src/features/manuscript-conflict/ui/manuscript-conflict-dialog.tsx`의 높이·grid min-size·overflow 구성과 해당 집중 테스트다. API, MSW 계약, 자동 저장 및 병합 규칙, 공용 `Dialog`, 다른 dialog 소비자, 원고 도메인 계약은 변경하지 않는다.

## 수용 기준

1. 1280×800과 375×800에서 40개 이상의 diff row가 있어도 dialog가 viewport를 넘지 않는다.
2. diff viewport는 `scrollHeight > clientHeight`이고 최하단까지 스크롤된다.
3. sticky column header가 diff viewport 상단에 유지된다.
4. 두 해결 버튼은 스크롤 전후 모두 보이고 포인터·Tab·Enter/Space로 실행할 수 있다.
5. 짧은 diff, scene-structure, loading/error/retry, Escape 및 focus trap/restore 회귀가 없다.

## 검증

```sh
cd frontend
mise exec -- pnpm vitest run src/features/manuscript-conflict/ui/manuscript-conflict-dialog.test.tsx src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm check
mise exec -- pnpm build
```

실제 브라우저에서 지정 route와 두 viewport로 20+20행 MSW revision conflict를 만들고 diff의 `clientHeight`, `scrollHeight`, 최종 `scrollTop`, footer bounding box를 기록한다.
