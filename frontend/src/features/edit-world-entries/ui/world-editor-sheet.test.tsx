import { useReducer } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import type { StoryBibleSnapshot } from "@/app/infrastructure/api/contracts";
import { ApiRequestError } from "@/app/infrastructure/api/api-client";

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

  test("autofocuses the first existing kind on a normal open", () => {
    renderEditor();

    expect(screen.getByRole("combobox", { name: "기존 항목 1 분류" })).toHaveFocus();
  });

  test("autofocuses the editor title when an empty editor opens", () => {
    renderEditor({
      state: createWorldEditorState({
        ...snapshot,
        storyBible: { ...snapshot.storyBible, worldEntries: [] },
      }),
    });

    expect(screen.getByRole("heading", { name: "세계관 수정 및 추가" })).toHaveFocus();
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

  test("removes resolved field feedback and updates the validation summary immediately", async () => {
    const user = userEvent.setup();
    render(<ValidationEditor />);
    const title = screen.getByRole("textbox", { name: "기존 항목 1 제목" });
    const description = screen.getByRole("textbox", { name: "기존 항목 1 설명" });

    await user.clear(title);
    await user.clear(description);
    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(screen.getByRole("alert")).toHaveTextContent("입력하지 않은 항목이 2개 있어요.");
    expect(title).toHaveAttribute("aria-invalid", "true");
    expect(title).toHaveAttribute("aria-describedby", "world-entry-world-1-title-error");
    expect(description).toHaveAttribute("aria-invalid", "true");

    await user.type(title, "온실");

    expect(screen.getByRole("alert")).toHaveTextContent("입력하지 않은 항목이 1개 있어요.");
    expect(screen.queryByText("제목을 입력해 주세요.")).not.toBeInTheDocument();
    expect(title).not.toHaveAttribute("aria-invalid");
    expect(title).not.toHaveAttribute("aria-describedby");
    expect(screen.getByText("설명을 입력해 주세요.")).toBeInTheDocument();
    expect(description).toHaveAttribute("aria-invalid", "true");

    await user.type(description, "두 사람의 장소");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("설명을 입력해 주세요.")).not.toBeInTheDocument();
    expect(description).not.toHaveAttribute("aria-invalid");
    expect(description).not.toHaveAttribute("aria-describedby");
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

  test("freezes edits and additions and offers guarded return while unavailable", () => {
    let state = createWorldEditorState(snapshot);
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "보존할 초안",
    });
    state = worldEditorReducer(state, {
      type: "save-failed",
      error: new ApiRequestError(404, {
        code: "STORY_BIBLE_NOT_FOUND",
        message: "없음",
        fieldErrors: [],
      }),
    });
    const onRequestClose = vi.fn();
    renderEditor({ state, onRequestClose });

    expect(screen.getByRole("textbox", { name: "기존 항목 1 제목" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "세계관 항목 추가" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
    screen.getByRole("button", { name: "세계관 보기로 돌아가기" }).click();
    expect(onRequestClose).toHaveBeenCalledOnce();
  });
});

function ValidationEditor() {
  const [state, dispatch] = useReducer(worldEditorReducer, snapshot, createWorldEditorState);

  return (
    <WorldEditorSheet
      open
      state={state}
      onFieldChange={(key, field, value) => dispatch({ type: "change-field", key, field, value })}
      onAdd={() => undefined}
      onSave={() => dispatch({ type: "validate" })}
      onRequestClose={() => undefined}
      onRetry={() => undefined}
      onRequestReload={() => undefined}
    />
  );
}

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
