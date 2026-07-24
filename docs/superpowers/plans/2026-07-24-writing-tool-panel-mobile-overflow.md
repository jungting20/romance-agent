# WritingToolPanel 모바일 시트 폭 이탈 수정 계획

> 버그 보고서: [WritingToolPanel 브라우저 탐색 보고서](../../bug-reports/2026-07-24-1431-writing-tool-panel.html#bug-001)
>
> 승인 설계: [WritingToolPanel 모바일 시트 폭 이탈 수정 설계](../specs/2026-07-24-writing-tool-panel-mobile-overflow-design.md)

## 목표

모바일 `AI 집필 도구` 시트 안의 `WritingToolPanel`을 부모 폭에 맞춰 닫기 버튼과 모든
도구·제안 컨트롤을 viewport 안에 유지하고, 데스크톱 리사이즈 패널과 기존 집필 지원
동작을 보존한다.

## 작업 1: 집중 회귀 테스트 추가

**수정 후보**

- `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`
- 필요할 때만 `frontend/src/modules/writing-assistant/ui/writing-tool-panel.test.tsx` 신규 생성

**절차**

1. 모바일 분기에서 `AI 집필 도구` dialog를 열고 패널이 모바일 Sheet의 가용 폭을
   사용하도록 하는 계약을 관찰 가능한 클래스/구조로 검증한다.
2. 선택 전 `문장 다듬기` disabled, 선택 후 enabled, 이어 쓰기·대사 제안의 적용/닫기,
   진단 제안의 닫기 전용 동작을 회귀 테스트로 유지한다.
3. 기존 구현에서 모바일 폭 회귀 테스트가 실패하는지 먼저 확인한다.

**집중 검증**

```sh
cd frontend
mise exec -- pnpm test -- src/pages/writing-workspace/writing-workspace-page.test.tsx
```

## 작업 2: 패널 폭을 컨테이너 소유로 정리

**수정 후보**

- `frontend/src/modules/writing-assistant/ui/writing-tool-panel.tsx`
- 모바일/데스크톱 컨테이너 구분이 꼭 필요할 때만
  `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`

**절차**

1. `WritingToolPanel` 최상위 `aside`가 모바일 Sheet의 실제 폭을 넘지 않도록
   `w-full`, `min-w-0`, `max-w-full` 또는 동등한 컨테이너 기반 폭 계약을 적용한다.
2. 데스크톱 폭은 기존 `Panel` 컨테이너가 소유하게 하여 `1280x800`, `1440x800`의
   오른쪽 패널 및 리사이즈 경계를 유지한다.
3. 헤더의 `AI 도구 닫기`, 네 도구 카드, 제안 카드가 축소 가능한지 확인하고
   불필요한 공용 `Sheet` 변경은 하지 않는다.
4. 작업 1의 테스트를 통과시킨다.

## 작업 3: 브라우저 및 전체 검증

1. clean MSW `silver-garden`, 인증 없음으로 `375x800`, `1280x800`, `1440x800`에서
   `/projects/silver-garden/write`를 연다.
2. 모바일에서 dialog·panel·닫기 버튼의 `getBoundingClientRect()`가 viewport 안인지
   측정하고 스크린샷을 남긴다.
3. 키보드로 패널을 열고 네 도구에 이동한다. 선택 전/후 문장 다듬기, 대사 제안,
   일관성 진단, 제안 닫기·원고 적용, `Escape`와 보이는 닫기 버튼, 패널 세로 스크롤을
   확인한다.
4. 콘솔 오류와 `/api/projects/silver-garden/workspace`, `story-bible`, 원고 PUT 요청을
   확인한다. 실제 외부 네트워크는 사용하지 않는다.
5. 프론트엔드 전체 검사를 실행한다.

```sh
cd frontend
mise exec -- pnpm check
mise exec -- pnpm build
```

## 완료 조건

- 설계의 수용 기준 1–6이 모두 증거와 함께 충족된다.
- 모바일 닫기 버튼과 패널 전체가 viewport 안에 있다.
- 데스크톱 레이아웃과 Writing Assistant 동작에 회귀가 없다.
- 도메인 계약, OpenAPI, 패키지·lockfile, 다른 화면을 변경하지 않는다.

