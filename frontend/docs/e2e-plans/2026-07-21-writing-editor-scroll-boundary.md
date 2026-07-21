# 집필 에디터 스크롤 경계 E2E 테스트 계획

## 계획 기준

- 대상 라우트: `/projects/silver-garden/write`
- 인증: 없음
- 승인된 설계: `docs/superpowers/specs/2026-07-21-writing-editor-scroll-boundary-design.md`
- 승인된 구현 계획: `docs/superpowers/plans/2026-07-21-writing-editor-scroll-boundary.md`
- 승인 revision: `e2c2dc1`
- 검토 대상:
  - `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
  - `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`
- 검토 결과: FE-001의 실제 브라우저/반응형 검증 누락은 Chromium 375x500, 1024x500, 1440x500 측정으로 해결되었고 재검토는 normalized PASS였다. 도입·기존·adoption finding은 없다.

이 계획은 AC-1부터 AC-4까지의 스크롤 경계와 반응형 분기만 자동화한다. AC-5의 입력·선택·자동저장·보조 패널 전체 기능은 기존 테스트의 책임으로 유지하며, 긴 콘텐츠를 만드는 데 필요한 원고 입력과 반응형 분기의 존재를 확인하는 최소 상호작용만 수행한다.

## 생성 대상

- 정확한 Playwright spec 경로: `frontend/e2e/writing-editor-scroll-boundary.spec.ts`
- `frontend/seed.spec.ts`는 빈 생성 placeholder이므로 코드나 구조를 재사용하지 않는다. 파일 자체도 수정하지 않는다.
- 기존 로컬 개발 MSW seed의 `silver-garden` 프로젝트와 실제 `/projects/silver-garden/write` 라우트는 재사용한다.
- 스크린샷 비교는 사용하지 않는다. 접근 가능한 role/name, DOM 스크롤 수치, bounding rectangle, 실제 `scrollTop` 변화로 판정한다.

## 수용 기준 추적

| 수용 기준                    | E2E 판정                                                                                                                          |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| AC-1 문서 스크롤 없음        | 각 뷰포트에서 `document.documentElement.scrollHeight <= window.innerHeight` 및 `window.scrollY === 0`                             |
| AC-2 중앙 `main` 자체 스크롤 | 원고 textbox의 가장 가까운 `main`에서 `scrollHeight > clientHeight`; `scrollTop = 240` 적용 후 실제 값이 0보다 크고 목표값에 도달 |
| AC-3 header/nav 위치 유지    | 중앙 `main` 스크롤 전후 header/nav의 `getBoundingClientRect().top` 변화가 1px 이내; header는 약 0px, nav는 약 64px                |
| AC-4 반응형 구성 보존        | 375px은 문맥 Sheet, 1024px은 고정 문맥 패널, 1440px은 리사이즈 패널 및 separator를 최소 확인                                      |
| AC-5 기능 회귀 없음          | 이 티켓 E2E에서는 새 기능 시나리오를 추가하지 않는다. 긴 원고 입력 성공과 분기별 패널/Sheet 노출만 smoke 확인                     |

## 공통 시작 상태와 결정적 긴 원고 준비

각 시나리오는 새 Playwright page/browser context의 깨끗한 MSW 상태에서 독립 실행한다.

1. 테스트별로 viewport를 정확히 지정한다: `375x500`, `1024x500`, `1440x500`.
2. `/projects/silver-garden/write`로 이동한다.
3. `getByRole("textbox", { name: "원고 본문" })`이 보일 때까지 기다린다. 이것이 MSW seed workspace 로드 완료 신호다.
4. 다음과 같이 테스트 파일 내부에서 고정된 180줄 원고를 만든다. 난수, 현재 시각, 외부 fixture 또는 테스트 실행 순서에 의존하지 않는다.

   ```ts
   const LONG_MANUSCRIPT = Array.from(
     { length: 180 },
     (_, index) =>
       `${String(index + 1).padStart(3, "0")}행 긴 원고 스크롤 경계를 검증하는 문장입니다.`,
   ).join("\n");
   ```

5. textbox에 `fill(LONG_MANUSCRIPT)`를 수행하고 `toHaveValue(LONG_MANUSCRIPT)`로 React 반영을 확인한다. 이 입력은 콘텐츠 높이를 결정적으로 만드는 준비 동작일 뿐, 자동저장 계약을 별도로 검증하지 않는다.
6. textbox의 가장 가까운 조상 `main`을 중앙 에디터 스크롤 컨테이너로 잡는다. 전역 `main` 선택자는 로딩/오류 화면과 혼동할 수 있으므로 사용하지 않는다.
7. 레이아웃 계산이 끝날 때까지 `expect.poll`로 중앙 `main.scrollHeight > main.clientHeight`를 기다린 뒤 측정한다.

## 공통 스크롤 경계 검증 절차

아래 절차를 세 viewport 시나리오 모두에서 동일하게 실행한다.

1. 중앙 에디터 `main`, 화면의 첫 `header`, `getByRole("tablist", { name: "집필 도메인" })`의 조상 `nav`를 찾는다.
2. `page.evaluate` 또는 locator `evaluate`로 다음 초기값을 한 번에 읽는다.
   - `document.documentElement.scrollHeight`
   - `window.innerHeight`
   - `window.scrollY`
   - editor의 `scrollHeight`, `clientHeight`, `scrollTop`
   - header와 nav의 `getBoundingClientRect().top`
3. 다음을 단언한다.
   - 문서 `scrollHeight <= innerHeight`
   - `window.scrollY === 0`
   - editor `scrollHeight > clientHeight`
   - header top은 0px에서 1px 이내, nav top은 64px에서 1px 이내
4. editor locator에서 `element.scrollTop = 240`을 실행한다. 이어서 `expect.poll`로 `scrollTop > 0` 및 `Math.abs(scrollTop - 240) <= 1`을 확인한다.
5. 스크롤 뒤 문서와 위치를 다시 측정한다.
   - 문서 `scrollHeight <= innerHeight`와 `window.scrollY === 0`이 유지된다.
   - header/nav top은 각 초기값과 1px 이내로 같다.
6. 실패 조건은 문서 높이가 viewport를 초과함, editor가 넘치지 않거나 `scrollTop`이 움직이지 않음, 문서가 움직임, 또는 header/nav top이 허용 오차를 벗어남이다.

## 시나리오 1: 375x500 모바일에서 중앙 스크롤과 문맥 Sheet를 보존한다

**관련 기준:** AC-1, AC-2, AC-3, AC-4 모바일 분기

**시작 상태:** viewport `375x500`, 새 context, MSW seed `silver-garden`, 인증 없음, query string 없음.

1. 공통 긴 원고 준비와 공통 스크롤 경계 검증을 수행한다.
2. `getByRole("tab", { name: "인물 보기" })`를 클릭한다.
3. `getByRole("dialog", { name: "인물 보기" })`가 보이고 그 안에 `등장인물` 콘텐츠가 있는지 확인한다. 이는 모바일 문맥 영역이 inline 고정 패널이 아니라 Sheet 분기로 유지됨을 판정한다.
4. `getByRole("button", { name: "닫기" })`를 클릭해 dialog가 사라지는지 확인한다.
5. 원고 textbox가 계속 DOM에 있고 보이는지 확인한다.

**성공 기준:** 공통 수치 검증이 모두 통과하고 모바일 Sheet가 열리고 닫힌 뒤 에디터가 남는다.

**실패 조건:** 문서 스크롤 발생, editor 비스크롤, header/nav 이동, 문맥 dialog 미노출, 또는 Sheet 종료 뒤 에디터 소실.

## 시나리오 2: 1024x500 고정 패널에서 중앙 스크롤 경계를 유지한다

**관련 기준:** AC-1, AC-2, AC-3, AC-4 고정 데스크톱 패널 분기

**시작 상태:** viewport `1024x500`, 새 context, MSW seed `silver-garden`, 인증 없음, query string 없음.

1. 원고 textbox와 함께 `getByRole("heading", { name: "원고 목차" })`가 화면에 보이는지 확인한다. 문맥 영역이 Sheet를 열지 않아도 inline으로 존재해야 한다.
2. `getByRole("separator")`가 하나도 없는지 확인한다. 이 너비는 리사이즈 패널 분기가 아니다.
3. 공통 긴 원고 준비와 공통 스크롤 경계 검증을 수행한다.
4. 검증 뒤에도 `원고 목차` heading이 보이고 dialog가 자동으로 열리지 않았는지 확인한다.

**성공 기준:** 고정 문맥 패널과 원고 editor가 동시에 유지되고 공통 수치 검증이 모두 통과한다.

**실패 조건:** 문맥 영역이 dialog에만 존재함, separator가 나타남, 문서 스크롤 발생, editor 비스크롤, 또는 header/nav 이동.

## 시나리오 3: 1440x500 리사이즈 패널에서 중앙 스크롤 경계를 유지한다

**관련 기준:** AC-1, AC-2, AC-3, AC-4 `>=1280px` 리사이즈 패널 분기

**시작 상태:** viewport `1440x500`, 새 context, MSW seed `silver-garden`, 인증 없음, query string 없음.

1. 원고 textbox와 `원고 목차` heading이 함께 보이는지 확인한다.
2. 초기 `getByRole("separator")`가 정확히 1개인지 확인해 문맥 패널과 중앙 editor가 리사이즈 패널 그룹에 있음을 판정한다.
3. 공통 긴 원고 준비와 공통 스크롤 경계 검증을 수행한다.
4. `getByRole("button", { name: "AI 도구 열기" })`를 클릭한다.
5. `getByRole("dialog", { name: "AI 집필 도구" })`는 나타나지 않고, `getByRole("heading", { name: "AI 집필 도구" })`와 separator 2개가 보이는지 확인한다. 이는 넓은 화면의 보조 패널도 Sheet가 아니라 세 번째 리사이즈 패널로 남았다는 최소 smoke 확인이다.

**성공 기준:** 리사이즈 분기의 초기/보조 패널 separator 수가 맞고 공통 수치 검증이 모두 통과한다.

**실패 조건:** 초기 separator 수가 다름, AI 도구가 dialog로 열림, 세 번째 패널 separator가 추가되지 않음, 문서 스크롤 발생, editor 비스크롤, 또는 header/nav 이동.

## 생성 지침

- 세 시나리오는 서로 독립된 `test`로 작성하고 공통 긴 원고 준비/측정만 작은 helper로 공유한다.
- viewport는 각 test 또는 각 독립 describe에서 명시적으로 설정한다. 프로젝트 기본 viewport에 의존하지 않는다.
- 사용자 요소 탐색은 role과 accessible name을 우선한다. 중앙 editor `main`과 nav는 접근 가능한 textbox/tablist에서 가장 가까운 의미 조상으로 찾는다.
- 픽셀 스크린샷이나 클래스 문자열만으로 성공을 판정하지 않는다.
- `waitForTimeout`을 사용하지 않는다. UI 표시에는 Playwright web-first assertion, 레이아웃 안정에는 `expect.poll`을 사용한다.
- 반응형 존재 검증을 넘어 탭 URL, 선택 범위, 자동저장 성공/실패, AI 제안 생성/적용, 세계관 편집 시나리오를 추가하지 않는다.
- 테스트 중 발견한 제품 결함을 spec에서 우회하거나 제품 코드로 수정하지 말고 main agent에 반환한다.

## 검증 명령

`frontend/`에서 다음 순서로 실행한다.

```sh
mise exec -- pnpm exec playwright test e2e/writing-editor-scroll-boundary.spec.ts
mise exec -- pnpm check
mise exec -- pnpm build
```

각 명령은 종료 코드 0이어야 한다. 첫 명령은 세 viewport 시나리오가 모두 실행되었는지도 결과에서 확인한다.

## 가정 및 미해결 사항

- 가정: E2E 실행 시 로컬 개발 서버가 Playwright가 접근하는 origin에서 실행 중이며 개발 모드 MSW가 활성화되어 있다. `silver-garden` seed가 `/projects/silver-garden/write`에서 로드된다.
- 가정: Playwright의 각 test가 새 browser context를 사용하므로 MSW의 in-memory manuscript 상태도 시나리오 간 공유되지 않는다. 각 test는 seed 화면을 다시 연 뒤 긴 원고를 다시 입력하므로 실행 순서에도 의존하지 않는다.
- 가정: 승인된 수동 Chromium 증거(문서 `scrollHeight === innerHeight === 500`, editor `scrollHeight` 약 6718/6738, `clientHeight` 436, `scrollTop=240`, header top 0/nav top 64)를 기준으로 1px 허용 오차를 사용한다. editor의 절대 `scrollHeight`는 폰트/렌더링 차이에 취약하므로 자동화에서는 대소 관계만 단언한다.
- 미해결: 현재 `frontend/playwright.config.ts`에는 `baseURL`과 `webServer`가 없다. generator는 실행 환경에서 제공되는 로컬 서버 origin을 명시적으로 사용하거나 main agent가 승인한 Playwright 서버 설정을 따라야 한다. 이 계획의 소유 범위에서는 config를 변경하지 않는다.
- 미해결 제품 결정은 없다. 이 계획은 승인된 스크롤 경계와 기존 반응형 분기를 확장하지 않는다.
