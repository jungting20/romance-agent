# 집필 에디터 새로고침 저장 복원 Implementation Plan

> **For agentic workers:** 이 티켓의 필수 스킬은 프로젝트의 `feature-development`다. 티켓 prompt에 따라 brainstorming과 writing-plans를 다시 수행하지 말고, 프로젝트가 요구하는 frontend 구현·review·Playwright gate를 따른다. 단계는 checkbox (`- [ ]`)로 추적한다.

> 버그 보고서: [집필 에디터 자동 저장 탐색 보고서](../../bug-reports/2026-07-21-1606-writing-editor-autosave.html#bug-001)

**Goal:** 개발 모드 MSW가 성공적으로 저장한 원고와 revision을 같은 탭의 전체 페이지 reload 뒤에도 복원한다.

**Architecture:** 개발 브라우저 MSW에만 연결하는 versioned `sessionStorage` adapter가 저장된 manuscript snapshot을 읽고 쓴다. mock workspace 모듈은 검증된 snapshot을 현재 seed workspace에 hydrate하며, 성공한 manuscript revision 교체 뒤에만 adapter를 호출한다. React, TanStack Query, Manuscript 도메인과 API 계약은 바꾸지 않는다.

**Tech Stack:** React 19, TypeScript 7, TanStack Query v5, MSW 2, Vitest 4, Playwright 1.61

## Global Constraints

- production 애플리케이션 상태는 계속 TanStack Query와 API가 소유한다.
- `sessionStorage` 접근은 `enableMocking()`의 development/MSW 활성 경계 밖으로 나오지 않는다.
- 새 browser context는 seed 원고와 revision 1에서 시작한다.
- 실패한 PUT과 `409 MANUSCRIPT_REVISION_CONFLICT`는 persisted snapshot을 변경하지 않는다.
- ticket-worker #1의 집필 에디터 스크롤 경계는 수정하지 않는다.
- OpenAPI, `docs/domains/manuscript.md`, backend, Story Bible 편집 동작은 변경하지 않는다.
- 새 dependency를 추가하지 않는다.

---

### Task 1: manuscript session snapshot의 직렬화 경계를 만든다

**Files:**
- Create: `frontend/src/mocks/data/manuscript-session-store.ts`
- Create: `frontend/src/mocks/data/manuscript-session-store.test.ts`

**Interfaces:**
- Consumes: `ApiManuscript`와 `ProjectWorkspaceResponse`의 manuscript/revision/project activity 필드
- Produces: `loadManuscriptSession(storage: Storage): PersistedManuscriptSession | undefined`, `saveManuscriptSession(storage: Storage, session: PersistedManuscriptSession): void`, `clearManuscriptSession(storage: Storage): void`

- [ ] **Step 1: 저장 형식과 실패 테스트를 작성한다**

다음처럼 schema version과 프로젝트별 manuscript snapshot을 저장한다. `entries`는 전체 workspace나 Story Bible을 복제하지 않는다.

```ts
export const MANUSCRIPT_SESSION_STORAGE_KEY = "romance-agent:msw:manuscripts:v1";

export interface PersistedManuscriptEntry {
  projectId: string;
  manuscript: ApiManuscript;
  manuscriptRevision: number;
  projectUpdatedAt: string;
}

export interface PersistedManuscriptSession {
  schemaVersion: 1;
  entries: PersistedManuscriptEntry[];
}
```

테스트는 정상 round-trip, 빈 본문, 여러 줄의 긴 본문, malformed JSON, `schemaVersion: 2`, 0/소수 revision, manuscript-project ID 불일치를 각각 검증한다. 잘못된 값은 throw하지 않고 key를 제거한 뒤 `undefined`를 반환해야 한다.

- [ ] **Step 2: focused test가 구현 부재로 실패하는지 확인한다**

Run from `frontend/`:

```sh
mise exec -- pnpm test -- src/mocks/data/manuscript-session-store.test.ts
```

Expected: `manuscript-session-store` module을 찾지 못해 실패한다.

- [ ] **Step 3: 최소 parser와 storage adapter를 구현한다**

JSON parse 뒤 `schemaVersion === 1`, `entries` 배열, 양의 정수 revision, 비어 있지 않은 IDs, manuscript의 `projectId` 일치, 활성 장면 존재, 모든 scene의 문자열 content를 명시적으로 검사한다. 반환 전후에는 `structuredClone`을 사용하고 원고 본문을 로그하지 않는다.

```ts
export function loadManuscriptSession(storage: Storage): PersistedManuscriptSession | undefined {
  const raw = storage.getItem(MANUSCRIPT_SESSION_STORAGE_KEY);
  if (raw === null) return undefined;
  try {
    const candidate: unknown = JSON.parse(raw);
    if (!isPersistedManuscriptSession(candidate)) throw new Error("invalid snapshot");
    return structuredClone(candidate);
  } catch {
    storage.removeItem(MANUSCRIPT_SESSION_STORAGE_KEY);
    return undefined;
  }
}
```

- [ ] **Step 4: focused test를 통과시킨다**

```sh
mise exec -- pnpm test -- src/mocks/data/manuscript-session-store.test.ts
```

Expected: 새 storage adapter 테스트가 모두 통과한다.

- [ ] **Step 5: adapter를 커밋한다**

```sh
git add frontend/src/mocks/data/manuscript-session-store.ts frontend/src/mocks/data/manuscript-session-store.test.ts
git commit -m "test(frontend): define manuscript mock session storage"
```

---

### Task 2: 성공한 mock manuscript 상태만 hydrate하고 persist한다

**Files:**
- Modify: `frontend/src/mocks/data/project-workspaces.ts:135-146`
- Modify: `frontend/src/mocks/data/project-workspaces.ts:339-367`
- Modify: `frontend/src/mocks/project-handlers.test.ts:200-242`
- Modify: `frontend/src/test/setup.ts:20-25`

**Interfaces:**
- Consumes: Task 1의 `PersistedManuscriptSession`
- Produces: `hydrateMockManuscripts(session: PersistedManuscriptSession | undefined): void`, `setMockManuscriptPersistor(persistor: ((session: PersistedManuscriptSession) => void) | undefined): void`

- [ ] **Step 1: reload-equivalent 상태 전이 테스트를 작성한다**

revision 1의 seed를 변경해 `replaceMockWorkspaceAtRevision()`으로 revision 2를 만든 뒤, persistor가 받은 snapshot을 `resetProjectWorkspaceMockData()` 다음 `hydrateMockManuscripts()`에 전달한다. `findMockWorkspace("silver-garden")`가 고유 본문, revision 2, 저장된 `projectUpdatedAt`을 반환해야 한다. 이어 `expectedRevision: 2` 저장이 revision 3으로 성공해야 한다.

실패와 충돌 케이스에서는 persistor call count가 증가하지 않는 테스트도 추가한다.

- [ ] **Step 2: 테스트가 hydrate/persist API 부재로 실패하는지 확인한다**

```sh
mise exec -- pnpm test -- src/mocks/project-handlers.test.ts -t "restores a saved manuscript after mock runtime reload"
```

Expected: 새 export가 없어 실패한다.

- [ ] **Step 3: seed 위에 검증된 manuscript snapshot만 hydrate한다**

`hydrateMockManuscripts()`는 각 entry의 `projectId`로 현재 seed workspace를 찾고 다음 세 필드만 교체한다.

```ts
projectWorkspaces[index] = {
  ...projectWorkspaces[index],
  project: { ...projectWorkspaces[index].project, updatedAt: entry.projectUpdatedAt },
  manuscript: structuredClone(entry.manuscript),
  manuscriptRevision: entry.manuscriptRevision,
};
```

알 수 없는 프로젝트 entry는 무시한다. Story Bible과 concept는 seed 값을 보존한다.

- [ ] **Step 4: revision 교체 성공 뒤에만 persistor를 호출한다**

`replaceMockWorkspaceAtRevision()`의 `replaced` 경로에서 최신 manuscript entries를 만들어 callback을 호출한다. `not-found`와 `revision-conflict` return보다 앞에서는 호출하지 않는다. callback이 storage 예외를 던지더라도 이미 성립한 mock API 저장을 실패로 바꾸지 않도록 callback 경계에서 예외를 잡고 원고 내용 없는 개발 경고만 남긴다.

- [ ] **Step 5: 테스트 teardown에서 persistor를 해제한다**

`resetProjectWorkspaceMockData()`가 seed 메모리를 복구하고 persistor도 `undefined`로 되돌리게 하거나, `src/test/setup.ts`의 `afterEach`에서 명시적으로 해제한다. 다른 handler 테스트에 session state가 새지 않아야 한다.

- [ ] **Step 6: mock 회귀 테스트를 통과시킨다**

```sh
mise exec -- pnpm test -- src/mocks/project-handlers.test.ts src/mocks/story-bible-handlers.test.ts src/mocks/data/manuscript-session-store.test.ts
```

Expected: 기존 원자 저장·동시 충돌·Story Bible 테스트와 새 reload-equivalent 테스트가 모두 통과한다.

- [ ] **Step 7: mock 상태 전이를 커밋한다**

```sh
git add frontend/src/mocks/data/project-workspaces.ts frontend/src/mocks/project-handlers.test.ts frontend/src/test/setup.ts
git commit -m "fix(frontend): persist mock manuscript revisions"
```

---

### Task 3: 개발 MSW bootstrap에 같은 탭 session을 연결한다

**Files:**
- Modify: `frontend/src/mocks/enable-mocking.ts:1-9`
- Create: `frontend/src/mocks/enable-mocking.test.ts`

**Interfaces:**
- Consumes: Task 1의 load/save adapter와 Task 2의 hydrate/persistor API
- Produces: development/MSW 활성 시에만 reload-surviving mock manuscript session

- [ ] **Step 1: bootstrap 경계 테스트를 작성한다**

MSW 활성 개발 분기에서 worker 시작 전에 storage snapshot을 hydrate하고 persistor를 연결하는 순서를 검증한다. `VITE_ENABLE_MSW=false` 또는 production 분기는 `sessionStorage`를 읽거나 쓰지 않아야 한다.

- [ ] **Step 2: 현재 bootstrap에서 실패하는지 확인한다**

```sh
mise exec -- pnpm test -- src/mocks/enable-mocking.test.ts
```

Expected: session hydrate/persist 연결이 없어 실패한다.

- [ ] **Step 3: worker 시작 전에 session을 연결한다**

개발/MSW 활성 분기 안에서만 다음 순서를 사용한다.

```ts
const session = loadManuscriptSession(window.sessionStorage);
hydrateMockManuscripts(session);
setMockManuscriptPersistor((next) => saveManuscriptSession(window.sessionStorage, next));
await worker.start({ onUnhandledRequest: "bypass" });
```

storage API 접근 자체가 거부되는 환경도 처리해 seed/메모리 MSW로 계속 시작해야 한다.

- [ ] **Step 4: bootstrap과 mock focused test를 통과시킨다**

```sh
mise exec -- pnpm test -- src/mocks/enable-mocking.test.ts src/mocks/project-handlers.test.ts src/mocks/data/manuscript-session-store.test.ts
```

Expected: 모든 focused test가 통과한다.

- [ ] **Step 5: bootstrap 변경을 커밋한다**

```sh
git add frontend/src/mocks/enable-mocking.ts frontend/src/mocks/enable-mocking.test.ts
git commit -m "fix(frontend): hydrate mock manuscript session"
```

---

### Task 4: 실제 reload 회귀와 전체 검증을 완료한다

**Files:**
- Create: `frontend/writing-workspace-reload.spec.ts`

**Interfaces:**
- Consumes: 완성된 MSW session persistence와 `/projects/silver-garden/write`
- Produces: full reload, 후속 revision, 새 context 격리의 브라우저 증거

- [ ] **Step 1: 프로젝트의 frontend review gate를 완료한다**

affected screen은 `/projects/$projectId/write`, API operation은 `getProjectWorkspace`와 `saveManuscript`다. 승인 OpenAPI 의미 변경이 없음을 reviewer에게 명시한다. accepted finding을 모두 해결하고 필요한 re-review를 마친 뒤 Playwright planner/generator를 호출한다.

- [ ] **Step 2: full reload 브라우저 검증을 추가한다**

새 context에서 `silver-garden-scene-1` 끝에 비밀이 아닌 고유 표식을 입력한다. `편집 중`, `저장 중`, `자동 저장됨`과 manuscript PUT 200을 기다리고 `page.reload()` 뒤 표식이 남아 있는지 검증한다. 한 글자를 더 입력한 후 request의 `expectedRevision`이 2이고 response revision이 3인지 확인한다. 새 browser context는 seed 본문/revision 1이어야 한다.

- [ ] **Step 3: 빈 본문과 긴 본문 reload를 검증한다**

동일 spec에서 빈 문자열과 여러 줄의 긴 고유 원고를 각각 저장하고 reload 뒤 정확히 일치하는지 검증한다. 긴 원고의 document scroll은 ticket-worker #1의 assertion과 중복 등록하지 않는다.

- [ ] **Step 4: 프론트엔드 전체 검증을 실행한다**

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: 두 명령 모두 종료 코드 0. `check`는 format, lint, typecheck, 전체 Vitest를 모두 통과한다.

- [ ] **Step 5: 범위와 계약을 대조한다**

`git diff -- frontend`에서 mock session adapter, mock state 연결, 승인된 test 외 변경이 없는지 확인한다. `docs/domains/manuscript.md`와 `docs/api/openapi.yaml`은 diff가 없어야 하며, ticket-worker #1의 스크롤 구현 파일을 이 티켓에서 수정하지 않는다.

- [ ] **Step 6: 최종 변경을 커밋한다**

```sh
git add frontend/writing-workspace-reload.spec.ts
git commit -m "test(frontend): cover manuscript reload restoration"
```
