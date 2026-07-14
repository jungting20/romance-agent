import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test } from "vitest";

import type {
  CompareManuscriptSceneResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
} from "@/app/infrastructure/api/contracts";
import { AppRoutes } from "@/app/app";
import { findMockWorkspace } from "@/mocks/data/project-workspaces";
import { server } from "@/mocks/server";

describe("WritingWorkspacePage", () => {
  test("shows a loading status while the workspace is being fetched", () => {
    server.use(
      http.get("/api/projects/:projectId/workspace", async () => {
        await delay("infinite");
        return HttpResponse.json({});
      }),
    );

    renderWorkspace();

    expect(screen.getByRole("status")).toHaveTextContent("작업 공간을 불러오는 중이에요.");
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

  test("switches the contextual panel between manuscript and characters", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    expect(await screen.findByText("원고 목차")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "인물 보기" }));

    expect(screen.getByText("등장인물")).toBeInTheDocument();
    expect(screen.getByText("서윤")).toBeInTheDocument();
    expect(screen.getByText("도현")).toBeInTheDocument();
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
      <MemoryRouter initialEntries={[`/projects/${projectId}/write`]}>
        <AppRoutes />
      </MemoryRouter>
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
