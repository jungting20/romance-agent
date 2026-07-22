import { expect, test as base, type BrowserContext, type Page, type Route } from "@playwright/test";

// spec: frontend/test-plans/manuscript-scene-title-edit-e2e.md
// seed: independent two-scene workspace fixture below (frontend/seed.spec.ts is intentionally unused)

const BASE_URL = process.env.MANUSCRIPT_SCENE_TITLE_EDIT_BASE_URL || "http://127.0.0.1:5173";
const WRITE_PATH = "/projects/silver-garden/write";
const WORKSPACE_PATH = "/api/projects/silver-garden/workspace";
const MANUSCRIPT_PATH = "/api/manuscripts/silver-garden-manuscript";
const DIFF_PATH = `${MANUSCRIPT_PATH}/scene-diffs`;
const OPENING_SCENE = `비가 그친 뒤의 온실은 오래된 비밀처럼 고요했다.

서윤은 젖은 돌바닥 위에 멈춰 섰다. 돌아보지 않아도 누가 와 있는지 알 수 있었다. 몇 년이 흘렀는데도 발소리 하나만은 기억 속 그대로였다.

“여긴 여전하네.”

도현의 목소리가 장미 향 사이로 낮게 번졌다. 서윤은 손에 든 편지를 조금 더 세게 쥐었다.`;
const SECOND_SCENE = "두 번째 장면의 본문은 첫 장면과 구별된다.";

type Scene = {
  id: string;
  title: string;
  chapterNumber: number;
  content: string;
  relatedCharacterIds: string[];
  relatedWorldEntryIds: string[];
};

type Manuscript = {
  id: string;
  projectId: string;
  scenes: Scene[];
  activeSceneId: string;
};
type Workspace = {
  project: {
    id: string;
    title: string;
    logline: string;
    tropeId: "reunion";
    updatedAt: string;
  };
  concept: {
    id: string;
    projectId: string;
    tropeId: "reunion";
    logline: string;
    protagonistNames: [string, string];
  };
  storyBible: {
    projectId: string;
    characters: Array<{
      id: string;
      name: string;
      role: "protagonist";
      desire: string;
      hiddenFeeling: string;
    }>;
    worldEntries: Array<{
      id: string;
      kind: "place";
      title: string;
      description: string;
    }>;
  };
  manuscript: Manuscript;
  manuscriptRevision: number;
};
type SaveRequest = { expectedRevision: number; manuscript: Manuscript };
type RecordedPut = SaveRequest & { method: "PUT"; url: string };
type DiffRequest = { sceneId: string; localContent: string };
type RecordedDiff = DiffRequest & { method: "POST"; url: string };
type DiffResponse = {
  sceneId: string;
  serverRevision: number;
  localContent: string;
  serverContent: string;
  serverManuscript: Manuscript;
  rows: unknown[];
};
type PutResponse =
  | { kind: "success"; revision?: number }
  | {
      kind: "error";
      status: 409 | 500;
      code: "MANUSCRIPT_REVISION_CONFLICT" | "INTERNAL_ERROR";
    };
type Server = {
  workspace: Workspace;
  puts: RecordedPut[];
  diffs: RecordedDiff[];
  unexpected: string[];
  pageErrors: string[];
  consoleErrors: string[];
  getCount: number;
  respondToPut: (request: RecordedPut, index: number) => PutResponse | Promise<PutResponse>;
  respondToDiff: (request: RecordedDiff, index: number) => DiffResponse;
  waitForPut: (index: number) => Promise<RecordedPut>;
  waitForDiff: (index: number) => Promise<RecordedDiff>;
  waitForGet: (index: number) => Promise<void>;
};
type Harness = { context: BrowserContext; page: Page; server: Server };

