import { createRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { createInitialManuscript } from "@/modules/manuscript";

import { ManuscriptEditor } from "./manuscript-editor";

test("forwards title, body, selection, and textarea ref interactions", async () => {
  const scene = createInitialManuscript("project-1").scenes[0]!;
  const onTitleCommit = vi.fn();
  const onChange = vi.fn();
  const onSelectionChange = vi.fn();
  const editorRef = createRef<HTMLTextAreaElement>();
  const user = userEvent.setup();
  render(
    <ManuscriptEditor
      ref={editorRef}
      scene={scene}
      titleEditingDisabled={false}
      onTitleCommit={onTitleCommit}
      onChange={onChange}
      onSelectionChange={onSelectionChange}
    />,
  );

  await user.click(screen.getByRole("button", { name: "장면 제목 수정" }));
  const titleInput = screen.getByRole("textbox", { name: "장면 제목" });
  await user.clear(titleInput);
  await user.type(titleInput, "새 장면 제목{Enter}");
  expect(onTitleCommit).toHaveBeenCalledWith("새 장면 제목");

  const body = screen.getByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" });
  fireEvent.change(body, { target: { value: "바뀐 본문", selectionStart: 3, selectionEnd: 3 } });
  fireEvent.select(body, { target: { selectionStart: 1, selectionEnd: 3 } });

  expect(onChange).toHaveBeenCalledWith("바뀐 본문");
  expect(onSelectionChange).toHaveBeenLastCalledWith({ start: 1, end: 3 });
  expect(editorRef.current).toBe(body);
});

test("disables title editing without disabling body editing", () => {
  const scene = createInitialManuscript("project-1").scenes[0]!;
  render(
    <ManuscriptEditor
      scene={scene}
      titleEditingDisabled
      onTitleCommit={vi.fn()}
      onChange={vi.fn()}
      onSelectionChange={vi.fn()}
    />,
  );

  expect(screen.getByRole("button", { name: "장면 제목 수정" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "원고 본문" })).toBeEnabled();
});
