# 세로 문맥 탭 방향키 결함 설계

## 목적

집필 작업공간 왼쪽의 세로 `원고 보기`·`인물 보기`·`세계관 보기` 탭이 화면 배치와 접근성 orientation에 맞게 위·아래 방향키로 이동하고 활성화되도록 한다.

## 근거

- 요구사항: `frontend/docs/ui-plans/writing-workspace-tab-url-state.md`는 vertical Tabs semantics와 Radix vertical-tabs keyboard behavior 보존을 명시한다.
- 재현 보고서: [ContextPanelContent 재시도 보고서](../../bug-reports/2026-07-24-1524-context-panel-content-retry.html#bug-001)
- clean run 1과 2 모두 기본 원고 URL에서 `원고 보기` 탭에 focus한 뒤 `ArrowDown`을 눌러도 focus, selected tab, URL이 바뀌지 않았다.
- 두 run 모두 tablist의 `aria-orientation`은 `horizontal`이었다. 대조 입력인 `ArrowRight`는 `인물 보기`와 `?tab=characters`로 전환했다.

## 심각도와 영향

심각도는 **Medium**이다. 포인터와 좌우 방향키 우회는 가능하지만, 시각적으로 세로인 문맥 navigation에서 예상되는 위·아래 키가 동작하지 않는다. 키보드와 보조기술 사용자는 orientation 정보를 잘못 전달받고 탭 전환을 예측하기 어렵다.

## 확인된 원인

`frontend/src/components/ui/tabs.tsx`의 `Tabs` wrapper는 `orientation`을 destructure해 `data-orientation`에만 쓰고, `TabsPrimitive.Root`에는 전달하지 않는다. 따라서 시각 class는 vertical이지만 Radix primitive는 기본 horizontal keyboard semantics와 `aria-orientation`을 사용한다.

## 범위

- `Tabs` wrapper가 받은 orientation을 Radix Root에 전달한다.
- 집필 작업공간 세 context tab의 위/아래 focus 이동·activation과 URL 연동을 검증한다.
- horizontal Tabs 기본 동작은 보존한다.
- `ContextPanelContent`의 세 콘텐츠, hidden 비노출, URL canonicalization/history, mobile Sheet와 desktop inline 구조를 보존한다.
- 제품 copy, API, 도메인 계약, 다른 context interaction, package/lockfile은 변경하지 않는다.

## 수용 기준

1. tablist가 `aria-orientation="vertical"`을 노출한다.
2. `원고 보기`에서 `ArrowDown`은 `인물 보기`, 다시 `ArrowDown`은 `세계관 보기`로 focus와 selection을 이동하고 canonical URL을 갱신한다.
3. `ArrowUp`과 처음/끝 wrap은 Radix vertical Tabs semantics를 따른다.
4. pointer 선택, direct URL, invalid/manuscript canonicalization, Back/Forward와 hidden panel 비노출이 유지된다.
5. 375x800 mobile Sheet, 768x800 fixed inline, 1440x800 resizable inline에서 동일한 tab semantics를 제공한다.
