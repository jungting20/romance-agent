import { expect, test, type BrowserContext, type Locator, type Request } from "@playwright/test";

// spec: frontend/test-plans/writing-workspace-reload-restoration.md
// seed: No seed file; start each test in a fresh browser context and navigate directly to /projects/silver-garden/write

const writingWorkspaceUrl = "http://127.0.0.1:5174/projects/silver-garden/write";
const workspacePath = "/api/projects/silver-garden/workspace";
const manuscriptPath = "/api/manuscripts/silver-garden-manuscript";

type Workspace = {
  manuscriptRevision: number;
  manuscript: {
    activeSceneId: string;
    scenes: Array<{
      id: string;
      content: string;
    }>;
  };
};

const isWorkspaceGet = (url: string, method: string) =>
  method === "GET" && new URL(url).pathname === workspacePath;

const isManuscriptPut = (url: string, method: string) =>
  method === "PUT" && new URL(url).pathname === manuscriptPath;

const getActiveScene = (workspace: Workspace) => {
  const activeScene = workspace.manuscript.scenes.find(
    (scene) => scene.id === workspace.manuscript.activeSceneId,
  );
  expect(activeScene).toBeDefined();
  return activeScene!;
};

const buildLongFixture = () =>
  [
    "<<<E2E-LONG-BEGIN>>>",
    ...Array.from(
      { length: 120 },
      (_, index) =>
        `단락 ${String(index + 1).padStart(3, "0")}: 비가 그친 정원, 서윤과 도현의 약속 — ASCII[${index}] !?.,:;"'() [] {} /\\ | +=_ * & % $ # @ ~`,
    ),
    "",
    "명시적 빈 줄 뒤의 마지막 한국어 문장.",
    "<<<E2E-LONG-END>>>",
  ].join("\n\n");