const test = base.extend<{ harness: Harness }>({
  harness: async ({ browser }, use) => {
    const context = await browser.newContext({
      baseURL: BASE_URL,
      serviceWorkers: "block",
      viewport: { width: 1024, height: 900 },
    });
    const page = await context.newPage();
    const server = createServer();
    page.on("pageerror", (error) => server.pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") server.consoleErrors.push(message.text());
    });
    await context.route(/\/api\/(?:projects|manuscripts)\//, (route) => handleRoute(route, server));

    await use({ context, page, server });

    expect(server.unexpected).toEqual([]);
    expect(server.pageErrors).toEqual([]);
    expect(
      server.consoleErrors.filter(
        (message) =>
          !message.startsWith("Failed to load resource: the server responded with a status of"),
      ),
    ).toEqual([]);
    await context.close();
  },
});

function initialWorkspace(): Workspace {
  return {
    project: {
      id: "silver-garden",
      title: "은빛 정원의 약속",
      logline: "오해로 헤어진 두 사람이 오래된 온실에서 다시 만난다.",
      tropeId: "reunion",
      updatedAt: "2026-07-13T05:00:00.000Z",
    },
    concept: {
      id: "silver-garden-concept",
      projectId: "silver-garden",
      tropeId: "reunion",
      logline: "오해로 헤어진 두 사람이 오래된 온실에서 다시 만난다.",
      protagonistNames: ["서윤", "도현"],
    },
    storyBible: {
      projectId: "silver-garden",
      characters: [
        {
          id: "character-1",
          name: "서윤",
          role: "protagonist",
          desire: "선택을 지킨다.",
          hiddenFeeling: "진심을 확인하고 싶다.",
        },
        {
          id: "character-2",
          name: "도현",
          role: "protagonist",
          desire: "신뢰받고 싶다.",
          hiddenFeeling: "놓치고 싶지 않다.",
        },
      ],
      worldEntries: [
        {
          id: "world-1",
          kind: "place",
          title: "비가 그친 온실",
          description: "두 사람이 다시 만나는 곳",
        },
      ],
    },
    manuscript: {
      id: "silver-garden-manuscript",
      projectId: "silver-garden",
      activeSceneId: "silver-garden-scene-1",
      scenes: [
        {
          id: "silver-garden-scene-1",
          title: "비가 그친 뒤의 정원",
          chapterNumber: 1,
          content: OPENING_SCENE,
          relatedCharacterIds: ["character-1", "character-2"],
          relatedWorldEntryIds: ["world-1"],
        },
        {
          id: "silver-garden-scene-2",
          title: "두 번째 장면",
          chapterNumber: 2,
          content: SECOND_SCENE,
          relatedCharacterIds: [],
          relatedWorldEntryIds: [],
        },
      ],
    },
    manuscriptRevision: 1,
  };
}

function createServer(): Server {
  const putWaiters = new Map<number, (request: RecordedPut) => void>();
  const diffWaiters = new Map<number, (request: RecordedDiff) => void>();
  const getWaiters = new Map<number, () => void>();
  const server: Server = {
    workspace: structuredClone(initialWorkspace()),
    puts: [],
    diffs: [],
    unexpected: [],
    pageErrors: [],
    consoleErrors: [],
    getCount: 0,
    respondToPut: () => ({ kind: "success" }),
    respondToDiff: (request) => ({
      sceneId: request.sceneId,
      serverRevision: server.workspace.manuscriptRevision,
      localContent: request.localContent,
      serverContent: scene(server.workspace.manuscript, request.sceneId).content,
      serverManuscript: structuredClone(server.workspace.manuscript),
      rows: [],
    }),
    waitForPut: (index) =>
      server.puts[index]
        ? Promise.resolve(server.puts[index]!)
        : new Promise((resolve) => putWaiters.set(index, resolve)),
    waitForDiff: (index) =>
      server.diffs[index]
        ? Promise.resolve(server.diffs[index]!)
        : new Promise((resolve) => diffWaiters.set(index, resolve)),
    waitForGet: (index) =>
      server.getCount > index
        ? Promise.resolve()
        : new Promise((resolve) => getWaiters.set(index, resolve)),
  };
  Object.defineProperties(server, {
    _putWaiters: { value: putWaiters },
    _diffWaiters: { value: diffWaiters },
    _getWaiters: { value: getWaiters },
  });
  return server;
}

