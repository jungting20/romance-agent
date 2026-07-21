import { expect, test as base, type BrowserContext, type Page, type Route } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:5174";
const WORKSPACE_PATH = "/api/projects/silver-garden/workspace";
const MANUSCRIPT_PATH = "/api/manuscripts/silver-garden-manuscript";
const WRITE_PATH = "/projects/silver-garden/write";
const LOCAL_SCENE_ID = "silver-garden-scene-e2e-local-scene";
const OPENING_SCENE = `비가 그친 뒤의 온실은 오래된 비밀처럼 고요했다.

서윤은 젖은 돌바닥 위에 멈춰 섰다. 돌아보지 않아도 누가 와 있는지 알 수 있었다. 몇 년이 흘렀는데도 발소리 하나만은 기억 속 그대로였다.

“여긴 여전하네.”

도현의 목소리가 장미 향 사이로 낮게 번졌다. 서윤은 손에 든 편지를 조금 더 세게 쥐었다.`;

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

type WorkspaceFixture = {
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

type SaveManuscriptRequest = {
  expectedRevision: number;
  manuscript: Manuscript;
};

type RecordedRequest = SaveManuscriptRequest & {
  method: "PUT";
  url: string;
};

type PutResponse =
  | { kind: "success"; revision?: number }
  | { kind: "error"; status: 409 | 500; code: "MANUSCRIPT_REVISION_CONFLICT" | "INTERNAL_ERROR" };

type TestServer = {
  workspace: WorkspaceFixture;
  requests: RecordedRequest[];
  unexpectedRequests: string[];
  pageErrors: string[];
  getCount: number;
  respondToPut: (request: RecordedRequest, index: number) => PutResponse;
  respondToGet: (index: number) => WorkspaceFixture;
  waitForPut: (index: number) => Promise<RecordedRequest>;
  waitForGet: (index: number) => Promise<void>;
};

type Harness = {
  context: BrowserContext;
  page: Page;
  server: TestServer;
};

type TestFixtures = { harness: Harness };

const test = base.extend<TestFixtures>({
  harness: async ({ browser }, use) => {
    const context = await browser.newContext({
      baseURL: BASE_URL,
      serviceWorkers: "block",
      viewport: { width: 1280, height: 900 },
    });
    const page = await context.newPage();
    await page.addInitScript(() => {
      Object.defineProperty(globalThis.crypto, "randomUUID", {
        configurable: true,
        value: () => "e2e-local-scene",
      });
    });

    const server = createTestServer();
    page.on("pageerror", (error) => server.pageErrors.push(error.message));
    await page.route(/\/api\/(?:projects|manuscripts)\//, (route) => handleApiRoute(route, server));

    await use({ context, page, server });

    expect(server.unexpectedRequests).toEqual([]);
    expect(server.pageErrors).toEqual([]);
    await context.close();
  },
});

function createInitialWorkspace(): WorkspaceFixture {
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
          id: "silver-garden-character-1",
          name: "서윤",
          role: "protagonist",
          desire: "상대에게 흔들리지 않고 자신의 선택을 지키고 싶다.",
          hiddenFeeling: "여전히 상대의 진심을 확인하고 싶다.",
        },
        {
          id: "silver-garden-character-2",
          name: "도현",
          role: "protagonist",
          desire: "과거의 오해를 풀고 다시 신뢰받고 싶다.",
          hiddenFeeling: "이번에는 먼저 놓치고 싶지 않다.",
        },
      ],
      worldEntries: [
        {
          id: "silver-garden-world-1",
          kind: "place",
          title: "비가 그친 온실",
          description:
            "두 사람이 과거에 마지막으로 만났던 장소. 젖은 흙과 오래된 장미 향이 남아 있다.",
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
          relatedCharacterIds: ["silver-garden-character-1", "silver-garden-character-2"],
          relatedWorldEntryIds: ["silver-garden-world-1"],
        },
      ],
    },
    manuscriptRevision: 1,
  };
}

