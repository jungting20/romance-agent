# 세계관 편집기 데스크톱 폭 복원 구현 계획

> 버그 보고서: [WorldEditorSheet 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1439-world-editor-sheet.html#bug-002)

## 목표

WorldEditorSheet에 승인된 desktop 약 40rem 폭을 실제 적용하면서 mobile full-width와 다른 Sheet 소비자의 폭을 보존한다.

## 작업

1. `frontend/src/components/ui/sheet.tsx`의 `data-[side=right]:sm:max-w-sm`과 `frontend/src/features/edit-world-entries/ui/world-editor-sheet.tsx`의 `sm:max-w-2xl`이 동시에 적용되는 computed style을 재현한다.
2. WorldEditorSheet 전용 override가 side-specific 기본보다 우선하도록 최소 변경한다. 공용 Sheet API를 바꾸는 경우 기존 호출자에 영향이 없는 explicit variant/prop을 사용한다.
3. focused test 또는 style contract test에서 WorldEditorSheet의 desktop width class와 mobile full-width 계약을 고정한다.
4. 실제 브라우저에서 dialog와 field bounding box를 1280×800, 375×800에서 측정한다.
5. context, character, AI tool Sheet의 폭이 변하지 않았는지 smoke check한다.

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
1280x800: WorldEditorSheet computed width/max-width와 field width 측정
375x800: full-width, horizontal overflow, footer/close/add/save visibility 확인
```

## 완료 조건

- desktop에서 384px 고정이 제거되고 승인된 약 40rem 폭이 적용된다.
- mobile와 다른 Sheet 소비자 회귀가 없다.
- 저장, validation, failure, conflict, unavailable 흐름의 의미가 바뀌지 않는다.

