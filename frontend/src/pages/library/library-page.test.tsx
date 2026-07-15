import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, test } from "vitest";

import { createAppMemoryRouter } from "@/app/app";
import type { ProjectListResponse } from "@/app/infrastructure/api/contracts";
import { server } from "@/mocks/server";

const projects: ProjectListResponse = {
  items: [
    {
      id: "returned-first",
      title: "먼저 온 이야기",
      logline: "서버가 첫 번째로 보낸 이야기다.",
      tropeId: "reunion",
      updatedAt: "2026-07-12T00:00:00.000Z",
    },
    {
      id: "returned-second",
      title: "나중에 온 이야기",
      logline: "서버가 두 번째로 보낸 이야기다.",
      tropeId: "contract-romance",
      updatedAt: "2026-07-14T00:00:00.000Z",
    },
  ],
};

describe("LibraryPage", () => {
  test("shows a loading status while projects are being fetched", async () => {
    server.use(
      http.get("/api/projects", async () => {
        await delay("infinite");
        return HttpResponse.json({ items: [] });
      }),
    );

    renderLibrary();

    expect(await screen.findByRole("status")).toHaveTextContent("작품을 불러오는 중이에요.");
  });

  test("retries a failed project request", async () => {
    let requestCount = 0;
    server.use(
      http.get("/api/projects", () => {
        requestCount += 1;
        return requestCount === 1
          ? HttpResponse.json(
              { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
              { status: 500 },
            )
          : HttpResponse.json(projects);
      }),
    );
    const user = userEvent.setup();
    renderLibrary();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "작품을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
    );

    await user.click(screen.getByRole("button", { name: "작품 목록 다시 불러오기" }));

    expect(await screen.findByText("먼저 온 이야기")).toBeInTheDocument();
    expect(requestCount).toBe(2);
  });

  test("shows an empty state when the library has no projects", async () => {
    server.use(http.get("/api/projects", () => HttpResponse.json({ items: [] })));

    renderLibrary();

    expect(await screen.findByText("아직 시작한 작품이 없어요.")).toBeInTheDocument();
    expect(screen.getByText("첫 이야기를 만들어 서재를 채워 보세요.")).toBeInTheDocument();
  });

  test("renders projects in the order returned by the server", async () => {
    server.use(http.get("/api/projects", () => HttpResponse.json(projects)));

    renderLibrary();

    const links = await screen.findAllByRole("link", { name: /온 이야기/ });
    expect(links.map((link) => link.textContent)).toEqual([
      expect.stringContaining("먼저 온 이야기"),
      expect.stringContaining("나중에 온 이야기"),
    ]);
    expect(screen.getByText("2개의 이야기가 기다리고 있어요")).toBeInTheDocument();
  });
});

function renderLibrary() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppMemoryRouter(["/"]);

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}