function createTestServer(): TestServer {
  const putWaiters = new Map<number, (request: RecordedRequest) => void>();
  const getWaiters = new Map<number, () => void>();
  const server: TestServer = {
    workspace: structuredClone(createInitialWorkspace()),
    requests: [],
    unexpectedRequests: [],
    pageErrors: [],
    getCount: 0,
    respondToPut: () => ({ kind: "success" }),
    respondToGet: () => structuredClone(server.workspace),
    waitForPut: (index) => {
      const recorded = server.requests[index];
      if (recorded) return Promise.resolve(recorded);
      return new Promise((resolve) => putWaiters.set(index, resolve));
    },
    waitForGet: (index) => {
      if (server.getCount > index) return Promise.resolve();
      return new Promise((resolve) => getWaiters.set(index, resolve));
    },
  };

  Object.defineProperties(server, {
    _putWaiters: { value: putWaiters },
    _getWaiters: { value: getWaiters },
  });
  return server;
}

async function handleApiRoute(route: Route, server: TestServer): Promise<void> {
  const request = route.request();
  const url = new URL(request.url());

  if (request.method() === "GET" && url.pathname === WORKSPACE_PATH) {
    const index = server.getCount;
    server.getCount += 1;
    getWaiters(server).get(index)?.();
    getWaiters(server).delete(index);
    await route.fulfill({ json: structuredClone(server.respondToGet(index)) });
    return;
  }

  if (request.method() === "GET" && url.pathname === "/api/projects/silver-garden/story-bible") {
    await route.fulfill({
      json: { storyBible: structuredClone(server.workspace.storyBible), storyBibleRevision: 1 },
    });
    return;
  }

  if (request.method() === "PUT" && url.pathname === MANUSCRIPT_PATH) {
    const body = (await request.postDataJSON()) as SaveManuscriptRequest;
    const recorded: RecordedRequest = {
      method: "PUT",
      url: request.url(),
      expectedRevision: body.expectedRevision,
      manuscript: structuredClone(body.manuscript),
    };
    const index = server.requests.push(recorded) - 1;
    putWaiters(server).get(index)?.(recorded);
    putWaiters(server).delete(index);
    const response = server.respondToPut(recorded, index);

    if (response.kind === "error") {
      await route.fulfill({
        status: response.status,
        json: { code: response.code, message: "저장 요청 실패", fieldErrors: [] },
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
          projectId: server.workspace.project.id,
          updatedAt: "2026-07-14T04:00:00.000Z",
        },
      },
    });
    return;
  }

  server.unexpectedRequests.push(`${request.method()} ${url.pathname}`);
  await route.fulfill({
    status: 404,
    json: { code: "PROJECT_NOT_FOUND", message: "unexpected request", fieldErrors: [] },
  });
}

function putWaiters(server: TestServer): Map<number, (request: RecordedRequest) => void> {
  return (server as TestServer & { _putWaiters: Map<number, (request: RecordedRequest) => void> })
    ._putWaiters;
}

function getWaiters(server: TestServer): Map<number, () => void> {
  return (server as TestServer & { _getWaiters: Map<number, () => void> })._getWaiters;
}

function serverOnlyScene(chapterNumber: number, content: string): Scene {
  return {
    id: "server-only-scene",
    title: "서버에서 추가된 장면",
    chapterNumber,
    content,
    relatedCharacterIds: [],
    relatedWorldEntryIds: [],
  };
}

function getScene(manuscript: Manuscript, id: string): Scene {
  const scene = manuscript.scenes.find((candidate) => candidate.id === id);
  expect(scene, `scene ${id} should exist`).toBeDefined();
  return scene!;
}

async function openWorkspace(page: Page, inlineSceneTree = true): Promise<void> {
  await page.goto(WRITE_PATH);
  await expectInitialWorkspace(page, inlineSceneTree);
}

