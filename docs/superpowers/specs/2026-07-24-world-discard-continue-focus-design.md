# 세계관 폐기 취소 후 편집기 포커스 복원 설계

> 버그 보고서: [WorldEditorSheet 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1439-world-editor-sheet.html#bug-001)

## 결함

`/projects/silver-garden/write?tab=world`에서 세계관 편집 내용을 변경한 뒤 `Escape`로 닫기를 시도하고 폐기 확인의 `계속 편집`을 선택하면, 편집 URL과 초안은 보존되지만 `document.activeElement`가 `BODY`가 된다. 동일 현상은 revision conflict의 `최신 세계관 불러오기` 확인에서 `계속 편집`을 선택해도 발생한다.

`REQ-WORLD-006`은 폐기 취소 뒤 편집기로 돌아가야 한다고 요구하고, `REQ-WORLD-010`은 키보드 조작과 visible focus를 요구한다. 키보드 사용자는 현재 위치를 잃고 다음 `Tab` 순서를 다시 탐색해야 한다.

## 재현 증거

- 환경: Chromium, MSW `silver-garden`, 인증 없음, 기준 revision `db203c2`.
- 실행 1: 기존 항목 제목 수정 → `Escape` → `계속 편집` 클릭. 초안은 유지됐지만 active element가 `BODY`였다.
- 실행 2: clean 페이지 재로드 → 제목 수정 → `Escape` → 기본 포커스의 `계속 편집`을 `Enter`로 선택. `activeTag: BODY`, `titlePreserved: true`가 다시 확인됐다.
- 추가 범위 확인: 409 conflict → `최신 세계관 불러오기` → `계속 편집`에서도 `BODY` 포커스와 local draft 보존이 확인됐다.
- 화면 증거: `docs/bug-reports/assets/2026-07-24-1439-world-editor-sheet/discard-focus-run2.png`.

## 기대 동작

폐기 확인을 취소하면 dialog가 닫힌 뒤 WorldEditorSheet 안의 유효하고 조작 가능한 control로 포커스가 복원되어야 한다. 가능하면 dialog를 열기 직전 control을 복원하고, 그 control이 사라졌다면 현재 첫 세계관 분류 field 같은 안정적인 Sheet fallback을 사용한다. close와 reload-latest intent 모두 같은 접근성 계약을 지켜야 한다.

## 범위

- `WorldDiscardDialog`의 취소 후 focus restoration.
- WorldEditorSheet의 dirty close와 conflict latest-reload 취소 흐름.
- 키보드 `Escape`/`Enter`, 마우스 취소, 초안·URL 보존 회귀.
- `변경사항 버리기`, 실제 latest reload, clean close, 저장 성공 후 launch focus 회귀.

## 제외 범위

- 인물 편집 dialog, 원고 conflict dialog와 공용 Dialog 소비자 전반.
- Story Bible 저장 의미, API, MSW 계약, domain contract 변경.
- WorldEditorSheet 레이아웃 또는 폭 수정.

## 구현 원칙

Dialog lifecycle의 `onCloseAutoFocus` 또는 명시적인 focus target ref를 사용해 dialog가 실제로 unmount된 뒤 포커스를 복원한다. 단순 `autoFocus`를 취소 버튼에 주는 것은 dialog 진입만 해결하며 종료 포커스를 보장하지 않는다. 숨겨졌거나 disabled인 노드로 포커스하지 않는다.

## 수용 기준

1. dirty close 확인에서 `계속 편집`을 mouse와 `Enter`로 선택하면 초안과 `panel=world-editor`가 유지된다.
2. dialog 종료 직후 active element는 WorldEditorSheet 내부의 visible, enabled control이다.
3. conflict latest-reload 확인의 취소도 같은 결과를 낸다.
4. `변경사항 버리기`와 latest reload 승인 동작은 기존 의미와 focus destination을 유지한다.
5. validation, save success/failure/conflict/unavailable 동작은 바뀌지 않는다.

