# 인물 변경사항 폐기 취소 후 편집기 포커스 복원 구현 계획

> 버그 보고서: [CharacterDiscardDialog 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1440-character-discard-dialog.html#bug-001)
>
> 설계: [인물 변경사항 폐기 취소 후 편집기 포커스 복원 설계](../specs/2026-07-24-character-discard-continue-focus-design.md)

## 목표

dirty 인물 등록·수정 Sheet의 discard dialog에서 `계속 편집`을 선택했을 때 draft와 URL뿐 아니라 편집기 내부 포커스도 복원한다. 범위는 `CharacterDiscardDialog`와 이를 조정하는 인물 카드 편집 feature에 한정한다.

## 작업 1: 집중 회귀 테스트로 결함 고정

**대상:**

- `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`
- `frontend/e2e/character-card-resilience-navigation.spec.ts`

1. 신규 등록과 기존 인물 수정에서 dirty close/`Escape`를 만들고 dialog의 초기 focus가 `계속 편집`인지 확인한다.
2. `계속 편집` 뒤 exact draft와 URL을 확인한 다음, `document.activeElement`가 열린 character Sheet 내부의 예상 control인지 assertion을 추가한다.
3. 브라우저 `Back`으로 열린 navigation discard를 취소한 경우에도 editor URL과 draft, Sheet 내부 focus를 검증한다.
4. `변경사항 버리기` 뒤 Sheet가 한 번만 닫히고 수정/등록 launch focus 또는 navigation 결과가 유지되는 기존 assertion을 보존한다.
5. 기존 구현에서 새 focus assertion이 실패해 결함을 재현하는지 확인한다.

검증:

```sh
cd frontend
mise exec -- pnpm exec vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
mise exec -- pnpm exec playwright test e2e/character-card-resilience-navigation.spec.ts
```

## 작업 2: discard 취소 전용 포커스 복원 구현

**주요 대상:**

- `frontend/src/features/character-card-editor/character-card-editor-sheet.tsx`
- 필요한 경우 `frontend/src/features/character-card-editor/use-character-card-editor.ts`
- 필요한 경우 해당 feature의 기존 public interface와 page wiring

1. controlled nested `Dialog`가 닫힐 때 Radix의 autofocus와 Sheet focus scope가 실행되는 순서를 확인한다.
2. discard를 연 직전의 Sheet 내부 active element를 복원할 수 있으면 사용하고, 제거되었거나 disabled이면 이름 input 등 안정적인 Sheet 내부 control을 사용한다.
3. 복원은 `계속 편집`/dialog cancel에만 적용한다. `변경사항 버리기`, navigation confirm, save success, clean close에는 적용하지 않는다.
4. 공용 `frontend/src/components/ui/dialog.tsx` 동작과 세계관·원고 dialog는 변경하지 않는다. 공용 primitive 변경이 불가피하다고 판단되면 이 티켓 범위를 넘으므로 먼저 main agent에 재승인을 요청한다.
5. create/edit, 닫기/`Escape`/`Back`의 동일 정책을 작은 typed interface로 연결하고 임의 timeout에 의존하지 않는다.

검증:

```sh
cd frontend
mise exec -- pnpm exec vitest run src/pages/writing-workspace/writing-workspace-page.test.tsx
```

## 작업 3: 회귀·브라우저 검증

1. 저장 중 MSW 응답을 지연해 form field, `인물 편집기 닫기`, `취소`, `저장 중…`이 disabled이고 `Escape`/outside dismissal이 차단되는지 확인한다.
2. `1280x800`과 `375x800`에서 신규/수정 Sheet, discard 초기 focus, `Tab`/`Shift+Tab` trap, `계속 편집` 후 Sheet 내부 focus, 확정 후 launch/navigation focus를 확인한다.
3. console error와 character API request 수를 확인해 새 오류와 중복 요청이 없는지 검증한다.
4. 전체 frontend 정적 검사와 build를 실행한다.

검증:

```sh
cd frontend
mise exec -- pnpm exec playwright test e2e/character-card-resilience-navigation.spec.ts
mise exec -- pnpm check
mise exec -- pnpm build
```

## 완료 조건

- 설계 문서의 모든 수용 기준이 자동화 테스트와 실제 브라우저에서 통과한다.
- 변경은 인물 discard 취소 포커스 범위 안에 머문다.
- Story Bible 도메인 계약과 OpenAPI는 의미 변경이 없어 수정하지 않는다.
- 관련 frontend 구현이 멈춘 뒤 root `AGENTS.md`의 read-only frontend review와 최종 통합 검증을 수행한다.

## 자체 검토

테스트가 먼저 결함을 고정하고, 구현은 discard 취소와 fallback focus에만 한정된다. 저장·discard 확정·navigation과 공용 dialog 소비자를 명시적인 회귀 경계로 두었으며 모든 단계에 실행 가능한 검증 명령을 포함했다.
