import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type { StoryBibleSnapshot } from "@/app/infrastructure/api/contracts";
import {
  useSaveWorldEntriesMutation,
  useStoryBibleQuery,
} from "@/features/story-bible-persistence";

import {
  createWorldEditorState,
  isWorldEditorDirty,
  toSaveWorldEntriesRequest,
  type WorldDiscardIntent,
  type WorldEditorAction,
  type WorldEditorState,
  worldEditorReducer,
} from "./world-entry-editor-state";

export interface WorldEntryEditor {
  state?: WorldEditorState;
  isInitializing: boolean;
  loadError?: ApiRequestError;
  retryLoad: () => void;
  requiresDiscardConfirmation: boolean;
  changeField: (key: string, field: "kind" | "title" | "description", value: string) => void;
  addRow: () => void;
  save: () => Promise<void>;
  retry: () => Promise<void>;
  requestClose: () => void;
  requestLatestReload: () => void;
  cancelDiscard: () => void;
  confirmDiscard: () => Promise<void>;
  confirmNavigationDiscard: () => Promise<boolean>;
}

export function useWorldEntryEditor({
  projectId,
  open,
  onSaved,
  onClose,
}: {
  projectId: string;
  open: boolean;
  onSaved: (snapshot: StoryBibleSnapshot) => void;
  onClose: () => void;
}): WorldEntryEditor {
  const query = useStoryBibleQuery(projectId);
  const mutation = useSaveWorldEntriesMutation();
  const [state, setState] = useState<WorldEditorState>();
  const [savedSnapshot, setSavedSnapshot] = useState<StoryBibleSnapshot>();
  const [closeRequested, setCloseRequested] = useState(false);
  const nextKey = useRef(0);
  const navigationResolution = useRef<((confirmed: boolean) => void) | null>(null);

  useEffect(() => {
    if (open && query.data && !state) setState(createWorldEditorState(query.data));
    if (!open && state) setState(undefined);
  }, [open, query.data, state]);

  useEffect(() => {
    if (!savedSnapshot) return;
    onSaved(savedSnapshot);
    setSavedSnapshot(undefined);
  }, [onSaved, savedSnapshot]);

  useEffect(() => {
    if (!closeRequested || !state || isWorldEditorDirty(state)) return;
    setCloseRequested(false);
    onClose();
  }, [closeRequested, onClose, state]);

  const dispatch = useCallback((action: WorldEditorAction) => {
    setState((current) => (current ? worldEditorReducer(current, action) : current));
  }, []);

  const save = useCallback(async () => {
    if (!state) return;
    const request = toSaveWorldEntriesRequest(state);
    if (!request) {
      dispatch({ type: "validate" });
      return;
    }
    dispatch({ type: "save-start" });
    try {
      const saved = await mutation.mutateAsync({ projectId, request });
      setState(createWorldEditorState(saved));
      setSavedSnapshot(saved);
    } catch (error) {
      dispatch({
        type: "save-failed",
        error:
          error instanceof ApiRequestError
            ? error
            : new ApiRequestError(500, {
                code: "INTERNAL_ERROR",
                message: "세계관을 저장하지 못했어요.",
                fieldErrors: [],
              }),
      });
    }
  }, [dispatch, mutation, onSaved, projectId, state]);

  const requestDiscard = useCallback(
    (intent: WorldDiscardIntent) => dispatch({ type: "request-discard", intent }),
    [dispatch],
  );

  return {
    state,
    isInitializing: open && !state,
    loadError: query.error instanceof ApiRequestError ? query.error : undefined,
    retryLoad: () => void query.refetch(),
    requiresDiscardConfirmation: Boolean(state && isWorldEditorDirty(state)),
    changeField: (key, field, value) => dispatch({ type: "change-field", key, field, value }),
    addRow: () => {
      const key = `new-${++nextKey.current}`;
      dispatch({ type: "add-row", key });
    },
    save,
    retry: save,
    requestClose: () => {
      if (state && isWorldEditorDirty(state)) requestDiscard("close");
      else onClose();
    },
    requestLatestReload: () => requestDiscard("reload-latest"),
    cancelDiscard: () => {
      navigationResolution.current?.(false);
      navigationResolution.current = null;
      dispatch({ type: "cancel-discard" });
    },
    confirmDiscard: async () => {
      if (!state?.discardIntent) return;
      const intent = state.discardIntent;
      if (intent === "reload-latest") {
        dispatch({ type: "reload-start" });
        const result = await query.refetch();
        if (result.data) dispatch({ type: "reload-success", snapshot: result.data });
        else if (result.error) {
          dispatch({
            type: "save-failed",
            error:
              result.error instanceof ApiRequestError
                ? result.error
                : new ApiRequestError(500, {
                    code: "INTERNAL_ERROR",
                    message: "세계관을 불러오지 못했어요.",
                    fieldErrors: [],
                  }),
          });
        }
        return;
      }
      if (intent === "navigation") {
        navigationResolution.current?.(true);
        navigationResolution.current = null;
        dispatch({ type: "cancel-discard" });
        return;
      }
      setState((current) =>
        current
          ? {
              ...current,
              draft: current.baseline,
              phase: { status: "ready" },
              errors: {},
              firstInvalidField: undefined,
              discardIntent: undefined,
            }
          : current,
      );
      setCloseRequested(true);
    },
    confirmNavigationDiscard: () => {
      if (!state || !isWorldEditorDirty(state)) return Promise.resolve(true);
      requestDiscard("navigation");
      return new Promise<boolean>((resolve) => {
        navigationResolution.current = resolve;
      });
    },
  };
}