function privateWaiters<T>(
  server: Server,
  key: "_putWaiters" | "_diffWaiters" | "_getWaiters",
): Map<number, T> {
  return (server as Server & Record<typeof key, Map<number, T>>)[key];
}

async function handleRoute(route: Route, server: Server): Promise<void> {
  const request = route.request();
  const pathname = new URL(request.url()).pathname;
  if (request.method() === "GET" && pathname === WORKSPACE_PATH) {
    const index = server.getCount++;
    privateWaiters<() => void>(server, "_getWaiters").get(index)?.();
    privateWaiters<() => void>(server, "_getWaiters").delete(index);
    await route.fulfill({ json: structuredClone(server.workspace) });
    return;
  }
  if (request.method() === "GET" && pathname === "/api/projects/silver-garden/story-bible") {
    await route.fulfill({
      json: {
        storyBible: structuredClone(server.workspace.storyBible),
        storyBibleRevision: 1,
      },
    });
    return;
  }
  if (request.method() === "PUT" && pathname === MANUSCRIPT_PATH) {
    const body = (await request.postDataJSON()) as SaveRequest;
    const recorded: RecordedPut = {
      method: "PUT",
      url: request.url(),
      expectedRevision: body.expectedRevision,
      manuscript: structuredClone(body.manuscript),
    };
    const index = server.puts.push(recorded) - 1;
    privateWaiters<(request: RecordedPut) => void>(server, "_putWaiters").get(index)?.(recorded);
    privateWaiters<(request: RecordedPut) => void>(server, "_putWaiters").delete(index);
    const response = await server.respondToPut(recorded, index);
    if (response.kind === "error") {
      await route.fulfill({
        status: response.status,
        json: {
          code: response.code,
          message: "저장 요청 실패",
          fieldErrors: [],
        },
      });
      return;
    }
    server.workspace.manuscript = structuredClone(recorded.manuscript);
    server.workspace.manuscriptRevision =
      response.revision ?? server.workspace.manuscriptRevision + 1;
    await route.fulfill({
      json: {
        manuscript: structuredClone(server.workspace.manuscript),
        manuscriptRevision: server.workspace.manuscriptRevision,
        projectActivity: {
          projectId: "silver-garden",
          updatedAt: "2026-07-22T01:00:00.000Z",
        },
      },
    });
    return;
  }
  if (request.method() === "POST" && pathname === DIFF_PATH) {
    const body = (await request.postDataJSON()) as DiffRequest;
    const recorded: RecordedDiff = {
      method: "POST",
      url: request.url(),
      sceneId: body.sceneId,
      localContent: body.localContent,
    };
    const index = server.diffs.push(recorded) - 1;
    privateWaiters<(request: RecordedDiff) => void>(server, "_diffWaiters").get(index)?.(recorded);
    privateWaiters<(request: RecordedDiff) => void>(server, "_diffWaiters").delete(index);
    const response = server.respondToDiff(recorded, index);
    server.workspace.manuscript = structuredClone(response.serverManuscript);
    server.workspace.manuscriptRevision = response.serverRevision;
    await route.fulfill({ json: response });
    return;
  }
  server.unexpected.push(`${request.method()} ${pathname}`);
  await route.fulfill({
    status: 404,
    json: {
      code: "PROJECT_NOT_FOUND",
      message: "unexpected request",
      fieldErrors: [],
    },
  });
}

function scene(manuscript: Manuscript, id: string): Scene {
  const found = manuscript.scenes.find((candidate) => candidate.id === id);
  expect(found).toBeDefined();
  return found!;
}

