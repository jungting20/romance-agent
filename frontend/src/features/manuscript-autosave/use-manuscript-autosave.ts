import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import { useSaveManuscriptMutation } from "@/features/project-persistence";
import type { Manuscript } from "@/modules/manuscript";

import { useManuscriptConflictResolution } from "./use-manuscript-conflict-resolution";

const AUTOSAVE_IDLE_MS = 800;

export type ManuscriptAutosaveStatus = "editing" | "saving" | "saved" | "error" | "conflict";

interface UseManuscriptAutosaveOptions {
  manuscript: Manuscript;
  manuscriptRevision: number;
}

type DraftUpdate = Manuscript | ((currentDraft: Manuscript) => Manuscript);

export function useManuscriptAutosave({
  manuscript,
  manuscriptRevision,
}: UseManuscriptAutosaveOptions) {
  const saveMutation = useSaveManuscriptMutation();
  const mutateAsyncRef = useRef(saveMutation.mutateAsync);
  mutateAsyncRef.current = saveMutation.mutateAsync;
  const [draft, setDraft] = useState(manuscript);
  const [status, setStatusState] = useState<ManuscriptAutosaveStatus>("saved");
  const draftRef = useRef(manuscript);
  const acknowledgedManuscriptRef = useRef(manuscript);
  const acknowledgedRevisionRef = useRef(manuscriptRevision);
  const inFlightRef = useRef(false);
  const statusRef = useRef<ManuscriptAutosaveStatus>("saved");
  const manuscriptGenerationRef = useRef(0);
  const saveSettledWaitersRef = useRef<Array<() => void>>([]);

  const setStatus = useCallback((nextStatus: ManuscriptAutosaveStatus) => {
    statusRef.current = nextStatus;
    setStatusState(nextStatus);
  }, []);

  const notifySaveSettled = useCallback(() => {
    const waiters = saveSettledWaitersRef.current;
    saveSettledWaitersRef.current = [];
    waiters.forEach((resolve) => resolve());
  }, []);

  const waitForActiveSave = useCallback(() => {
    if (!inFlightRef.current) {
      return Promise.resolve();
    }

    return new Promise<void>((resolve) => {
      saveSettledWaitersRef.current.push(resolve);
    });
  }, []);

  const getDraft = useCallback(() => draftRef.current, []);
  const getAcknowledgedManuscript = useCallback(() => acknowledgedManuscriptRef.current, []);
  const getManuscriptGeneration = useCallback(() => manuscriptGenerationRef.current, []);
  const isSaveInFlight = useCallback(() => inFlightRef.current, []);

  const beginResolutionSave = useCallback(() => {
    if (inFlightRef.current) {
      return null;
    }
    const manuscriptGeneration = manuscriptGenerationRef.current;
    inFlightRef.current = true;
    setStatus("saving");
    return manuscriptGeneration;
  }, [setStatus]);

  const finishResolutionSave = useCallback(
    (manuscriptGeneration: number) => {
      if (manuscriptGenerationRef.current !== manuscriptGeneration) {
        return;
      }
      inFlightRef.current = false;
      notifySaveSettled();
    },
    [notifySaveSettled],
  );

  const adoptManuscript = useCallback((nextManuscript: Manuscript, nextRevision: number) => {
    acknowledgedManuscriptRef.current = nextManuscript;
    acknowledgedRevisionRef.current = nextRevision;
    draftRef.current = nextManuscript;
    setDraft(nextManuscript);
  }, []);

  const conflictHost = useMemo(
    () => ({
      getDraft,
      getAcknowledgedManuscript,
      getManuscriptGeneration,
      isSaveInFlight,
      beginResolutionSave,
      finishResolutionSave,
      adoptManuscript,
      setStatus,
    }),
    [
      adoptManuscript,
      beginResolutionSave,
      finishResolutionSave,
      getDraft,
      getAcknowledgedManuscript,
      getManuscriptGeneration,
      isSaveInFlight,
      setStatus,
    ],
  );

  const conflictResolution = useManuscriptConflictResolution(conflictHost);
  const { enterConflict, resetConflict } = conflictResolution;

  const saveCurrentDraft = useCallback(async (): Promise<boolean> => {
    if (inFlightRef.current || statusRef.current === "conflict") {
      return false;
    }

    const savingDraft = draftRef.current;
    const expectedRevision = acknowledgedRevisionRef.current;
    const manuscriptGeneration = manuscriptGenerationRef.current;
    inFlightRef.current = true;
    setStatus("saving");

    try {
      const saved = await mutateAsyncRef.current({
        manuscriptId: savingDraft.id,
        request: { manuscript: savingDraft, expectedRevision },
      });

      if (manuscriptGenerationRef.current !== manuscriptGeneration) {
        return false;
      }

      acknowledgedManuscriptRef.current = saved.manuscript;
      acknowledgedRevisionRef.current = saved.manuscriptRevision;
      if (draftRef.current === savingDraft) {
        draftRef.current = saved.manuscript;
        setDraft(saved.manuscript);
        setStatus("saved");
      } else {
        setStatus("editing");
      }
      return true;
    } catch (error) {
      if (manuscriptGenerationRef.current !== manuscriptGeneration) {
        return false;
      }

      if (
        error instanceof ApiRequestError &&
        error.status === 409 &&
        error.error.code === "MANUSCRIPT_REVISION_CONFLICT"
      ) {
        enterConflict(error);
        return false;
      }

      setStatus("error");
      return false;
    } finally {
      if (manuscriptGenerationRef.current === manuscriptGeneration) {
        inFlightRef.current = false;
        notifySaveSettled();
      }
    }
  }, [enterConflict, notifySaveSettled, setStatus]);

  const flush = useCallback(async (): Promise<boolean> => {
    while (true) {
      if (statusRef.current === "error" || statusRef.current === "conflict") {
        return false;
      }

      if (inFlightRef.current) {
        await waitForActiveSave();
        continue;
      }

      if (statusRef.current === "saved") {
        return true;
      }

      if (statusRef.current === "editing") {
        if (!(await saveCurrentDraft())) {
          return false;
        }
        continue;
      }

      await Promise.resolve();
    }
  }, [saveCurrentDraft, waitForActiveSave]);

  useEffect(() => {
    if (status !== "editing") {
      return;
    }

    const timeout = window.setTimeout(() => {
      void saveCurrentDraft();
    }, AUTOSAVE_IDLE_MS);

    return () => window.clearTimeout(timeout);
  }, [draft, saveCurrentDraft, status]);

  useEffect(() => {
    if (manuscript.id === acknowledgedManuscriptRef.current.id) {
      if (manuscriptRevision > acknowledgedRevisionRef.current && statusRef.current === "saved") {
        draftRef.current = manuscript;
        acknowledgedManuscriptRef.current = manuscript;
        acknowledgedRevisionRef.current = manuscriptRevision;
        setDraft(manuscript);
      }
      return;
    }

    manuscriptGenerationRef.current += 1;
    inFlightRef.current = false;
    notifySaveSettled();
    draftRef.current = manuscript;
    acknowledgedManuscriptRef.current = manuscript;
    acknowledgedRevisionRef.current = manuscriptRevision;
    setDraft(manuscript);
    resetConflict();
    setStatus("saved");
  }, [manuscript, manuscriptRevision, notifySaveSettled, resetConflict, setStatus]);

  const updateDraft = useCallback(
    (update: DraftUpdate) => {
      const nextDraft = typeof update === "function" ? update(draftRef.current) : update;
      draftRef.current = nextDraft;
      setDraft(nextDraft);

      if (statusRef.current === "conflict") {
        return;
      }

      if (statusRef.current !== "saving") {
        setStatus("editing");
      }
    },
    [setStatus],
  );

  const retry = useCallback((): Promise<boolean> => {
    if (statusRef.current === "error") {
      return saveCurrentDraft();
    }
    return Promise.resolve(false);
  }, [saveCurrentDraft]);

  return {
    draft,
    updateDraft,
    status,
    retry,
    flush,
    conflict: conflictResolution.conflict,
    conflictKind: conflictResolution.conflictKind,
    conflictComparison: conflictResolution.conflictComparison,
    isConflictDialogOpen: conflictResolution.isConflictDialogOpen,
    isComparingConflict: conflictResolution.isComparingConflict,
    isConflictCompareError: conflictResolution.isConflictCompareError,
    isResolvingConflict: conflictResolution.isResolvingConflict,
    isConflictResolutionError: conflictResolution.isConflictResolutionError,
    keepLocal: conflictResolution.keepLocal,
    retryKeepLocal: conflictResolution.retryKeepLocal,
    applyServer: conflictResolution.applyServer,
    retryConflictComparison: conflictResolution.retryConflictComparison,
    setConflictDialogVisibility: conflictResolution.setConflictDialogVisibility,
    openConflictDialog: conflictResolution.openConflictDialog,
  };
}
