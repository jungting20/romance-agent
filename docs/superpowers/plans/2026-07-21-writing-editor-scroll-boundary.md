# 집필 에디터 스크롤 경계 수정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 긴 원고에서도 집필 화면의 문서 전체가 아니라 중앙 에디터 영역만 세로로 스크롤되게 한다.

**Architecture:** 집필 워크스페이스 루트를 작은 뷰포트 높이에 고정하고, 헤더 아래 flex 자식의 높이 축소 경계를 명시한다. 중앙 원고 `main`만 `overflow-y-auto`를 소유하며 도메인 모델, 상태, API는 변경하지 않는다.

**Tech Stack:** React 19, TypeScript 7, Tailwind CSS 4, Vitest, Testing Library

## Global Constraints

- 전역 `body` 또는 다른 라우트의 스크롤 정책을 변경하지 않는다.
- `ManuscriptEditor`의 원고 입력·선택 이벤트와 자동 저장 흐름을 변경하지 않는다.
- 데스크톱 고정·리사이즈 패널과 모바일 시트 분기를 모두 보존한다.
- 도메인과 OpenAPI 계약은 변경하지 않는다.

---

### Task 1: 집필 화면의 스크롤 소유권 고정

**Files:**
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx:114`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx:309`
- Modify: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx:320`
- Test: `frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx`

**Interfaces:**
- Consumes: `LoadedWritingWorkspace`의 기존 중앙 `editor` JSX와 반응형 패널 분기
- Produces: 뷰포트에 고정된 집필 화면과 `overflow-y-auto`를 소유하는 중앙 원고 `main`

- [ ] **Step 1: 스크롤 경계 회귀 테스트를 추가한다**

`writing-workspace-page.test.tsx`에서 정상 워크스페이스를 렌더링하고, 원고 본문에서 가장 가까운 `main`과 최상위 집필 컨테이너를 찾아 다음 계약을 검증한다.

```tsx
test("keeps document scrolling locked to the manuscript editor region", async () => {
  setViewportWidth(1024);
  const { container } = renderWorkspace();

  const manuscript = await screen.findByRole("textbox", { name: "원고 본문" });
  const editorRegion = manuscript.closest("main");
  const workspace = container.firstElementChild;

  expect(workspace).toHaveClass("h-svh", "overflow-hidden");
  expect(editorRegion).toHaveClass("min-h-0", "overflow-y-auto");
  expect(editorRegion?.parentElement).toHaveClass("min-h-0", "overflow-hidden");
});
```

- [ ] **Step 2: 테스트가 현재 레이아웃에서 실패하는지 확인한다**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- writing-workspace-page.test.tsx -t "keeps document scrolling locked"
```

Expected: `h-svh` 또는 `min-h-0`/`overflow-hidden` 경계가 없어 실패한다.

- [ ] **Step 3: 최소 레이아웃 변경으로 높이와 오버플로 경계를 연결한다**

`writing-workspace-page.tsx`에서 다음 원칙으로 기존 클래스만 조정한다.

```tsx
<div className="flex h-svh min-h-0 flex-col overflow-hidden bg-[#ede6dd]">
```

중앙 원고 영역은 축소 가능한 고정 높이 스크롤 컨테이너로 만든다.

```tsx
<main className="h-full min-h-0 min-w-0 overflow-y-auto p-3 sm:p-5 lg:p-6">
```

중앙 에디터를 감싸는 각 반응형 분기의 직접 래퍼에는 같은 경계를 적용한다.

```tsx
<div className="min-h-0 min-w-0 flex-1 overflow-hidden">{editor}</div>
```

리사이즈 패널 분기는 `ResizablePanel`이 중앙 `main`의 높이를 제한하도록 패널에 `className="min-h-0 overflow-hidden"`을 지정한다. 로딩 화면도 정상 화면과 같은 높이 정책을 사용해 로딩 완료 시 문서 스크롤 경계가 바뀌지 않게 한다.

- [ ] **Step 4: 집중 테스트를 통과시킨다**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- writing-workspace-page.test.tsx
```

Expected: `writing-workspace-page.test.tsx`의 모든 테스트가 통과한다.

- [ ] **Step 5: 브라우저에서 실제 스크롤 동작을 검증한다**

개발 서버에서 `/projects/silver-garden/write`를 열고 뷰포트 높이를 줄인 뒤 긴 원고를 사용해 다음을 확인한다.

```js
document.documentElement.scrollHeight <= window.innerHeight
```

중앙 에디터 `main`은 `scrollHeight > clientHeight`이고 `scrollTop` 변경이 가능해야 한다. 에디터를 스크롤한 전후에 헤더와 왼쪽 도구 내비게이션의 `getBoundingClientRect().top` 값은 같아야 한다. 데스크톱 리사이즈 패널, 고정 패널 너비, 모바일 너비에서 각각 확인한다.

- [ ] **Step 6: 프론트엔드 검증을 완료한다**

Run from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: 두 명령 모두 종료 코드 0.

- [ ] **Step 7: 변경을 커밋한다**

```sh
git add frontend/src/pages/writing-workspace/writing-workspace-page.tsx frontend/src/pages/writing-workspace/writing-workspace-page.test.tsx
git commit -m "fix(frontend): constrain manuscript editor scrolling"
```