async function openWorkspace(page: Page, inlineTree = true): Promise<void> {
  await page.goto(WRITE_PATH);
  await expect(page.getByRole("textbox", { name: "원고 본문" })).toHaveValue(OPENING_SCENE);
  await expect(page.getByRole("heading", { name: "비가 그친 뒤의 정원" })).toBeVisible();
  if (inlineTree)
    await expect(page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toHaveAttribute(
      "aria-current",
      "true",
    );
  await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
}

async function editTitle(page: Page, value: string): Promise<void> {
  await page.getByRole("button", { name: "장면 제목 수정" }).click();
  await page.getByRole("textbox", { name: "장면 제목" }).fill(value);
}

async function expectSurfaces(
  page: Page,
  title: string,
  chapter = 1,
  inlineTree = true,
): Promise<void> {
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText(`${chapter}장 · ${title}`, { exact: true })).toBeVisible();
  if (inlineTree)
    await expect(page.getByRole("button", { name: `${chapter}장 ${title}` })).toHaveAttribute(
      "aria-current",
      "true",
    );
}

function serverLatest(
  local: Workspace,
  title = "서버 최신 제목",
  content = "서버 최신 본문",
): Manuscript {
  return {
    ...structuredClone(local.manuscript),
    scenes: local.manuscript.scenes.map((item) =>
      item.id === "silver-garden-scene-1" ? { ...item, title, content } : item,
    ),
  };
}

