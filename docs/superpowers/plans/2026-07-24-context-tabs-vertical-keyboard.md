# 세로 문맥 탭 방향키 수정 계획

## authoritative inputs

- 설계: `docs/superpowers/specs/2026-07-24-context-tabs-vertical-keyboard-design.md`
- 증거: [보고서 bug-001](../../bug-reports/2026-07-24-1524-context-panel-content-retry.html#bug-001)
- UI 계약: `frontend/docs/ui-plans/writing-workspace-tab-url-state.md`

## 작업 1: Tabs orientation 회귀 테스트

기존 Tabs primitive 또는 writing-workspace screen 테스트에 다음을 추가한다.

- vertical root의 `aria-orientation="vertical"`
- `ArrowDown`/`ArrowUp` focus·selection 이동과 wrap
- horizontal 기본 root의 기존 좌우 키 동작
- context tab keyboard activation과 canonical URL/visible panel 일치

집중 검증:

```sh
cd frontend
mise exec -- pnpm exec vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
```

## 작업 2: orientation prop 전달

`frontend/src/components/ui/tabs.tsx`의 wrapper에서 `orientation`을 Radix `TabsPrimitive.Root`에 명시적으로 전달한다. `data-orientation`, 기존 variant와 class 조합은 보존한다. 다른 Tabs 소비자나 제품 흐름을 함께 변경하지 않는다.

## 작업 3: 화면 회귀와 실제 브라우저 검증

```sh
cd frontend
mise exec -- pnpm exec vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm exec playwright test e2e/writing-workspace-tab-url-state.spec.ts
mise exec -- pnpm check
mise exec -- pnpm build
```

Playwright의 독립 clean context에서 `375x800`, `768x800`, `1440x800`을 각각 검증한다.

1. 기본 원고 탭 focus 후 `ArrowDown` 두 번과 `ArrowUp`, wrap
2. focus·selected state·URL·visible content의 동시 일치
3. inactive `TabsContent` hidden/non-visible
4. direct characters/world, explicit manuscript, invalid tab canonicalization
5. Characters → World → Back/Forward
6. mobile Sheet open/close focus return과 URL 유지
7. inline/Sheet scroll 경계와 console/network 오류

## 금지 범위

ContextPanelContent 자식 기능, mobile Sheet 소유 상태, URL 계약, autosave, AI/editor overlay, API/OpenAPI, 도메인 문서, package/lockfile은 수정하지 않는다.
