import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, test, vi } from "vitest";

import { createAppMemoryRouter } from "@/app/app";
import type {
  CreateProjectRequest,
  ProjectWorkspaceResponse,
} from "@/app/infrastructure/api/contracts";
import { server } from "@/mocks/server";

describe("SetupPage", () => {
  test("disables duplicate submission while project creation is pending", async () => {
    let releaseRequest!: () => void;
    const requestPending = new Promise<void>((resolve) => {
      releaseRequest = resolve;
    });
    const requestSpy = vi.fn();
    server.use(
      http.post("/api/projects", async ({ request }) => {
        requestSpy(await request.json());
        await requestPending;
        return HttpResponse.json(createWorkspace("pending-project"), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderSetup();

    await user.type(await screen.findByLabelText("작품 제목"), "기다리는 이야기");
    const submitButton = screen.getByRole("button", { name: "작업 공간 열기" });
    await user.click(submitButton);

    await waitFor(() => {
      expect(submitButton).toBeDisabled();
      expect(submitButton).toHaveAccessibleName("작업 공간 여는 중");
    });
    expect(screen.getByLabelText("작품 제목")).toBeDisabled();
    expect(screen.getByRole("form", { name: "새 프로젝트 설정" })).toHaveAttribute(
      "aria-busy",
      "true",
    );
    await user.click(submitButton);
    expect(requestSpy).toHaveBeenCalledTimes(1);

    releaseRequest();
  });

  test("associates 422 field messages with the affected inputs", async () => {
    server.use(
      http.post("/api/projects", () =>
        HttpResponse.json(
          {
            code: "INVALID_PROTAGONISTS",
            message: "입력 내용을 확인해 주세요.",
            fieldErrors: [
              { path: "title", message: "이미 사용 중인 작품 제목이에요." },
              { path: "protagonistNames", message: "두 주인공의 이름을 확인해 주세요." },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderSetup();

    await user.type(await screen.findByLabelText("작품 제목"), "겹치는 제목");
    await user.click(screen.getByRole("button", { name: "작업 공간 열기" }));

    expect(await screen.findByText("이미 사용 중인 작품 제목이에요.")).toBeInTheDocument();
    expect(screen.getByLabelText("작품 제목")).toHaveAccessibleDescription(
      "이미 사용 중인 작품 제목이에요.",
    );
    expect(screen.getByLabelText("첫 번째 주인공")).toHaveAccessibleDescription(
      "두 주인공의 이름을 확인해 주세요.",
    );
    expect(screen.getByLabelText("두 번째 주인공")).toHaveAccessibleDescription(
      "두 주인공의 이름을 확인해 주세요.",
    );
  });

  test("shows form-level feedback for a 422 field path that has no input", async () => {
    server.use(
      http.post("/api/projects", () =>
        HttpResponse.json(
          {
            code: "INVALID_TROPE",
            message: "선택한 로맨스 트로프를 찾을 수 없습니다.",
            fieldErrors: [{ path: "tropeId", message: "등록된 로맨스 트로프를 선택해 주세요." }],
          },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderSetup();

    await user.type(await screen.findByLabelText("작품 제목"), "트로프 오류 이야기");
    await user.click(screen.getByRole("button", { name: "작업 공간 열기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "선택한 로맨스 트로프를 찾을 수 없습니다.",
    );
  });

  test("shows a generic error when project creation fails", async () => {
    server.use(
      http.post("/api/projects", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderSetup();

    await user.type(await screen.findByLabelText("작품 제목"), "실패하는 이야기");
    await user.click(screen.getByRole("button", { name: "작업 공간 열기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "프로젝트를 만들지 못했어요. 잠시 후 다시 시도해 주세요.",
    );
  });

  test("navigates to the workspace ID returned by the server", async () => {
    let submittedRequest: CreateProjectRequest | undefined;
    server.use(
      http.post("/api/projects", async ({ request }) => {
        submittedRequest = (await request.json()) as CreateProjectRequest;
        return HttpResponse.json(createWorkspace("server-project-id"), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    const router = renderSetup();

    await user.type(await screen.findByLabelText("작품 제목"), "서버가 만든 이야기");
    await user.click(screen.getByRole("button", { name: "작업 공간 열기" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/projects/server-project-id/write");
    });
    expect(submittedRequest).toMatchObject({
      title: "서버가 만든 이야기",
      tropeId: "reunion",
      protagonistNames: ["서윤", "도현"],
    });
  });
});

function renderSetup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppMemoryRouter(["/new/setup?trope=reunion"]);

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  return router;
}

function createWorkspace(projectId: string): ProjectWorkspaceResponse {
  return {
    project: {
      id: projectId,
      title: "서버가 만든 이야기",
      logline: "다시 만난 두 사람의 이야기",
      tropeId: "reunion",
      updatedAt: "2026-07-14T03:00:00.000Z",
    },
    concept: {
      id: `${projectId}-concept`,
      projectId,
      tropeId: "reunion",
      logline: "다시 만난 두 사람의 이야기",
      protagonistNames: ["서윤", "도현"],
    },
    storyBible: { projectId, characters: [], worldEntries: [] },
    manuscript: {
      id: `${projectId}-manuscript`,
      projectId,
      scenes: [],
      activeSceneId: `${projectId}-scene-1`,
    },
    manuscriptRevision: 1,
  };
}
