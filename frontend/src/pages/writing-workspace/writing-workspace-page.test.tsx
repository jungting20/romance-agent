import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";

import type {
  CompareManuscriptSceneResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
} from "@/app/infrastructure/api/contracts";
import { createAppMemoryRouter } from "@/app/app";
import { findMockWorkspace } from "@/mocks/data/project-workspaces";
import { server } from "@/mocks/server";

afterEach(() => {
  vi.unstubAllGlobals();
});

function setViewportWidth(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => {
    const minimumWidth = Number(query.match(/min-width:\s*(\d+)px/)?.[1] ?? 0);
    return {
      matches: width >= minimumWidth,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } satisfies MediaQueryList;
  });
}

describe("WritingWorkspacePage", () => {
  test("shows a workspace skeleton while the workspace is being fetched", () => {
    server.use(
      http.get("/api/projects/:projectId/workspace", async () => {
        await delay("infinite");
        return HttpResponse.json({});
      }),
    );

    const { container } = renderWorkspace();

    expect(screen.getByRole("status")).toHaveTextContent("작업 공간을 불러오는 중이에요.");
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(3);
  });

  test("retries a transient workspace loading error", async () => {
    let requestCount = 0;
    const workspace = getWorkspace();
    server.use(
      http.get("/api/projects/:projectId/workspace", () => {
        requestCount += 1;
        return requestCount === 1
          ? HttpResponse.json(
              { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
              { status: 500 },
            )
          : HttpResponse.json(workspace);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "작업 공간을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
    );
    await user.click(screen.getByRole("button", { name: "작업 공간 다시 불러오기" }));

    expect(
      await screen.findByRole("heading", { name: workspace.project.title }),
    ).toBeInTheDocument();
    expect(requestCount).toBe(2);
  });

  test("shows a project-not-found view without redirecting", async () => {
    renderWorkspace("missing-project");

    expect(
      await screen.findByRole("heading", { name: "프로젝트를 찾을 수 없어요" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "작품 서재로 돌아가기" })).toBeInTheDocument();
  });

  test("opens the selected contextual tab in a mobile sheet", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    renderWorkspace();

    const charactersTab = await screen.findByRole("tab", { name: "인물 보기" });
    expect(screen.getAllByRole("tab")).toHaveLength(3);

    await user.click(charactersTab);

    const contextSheet = screen.getByRole("dialog", { name: "인물 보기" });
    expect(contextSheet).toHaveTextContent("등장인물");
    expect(contextSheet).toHaveTextContent("서윤");
    expect(charactersTab).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "인물 보기" })).not.toBeInTheDocument();
  });

  test("opens and closes the AI tool as a sheet below the desktop breakpoint", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "AI 도구 열기" }));
    expect(screen.getByRole("dialog", { name: "AI 집필 도구" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "AI 집필 도구" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "원고 본문" })).toBeInTheDocument();
  });

  test("adds a resize handle only for each visible adjacent desktop panel", async () => {
    setViewportWidth(1280);
    const user = userEvent.setup();
    renderWorkspace();

    await screen.findByRole("textbox", { name: "원고 본문" });
    expect(screen.getAllByRole("separator")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));
    expect(screen.queryByRole("dialog", { name: "AI 집필 도구" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("separator")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "AI 도구 닫기" }));
    expect(screen.getAllByRole("separator")).toHaveLength(1);
  });

  test("applies a requested continuation to the manuscript", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole("textbox", { name: "원고 본문" });
    const original = (editor as HTMLTextAreaElement).value;

    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));

    expect(screen.getByRole("heading", { name: "AI 집필 도구" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "문장 다듬기" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "이어 쓰기" }));
    expect(screen.getByText("다음 문단 제안")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "원고에 적용" }));

    expect((editor as HTMLTextAreaElement).value.length).toBeGreaterThan(original.length);
  });

  test("enables sentence refinement only for selected manuscript text", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    const original = editor.value;

    editor.setSelectionRange(0, 8);
    fireEvent.select(editor);
    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));

    const refine = screen.getByRole("button", { name: "문장 다듬기" });
    expect(refine).toBeEnabled();

    await user.click(refine);
    expect(screen.getByText("감정을 보여주는 문장")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "원고에 적용" }));

    expect(editor.value).not.toBe(original);
  });

  test("inserts a continuation at the current cursor, including position zero", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });

    editor.setSelectionRange(0, 0);
    fireEvent.select(editor);
    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));
    await user.click(screen.getByRole("button", { name: "이어 쓰기" }));
    await user.click(screen.getByRole("button", { name: "원고에 적용" }));

    expect(editor.value).toMatch(/^\n\n/);
  });

  test("shows editing and failed save states, then retries without losing the draft", async () => {
    let saveCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        saveCount += 1;
        const body = (await request.json()) as SaveManuscriptRequest;
        if (saveCount === 1) {
          return HttpResponse.json(
            { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
            { status: 500 },
          );
        }

        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        });
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    expect(screen.getByRole("status")).toHaveAccessibleName("자동 저장됨");

    fireEvent.change(editor, { target: { value: "저장에 실패해도 남는 원고" } });
    expect(screen.getByRole("status")).toHaveAccessibleName("편집 중");

    expect(await screen.findByRole("alert")).toHaveTextContent("저장 실패");
    expect(editor.value).toBe("저장에 실패해도 남는 원고");
    await user.click(screen.getByRole("button", { name: "원고 저장 다시 시도" }));

    expect(await screen.findByRole("status")).toHaveTextContent("자동 저장됨");
    expect(editor.value).toBe("저장에 실패해도 남는 원고");
    expect(saveCount).toBe(2);
  });

  test("saves an edit immediately before internal navigation and proceeds only after success", async () => {
    const requests: SaveManuscriptRequest[] = [];
    let releaseSave!: () => void;
    const saveBarrier = new Promise<void>((resolve) => {
      releaseSave = resolve;
    });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        await saveBarrier;
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        });
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });

    fireEvent.change(editor, { target: { value: "탐색 전에 저장할 원고" } });
    await user.click(screen.getByRole("link", { name: "작품 서재로 돌아가기" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(screen.getByRole("heading", { name: getWorkspace().project.title })).toBeInTheDocument();
    expect(requests[0].manuscript.scenes[0].content).toBe("탐색 전에 저장할 원고");

    releaseSave();
    expect(
      await screen.findByRole("heading", { name: "다시, 이야기를 시작해 볼까요?" }),
    ).toBeInTheDocument();
  });

  test("saves a newer edit queued behind an active save before navigating", async () => {
    const requests: SaveManuscriptRequest[] = [];
    let releaseFirstSave!: () => void;
    const firstSaveBarrier = new Promise<void>((resolve) => {
      releaseFirstSave = resolve;
    });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        if (requests.length === 1) {
          await firstSaveBarrier;
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: requests.length + 1,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        });
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });

    fireEvent.change(editor, { target: { value: "첫 저장 원고" } });
    await waitFor(() => expect(requests).toHaveLength(1), { timeout: 2_000 });
    fireEvent.change(editor, { target: { value: "뒤에 대기한 최신 원고" } });
    await user.click(screen.getByRole("link", { name: "작품 서재로 돌아가기" }));

    expect(screen.getByRole("heading", { name: getWorkspace().project.title })).toBeInTheDocument();
    releaseFirstSave();
    expect(
      await screen.findByRole("heading", { name: "다시, 이야기를 시작해 볼까요?" }),
    ).toBeInTheDocument();
    expect(requests).toHaveLength(2);
    expect(requests[1].expectedRevision).toBe(2);
    expect(requests[1].manuscript.scenes[0].content).toBe("뒤에 대기한 최신 원고");
  });

  test("warns before unloading while the manuscript has unsaved work", async () => {
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    fireEvent.change(editor, { target: { value: "닫기 전에 지킬 원고" } });

    const beforeUnload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(beforeUnload);

    expect(beforeUnload.defaultPrevented).toBe(true);
  });

  test("cancels internal navigation when the immediate save fails and exposes retry", async () => {
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    fireEvent.change(editor, { target: { value: "실패해도 지킬 원고" } });

    await user.click(screen.getByRole("link", { name: "작품 서재로 돌아가기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("저장 실패");
    expect(screen.getByRole("button", { name: "원고 저장 다시 시도" })).toBeInTheDocument();
    expect(editor.value).toBe("실패해도 지킬 원고");
    const beforeUnload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(beforeUnload);
    expect(beforeUnload.defaultPrevented).toBe(true);
  });

  test("cancels internal navigation when saving finds a conflict", async () => {
    const workspace = getWorkspace();
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 2,
          localContent: body.localContent,
          serverContent: workspace.manuscript.scenes[0].content,
          serverManuscript: workspace.manuscript,
          rows: [],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    fireEvent.change(editor, { target: { value: "충돌해도 지킬 원고" } });

    await user.click(screen.getByRole("link", { name: "작품 서재로 돌아가기" }));

    expect(await screen.findByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();
    expect(editor.value).toBe("충돌해도 지킬 원고");
    const beforeUnload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(beforeUnload);
    expect(beforeUnload.defaultPrevented).toBe(true);
  });

  test("opens the conflict comparison and Escape closes it without discarding the draft", async () => {
    const workspace = getWorkspace();
    let compareCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        compareCount += 1;
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 2,
          localContent: body.localContent,
          serverContent: "서버 최신 장면",
          serverManuscript: {
            ...workspace.manuscript,
            scenes: workspace.manuscript.scenes.map((scene) =>
              scene.id === body.sceneId ? { ...scene, content: "서버 최신 장면" } : scene,
            ),
          },
          rows: [
            {
              kind: "local-only",
              localLineNumber: 1,
              localText: body.localContent,
              serverLineNumber: null,
              serverText: null,
            },
            {
              kind: "server-only",
              localLineNumber: null,
              localText: null,
              serverLineNumber: 1,
              serverText: "서버 최신 장면",
            },
          ],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" });

    fireEvent.change(editor, { target: { value: "Escape 뒤에도 남는 로컬 장면" } });
    expect(await screen.findByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "내 편집본" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "서버 최신본" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "내 편집본 유지" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toBeEnabled();
    expect(compareCount).toBe(1);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "원고 저장 충돌 해결" })).not.toBeInTheDocument();
    expect(editor.value).toBe("Escape 뒤에도 남는 로컬 장면");
  });

  test("keeps the modal locked during local resolution and safely adopts its successful save", async () => {
    const workspace = getWorkspace();
    let saveCount = 0;
    let releaseResolution!: () => void;
    const resolutionBarrier = new Promise<void>((resolve) => {
      releaseResolution = resolve;
    });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        saveCount += 1;
        const body = (await request.json()) as SaveManuscriptRequest;
        if (saveCount === 1) {
          return HttpResponse.json(
            { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
            { status: 409 },
          );
        }
        await resolutionBarrier;
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 3,
          projectActivity: {
            projectId: workspace.project.id,
            updatedAt: "2026-07-14T06:00:00Z",
          },
        });
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 2,
          localContent: body.localContent,
          serverContent: "서버 최신 장면",
          serverManuscript: {
            ...workspace.manuscript,
            scenes: workspace.manuscript.scenes.map((scene) =>
              scene.id === body.sceneId ? { ...scene, content: "서버 최신 장면" } : scene,
            ),
          },
          rows: [],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" });
    fireEvent.change(editor, { target: { value: "해결 응답까지 지킬 로컬 장면" } });
    await screen.findByRole("dialog", { name: "원고 저장 충돌 해결" });

    await user.click(screen.getByRole("button", { name: "내 편집본 유지" }));
    expect(screen.queryByRole("textbox", { name: "원고 본문" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();

    releaseResolution();
    const restoredEditor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    expect(restoredEditor.value).toBe("해결 응답까지 지킬 로컬 장면");
    expect(screen.queryByRole("dialog", { name: "원고 저장 충돌 해결" })).not.toBeInTheDocument();
    expect(saveCount).toBe(2);
  });
});

function renderWorkspace(projectId = "silver-garden") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={createAppMemoryRouter([`/projects/${projectId}/write`])} />
    </QueryClientProvider>,
  );
}

function getWorkspace(): ProjectWorkspaceResponse {
  const workspace = findMockWorkspace("silver-garden");
  if (!workspace) {
    throw new Error("Expected the seeded workspace");
  }
  return workspace;
}
