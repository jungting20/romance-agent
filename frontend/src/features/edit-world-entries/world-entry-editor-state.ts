import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type {
  SaveWorldEntriesRequest,
  StoryBibleSnapshot,
} from "@/app/infrastructure/api/contracts";
import {
  type WorldEntryDraftErrors,
  type WorldEntryDraftValue,
  validateWorldEntryDraft,
} from "@/modules/story-bible/domain/story-bible";

export interface WorldEditorDraftRow extends WorldEntryDraftValue {
  key: string;
  id?: string;
}

export interface WorldEditorDraft {
  revision: number;
  rows: WorldEditorDraftRow[];
}

export type WorldEditorPhase =
  | { status: "ready" }
  | { status: "validating" }
  | { status: "saving"; submittedDraft: WorldEditorDraft }
  | { status: "retryable-error"; error: ApiRequestError }
  | { status: "conflict" }
  | { status: "reloading" }
  | { status: "unavailable"; error: ApiRequestError };

export interface WorldEditorFieldIdentity {
  key: string;
  field: keyof WorldEntryDraftErrors;
}

export type WorldDiscardIntent = "close" | "navigation" | "reload-latest";

export interface WorldEditorState {
  baseline: WorldEditorDraft;
  draft: WorldEditorDraft;
  phase: WorldEditorPhase;
  errors: Record<string, WorldEntryDraftErrors>;
  firstInvalidField?: WorldEditorFieldIdentity;
  discardIntent?: WorldDiscardIntent;
}

export type WorldEditorAction =
  | {
      type: "change-field";
      key: string;
      field: keyof WorldEntryDraftValue;
      value: WorldEntryDraftValue[keyof WorldEntryDraftValue];
    }
  | { type: "add-row"; key: string }
  | { type: "validate" }
  | { type: "save-start" }
  | { type: "save-failed"; error: ApiRequestError }
  | { type: "reload-start" }
  | { type: "reload-success"; snapshot: StoryBibleSnapshot }
  | { type: "request-discard"; intent: WorldDiscardIntent }
  | { type: "cancel-discard" };

export function createWorldEditorState(snapshot: StoryBibleSnapshot): WorldEditorState {
  const draft = draftFromSnapshot(snapshot);
  return {
    baseline: draft,
    draft,
    phase: { status: "ready" },
    errors: {},
  };
}

export function isWorldEditorDirty(state: WorldEditorState): boolean {
  return !draftsEqual(state.draft, state.baseline);
}

export function isWorldEditorFrozen(state: WorldEditorState): boolean {
  return state.phase.status === "saving" || state.phase.status === "reloading";
}

export function worldEditorReducer(
  state: WorldEditorState,
  action: WorldEditorAction,
): WorldEditorState {
  if (
    isWorldEditorFrozen(state) &&
    action.type !== "save-failed" &&
    action.type !== "reload-success"
  ) {
    return state;
  }

  switch (action.type) {
    case "change-field":
      return {
        ...state,
        draft: {
          ...state.draft,
          rows: state.draft.rows.map((row) =>
            row.key === action.key
              ? ({ ...row, [action.field]: action.value } as WorldEditorDraftRow)
              : row,
          ),
        },
        phase: { status: "ready" },
      };
    case "add-row":
      return {
        ...state,
        draft: {
          ...state.draft,
          rows: [
            ...state.draft.rows,
            { key: action.key, kind: "place", title: "", description: "" },
          ],
        },
        phase: { status: "ready" },
      };
    case "validate": {
      const validation = validateDraft(state.draft);
      return {
        ...state,
        phase: { status: "validating" },
        errors: validation.errors,
        firstInvalidField: validation.firstInvalidField,
      };
    }
    case "save-start":
      return { ...state, phase: { status: "saving", submittedDraft: state.draft } };
    case "save-failed":
      if (
        action.error.status === 409 &&
        action.error.error.code === "STORY_BIBLE_REVISION_CONFLICT"
      ) {
        return { ...state, phase: { status: "conflict" } };
      }
      if (
        action.error.status === 404 &&
        (action.error.error.code === "PROJECT_NOT_FOUND" ||
          action.error.error.code === "STORY_BIBLE_NOT_FOUND")
      ) {
        return { ...state, phase: { status: "unavailable", error: action.error } };
      }
      return { ...state, phase: { status: "retryable-error", error: action.error } };
    case "reload-start":
      return { ...state, phase: { status: "reloading" }, discardIntent: undefined };
    case "reload-success":
      return createWorldEditorState(action.snapshot);
    case "request-discard":
      return { ...state, discardIntent: action.intent };
    case "cancel-discard":
      return { ...state, discardIntent: undefined };
  }
}

export function toSaveWorldEntriesRequest(
  state: WorldEditorState,
): SaveWorldEntriesRequest | undefined {
  const validation = validateDraft(state.draft);
  if (validation.firstInvalidField) return undefined;

  return {
    expectedRevision: state.draft.revision,
    updates: state.draft.rows
      .filter((row): row is WorldEditorDraftRow & { id: string } => row.id !== undefined)
      .map(({ id, kind, title, description }) => ({
        id,
        ...validateWorldEntryDraft({ kind, title, description }).value!,
      })),
    additions: state.draft.rows
      .filter((row) => row.id === undefined)
      .map(
        ({ kind, title, description }) =>
          validateWorldEntryDraft({ kind, title, description }).value!,
      ),
  };
}

function validateDraft(draft: WorldEditorDraft): {
  errors: Record<string, WorldEntryDraftErrors>;
  firstInvalidField?: WorldEditorFieldIdentity;
} {
  const errors: Record<string, WorldEntryDraftErrors> = {};
  let firstInvalidField: WorldEditorFieldIdentity | undefined;

  for (const row of draft.rows) {
    const result = validateWorldEntryDraft(row);
    if (Object.keys(result.errors).length === 0) continue;
    errors[row.key] = result.errors;
    firstInvalidField ??= {
      key: row.key,
      field: result.errors.title ? "title" : "description",
    };
  }

  return { errors, firstInvalidField };
}

function draftFromSnapshot(snapshot: StoryBibleSnapshot): WorldEditorDraft {
  return {
    revision: snapshot.storyBibleRevision,
    rows: snapshot.storyBible.worldEntries.map((entry) => ({
      key: entry.id,
      id: entry.id,
      kind: entry.kind,
      title: entry.title,
      description: entry.description,
    })),
  };
}

function draftsEqual(left: WorldEditorDraft, right: WorldEditorDraft): boolean {
  if (left.revision !== right.revision || left.rows.length !== right.rows.length) return false;
  return left.rows.every((row, index) => {
    const other = right.rows[index];
    return (
      row.key === other.key &&
      row.id === other.id &&
      row.kind === other.kind &&
      row.title === other.title &&
      row.description === other.description
    );
  });
}
