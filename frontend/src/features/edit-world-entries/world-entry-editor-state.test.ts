import { describe, expect, test } from "vitest";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type { StoryBibleSnapshot } from "@/app/infrastructure/api/contracts";

import {
  createWorldEditorState,
  isWorldEditorDirty,
  toSaveWorldEntriesRequest,
  worldEditorReducer,
} from "./world-entry-editor-state";

const snapshot: StoryBibleSnapshot = {
  storyBibleRevision: 4,
  storyBible: {
    projectId: "project-1",
    characters: [],
    worldEntries: [
      { id: "world-1", kind: "place", title: "온실", description: "비밀 장소" },
      { id: "world-2", kind: "rule", title: "서약", description: "왕실의 규칙" },
    ],
  },
};

describe("worldEditorReducer", () => {
  test("starts pristine and immutably updates an existing row while retaining its identity", () => {
    const initial = createWorldEditorState(snapshot);
    const next = worldEditorReducer(initial, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "유리 온실",
    });

    expect(isWorldEditorDirty(initial)).toBe(false);
    expect(isWorldEditorDirty(next)).toBe(true);
    expect(initial.draft.rows[0].title).toBe("온실");
    expect(next.draft.rows[0]).toMatchObject({ key: "world-1", id: "world-1", title: "유리 온실" });
  });

  test("appends multiple client-keyed additions without serializing their render keys", () => {
    let state = createWorldEditorState(snapshot);
    state = worldEditorReducer(state, { type: "add-row", key: "new-a" });
    state = worldEditorReducer(state, { type: "add-row", key: "new-b" });
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "new-a",
      field: "title",
      value: " 열쇠 ",
    });
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "new-a",
      field: "description",
      value: " 문을 연다 ",
    });
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "new-b",
      field: "title",
      value: " 금지 ",
    });
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "new-b",
      field: "description",
      value: " 떠나지 않는다 ",
    });

    const request = toSaveWorldEntriesRequest(state);
    expect(state.draft.rows.slice(-2).map(({ key, id }) => ({ key, id }))).toEqual([
      { key: "new-a", id: undefined },
      { key: "new-b", id: undefined },
    ]);
    expect(request?.additions).toEqual([
      { kind: "place", title: "열쇠", description: "문을 연다" },
      { kind: "place", title: "금지", description: "떠나지 않는다" },
    ]);
    expect(JSON.stringify(request)).not.toContain("new-a");
  });

  test("collects all validation errors and identifies the first invalid field", () => {
    let state = createWorldEditorState({
      ...snapshot,
      storyBible: { ...snapshot.storyBible, worldEntries: [] },
    });
    state = worldEditorReducer(state, { type: "add-row", key: "new-a" });
    state = worldEditorReducer(state, { type: "add-row", key: "new-b" });
    state = worldEditorReducer(state, { type: "validate" });

    expect(state.phase).toEqual({ status: "validating" });
    expect(state.errors).toEqual({
      "new-a": { title: "제목을 입력해 주세요.", description: "설명을 입력해 주세요." },
      "new-b": { title: "제목을 입력해 주세요.", description: "설명을 입력해 주세요." },
    });
    expect(state.firstInvalidField).toEqual({ key: "new-a", field: "title" });
    expect(toSaveWorldEntriesRequest(state)).toBeUndefined();
  });

  test("clears only the resolved field error as the draft is corrected", () => {
    let state = createWorldEditorState({
      ...snapshot,
      storyBible: {
        ...snapshot.storyBible,
        worldEntries: [{ id: "world-1", kind: "place", title: "", description: "" }],
      },
    });
    state = worldEditorReducer(state, { type: "validate" });

    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "온실",
    });

    expect(state.errors).toEqual({
      "world-1": { description: "설명을 입력해 주세요." },
    });
    expect(state.firstInvalidField).toBeUndefined();

    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "description",
      value: "두 사람의 장소",
    });

    expect(state.errors).toEqual({});
    expect(state.firstInvalidField).toBeUndefined();
  });

  test("preserves validation errors on unchanged fields and rows", () => {
    let state = createWorldEditorState({
      ...snapshot,
      storyBible: { ...snapshot.storyBible, worldEntries: [] },
    });
    state = worldEditorReducer(state, { type: "add-row", key: "new-a" });
    state = worldEditorReducer(state, { type: "add-row", key: "new-b" });
    state = worldEditorReducer(state, { type: "validate" });

    state = worldEditorReducer(state, {
      type: "change-field",
      key: "new-a",
      field: "title",
      value: "온실",
    });

    expect(state.errors).toEqual({
      "new-a": { description: "설명을 입력해 주세요." },
      "new-b": { title: "제목을 입력해 주세요.", description: "설명을 입력해 주세요." },
    });
  });

  test("freezes the submitted draft and ignores edits while saving", () => {
    let state = createWorldEditorState(snapshot);
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "수정",
    });
    state = worldEditorReducer(state, { type: "save-start" });
    const saving = state;
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "늦은 수정",
    });

    expect(saving.phase.status).toBe("saving");
    expect(state).toBe(saving);
    expect(saving.phase).toMatchObject({ submittedDraft: saving.draft });
  });

  test.each([
    [500, "INTERNAL_ERROR", "retryable-error"],
    [409, "STORY_BIBLE_REVISION_CONFLICT", "conflict"],
    [404, "STORY_BIBLE_NOT_FOUND", "unavailable"],
  ] as const)("maps %s %s to %s without losing the draft", (status, code, expected) => {
    let state = createWorldEditorState(snapshot);
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "보존할 수정",
    });
    const draft = state.draft;
    state = worldEditorReducer(state, {
      type: "save-failed",
      error: new ApiRequestError(status, { code, message: "실패", fieldErrors: [] }),
    });

    expect(state.phase.status).toBe(expected);
    expect(state.draft).toBe(draft);
  });

  test("keeps a save-time unavailable draft frozen against field changes and additions", () => {
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
    const unavailable = state;

    state = worldEditorReducer(state, { type: "add-row", key: "must-not-add" });
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "바뀌면 안 됨",
    });

    expect(state).toBe(unavailable);
    expect(state.draft.rows).toHaveLength(2);
    expect(state.draft.rows[0].title).toBe("보존할 초안");
  });

  test("preserves the old draft during latest reload and replaces it only after success", () => {
    let state = createWorldEditorState(snapshot);
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "로컬 초안",
    });
    const oldDraft = state.draft;
    state = worldEditorReducer(state, { type: "reload-start" });
    expect(state.phase).toEqual({ status: "reloading" });
    expect(state.draft).toBe(oldDraft);

    const latest = {
      ...snapshot,
      storyBibleRevision: 5,
      storyBible: {
        ...snapshot.storyBible,
        worldEntries: [{ ...snapshot.storyBible.worldEntries[0], title: "서버 최신" }],
      },
    };
    state = worldEditorReducer(state, { type: "reload-success", snapshot: latest });
    expect(state.phase).toEqual({ status: "ready" });
    expect(state.draft.rows[0].title).toBe("서버 최신");
    expect(isWorldEditorDirty(state)).toBe(false);
  });

  test("records and cancels discard intent without changing the draft", () => {
    let state = createWorldEditorState(snapshot);
    state = worldEditorReducer(state, {
      type: "change-field",
      key: "world-1",
      field: "title",
      value: "초안",
    });
    const draft = state.draft;
    state = worldEditorReducer(state, { type: "request-discard", intent: "close" });
    expect(state.discardIntent).toBe("close");
    state = worldEditorReducer(state, { type: "cancel-discard" });
    expect(state.discardIntent).toBeUndefined();
    expect(state.draft).toBe(draft);
  });
});
