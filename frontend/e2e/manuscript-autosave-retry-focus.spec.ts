import { expect, test as base, type BrowserContext, type Page, type Route } from "@playwright/test";

import type {
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
} from "@/app/infrastructure/api/contracts";
import { findMockWorkspace } from "@/mocks/data/project-workspaces";

const BASE_URL = process.env.MANUSCRIPT_AUTOSAVE_RETRY_BASE_URL || "http://127.0.0.1:4173";
const WRITE_PATH = "/projects/silver-garden/write";
const WORKSPACE_PATH = "/api/projects/silver-garden/workspace";
const STORY_BIBLE_PATH = "/api/projects/silver-garden/story-bible";
const MANUSCRIPT_PATH = "/api/manuscripts/silver-garden-manuscript";

type Harness = {
  context: BrowserContext;
  page: Page;
  requests: SaveManuscriptRequest[];
  unexpectedRequests: string[];
};

const test = base.extend<{ harness: Harness }>({
  harness: async ({ browser }, use) => {
    const context = await browser.newContext({
      baseURL: BASE_URL,
      serviceWorkers: "block",
      viewport: { width: 1280, height: 800 },
    });
    const page = await context.newPage();
    const workspace = findMockWorkspace("silver-garden");
    if (!workspace) throw new Error("silver-garden workspace seed is missing");
    const requests: SaveManuscriptRequest[] = [];
    const unexpectedRequests: string[] = [];
    await context.route(/\/api\/(?:projects|manuscripts)\//, (route) =>
      handleApiRoute(route, workspace, requests, unexpectedRequests),
    );

    await use({ context, page, requests, unexpectedRequests });

    expect(unexpectedRequests).toEqual([]);
    await context.close();
  },
});

for (const activation of ["mouse", "keyboard"] as const) {
  test(`successful ${activation} retry restores manuscript focus and selection`, async ({
    harness: { page, requests },
  }) => {
    await page.goto(WRITE_PATH);
    const editor = page.getByRole("textbox", { name: "원고 본문" });
    const value = `${activation} 재시도 포커스 검증 원고`;
    await editor.fill(value);
    await expect(page.getByRole("alert")).toContainText("저장 실패");
    await editor.evaluate((element: HTMLTextAreaElement) => element.setSelectionRange(2, 7));
    const retryButton = page.getByRole("button", { name: "원고 저장 다시 시도" });

    if (activation === "mouse") {
      await retryButton.click();
    } else {
      await page.getByRole("link", { name: "작품 서재로 돌아가기" }).focus();
      await page.keyboard.press("Tab");
      await expect(retryButton).toBeFocused();
      await page.keyboard.press("Enter");
    }

    await expect(page.getByRole("status", { name: "자동 저장됨" })).toBeVisible();
    await expect(editor).toBeFocused();
    await expect(editor).toHaveValue(value);
    expect(
      await editor.evaluate((element: HTMLTextAreaElement) => ({
        start: element.selectionStart,
        end: element.selectionEnd,
        isActive: document.activeElement === element,
      })),
    ).toEqual({ start: 2, end: 7, isActive: true });
    expect(requests).toHaveLength(2);
    expect(requests.map(({ expectedRevision }) => expectedRevision)).toEqual([1, 1]);
    expect(requests.map(({ manuscript }) => manuscript.scenes[0]?.content)).toEqual([value, value]);
  });
}

async function handleApiRoute(
  route: Route,
  workspace: ProjectWorkspaceResponse,
  requests: SaveManuscriptRequest[],
  unexpectedRequests: string[],
): Promise<void> {
  const request = route.request();
  const pathname = new URL(request.url()).pathname;

  if (request.method() === "GET" && pathname === WORKSPACE_PATH) {
    await route.fulfill({ json: structuredClone(workspace) });
    return;
  }

  if (request.method() === "GET" && pathname === STORY_BIBLE_PATH) {
    await route.fulfill({
      json: { storyBible: structuredClone(workspace.storyBible), storyBibleRevision: 1 },
    });
    return;
  }

  if (request.method() === "PUT" && pathname === MANUSCRIPT_PATH) {
    const body = (await request.postDataJSON()) as SaveManuscriptRequest;
    requests.push(structuredClone(body));
    if (requests.length === 1) {
      await route.fulfill({
        status: 500,
        json: {
          code: "INTERNAL_ERROR",
          message: "잠시 후 다시 시도해 주세요.",
          fieldErrors: [],
        },
      });
      return;
    }

    workspace.manuscript = structuredClone(body.manuscript);
    workspace.manuscriptRevision = 2;
    await route.fulfill({
      json: {
        manuscript: structuredClone(workspace.manuscript),
        manuscriptRevision: workspace.manuscriptRevision,
        projectActivity: {
          projectId: workspace.project.id,
          updatedAt: "2026-07-24T06:00:00.000Z",
        },
      },
    });
    return;
  }

  unexpectedRequests.push(`${request.method()} ${pathname}`);
  await route.fulfill({
    status: 404,
    json: { code: "PROJECT_NOT_FOUND", message: "unexpected request", fieldErrors: [] },
  });
}
