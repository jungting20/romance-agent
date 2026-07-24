# 세계관 편집기 데스크톱 폭 복원 설계

> 버그 보고서: [WorldEditorSheet 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1439-world-editor-sheet.html#bug-002)

## 결함

1280px 폭에서 WorldEditorSheet는 요구된 약 40rem 편집 surface가 아니라 384px(`sm:max-w-sm`)로 렌더링된다. 실제 dialog 측정값은 두 clean 실행 모두 `width: 384`, `maxWidth: 384px`였다. 분류·제목·설명의 실제 입력 폭은 319px로 축소된다.

UI 계획은 desktop Sheet를 약 40rem(`sm:max-w-2xl`)로 규정한다. WorldEditorSheet는 `sm:max-w-2xl`을 전달하지만 공용 Sheet의 `data-[side=right]:sm:max-w-sm`도 함께 남아 실제 computed max-width가 384px가 된다.

## 재현 증거

- 환경: Chromium, MSW `silver-garden`, 인증 없음, 기준 revision `db203c2`.
- 실행 1: clean `?tab=world` → `세계관 수정 및 추가` → accessibility snapshot box `384px`.
- 실행 2: clean 페이지 재로드 → 재진입 → DOM 측정 `width: 384`, `maxWidth: 384px`, 입력 폭 `319px`.
- 화면 증거: `docs/bug-reports/assets/2026-07-24-1439-world-editor-sheet/desktop-width-run2.png`.

## 기대 동작

작은 화면에서는 full-width Sheet를 유지하고, `sm` 이상 desktop에서는 승인된 WorldEditorSheet 전용 최대 폭 약 40rem이 실제 computed style로 적용되어야 한다. 공용 Sheet의 다른 소비자 기본 폭은 바뀌지 않아야 한다.

## 범위

- WorldEditorSheet에서 side-specific 기본 max-width보다 우선하는 소비자 폭 적용.
- 1280×800 desktop의 computed width와 긴 title/description 편집성.
- 375×800 mobile full-width, scroll, footer control 회귀.

## 제외 범위

- 공용 Sheet의 기본 폭을 일괄 변경하는 redesign.
- Character editor, context Sheet, AI tool Sheet의 폭 변경.
- world editor의 저장·validation·conflict 의미 변경.

## 구현 원칙

WorldEditorSheet의 width override가 Tailwind modifier 충돌 없이 공용 side-specific class를 실제로 이기도록 한다. 필요하면 Sheet primitive가 소비자 폭 override를 안전하게 받을 수 있는 좁은 API를 사용하되 다른 소비자의 computed width를 회귀 검증한다.

## 수용 기준

1. 1280×800에서 WorldEditorSheet의 computed max-width는 승인된 약 40rem이고 실제 폭은 384px에 고정되지 않는다.
2. 375×800에서는 viewport를 넘지 않고 full-width이며 좌우 control이 잘리지 않는다.
3. header, scrollable form, fixed footer와 keyboard focus 동작은 유지된다.
4. 공용 Sheet의 다른 소비자 기본 폭은 변하지 않는다.