const observeAutosaveStatuses = async (status: Locator) => {
  await status.evaluate((element) => {
    const observedStatuses: string[] = [];
    const recordStatus = () => {
      const currentStatus = element.textContent?.trim();
      if (currentStatus && observedStatuses.at(-1) !== currentStatus) {
        observedStatuses.push(currentStatus);
        element.setAttribute("data-e2e-observed-statuses", JSON.stringify(observedStatuses));
      }
    };

    recordStatus();
    new MutationObserver(recordStatus).observe(element, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  });
};

const expectAutosaveStatusSequence = async (status: Locator) => {
  await expect(status).toHaveAttribute(
    "data-e2e-observed-statuses",
    JSON.stringify(["자동 저장됨", "편집 중", "저장 중", "자동 저장됨"]),
  );
};

test.describe("Same-context autosave and full-reload restoration", () => {
  test("Autosave followed by a full reload restores the unique marker and revision 2", async ({
    page,
  }) => {
    const marker = "\n[e2e-reload-marker]";
    const manuscriptPutRequests: Request[] = [];
    page.on("request", (request) => {
      if (isManuscriptPut(request.url(), request.method())) {
        manuscriptPutRequests.push(request);
      }
    });

    // 1. Create a fresh browser context and page, register observers for workspace GETs and manuscript PUTs, and navigate directly to `/projects/silver-garden/write`.
    const initialWorkspaceResponsePromise = page.waitForResponse((response) =>
      isWorkspaceGet(response.url(), response.request().method()),
    );
    await page.goto(writingWorkspaceUrl);
    const initialWorkspaceResponse = await initialWorkspaceResponsePromise;
    const initialWorkspace = (await initialWorkspaceResponse.json()) as Workspace;
    const initialActiveScene = getActiveScene(initialWorkspace);
    const manuscriptTextbox = page.getByRole("textbox", {
      name: "원고 본문",
    });
    const autosaveStatus = page.getByRole("status");

    expect(initialWorkspaceResponse.status()).toBe(200);
    expect(initialWorkspace.manuscriptRevision).toBe(1);
    await expect(manuscriptTextbox).toHaveValue(initialActiveScene.content);
    await expect(autosaveStatus).toContainText("자동 저장됨");

    // 2. Append a deterministic unique marker such as `\n[e2e-reload-marker]` to the existing `원고 본문` value, preserving all seed text.
    const editedContent = initialActiveScene.content + marker;
    const putResponsePromise = page.waitForResponse((response) =>
      isManuscriptPut(response.url(), response.request().method()),
    );
    await observeAutosaveStatuses(autosaveStatus);
    await manuscriptTextbox.fill(editedContent);
    await expect(autosaveStatus).toContainText("편집 중");
    const putResponse = await putResponsePromise;
    const putResponseBody = await putResponse.json();
    await expect(autosaveStatus).toContainText("자동 저장됨");
    await expectAutosaveStatusSequence(autosaveStatus);

    expect(manuscriptPutRequests).toHaveLength(1);
    expect(manuscriptPutRequests[0].postDataJSON()).toMatchObject({
      expectedRevision: 1,
      manuscript: {
        scenes: expect.arrayContaining([
          expect.objectContaining({
            id: initialWorkspace.manuscript.activeSceneId,
            content: editedContent,
          }),
        ]),
      },
    });
    expect(putResponse.status()).toBe(200);
    expect(putResponseBody.manuscriptRevision).toBe(2);

    // 3. Perform a real full-page reload with `page.reload()`, wait for the reloaded workspace GET and the editor to finish loading, then read the textbox value.
    const reloadedWorkspaceResponsePromise = page.waitForResponse((response) =>
      isWorkspaceGet(response.url(), response.request().method()),
    );
    await page.reload();
    const reloadedWorkspaceResponse = await reloadedWorkspaceResponsePromise;
    const reloadedWorkspace = (await reloadedWorkspaceResponse.json()) as Workspace;
    const reloadedActiveScene = getActiveScene(reloadedWorkspace);

    expect(reloadedWorkspace.manuscriptRevision).toBe(2);
    expect(reloadedActiveScene.content).toContain(marker);
    await expect(manuscriptTextbox).toHaveValue(reloadedActiveScene.content);
    await expect(manuscriptTextbox).toHaveValue(editedContent);
  });

  test("The first save after reload sends expectedRevision 2 and returns revision 3", async ({
    page,
  }) => {
    const setupMarker = "\n[e2e-reload-setup-marker]";
    const manuscriptTextbox = page.getByRole("textbox", {
      name: "원고 본문",
    });
    const autosaveStatus = page.getByRole("status");

    // 1. In a fresh browser context, navigate to `/projects/silver-garden/write`, append a unique setup marker, wait for the successful autosave response at revision 2, then perform a real full-page reload and confirm the workspace GET restores that marker with `manuscriptRevision: 2`.
    const initialWorkspaceResponsePromise = page.waitForResponse((response) =>
      isWorkspaceGet(response.url(), response.request().method()),
    );
    await page.goto(writingWorkspaceUrl);
    const initialWorkspaceResponse = await initialWorkspaceResponsePromise;
    const initialWorkspace = (await initialWorkspaceResponse.json()) as Workspace;
    const initialActiveScene = getActiveScene(initialWorkspace);
    expect(initialWorkspace.manuscriptRevision).toBe(1);

    const setupContent = initialActiveScene.content + setupMarker;
    const setupPutResponsePromise = page.waitForResponse((response) =>
      isManuscriptPut(response.url(), response.request().method()),
    );
    await manuscriptTextbox.fill(setupContent);
    const setupPutResponse = await setupPutResponsePromise;
    const setupPutResponseBody = await setupPutResponse.json();
    expect(setupPutResponse.request().postDataJSON()).toMatchObject({
      expectedRevision: 1,
    });
    expect(setupPutResponse.status()).toBe(200);
    expect(setupPutResponseBody.manuscriptRevision).toBe(2);
    await expect(autosaveStatus).toContainText("자동 저장됨");

    const reloadedWorkspaceResponsePromise = page.waitForResponse((response) =>
      isWorkspaceGet(response.url(), response.request().method()),
    );
    await page.reload();
    const reloadedWorkspaceResponse = await reloadedWorkspaceResponsePromise;
    const reloadedWorkspace = (await reloadedWorkspaceResponse.json()) as Workspace;
    const restoredActiveScene = getActiveScene(reloadedWorkspace);
    expect(reloadedWorkspace.manuscriptRevision).toBe(2);
    expect(restoredActiveScene.content).toBe(setupContent);
    await expect(manuscriptTextbox).toHaveValue(restoredActiveScene.content);

    // 2. Append one additional deterministic character to the restored textbox value, register the PUT observer before editing, and wait for the autosave to complete.
    const nextContent = restoredActiveScene.content + "!";
    const nextPutResponsePromise = page.waitForResponse((response) =>
      isManuscriptPut(response.url(), response.request().method()),
    );
    await observeAutosaveStatuses(autosaveStatus);
    await manuscriptTextbox.fill(nextContent);
    await expect(autosaveStatus).toContainText("편집 중");
    const nextPutResponse = await nextPutResponsePromise;
    const nextPutResponseBody = await nextPutResponse.json();
    await expect(autosaveStatus).toContainText("자동 저장됨");
    await expectAutosaveStatusSequence(autosaveStatus);

    expect(nextPutResponse.request().postDataJSON()).toMatchObject({
      expectedRevision: 2,
      manuscript: {
        scenes: expect.arrayContaining([
          expect.objectContaining({
            id: reloadedWorkspace.manuscript.activeSceneId,
            content: nextContent,
          }),
        ]),
      },
    });
    expect(nextPutResponse.status()).toBe(200);
    expect(nextPutResponseBody.manuscriptRevision).toBe(3);
  });

  test("Empty manuscript content survives autosave and full reload exactly", async ({ page }) => {
    const manuscriptTextbox = page.getByRole("textbox", {
      name: "원고 본문",
    });
    const autosaveStatus = page.getByRole("status");

    // 1. In a fresh browser context, navigate to `/projects/silver-garden/write`, register the manuscript PUT observer, and replace the `원고 본문` value with the empty string.
    await page.goto(writingWorkspaceUrl);
    const putResponsePromise = page.waitForResponse((response) =>
      isManuscriptPut(response.url(), response.request().method()),
    );
    await observeAutosaveStatuses(autosaveStatus);
    await manuscriptTextbox.fill("");
    await expect(autosaveStatus).toContainText("편집 중");
    const putResponse = await putResponsePromise;
    const putRequestBody = putResponse.request().postDataJSON();
    const putActiveScene = putRequestBody.manuscript.scenes.find(
      (scene: { id: string }) => scene.id === putRequestBody.manuscript.activeSceneId,
    );
    const putResponseBody = await putResponse.json();
    await expect(autosaveStatus).toContainText("자동 저장됨");
    await expectAutosaveStatusSequence(autosaveStatus);

    expect(putRequestBody.expectedRevision).toBe(1);
    expect(putActiveScene.content).toBe("");
    expect(putResponse.status()).toBe(200);
    expect(putResponseBody.manuscriptRevision).toBe(2);

    // 2. Perform a real full-page reload, wait for the workspace GET and editor load, and assert the textbox value with an exact empty-string assertion.
    const reloadedWorkspaceResponsePromise = page.waitForResponse((response) =>
      isWorkspaceGet(response.url(), response.request().method()),
    );
    await page.reload();
    const reloadedWorkspaceResponse = await reloadedWorkspaceResponsePromise;
    const reloadedWorkspace = (await reloadedWorkspaceResponse.json()) as Workspace;
    const reloadedActiveScene = getActiveScene(reloadedWorkspace);

    expect(reloadedWorkspace.manuscriptRevision).toBe(2);
    expect(reloadedActiveScene.content).toBe("");
    await expect(manuscriptTextbox).toHaveValue("");
  });

  test("Long multiline manuscript content survives autosave and full reload byte-for-string exactly", async ({
    page,
  }) => {
    // 1. In a fresh browser context, navigate to `/projects/silver-garden/write` and build a deterministic long multiline string with several thousand characters, Korean and ASCII text, explicit blank lines, punctuation, and unique beginning/end sentinels; do not perform or assert any scrolling.
    const longFixture = buildLongFixture();
    expect(longFixture.length).toBeGreaterThan(5_000);
    expect(longFixture).toMatch(/^<<<E2E-LONG-BEGIN>>>\n\n[\s\S]*\n\n<<<E2E-LONG-END>>>$/);
    expect(longFixture).toContain("\n\n\n\n명시적 빈 줄");
    await page.goto(writingWorkspaceUrl);
    const manuscriptTextbox = page.getByRole("textbox", {
      name: "원고 본문",
    });
    const autosaveStatus = page.getByRole("status");

    // 2. Register the PUT observer, replace the textbox value with the long multiline fixture, and wait for the autosave to finish.
    const putResponsePromise = page.waitForResponse((response) =>
      isManuscriptPut(response.url(), response.request().method()),
    );
    await observeAutosaveStatuses(autosaveStatus);
    await manuscriptTextbox.fill(longFixture);
    await expect(autosaveStatus).toContainText("편집 중");
    const putResponse = await putResponsePromise;
    const putRequestBody = putResponse.request().postDataJSON();
    const putActiveScene = putRequestBody.manuscript.scenes.find(
      (scene: { id: string }) => scene.id === putRequestBody.manuscript.activeSceneId,
    );
    const putResponseBody = await putResponse.json();
    await expect(autosaveStatus).toContainText("자동 저장됨");
    await expectAutosaveStatusSequence(autosaveStatus);

    expect(putRequestBody.expectedRevision).toBe(1);
    expect(putActiveScene.content).toBe(longFixture);
    expect(putResponse.status()).toBe(200);
    expect(putResponseBody.manuscriptRevision).toBe(2);

    // 3. Perform a real full-page reload, wait for the workspace GET and editor load, and compare both the response active-scene content and textbox value directly with the original fixture.
    const reloadedWorkspaceResponsePromise = page.waitForResponse((response) =>
      isWorkspaceGet(response.url(), response.request().method()),
    );
    await page.reload();
    const reloadedWorkspaceResponse = await reloadedWorkspaceResponsePromise;
    const reloadedWorkspace = (await reloadedWorkspaceResponse.json()) as Workspace;
    const reloadedActiveScene = getActiveScene(reloadedWorkspace);

    expect(reloadedWorkspace.manuscriptRevision).toBe(2);
    expect(reloadedActiveScene.content).toBe(longFixture);
    await expect(manuscriptTextbox).toHaveValue(longFixture);
  });
});

test.describe("Browser-context isolation", () => {
  test("A new browser context starts from the seed manuscript at revision 1", async ({
    browser,
  }) => {
    const contextAMarker = "\n[e2e-context-a-marker]";
    const contextA = await browser.newContext();
    let contextB: BrowserContext | undefined;

    try {
      // 1. Create browser context A, navigate to `/projects/silver-garden/write`, append a unique context-A marker, and wait for its successful autosave response at revision 2.
      const pageA = await contextA.newPage();
      const contextAWorkspaceResponsePromise = pageA.waitForResponse((response) =>
        isWorkspaceGet(response.url(), response.request().method()),
      );
      await pageA.goto(writingWorkspaceUrl);
      const contextAWorkspaceResponse = await contextAWorkspaceResponsePromise;
      const contextAWorkspace = (await contextAWorkspaceResponse.json()) as Workspace;
      const contextAActiveScene = getActiveScene(contextAWorkspace);
      const contextATextbox = pageA.getByRole("textbox", {
        name: "원고 본문",
      });
      const contextAEditedContent = contextAActiveScene.content + contextAMarker;
      const contextAPutResponsePromise = pageA.waitForResponse((response) =>
        isManuscriptPut(response.url(), response.request().method()),
      );
      await contextATextbox.fill(contextAEditedContent);
      const contextAPutResponse = await contextAPutResponsePromise;
      const contextAPutResponseBody = await contextAPutResponse.json();

      expect(contextAPutResponse.request().postDataJSON()).toMatchObject({
        expectedRevision: 1,
      });
      expect(contextAPutResponse.status()).toBe(200);
      expect(contextAPutResponseBody.manuscriptRevision).toBe(2);
      await expect(contextATextbox).toHaveValue(contextAEditedContent);

      // 2. Create a genuinely new browser context B (not merely a new page or tab in context A), register the initial workspace GET observer, and navigate context B directly to `/projects/silver-garden/write`.
      contextB = await browser.newContext();
      const pageB = await contextB.newPage();
      const contextBWorkspaceResponsePromise = pageB.waitForResponse((response) =>
        isWorkspaceGet(response.url(), response.request().method()),
      );
      await pageB.goto(writingWorkspaceUrl);
      const contextBWorkspaceResponse = await contextBWorkspaceResponsePromise;
      const contextBWorkspace = (await contextBWorkspaceResponse.json()) as Workspace;
      const contextBActiveScene = getActiveScene(contextBWorkspace);
      const contextBTextbox = pageB.getByRole("textbox", {
        name: "원고 본문",
      });

      expect(contextBWorkspace.manuscriptRevision).toBe(1);
      expect(contextBActiveScene.content).not.toContain(contextAMarker);
      await expect(contextBTextbox).toHaveValue(contextBActiveScene.content);
      expect(await contextBTextbox.inputValue()).not.toContain(contextAMarker);
    } finally {
      // 3. Close both contexts without adding scroll assertions or exercising any other route.
      await contextB?.close();
      await contextA.close();
    }
  });
});
