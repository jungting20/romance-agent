# 인물 변경사항 폐기 취소 후 편집기 포커스 복원 설계

> 버그 보고서: [CharacterDiscardDialog 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1440-character-discard-dialog.html#bug-001)

## 결함 요약

`/projects/silver-garden/write?tab=characters`에서 신규 등록 또는 수정 Sheet를 dirty 상태로 만든 뒤 닫기·`Escape`·브라우저 `Back`으로 `CharacterDiscardDialog`를 열고 `계속 편집`을 선택하면, draft와 editor URL은 유지되지만 포커스가 편집기 안으로 돌아오지 않고 `document.body`로 이동한다.

`frontend/docs/ui-plans/character-card-create-edit.md`의 REQ-08과 접근성 기준은 discard 취소 시 draft/URL을 보존하고 편집기 맥락으로 포커스를 돌려야 한다. `frontend/docs/e2e-plans/character-card-create-edit.md`도 dirty 닫기, `Escape`, `Back` 취소 뒤 editor URL·exact draft·focus 복원을 요구한다.

## 범위

- `CharacterDiscardDialog`에서 `계속 편집`을 실행한 직후, 방금 편집하던 인물 Sheet 안의 합리적인 편집 맥락으로 포커스를 복원한다.
- 신규 등록과 기존 인물 수정, 명시적 닫기·`Escape`·navigation discard 취소를 같은 규칙으로 다룬다.
- draft, URL search, dialog 초기 포커스, discard 확정, Sheet 종료 후 launch action 포커스, 저장 중 차단을 보존한다.

## 제외 범위

- 인물 저장·검증·API·Story Bible 모델의 의미 변경
- discard 문구나 버튼 순서 변경
- 세계관 편집기, 원고 conflict/retry dialog, 공용 `Dialog`의 다른 소비자 변경
- 모바일 Sheet 구조, 신규 반응형 디자인, 새 패키지 도입

## 재현 증거

환경은 인증 없는 로컬 MSW `silver-garden`, revision `db203c227ff68d319687c8761dd5a789f2d376cc`, 브라우저 실제 viewport `1280x720`이다. 할당된 `1280x800`, `375x800`은 현재 브라우저 도구가 viewport 변경을 제공하지 않아 미확인이다.

1. clean 수정 재현: 서윤 수정 → 성격 변경 → `Escape` → `계속 편집`. 결과는 성격 draft와 `panel=character-editor&characterId=silver-garden-character-1` URL이 보존됐지만 `document.activeElement`가 `BODY`였다.
2. clean 신규 재현: 새 인물 등록 → 이름 `포커스 재현` 입력 → `Escape` → `계속 편집`. 결과는 이름 draft와 `panel=character-editor` URL이 보존됐지만 `document.activeElement`가 `BODY`, `inDialog=false`였다.
3. 추가 명시적 닫기 재현: 서윤 수정 → 성격 변경 → `인물 편집기 닫기` → `계속 편집`. 같은 결과가 재현됐다.

- [신규 등록 clean 재현 화면](../../bug-reports/assets/2026-07-24-1440-character-discard-dialog/continue-editing-focus-run2.png)
- [명시적 닫기 추가 재현 화면](../../bug-reports/assets/2026-07-24-1440-character-discard-dialog/continue-editing-focus-run3.png)

스크린샷은 Sheet가 유지되고 draft가 보존된 화면을 보여준다. 포커스 판정은 같은 시점의 `document.activeElement` 측정값으로 확인했다.

## 기대 동작

- discard dialog가 열리면 `계속 편집`이 초기 포커스를 가진다.
- `계속 편집`을 선택하면 dialog만 닫고 Sheet·draft·URL을 유지한다.
- dialog를 연 사용자의 작업 맥락이 아직 유효하면 그 control로, 그렇지 않으면 Sheet의 안정적인 첫 편집 control로 포커스를 복원한다.
- 복원된 포커스는 `CharacterCardEditorSheet`의 focus trap 안에 있어야 한다.
- `변경사항 버리기`는 기존처럼 Sheet를 닫고 launch action 또는 확정된 navigation으로 포커스·이동을 넘긴다.

## 구현 방향

`CharacterDiscardDialog`는 현재 controlled `Dialog`를 trigger 없이 열고 `onCancel`에서 상태만 닫는다. 확인된 소스 위치는 `frontend/src/features/character-card-editor/character-card-editor-sheet.tsx:269`와 `frontend/src/features/character-card-editor/use-character-card-editor.ts:192`이다. 명시적인 복원 대상이나 `onCloseAutoFocus` 처리가 보이지 않는 것이 원인 후보지만, 구현 전에 실제 Radix close autofocus 순서와 중첩 Sheet lifecycle로 검증해야 한다.

복원 정책은 `CharacterDiscardDialog` 또는 해당 interaction을 조정하는 feature 경계에 국소화한다. 공용 `Dialog` primitive를 전역 변경하지 말고, Sheet가 닫히는 discard 확정과 navigation 확정에는 취소용 포커스 복원을 실행하지 않는다. 닫기 방식별 임시 ref가 필요하다면 Sheet 안의 마지막 유효 active element를 안전하게 보관하고, DOM에서 제거됐거나 disabled인 경우 이름 input 같은 안정적인 fallback을 사용한다.

## 수용 기준

- 신규/수정 dirty Sheet에서 명시적 닫기, `Escape`, 브라우저 `Back` 후 `계속 편집`을 선택하면 exact draft와 editor URL이 유지된다.
- 각 경로에서 `document.activeElement`는 `CharacterCardEditorSheet` 내부의 포커스 가능한 control이다.
- discard dialog의 초기 포커스와 `Tab`/`Shift+Tab` trap은 유지된다.
- `변경사항 버리기` 뒤 Sheet가 한 번만 닫히고 launch focus 또는 확정 navigation이 유지된다.
- 저장 중에는 폼, 닫기, 취소, 저장이 disabled이고 `Escape`/outside dismissal이 차단된다.
- create/edit 저장·실패 재시도·unavailable 흐름과 공용 dialog 소비자는 회귀하지 않는다.

## 검증 명령

```sh
cd frontend
mise exec -- pnpm exec vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm exec playwright test e2e/character-card-resilience-navigation.spec.ts
mise exec -- pnpm check
mise exec -- pnpm build
```

실제 브라우저에서는 `1280x800`과 `375x800` 각각에서 신규/수정, 닫기/`Escape`/`Back`, dialog keyboard trap, discard 확정 focus, 저장 중 차단을 다시 확인한다.

## 자체 검토

결함은 권위 요구사항과 두 번의 clean 재현으로 뒷받침되며, draft 저장 의미나 다른 dialog를 변경하지 않는 독립 수정 단위다. 원인 설명은 검증되지 않은 가설로 표시했고, 정상 동작으로 확인된 discard 확정·navigation·saving 동작을 보존 조건에 포함했다.
