# 인물 카드 편집기 데스크톱 폭 결함 설계

## 목적

집필 작업공간의 `CharacterCardEditorSheet`가 데스크톱에서 승인된 넓은 편집 폭을 사용하도록 한다. 현재 1280px 너비의 브라우저에서 신규·수정 Sheet가 384px로 렌더링되어 9개 인물 기준 정보 필드를 좁은 열에서 편집해야 한다.

## 근거

- 요구사항: `frontend/docs/ui-plans/character-card-create-edit.md`의 desktop responsive 기준은 오른쪽 bounded Sheet를 `sm:max-w-2xl` 수준으로 제공한다.
- 재현 보고서: [CharacterCardEditorSheet 브라우저 버그 탐색 보고서](../../bug-reports/2026-07-24-1516-character-card-editor-sheet.html#bug-001)
- clean run 1: `1280x720` viewport에서 신규 Sheet의 bounding box가 `x=896, width=384`였다.
- clean run 2: 같은 시작 URL을 새로 열고 다시 신규 Sheet를 열었을 때 동일하게 `width=384`였다.
- 수정 Sheet도 `width=384`였고 이름 입력 폭은 351px였다.

## 사용자 영향과 심각도

심각도는 **Medium**이다. 저장이나 데이터 무결성을 막지는 않지만, 성격·문체·대사 스타일·기본 욕망·숨은 감정처럼 긴 문자열을 반복 편집하는 핵심 폼이 불필요하게 좁아져 줄바꿈과 세로 이동이 증가한다. 데스크톱용으로 승인된 정보 밀도와 wireframe을 충족하지 못한다.

## 범위

- `CharacterCardEditorSheet`의 desktop width override만 수정한다.
- 신규와 기존 인물 수정 Sheet에 같은 폭 정책을 적용한다.
- 375px mobile에서는 기존 full-width 동작을 보존한다.
- 공용 `Sheet` 기본 폭과 다른 Sheet 소비자는 변경하지 않는다.
- 9개 필드, 불변 ID, validation, 저장·실패·unavailable·discard·focus·scroll 의미는 변경하지 않는다.
- API, Story Bible 도메인 계약, package/lockfile은 변경하지 않는다.

## 설계 방향

`CharacterCardEditorSheet` 소비자 수준에서 side-specific 공용 max-width보다 명확히 우선하는 desktop max-width를 선언한다. 공용 `SheetContent`를 전역 변경하지 않아 다른 소비자의 레이아웃을 보존한다. 1280px desktop에서 약 `40rem`(`sm:max-w-2xl`)의 편집 폭을 제공하고, breakpoint 미만에서는 `w-full`을 유지한다.

확인된 DOM에는 공용 `data-[side=right]:sm:max-w-sm`와 소비자의 `sm:max-w-2xl`이 함께 존재했다. Tailwind 생성 CSS의 selector 우선순위 때문에 공용 규칙이 이긴 것으로 보이나, 이는 구현 전 CSS 산출물을 확인해야 하는 **원인 가설**이다.

## 수용 기준

1. 1280x800에서 신규와 수정 `CharacterCardEditorSheet`가 약 40rem 폭으로 렌더링된다.
2. 375x800에서 Sheet는 viewport full width이고 가로 overflow가 없다.
3. 공용 `Sheet`와 다른 소비자의 width는 바뀌지 않는다.
4. 이름·성별·나이·역할·성격·문체·대사 스타일·기본 욕망·숨은 감정, 수정 ID와 footer action이 scroll을 통해 모두 도달 가능하다.
5. 기존 create/edit, validation, 중복 저장 차단, failure/retry, unavailable, close/discard, keyboard focus 동작이 회귀하지 않는다.