async function expectInitialWorkspace(page: Page, inlineSceneTree: boolean): Promise<void> {
  await expect(page.getByRole("textbox", { name: "원고 본문" })).toHaveValue(OPENING_SCENE);
  if (inlineSceneTree) {
    await expect(page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toHaveAttribute(
      "aria-current",
      "true",
    );
  }
  await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
}

async function addScene(page: Page): Promise<void> {
  await page.getByRole("button", { name: "새 장면 추가" }).click();
  await expect(page.getByRole("button", { name: "2장 제목 없는 장면" })).toHaveAttribute(
    "aria-current",
    "true",
  );
}

async function expectAddedScene(page: Page, content: string): Promise<void> {
  const firstSceneButton = page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" });
  const secondSceneButton = page.getByRole("button", { name: "2장 제목 없는 장면" });
  await expect(firstSceneButton).toBeVisible();
  await expect(firstSceneButton).not.toHaveAttribute("aria-current", "true");
  await expect(secondSceneButton).toHaveCount(1);
  await expect(secondSceneButton).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("heading", { name: "제목 없는 장면" })).toBeVisible();
  await expect(page.getByText("2장 · 제목 없는 장면", { exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "원고 본문" })).toHaveValue(content);
}

test.describe("원고 장면 추가", () => {
  test("새 장면을 즉시 추가하고 편집기 포커스와 live 알림을 제공한다", async ({
    harness: { page, server },
  }) => {
    await openWorkspace(page);
    const putPromise = server.waitForPut(0);

    await addScene(page);
    await expectAddedScene(page, "");
    await expect(page.getByRole("textbox", { name: "원고 본문" })).toBeFocused();
    const liveRegion = page
      .locator('[aria-live="polite"]')
      .filter({ hasText: "2장 장면을 추가했어요" });
    await expect(liveRegion).toHaveCount(1);
    await expect(liveRegion).toContainText("2장 장면을 추가했어요");

    await putPromise;
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
  });

  test("새 장면에 입력한 전체 원고를 자동 저장하고 새로고침 후 복원한다", async ({
    harness: { page, server },
  }) => {
    await openWorkspace(page);
    await addScene(page);
    const putPromise = server.waitForPut(0);
    await page.getByRole("textbox", { name: "원고 본문" }).fill("온실 문이 천천히 열렸다.");

    const firstPut = await putPromise;
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
    expect(firstPut.expectedRevision).toBe(1);
    expect(firstPut.manuscript.scenes).toHaveLength(2);
    expect(firstPut.manuscript.scenes[0]).toEqual(createInitialWorkspace().manuscript.scenes[0]);
    expect(firstPut.manuscript.scenes[1]).toEqual({
      id: LOCAL_SCENE_ID,
      title: "제목 없는 장면",
      chapterNumber: 2,
      content: "온실 문이 천천히 열렸다.",
      relatedCharacterIds: [],
      relatedWorldEntryIds: [],
    });
    expect(firstPut.manuscript.activeSceneId).toBe(LOCAL_SCENE_ID);

    const reloadGet = server.waitForGet(1);
    await page.reload();
    await reloadGet;
    await expectAddedScene(page, "온실 문이 천천히 열렸다.");
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
  });

  test("기존 장면을 다시 선택해도 새 장면과 입력을 잃지 않는다", async ({
    harness: { page, server },
  }) => {
    await openWorkspace(page);
    await addScene(page);
    const initialSave = server.waitForPut(0);
    await page.getByRole("textbox", { name: "원고 본문" }).fill("두 번째 장면의 로컬 문장");
    await initialSave;
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();

    await page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" }).click();
    await expect(page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    await expect(page.getByText("1장 · 비가 그친 뒤의 정원", { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "원고 본문" })).toHaveValue(OPENING_SCENE);
    await expect(page.getByRole("button", { name: "2장 제목 없는 장면" })).toBeVisible();

    const selectionSave = server.waitForPut(1);
    await page.getByRole("button", { name: "2장 제목 없는 장면" }).click();
    await expectAddedScene(page, "두 번째 장면의 로컬 문장");
    const secondPut = await selectionSave;
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
    expect(secondPut.manuscript.scenes).toHaveLength(2);
    expect(secondPut.manuscript.activeSceneId).toBe(LOCAL_SCENE_ID);

    const reloadGet = server.waitForGet(1);
    await page.reload();
    await reloadGet;
    await expectAddedScene(page, "두 번째 장면의 로컬 문장");
  });

  test("모바일 원고 Sheet에서 추가 후 Sheet를 닫고 편집기로 이동한다", async ({
    harness: { page },
  }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await openWorkspace(page, false);
    await page.getByRole("tab", { name: "원고 보기" }).click();
    const dialog = page.getByRole("dialog", { name: "원고 보기" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toHaveAttribute(
      "aria-current",
      "true",
    );

    await dialog.getByRole("button", { name: "새 장면 추가" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("textbox", { name: "원고 본문" })).toBeFocused();

    await page.getByRole("tab", { name: "원고 보기" }).click();
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "2장 제목 없는 장면" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("일반 저장 실패와 재시도 중 로컬 새 장면을 보존한다", async ({
    harness: { page, server },
  }) => {
    server.respondToPut = (_request, index) =>
      index === 0 ? { kind: "error", status: 500, code: "INTERNAL_ERROR" } : { kind: "success" };
    await openWorkspace(page);
    await addScene(page);
    const failedPut = server.waitForPut(0);
    await page.getByRole("textbox", { name: "원고 본문" }).fill("실패 뒤에도 남을 장면");
    await failedPut;

    const alert = page.getByRole("alert");
    await expect(alert).toContainText("저장 실패");
    const retryButton = page.getByRole("button", { name: "원고 저장 다시 시도" });
    await expect(retryButton).toBeVisible();
    await expectAddedScene(page, "실패 뒤에도 남을 장면");
    await expect(page.getByRole("button", { name: "새 장면 추가" })).toBeEnabled();

    const retryPutPromise = server.waitForPut(1);
    await retryButton.click();
    const retryPut = await retryPutPromise;
    expect(retryPut.expectedRevision).toBe(1);
    expect(retryPut.manuscript.scenes).toHaveLength(2);
    expect(getScene(retryPut.manuscript, LOCAL_SCENE_ID).content).toBe("실패 뒤에도 남을 장면");
    expect(retryPut.manuscript.activeSceneId).toBe(LOCAL_SCENE_ID);
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();

    const reloadGet = server.waitForGet(1);
    await page.reload();
    await reloadGet;
    await expectAddedScene(page, "실패 뒤에도 남을 장면");
  });

  test("안전한 구조 병합으로 서버 최신 변경과 로컬 새 장면을 모두 유지한다", async ({
    harness: { page, server },
  }) => {
    const initialScene = structuredClone(server.workspace.manuscript.scenes[0]);
    const latestWorkspace = structuredClone(server.workspace);
    latestWorkspace.manuscriptRevision = 7;
    latestWorkspace.manuscript.scenes = [
      { ...initialScene, content: "서버 최신 본문" },
      serverOnlyScene(3, "보존해야 하는 서버 변경"),
    ];
    latestWorkspace.manuscript.activeSceneId = "server-only-scene";
    let conflictReturned = false;
    server.respondToGet = (index) =>
      structuredClone(index === 1 && conflictReturned ? latestWorkspace : server.workspace);
    server.respondToPut = (_request, index) => {
      if (index === 0) {
        conflictReturned = true;
        return { kind: "error", status: 409, code: "MANUSCRIPT_REVISION_CONFLICT" };
      }
      return { kind: "success", revision: 8 };
    };

    await openWorkspace(page);
    await addScene(page);
    const conflictPut = server.waitForPut(0);
    await page.getByRole("textbox", { name: "원고 본문" }).fill("병합해 지킬 로컬 새 장면");
    await conflictPut;
    const dialog = page.getByRole("dialog", { name: "원고 저장 충돌 해결" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("서버 최신 원고에 아직 없는 새 장면이 있어요.");
    await expect(dialog.getByRole("button", { name: "내 새 장면 유지" })).toBeEnabled();
    await expect(dialog.getByRole("button", { name: "서버 최신본 적용" })).toBeEnabled();
    await expect(dialog.getByRole("table")).toHaveCount(0);
    await expect(page.locator('button[aria-label="새 장면 추가"]')).toBeDisabled();

    const resolutionPutPromise = server.waitForPut(1);
    await dialog.getByRole("button", { name: "내 새 장면 유지" }).click();
    const resolutionPut = await resolutionPutPromise;
    expect(resolutionPut.expectedRevision).toBe(7);
    expect(resolutionPut.manuscript.scenes.map(({ id }) => id)).toEqual([
      "silver-garden-scene-1",
      "server-only-scene",
      LOCAL_SCENE_ID,
    ]);
    expect(getScene(resolutionPut.manuscript, "silver-garden-scene-1").content).toBe(
      "서버 최신 본문",
    );
    expect(getScene(resolutionPut.manuscript, "server-only-scene").content).toBe(
      "보존해야 하는 서버 변경",
    );
    expect(getScene(resolutionPut.manuscript, LOCAL_SCENE_ID).content).toBe(
      "병합해 지킬 로컬 새 장면",
    );
    expect(resolutionPut.manuscript.activeSceneId).toBe(LOCAL_SCENE_ID);
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
    await expectAddedScene(page, "병합해 지킬 로컬 새 장면");

    const reloadGet = server.waitForGet(2);
    await page.reload();
    await reloadGet;
    await expect(page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toBeVisible();
    await expect(page.getByRole("button", { name: "3장 서버에서 추가된 장면" })).toBeVisible();
    await expectAddedScene(page, "병합해 지킬 로컬 새 장면");
    expect(server.workspace.manuscript.scenes.map(({ id }) => id)).toEqual([
      "silver-garden-scene-1",
      "server-only-scene",
      LOCAL_SCENE_ID,
    ]);
  });

  test("서버 최신본 적용으로 로컬 전용 장면과 미저장 내용을 버린다", async ({
    harness: { page, server },
  }) => {
    const latestWorkspace = structuredClone(server.workspace);
    latestWorkspace.manuscriptRevision = 7;
    latestWorkspace.manuscript.scenes = [
      structuredClone(server.workspace.manuscript.scenes[0]),
      serverOnlyScene(2, "서버가 확정한 장면"),
    ];
    latestWorkspace.manuscript.activeSceneId = "server-only-scene";
    let conflictReturned = false;
    server.respondToGet = () =>
      structuredClone(conflictReturned ? latestWorkspace : server.workspace);
    server.respondToPut = () => {
      conflictReturned = true;
      return { kind: "error", status: 409, code: "MANUSCRIPT_REVISION_CONFLICT" };
    };

    await openWorkspace(page);
    await addScene(page);
    const conflictPut = server.waitForPut(0);
    await page.getByRole("textbox", { name: "원고 본문" }).fill("버려질 로컬 전용 본문");
    await conflictPut;
    const dialog = page.getByRole("dialog", { name: "원고 저장 충돌 해결" });
    await expect(dialog.getByRole("button", { name: "내 새 장면 유지" })).toBeEnabled();
    const applyServer = dialog.getByRole("button", { name: "서버 최신본 적용" });
    await expect(applyServer).toBeEnabled();

    await applyServer.click();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("button", { name: "2장 서버에서 추가된 장면" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    await expect(page.getByText("2장 · 서버에서 추가된 장면", { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "원고 본문" })).toHaveValue(
      "서버가 확정한 장면",
    );
    await expect(page.getByRole("button", { name: "2장 제목 없는 장면" })).toHaveCount(0);
    await expect(page.getByText("버려질 로컬 전용 본문", { exact: true })).toHaveCount(0);
    expect(server.requests).toHaveLength(1);

    const reloadGet = server.waitForGet(2);
    await page.reload();
    await reloadGet;
    await expect(page.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toBeVisible();
    await expect(page.getByRole("button", { name: "2장 서버에서 추가된 장면" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    await expect(page.getByRole("button", { name: "2장 제목 없는 장면" })).toHaveCount(0);
    await expect(page.getByRole("textbox", { name: "원고 본문" })).toHaveValue(
      "서버가 확정한 장면",
    );
    expect(server.requests).toHaveLength(1);
  });
});
