# WritingToolPanel 모바일 시트 폭 이탈 수정 설계

> 버그 보고서: [WritingToolPanel 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1431-writing-tool-panel.html#bug-001)

## 문제

`/projects/silver-garden/write`를 `375x800`에서 열고 `AI 도구 열기`를 실행하면 모바일
`Sheet`는 화면 오른쪽의 `281px` 영역을 소유하지만, 그 안의 `WritingToolPanel`은
`336px` 고정 폭으로 렌더링된다. 두 번의 clean MSW `silver-garden` 실행에서 패널의
오른쪽 경계가 모두 `431px`, `AI 도구 닫기` 버튼이 `387..415px`로 측정되어
`375px` viewport 밖으로 이탈했다.

이 때문에 패널 오른쪽 테두리와 도구 카드 일부가 잘리고, 닫기 버튼은 포인터로 볼 수도
누를 수도 없다. `Escape`로 닫는 복구 경로는 동작하지만 화면 안에 보이는 닫기 동작을
대체하지 못한다.

## 요구사항 근거

- `frontend/docs/frontend-coding-rules.md`는 키보드 호환 상호작용, 접근 가능한 이름,
  보이는 포커스와 반응형 상태를 요구한다.
- 기존 집필 화면 설계는 좁은 화면에서 `AI 집필 도구`를 접근 가능한 모바일
  `Sheet`로 제공한다.
- 지정된 사용자 흐름은 `375x800`에서 도구 실행, 제안 닫기·원고 적용, 패널 닫기,
  키보드·포커스·스크롤을 사용할 수 있어야 한다.

## 범위

- 모바일 `Sheet` 안에서 `WritingToolPanel`과 헤더, 닫기 버튼, 도구 카드 및 제안 카드가
  사용 가능한 가로 폭을 넘지 않도록 한다.
- 데스크톱 `1280x800`, `1440x800`의 오른쪽 패널 폭과 리사이즈 레이아웃을 보존한다.
- 기존 이어 쓰기, 선택 전/후 문장 다듬기, 대사 제안, 일관성 진단, 제안 닫기와 적용
  동작을 보존한다.

## 제외 범위

- AI 제안 문구·생성 규칙, 원고 적용 알고리즘, 자동 저장, API, MSW 데이터, 도메인 계약
- 공용 `Sheet`의 다른 소비자 동작 변경
- WritingToolPanel 밖의 집필 화면 레이아웃 재설계

## 확인된 관찰과 원인 가설

`frontend/src/components/ui/sheet.tsx`의 오른쪽 `SheetContent`는 모바일에서 `w-3/4`이고,
`frontend/src/modules/writing-assistant/ui/writing-tool-panel.tsx`의 최상위 `aside`는
`w-[21rem]`이다. 고정 자식 폭이 시트 폭보다 커서 이탈한다는 설명은 소스 기반 가설이며,
수정 시 집중 테스트와 실제 브라우저 기하 측정으로 확정해야 한다.

## 수용 기준

1. clean `silver-garden`, 인증 없음, `375x800`에서 패널과 모든 자식의 좌우 경계가
   `0..375px` 안에 있고 `AI 도구 닫기` 버튼 전체가 보이며 포인터로 실행된다.
2. 패널을 연 직후 모바일 focus trap과 `Escape` 닫기가 유지되고, 패널 내부 세로
   스크롤로 모든 도구와 제안 동작에 도달할 수 있다.
3. 선택이 없을 때 `문장 다듬기`는 disabled이고 원고를 선택하면 enabled가 된다.
4. 이어 쓰기·대사 제안에는 `원고에 적용`과 `닫기`가 보이며, 일관성 진단에는
   `닫기`만 보인다. 적용 및 닫기 동작은 기존 의미를 보존한다.
5. `1280x800`, `1440x800`에서 데스크톱 오른쪽 패널은 화면 안에 유지되고 중앙
   편집기·왼쪽 패널 리사이즈 동작을 회귀시키지 않는다.
6. 제품 코드 변경은 WritingToolPanel 모바일 폭 결함에 필요한 최소 범위로 제한하고
   API·도메인 계약·패키지 파일을 변경하지 않는다.

## 증거

- [1차 clean-state 화면](../../bug-reports/assets/2026-07-24-1431-writing-tool-panel/mobile-overflow-run1.png)
- [2차 clean-state 화면](../../bug-reports/assets/2026-07-24-1431-writing-tool-panel/mobile-overflow-run2.png)
- 2차 측정: viewport `375x800`, dialog `94..375px`, panel `95..431px`,
  close button `387..415px`, `closeInViewport=false`

