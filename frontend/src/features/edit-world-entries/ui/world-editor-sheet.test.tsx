import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import type { StoryBibleSnapshot } from "@/app/infrastructure/api/contracts";

import { createWorldEditorState, worldEditorReducer } from "../world-entry-editor-state";
import { WorldEditorSheet } from "./world-editor-sheet";

const snapshot: StoryBibleSnapshot = {
  storyBibleRevision: 1,
  storyBible: {
    projectId: "silver-garden",
    characters: [],
    worldEntries: [{ id: "world-1", kind: "place", title: "온실", description: "두 사람의 장소" }],
  },
};

describe("WorldEditorSheet", () => {
  test("renders labeled existing fields and emits controlled edits", async () => {
    const user = userEvent.setup();
    const onFieldChange = vi.fn();
    renderEditor({ onFieldChange });

    expect(screen.getByRole("dialog", { name: "세계관 수정 및 추가" })).toBeInTheDocument();
    expect(screen.getByText("기존 항목 1")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "기존 항목 1 분류" })).toHaveValue("place");
    expect(screen.getByRole("textbox", { name: "기존 항목 1 제목" })).toHaveValue("온실");
    expect(screen.getByRole("textbox", { name: "기존 항목 1 설명" })).toHaveValue("두 사람의 장소");

    await user.clear(screen.getByRole("textbox", { name: "기존 항목 1 제목" }));
    expect(onFieldChange).toHaveBeenCalledWith("world-1", "title", "");
  });

  test("focuses the first invalid field and exposes every validation error", () => {
    let state = createWorldEditorState({
      ...snapshot,
      storyBible: { ...snapshot.storyBible, worldEntries: [] },
    });
    state = worldEditorReducer(state, { type: "add-row", key: "new-1" });
    state = worldEditorReducer(state, { type: "validate" });
    renderEditor({ state });

    expect(screen.getByRole("alert")).toHaveTextContent("입력하지 않은 항목");
    expect(screen.getByText("제목을 입력해 주세요.")).toBeInTheDocument();
    expect(screen.getByText("설명을 입력해 주세요.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "새 항목 1 제목" })).toHaveFocus();
  });

  test("freezes every editing and close control while saving", () => {
    let state = createWorldEditorState(snapshot);
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "수정",
    });
    state = worldEditorReducer(state, { type: "save-start" });
    renderEditor({ state });

    expect(screen.getByRole("status")).toHaveTextContent("세계관을 저장하는 중이에요.");
    expect(screen.getByRole("combobox", { name: "기존 항목 1 분류" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "세계관 항목 추가" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "세계관 편집기 닫기" })).toBeDisabled();
  });
});

function renderEditor(overrides: Partial<React.ComponentProps<typeof WorldEditorSheet>> = {}) {
  return render(
    <WorldEditorSheet
      open
      state={createWorldEditorState(snapshot)}
      onFieldChange={vi.fn()}
      onAdd={vi.fn()}
      onSave={vi.fn()}
      onRequestClose={vi.fn()}
      onRetry={vi.fn()}
      onRequestReload={vi.fn()}
      {...overrides}
    />,
  );
}
