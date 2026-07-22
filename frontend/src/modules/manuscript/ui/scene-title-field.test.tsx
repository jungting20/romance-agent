import { useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { SceneTitleField } from "./scene-title-field";

test("edits the existing title with Enter and restores the heading", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  function StatefulTitleField() {
    const [title, setTitle] = useState("비가 그친 뒤의 정원");
    return (
      <SceneTitleField
        title={title}
        disabled={false}
        onCommit={(nextTitle) => {
          onCommit(nextTitle);
          setTitle(nextTitle.trim());
        }}
      />
    );
  }
  render(<StatefulTitleField />);

  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  const input = screen.getByRole("textbox", { name: "장면 제목" });
  expect(input).toHaveFocus();
  expect(input).toHaveValue("비가 그친 뒤의 정원");
  expect(input).toHaveProperty("selectionStart", 0);
  expect(input).toHaveProperty("selectionEnd", "비가 그친 뒤의 정원".length);

  await user.clear(input);
  await user.type(input, "  남겨진 편지  {Enter}");

  expect(onCommit).toHaveBeenCalledOnce();
  expect(onCommit).toHaveBeenCalledWith("  남겨진 편지  ");
  expect(screen.getByRole("heading", { name: "남겨진 편지" })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("장면 제목을 저장할 준비가 되었어요.");
});

test("commits on blur and cancels with Escape", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  const { rerender } = render(
    <>
      <SceneTitleField title="첫 제목" disabled={false} onCommit={onCommit} />
      <button type="button">다음 작업</button>
    </>,
  );

  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  await user.clear(screen.getByRole("textbox", { name: "장면 제목" }));
  await user.type(screen.getByRole("textbox", { name: "장면 제목" }), "두 번째 제목");
  await user.tab();
  expect(onCommit).toHaveBeenLastCalledWith("두 번째 제목");
  expect(screen.getByRole("button", { name: "다음 작업" })).toHaveFocus();

  rerender(
    <>
      <SceneTitleField title="두 번째 제목" disabled={false} onCommit={onCommit} />
      <button type="button">다음 작업</button>
    </>,
  );
  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  await user.type(screen.getByRole("textbox", { name: "장면 제목" }), " 폐기");
  await user.keyboard("{Escape}");
  expect(onCommit).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("heading", { name: "두 번째 제목" })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("장면 제목 수정을 취소했어요.");
});

test("keeps a blank title in edit mode with a linked error", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  render(<SceneTitleField title="기존 제목" disabled={false} onCommit={onCommit} />);

  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  const input = screen.getByRole("textbox", { name: "장면 제목" });
  await user.clear(input);
  await user.type(input, "   {Enter}");

  expect(onCommit).not.toHaveBeenCalled();
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(input).toHaveAccessibleDescription("장면 제목을 입력해 주세요.");
});

test("preserves an in-progress value but blocks commit while disabled", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  const { rerender } = render(
    <SceneTitleField title="기존 제목" disabled={false} onCommit={onCommit} />,
  );
  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  await user.clear(screen.getByRole("textbox", { name: "장면 제목" }));
  await user.type(screen.getByRole("textbox", { name: "장면 제목" }), "보존할 제목");

  rerender(<SceneTitleField title="기존 제목" disabled onCommit={onCommit} />);

  expect(screen.getByRole("textbox", { name: "장면 제목" })).toHaveValue("보존할 제목");
  expect(screen.getByRole("textbox", { name: "장면 제목" })).toBeDisabled();
  expect(onCommit).not.toHaveBeenCalled();
});

test("cancels a scheduled blur commit when editing becomes disabled", async () => {
  vi.useFakeTimers();
  try {
    const onCommit = vi.fn();
    const { rerender } = render(
      <SceneTitleField title="기존 제목" disabled={false} onCommit={onCommit} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "장면 제목 수정" }));
    const input = screen.getByRole("textbox", { name: "장면 제목" });
    fireEvent.change(input, { target: { value: "충돌 중 보존할 제목" } });
    fireEvent.blur(input);

    rerender(<SceneTitleField title="기존 제목" disabled onCommit={onCommit} />);
    await act(async () => {
      vi.runAllTimers();
    });

    expect(onCommit).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox", { name: "장면 제목" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "장면 제목" })).toHaveValue("충돌 중 보존할 제목");
  } finally {
    vi.useRealTimers();
  }
});

test("returns keyboard focus to the edit button after Enter and Escape", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  render(<SceneTitleField title="기존 제목" disabled={false} onCommit={onCommit} />);

  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  const enterInput = screen.getByRole("textbox", { name: "장면 제목" });
  await user.clear(enterInput);
  await user.type(enterInput, "확정할 제목{Enter}");

  const editButton = screen.getByRole("button", { name: "장면 제목 수정" });
  expect(document.activeElement).toBe(editButton);

  await user.click(editButton);
  await user.type(screen.getByRole("textbox", { name: "장면 제목" }), " 취소할 값");
  await user.keyboard("{Escape}");

  expect(document.activeElement).toBe(screen.getByRole("button", { name: "장면 제목 수정" }));
});

test("resets an uncommitted draft when a different keyed scene renders", async () => {
  const user = userEvent.setup();
  const onCommit = vi.fn();
  const { rerender } = render(
    <SceneTitleField key="scene-1" title="첫 장면" disabled={false} onCommit={onCommit} />,
  );
  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  await user.type(screen.getByRole("textbox", { name: "장면 제목" }), "의 미완성 초안");

  rerender(
    <SceneTitleField key="scene-2" title="두 번째 장면" disabled={false} onCommit={onCommit} />,
  );

  expect(screen.getByRole("heading", { name: "두 번째 장면" })).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: "장면 제목" })).not.toBeInTheDocument();
  expect(onCommit).not.toHaveBeenCalled();
});
