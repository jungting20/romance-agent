import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test } from "vitest";

import { AppRoutes } from "@/app/app";
import { AppProvider } from "@/app/state/app-provider";

describe("WritingWorkspacePage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  test("switches the contextual panel between manuscript and characters", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    expect(screen.getByText("원고 목차")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "인물 보기" }));

    expect(screen.getByText("등장인물")).toBeInTheDocument();
    expect(screen.getByText("서윤")).toBeInTheDocument();
    expect(screen.getByText("도현")).toBeInTheDocument();
  });

  test("applies a requested continuation to the manuscript", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const editor = screen.getByRole("textbox", { name: "원고 본문" });
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
    const editor = screen.getByRole<HTMLTextAreaElement>("textbox", {
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
    const editor = screen.getByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });

    editor.setSelectionRange(0, 0);
    fireEvent.select(editor);
    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));
    await user.click(screen.getByRole("button", { name: "이어 쓰기" }));
    await user.click(screen.getByRole("button", { name: "원고에 적용" }));

    expect(editor.value).toMatch(/^\n\n/);
  });
});

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={["/projects/silver-garden/write"]}>
      <AppProvider>
        <AppRoutes />
      </AppProvider>
    </MemoryRouter>,
  );
}
