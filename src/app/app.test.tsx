import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test } from "vitest";

import { AppProvider } from "./state/app-provider";

describe("core writing journey", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  test("opens trope selection from the project library", async () => {
    const { AppRoutes } = await import("./app");
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppProvider>
          <AppRoutes />
        </AppProvider>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "다시, 이야기를 시작해 볼까요?" }),
    ).toBeInTheDocument();
    expect(screen.getByText("은빛 정원의 약속")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "새 작품 시작" }));

    expect(screen.getByRole("heading", { name: "어떤 사랑을 쓰고 싶나요?" })).toBeInTheDocument();
  });

  test("creates a project from a trope and opens its workspace", async () => {
    const { AppRoutes } = await import("./app");
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/new"]}>
        <AppProvider createId={() => "moonlight-reunion"}>
          <AppRoutes />
        </AppProvider>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("link", { name: "재회 로맨스 선택" }));

    expect(
      screen.getByRole("heading", { name: "이야기의 첫 문장을 준비할게요" }),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("작품 제목"), "달빛 아래 다시");
    await user.clear(screen.getByLabelText("첫 번째 주인공"));
    await user.type(screen.getByLabelText("첫 번째 주인공"), "유진");
    await user.clear(screen.getByLabelText("두 번째 주인공"));
    await user.type(screen.getByLabelText("두 번째 주인공"), "태오");
    await user.click(screen.getByRole("button", { name: "작업 공간 열기" }));

    expect(screen.getByRole("heading", { name: "달빛 아래 다시" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "원고 본문" })).toBeInTheDocument();
  });
});
