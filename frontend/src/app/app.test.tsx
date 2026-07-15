import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, test } from "vitest";

import { findMockWorkspace } from "@/mocks/data/project-workspaces";
import { server } from "@/mocks/server";

import { createAppMemoryRouter } from "./app";

describe("core writing journey", () => {
  test("replace-navigates unknown routes to the project library", async () => {
    const router = renderApp(["/missing-route"]);

    expect(
      await screen.findByRole("heading", { name: "다시, 이야기를 시작해 볼까요?" }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
    expect(router.state.location.state.__TSR_index).toBe(0);
  });

  test("opens trope selection from the project library", async () => {
    const user = userEvent.setup();

    renderApp(["/"]);

    expect(
      await screen.findByRole("heading", { name: "다시, 이야기를 시작해 볼까요?" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("은빛 정원의 약속")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "새 작품 시작" }));

    expect(
      await screen.findByRole("heading", { name: "어떤 사랑을 쓰고 싶나요?" }),
    ).toBeInTheDocument();
  });

  test("opens the workspace identified by the project creation response", async () => {
    const user = userEvent.setup();
    const workspace = findMockWorkspace("silver-garden");
    if (!workspace) {
      throw new Error("Expected the seeded workspace");
    }
    server.use(http.post("/api/projects", () => HttpResponse.json(workspace, { status: 201 })));

    renderApp(["/new"]);

    await user.click(await screen.findByRole("link", { name: "재회 로맨스 선택" }));

    expect(
      await screen.findByRole("heading", { name: "이야기의 첫 문장을 준비할게요" }),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("작품 제목"), "달빛 아래 다시");
    await user.clear(screen.getByLabelText("첫 번째 주인공"));
    await user.type(screen.getByLabelText("첫 번째 주인공"), "유진");
    await user.clear(screen.getByLabelText("두 번째 주인공"));
    await user.type(screen.getByLabelText("두 번째 주인공"), "태오");
    await user.click(screen.getByRole("button", { name: "작업 공간 열기" }));

    expect(await screen.findByRole("heading", { name: "은빛 정원의 약속" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "원고 본문" })).toBeInTheDocument();
  });
});

function renderApp(initialEntries: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppMemoryRouter(initialEntries);

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  return router;
}