test.describe("핵심 인라인 편집과 접근성", () => {
  test("Enter 확정은 세 표면을 동기화하고 전체 원고를 저장·재접속 복원한다", async ({
    harness: { context, page, server },
  }) => {
    // 1. route로 이동해 본문, 세 제목 표면, active 항목과 자동 저장 상태를 확인한다.
    await openWorkspace(page);

    // 2. 제목 편집을 열면 입력에 focus되고 기존 제목 전체가 선택된다.
    await page.getByRole("button", { name: "장면 제목 수정" }).click();
    const input = page.getByRole("textbox", { name: "장면 제목" });
    await expect(input).toBeFocused();
    await expect(input).toHaveJSProperty("selectionStart", 0);
    await expect(input).toHaveJSProperty("selectionEnd", "비가 그친 뒤의 정원".length);

    // 3. 공백이 있는 제목을 Enter로 확정하면 trim된 제목과 안내, focus가 동기화된다.
    await input.fill("  남겨진 편지  ");
    await input.press("Enter");
    await expect(
      page.locator('span[role="status"]').filter({
        hasText: "장면 제목을 저장할 준비가 되었어요.",
      }),
    ).toBeAttached();
    await expectSurfaces(page, "남겨진 편지");
    await expect(page.getByRole("button", { name: "장면 제목 수정" })).toBeFocused();

    // 4. debounce PUT은 기존 전체 원고 계약으로 정확히 한 번 저장한다.
    const firstPut = await server.waitForPut(0);
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
    expect(server.puts).toHaveLength(1);
    expect(firstPut.expectedRevision).toBe(1);
    expect(firstPut.manuscript).toEqual({
      ...initialWorkspace().manuscript,
      scenes: [
        { ...initialWorkspace().manuscript.scenes[0]!, title: "남겨진 편지" },
        initialWorkspace().manuscript.scenes[1]!,
      ],
    });

    // 5. reload와 같은 context의 새 page 재접속 모두 revision 2 원고를 복원한다.
    const reloadGet = server.waitForGet(1);
    await page.reload();
    await reloadGet;
    await expectSurfaces(page, "남겨진 편지");
    const reconnect = await context.newPage();
    reconnect.on("pageerror", (error) => server.pageErrors.push(error.message));
    await reconnect.goto(WRITE_PATH);
    await expectSurfaces(reconnect, "남겨진 편지");
    await expect(reconnect.getByRole("textbox", { name: "원고 본문" })).toHaveValue(OPENING_SCENE);
    await reconnect.close();
  });

  test("Escape는 초안을 취소하고 수정 버튼으로 focus를 복원한다", async ({
    harness: { page, server },
  }) => {
    await openWorkspace(page);
    // 1. 제목 편집을 열고 미확정 초안을 입력한다.
    await editTitle(page, "저장하면 안 되는 제목");
    // 2. Escape로 취소하면 기존 표면과 focus, 취소 안내가 복원된다.
    await page.getByRole("textbox", { name: "장면 제목" }).press("Escape");
    await expect(
      page.locator('span[role="status"]').filter({
        hasText: "장면 제목 수정을 취소했어요.",
      }),
    ).toBeAttached();
    await expect(page.getByRole("textbox", { name: "장면 제목" })).toHaveCount(0);
    await expectSurfaces(page, "비가 그친 뒤의 정원");
    await expect(page.getByRole("button", { name: "장면 제목 수정" })).toBeFocused();
    // 3. debounce 경과 뒤에도 취소 초안 PUT은 없다.
    await page.waitForTimeout(900);
    expect(server.puts).toEqual([]);
  });

  test("공백 Enter는 연결된 필드 오류를 유지하고 저장하지 않는다", async ({
    harness: { page, server },
  }) => {
    await openWorkspace(page);
    // 1. 공백만 Enter하면 입력 focus와 연결된 exact 오류를 유지한다.
    await editTitle(page, "   ");
    const input = page.getByRole("textbox", { name: "장면 제목" });
    await input.press("Enter");
    await expect(input).toBeFocused();
    await expect(input).toHaveAttribute("aria-invalid", "true");
    const errorId = await input.getAttribute("aria-describedby");
    expect(errorId).toBeTruthy();
    await expect(page.locator(`#${errorId!}`)).toHaveText("장면 제목을 입력해 주세요.");
    await expect(page.getByRole("alert")).toHaveText("장면 제목을 입력해 주세요.");
    // 2. debounce 경과 뒤에도 committed 표면과 요청은 바뀌지 않는다.
    await page.waitForTimeout(900);
    expect(server.puts).toEqual([]);
    await expect(page.getByText("1장 · 비가 그친 뒤의 정원", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    // 3. 한 글자를 입력하면 오류는 해소되지만 명시 확정 전 표면은 그대로다.
    await input.fill("제");
    await expect(input).not.toHaveAttribute("aria-invalid", "true");
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.getByText("1장 · 비가 그친 뒤의 정원", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });
});

test.describe("저장 실패와 재시도", () => {
  test("첫 저장 실패 뒤 제목을 유지하고 같은 최신 원고로 재시도한다", async ({
    harness: { page, server },
  }) => {
    server.respondToPut = (_request, index) =>
      index === 0
        ? { kind: "error", status: 500, code: "INTERNAL_ERROR" }
        : { kind: "success", revision: 2 };
    await openWorkspace(page);
    // 1. 제목을 확정해 첫 500 뒤 alert와 로컬 제목 전체를 확인한다.
    await editTitle(page, "실패해도 남는 제목");
    await page.getByRole("textbox", { name: "장면 제목" }).press("Enter");
    const first = await server.waitForPut(0);
    await expect(page.getByRole("alert")).toContainText("저장 실패");
    await expectSurfaces(page, "실패해도 남는 제목");
    // 2. 다시 시도는 revision 1의 같은 최신 전체 원고를 저장한다.
    const secondPromise = server.waitForPut(1);
    await page.getByRole("button", { name: "원고 저장 다시 시도" }).click();
    const second = await secondPromise;
    expect(first.expectedRevision).toBe(1);
    expect(second).toEqual({
      ...first,
      manuscript: structuredClone(first.manuscript),
    });
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
    // 3. reload 뒤 revision 2의 로컬 제목이며 conflict dialog는 없다.
    await page.reload();
    await expectSurfaces(page, "실패해도 남는 제목");
    await expect(page.getByRole("dialog", { name: "원고 저장 충돌 해결" })).toHaveCount(0);
  });
});

test.describe("409 충돌 해결", () => {
  test("내 편집본 유지는 로컬 제목을 서버 revision 위에 보존한다", async ({
    harness: { page, server },
  }) => {
    const authoritative = serverLatest(server.workspace);
    server.respondToPut = (_request, index) =>
      index === 0
        ? { kind: "error", status: 409, code: "MANUSCRIPT_REVISION_CONFLICT" }
        : { kind: "success", revision: 8 };
    server.respondToDiff = (request) => ({
      sceneId: request.sceneId,
      serverRevision: 7,
      localContent: request.localContent,
      serverContent: "서버 최신 본문",
      serverManuscript: authoritative,
      rows: [],
    });
    await openWorkspace(page);
    // 1. 로컬 제목 확정의 409와 scene-diffs 뒤 dialog 및 배경 잠금을 확인한다.
    await editTitle(page, "내가 유지할 제목");
    await page.getByRole("textbox", { name: "장면 제목" }).press("Enter");
    await server.waitForDiff(0);
    const dialog = page.getByRole("dialog", { name: "원고 저장 충돌 해결" });
    await expect(dialog).toBeVisible();
    await expect(page.locator('button[aria-label="장면 제목 수정"]')).toBeDisabled();
    // 2. 내 편집본 유지는 revision 7 위에 로컬 title/content와 서버의 unrelated 장면을 병합한다.
    const resolutionPromise = server.waitForPut(1);
    await dialog.getByRole("button", { name: "내 편집본 유지" }).click();
    const resolution = await resolutionPromise;
    expect(resolution.expectedRevision).toBe(7);
    expect(scene(resolution.manuscript, "silver-garden-scene-1").title).toBe("내가 유지할 제목");
    expect(scene(resolution.manuscript, "silver-garden-scene-1").content).toBe(OPENING_SCENE);
    expect(scene(resolution.manuscript, "silver-garden-scene-2")).toEqual(
      scene(authoritative, "silver-garden-scene-2"),
    );
    await expect(dialog).toBeHidden();
    await expectSurfaces(page, "내가 유지할 제목");
    await expect(page.getByRole("button", { name: "장면 제목 수정" })).toBeEnabled();
    // 3. reload 뒤 revision 8 결과를 복원한다.
    await page.reload();
    await expectSurfaces(page, "내가 유지할 제목");
  });

  test("서버 최신본 적용은 로컬 제목을 버리고 재저장하지 않는다", async ({
    harness: { page, server },
  }) => {
    const authoritative = serverLatest(server.workspace);
    server.respondToPut = () => ({
      kind: "error",
      status: 409,
      code: "MANUSCRIPT_REVISION_CONFLICT",
    });
    server.respondToDiff = (request) => ({
      sceneId: request.sceneId,
      serverRevision: 7,
      localContent: request.localContent,
      serverContent: "서버 최신 본문",
      serverManuscript: authoritative,
      rows: [],
    });
    await openWorkspace(page);
    // 1. 버릴 로컬 제목을 확정해 409 dialog를 연다.
    await editTitle(page, "버려질 로컬 제목");
    await page.getByRole("textbox", { name: "장면 제목" }).press("Enter");
    const dialog = page.getByRole("dialog", { name: "원고 저장 충돌 해결" });
    await expect(dialog).toBeVisible();
    // 2. 서버 최신본 적용은 authoritative 원고를 채택하고 추가 PUT을 만들지 않는다.
    await dialog.getByRole("button", { name: "서버 최신본 적용" }).click();
    await expect(dialog).toBeHidden();
    await expectSurfaces(page, "서버 최신 제목");
    await expect(page.getByRole("textbox", { name: "원고 본문" })).toHaveValue("서버 최신 본문");
    await expect(page.getByRole("button", { name: "장면 제목 수정" })).toBeEnabled();
    await page.waitForTimeout(900);
    expect(server.puts).toHaveLength(1);
    // 3. reload도 revision 7 서버 원고만 복원한다.
    await page.reload();
    await expectSurfaces(page, "서버 최신 제목");
    expect(server.puts).toHaveLength(1);
  });

  test("이전 저장이 충돌하는 동안 입력 중 제목은 잠기지만 초안은 보존된다", async ({
    harness: { page, server },
  }) => {
    let release!: () => void;
    const barrier = new Promise<void>((resolve) => {
      release = resolve;
    });
    const authoritative = serverLatest(server.workspace, "비가 그친 뒤의 정원", "서버가 바꾼 본문");
    server.respondToPut = async (_request, index) => {
      if (index === 0) {
        await barrier;
        return {
          kind: "error",
          status: 409,
          code: "MANUSCRIPT_REVISION_CONFLICT",
        };
      }
      return { kind: "success", revision: index === 1 ? 8 : 9 };
    };
    server.respondToDiff = (request) => ({
      sceneId: request.sceneId,
      serverRevision: 7,
      localContent: request.localContent,
      serverContent: "서버가 바꾼 본문",
      serverManuscript: authoritative,
      rows: [],
    });
    await openWorkspace(page);
    // 1. 본문 autosave PUT을 시작하고 응답 barrier에서 보류한다.
    const body = page.getByRole("textbox", { name: "원고 본문" });
    await body.fill(`${OPENING_SCENE}\n충돌을 만드는 로컬 문장`);
    const pending = await server.waitForPut(0);
    // 2. PUT 대기 중 제목 편집을 열어 Enter/blur 없는 초안을 입력한다.
    await editTitle(page, "충돌 중 보존할 제목");
    const title = page.locator('input[aria-label="장면 제목"]');
    // 3. 409 해제 뒤 dialog 배경에서 초안 value와 disabled, request 비포함을 확인한다.
    release();
    await server.waitForDiff(0);
    const dialog = page.getByRole("dialog", { name: "원고 저장 충돌 해결" });
    await expect(dialog).toBeVisible();
    await expect(title).toHaveValue("충돌 중 보존할 제목");
    await expect(title).toBeDisabled();
    expect(
      pending.manuscript.scenes.every(({ title: saved }) => saved !== "충돌 중 보존할 제목"),
    ).toBe(true);
    expect(server.diffs[0]).toEqual(
      expect.objectContaining({
        localContent: `${OPENING_SCENE}\n충돌을 만드는 로컬 문장`,
      }),
    );
    // 4. body 충돌을 내 편집본 유지로 해결하면 input 초안만 enabled로 복원된다.
    const resolutionPromise = server.waitForPut(1);
    await dialog.getByRole("button", { name: "내 편집본 유지" }).click();
    await resolutionPromise;
    await expect(title).toBeEnabled();
    await expect(title).toHaveValue("충돌 중 보존할 제목");
    await expect(page.getByText("1장 · 비가 그친 뒤의 정원", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    // 5. 이제 Enter로 명시 확정한 다음 PUT만 보존 제목을 포함한다.
    const titlePutPromise = server.waitForPut(2);
    await title.press("Enter");
    const titlePut = await titlePutPromise;
    expect(scene(titlePut.manuscript, "silver-garden-scene-1").title).toBe("충돌 중 보존할 제목");
    await expectSurfaces(page, "충돌 중 보존할 제목");
    await expect(page.getByRole("button", { name: "장면 제목 수정" })).toBeFocused();
  });
});

test.describe("장면 전환과 반응형 동등성", () => {
  test("장면 전환은 이전 장면의 미확정 제목 초안을 폐기한다", async ({
    harness: { page, server },
  }) => {
    await openWorkspace(page);
    // 1. scene 1 제목에 미확정 초안을 입력한다.
    await editTitle(page, "저장하면 안 되는 제목");
    // 2. scene 2로 전환하면 초안을 폐기하고 selection 저장에도 기존 scene-1 제목만 포함한다.
    const selectSecond = server.waitForPut(0);
    await page.getByRole("button", { name: "2장 두 번째 장면" }).click();
    await expectSurfaces(page, "두 번째 장면", 2);
    await expect(page.getByRole("textbox", { name: "원고 본문" })).toHaveValue(SECOND_SCENE);
    await expect(page.getByRole("textbox", { name: "장면 제목" })).toHaveCount(0);
    const selectionPut = await selectSecond;
    expect(scene(selectionPut.manuscript, "silver-garden-scene-1").title).toBe(
      "비가 그친 뒤의 정원",
    );
    expect(JSON.stringify(selectionPut)).not.toContain("저장하면 안 되는 제목");
    // 3. scene 1로 돌아가도 원래 제목이며 초안은 부활하지 않는다.
    await page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" }).click();
    await expectSurfaces(page, "비가 그친 뒤의 정원");
    await expect(page.getByRole("textbox", { name: "장면 제목" })).toHaveCount(0);
  });

  for (const viewport of [
    { label: "375x812", width: 375, height: 812 },
    { label: "1024x900", width: 1024, height: 900 },
  ]) {
    test(`375px와 1024px에서 같은 accessible 키보드 상호작용을 제공한다 — ${viewport.label}`, async ({
      harness: { page, server },
    }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await openWorkspace(page, viewport.width >= 1024);
      // 1. heading과 수정 버튼이 겹치지 않고, 같은 accessible input이 focus/전체 선택된다.
      const heading = page.getByRole("heading", {
        name: "비가 그친 뒤의 정원",
      });
      const edit = page.getByRole("button", { name: "장면 제목 수정" });
      const [headingBox, editBox] = await Promise.all([heading.boundingBox(), edit.boundingBox()]);
      expect(headingBox).not.toBeNull();
      expect(editBox).not.toBeNull();
      expect(
        headingBox!.x + headingBox!.width <= editBox!.x ||
          editBox!.x + editBox!.width <= headingBox!.x ||
          headingBox!.y + headingBox!.height <= editBox!.y ||
          editBox!.y + editBox!.height <= headingBox!.y,
      ).toBe(true);
      await edit.click();
      const input = page.getByRole("textbox", { name: "장면 제목" });
      await expect(input).toBeFocused();
      await expect(input).toHaveJSProperty("selectionStart", 0);
      await expect(input).toHaveJSProperty("selectionEnd", "비가 그친 뒤의 정원".length);
      // 2. viewport별 제목을 Enter로 확정하고 한 PUT과 focus/세 표면을 확인한다.
      const responsiveTitle = `반응형 제목 ${viewport.width}`;
      await input.fill(responsiveTitle);
      const putPromise = server.waitForPut(0);
      await input.press("Enter");
      const put = await putPromise;
      expect(put.expectedRevision).toBe(1);
      expect(scene(put.manuscript, "silver-garden-scene-1").title).toBe(responsiveTitle);
      await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
      await expect(page.getByRole("button", { name: "장면 제목 수정" })).toBeFocused();
      await expectSurfaces(page, responsiveTitle, 1, viewport.width >= 1024);
      expect(server.puts).toHaveLength(1);
      // 3. desktop inline 또는 mobile 원고 보기 Sheet에서 같은 active SceneTree 제목을 확인한다.
      if (viewport.width < 1024) {
        await page.getByRole("tab", { name: "원고 보기" }).click();
        const sheet = page.getByRole("dialog", { name: "원고 보기" });
        await expect(sheet.getByRole("button", { name: `1장 ${responsiveTitle}` })).toHaveAttribute(
          "aria-current",
          "true",
        );
        await page.keyboard.press("Escape");
        await expect(sheet).toBeHidden();
        await expect(page.getByRole("heading", { name: responsiveTitle })).toBeVisible();
      } else {
        await expect(page.getByRole("button", { name: `1장 ${responsiveTitle}` })).toHaveAttribute(
          "aria-current",
          "true",
        );
      }
    });
  }
});
