# 인물 카드 편집기 데스크톱 폭 수정 계획

## authoritative inputs

- 설계: `docs/superpowers/specs/2026-07-24-character-card-editor-desktop-width-design.md`
- 증거: [보고서 bug-001](../../bug-reports/2026-07-24-1516-character-card-editor-sheet.html#bug-001)
- UI 기준: `frontend/docs/ui-plans/character-card-create-edit.md`
- 도메인 기준: `docs/domains/story-bible.md`

## 작업 1: 폭 회귀 테스트 추가

`CharacterCardEditorSheet` 또는 완성 화면의 기존 테스트 패턴을 사용해 desktop과 mobile의 computed/bounding width를 검증한다.

- 1280x800 신규와 수정 Sheet가 약 `40rem`인지 확인한다.
- 375x800에서 full-width이고 `scrollWidth <= clientWidth`인지 확인한다.
- 다른 Sheet 소비자의 기본 폭은 이 테스트 범위에서 건드리지 않는다.

집중 검증:

```sh
cd frontend
mise exec -- pnpm exec vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
```

## 작업 2: CharacterCardEditorSheet 로컬 width override 수정

`frontend/src/features/character-card-editor/character-card-editor-sheet.tsx`에서 공용 side-specific `sm:max-w-sm`보다 우선하는 소비자 전용 desktop max-width를 적용한다. 공용 `frontend/src/components/ui/sheet.tsx`는 수정하지 않는다.

확인 항목:

- 신규/수정 공통 적용
- mobile `w-full` 보존
- header, `ScrollArea`, fixed footer 구조 보존
- 필드, validation, 저장, unavailable, discard 동작 무변경

## 작업 3: 회귀 및 실제 브라우저 검증

```sh
cd frontend
mise exec -- pnpm exec vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm exec playwright test e2e/character-card-create-edit.spec.ts e2e/character-card-resilience-navigation.spec.ts
mise exec -- pnpm check
mise exec -- pnpm build
```

Playwright에서 `1280x800`과 `375x800`으로 다음을 확인한다.

1. 신규와 서윤 수정 Sheet의 bounding box와 가로 overflow
2. 9개 mutable 필드와 수정 ID의 label, scroll 도달성
3. 빈 이름 validation과 해결 시 피드백 제거
4. 빠른 이중 저장의 단일 요청
5. 500 failure/retry와 404 unavailable의 draft·disabled 상태
6. clean/dirty close, Escape, overlay, focus trap과 복원

## 금지 범위

공용 `Sheet` 폭, 다른 Sheet 소비자, API/OpenAPI, Story Bible 의미, 저장·validation·failure·discard 상태, package/lockfile을 수정하지 않는다.
