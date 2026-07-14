import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type {
  CompareManuscriptSceneResponse,
  ProjectWorkspaceResponse,
} from "@/app/infrastructure/api/contracts";
import {
  projectKeys,
  useCompareManuscriptSceneMutation,
  useSaveManuscriptMutation,
} from "@/features/project-persistence";
import type { Manuscript } from "@/modules/manuscript";
import { updateSceneContent } from "@/modules/manuscript";

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
  const queryClient = useQueryClient();
  const saveMutation = useSaveManuscriptMutation();
  const compareMutation = useCompareManuscriptSceneMutation();
  const mutateAsyncRef = useRef(saveMutation.mutateAsync);
  mutateAsyncRef.current = saveMutation.mutateAsync;
  const compareAsyncRef = useRef(compareMutation.mutateAsync);
  compareAsyncRef.current = compareMutation.mutateAsync;
  const [draft, setDraft] = useState(manuscript);
  const [status, setStatusState] = useState<ManuscriptAutosaveStatus>("saved");
  const [conflict, setConflict] = useState<ApiRequestError | null>(null);
  const [conflictComparison, setConflictComparison] =
    useState<CompareManuscriptSceneResponse | null>(null);
  const [isConflictDialogOpen, setConflictDialogOpen] = useState(false);
  const [isComparingConflict, setComparingConflict] = useState(false);
  const [isConflictCompareError, setConflictCompareError] = useState(false);
  const [isResolvingConflict, setResolvingConflict] = useState(false);
  const [isConflictResolutionError, setConflictResolutionError] = useState(false);
  const draftRef = useRef(manuscript);
  const acknowledgedManuscriptRef = useRef(manuscript);
  const acknowledgedRevisionRef = useRef(manuscriptRevision);
  const inFlightRef = useRef(false);
  const statusRef = useRef<ManuscriptAutosaveStatus>("saved");
  const conflictComparisonRef = useRef<CompareManuscriptSceneResponse | null>(null);
  const comparisonRequestRef = useRef(0);
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

  const requestConflictComparison = useCallback(
    async ({
      manuscriptId,
      sceneId,
      localContent,
    }: {
      manuscriptId: string;
      sceneId: string;
      localContent: string;
    }) => {
      const requestId = comparisonRequestRef.current + 1;
      const manuscriptGeneration = manuscriptGenerationRef.current;
      comparisonRequestRef.current = requestId;
      setConflictDialogOpen(true);
      setComparingConflict(true);
      setConflictCompareError(false);

      try {
        const comparison = await compareAsyncRef.current({
          manuscriptId,
          request: { sceneId, localContent },
        });
        if (
          comparisonRequestRef.current !== requestId ||
          manuscriptGenerationRef.current !== manuscriptGeneration
        ) {
          return;
        }
        conflictComparisonRef.current = comparison;
        setConflictComparison(comparison);
      } catch {
        if (
          comparisonRequestRef.current === requestId &&
          manuscriptGenerationRef.current === manuscriptGeneration
        ) {
          setConflictCompareError(true);
        }
      } finally {
        if (
          comparisonRequestRef.current === requestId &&
          manuscriptGenerationRef.current === manuscriptGeneration
        ) {
          setComparingConflict(false);
        }
      }
    },
    [],
  );

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
      setConflict(null);
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
        setConflict(error);
        setStatus("conflict");
        const currentDraft = draftRef.current;
        const scene = currentDraft.scenes.find(({ id }) => id === currentDraft.activeSceneId);
        if (scene) {
          void requestConflictComparison({
            manuscriptId: currentDraft.id,
            sceneId: scene.id,
            localContent: scene.content,
          });
        }
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
  }, [notifySaveSettled, requestConflictComparison, setStatus]);

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
    comparisonRequestRef.current += 1;
    inFlightRef.current = false;
    notifySaveSettled();
    draftRef.current = manuscript;
    acknowledgedManuscriptRef.current = manuscript;
    acknowledgedRevisionRef.current = manuscriptRevision;
    setDraft(manuscript);
    setConflict(null);
    conflictComparisonRef.current = null;
    setConflictComparison(null);
    setConflictDialogOpen(false);
    setComparingConflict(false);
    setConflictCompareError(false);
    setResolvingConflict(false);
    setConflictResolutionError(false);
    setStatus("saved");
  }, [manuscript, manuscriptRevision, notifySaveSettled, setStatus]);

  const updateDraft = useCallback(
    (update: DraftUpdate) => {
      const nextDraft = typeof update === "function" ? update(draftRef.current) : update;
      draftRef.current = nextDraft;
      setDraft(nextDraft);

      if (statusRef.current === "conflict") {
        return;
      }

      setConflict(null);

      if (statusRef.current !== "saving") {
        setStatus("editing");
      }
    },
    [setStatus],
  );

  const retry = useCallback(() => {
    if (statusRef.current === "error") {
      void saveCurrentDraft();
    }
  }, [saveCurrentDraft]);

  const retryConflictComparison = useCallback(() => {
    const currentDraft = draftRef.current;
    const scene = currentDraft.scenes.find(({ id }) => id === currentDraft.activeSceneId);
    if (scene) {
      void requestConflictComparison({
        manuscriptId: currentDraft.id,
        sceneId: scene.id,
        localContent: scene.content,
      });
    }
  }, [requestConflictComparison]);

  const keepLocal = useCallback(async () => {
    const comparison = conflictComparisonRef.current;
    if (!comparison || isResolvingConflict || inFlightRef.current) {
      return;
    }

    const resolvedManuscript = updateSceneContent(
      comparison.serverManuscript,
      comparison.sceneId,
      comparison.localContent,
    );
    const manuscriptGeneration = manuscriptGenerationRef.current;
    inFlightRef.current = true;
    setResolvingConflict(true);
    setConflictResolutionError(false);
    setStatus("saving");

    try {
      const saved = await mutateAsyncRef.current({
        manuscriptId: resolvedManuscript.id,
        request: {
          manuscript: resolvedManuscript,
          expectedRevision: comparison.serverRevision,
        },
      });
      if (manuscriptGenerationRef.current !== manuscriptGeneration) {
        return;
      }
      acknowledgedManuscriptRef.current = saved.manuscript;
      acknowledgedRevisionRef.current = saved.manuscriptRevision;
      draftRef.current = saved.manuscript;
      setDraft(saved.manuscript);
      setConflict(null);
      conflictComparisonRef.current = null;
      setConflictComparison(null);
      setConflictDialogOpen(false);
      setConflictCompareError(false);
      setConflictResolutionError(false);
      setStatus("saved");
    } catch (error) {
      if (manuscriptGenerationRef.current !== manuscriptGeneration) {
        return;
      }
      if (
        error instanceof ApiRequestError &&
        error.status === 409 &&
        error.error.code === "MANUSCRIPT_REVISION_CONFLICT"
      ) {
        setConflict(error);
        setConflictResolutionError(false);
        setStatus("conflict");
        await requestConflictComparison({
          manuscriptId: resolvedManuscript.id,
          sceneId: comparison.sceneId,
          localContent: comparison.localContent,
        });
      } else {
        setConflictDialogOpen(true);
        setConflictResolutionError(true);
        setStatus("conflict");
      }
    } finally {
      if (manuscriptGenerationRef.current === manuscriptGeneration) {
        inFlightRef.current = false;
        notifySaveSettled();
        setResolvingConflict(false);
      }
    }
  }, [isResolvingConflict, notifySaveSettled, requestConflictComparison, setStatus]);

  const applyServer = useCallback(() => {
    const comparison = conflictComparisonRef.current;
    if (!comparison || isResolvingConflict || inFlightRef.current) {
      return;
    }

    const serverManuscript = comparison.serverManuscript;
    draftRef.current = serverManuscript;
    acknowledgedManuscriptRef.current = serverManuscript;
    acknowledgedRevisionRef.current = comparison.serverRevision;
    setDraft(serverManuscript);
    setConflict(null);
    conflictComparisonRef.current = null;
    setConflictComparison(null);
    setConflictDialogOpen(false);
    setConflictCompareError(false);
    setConflictResolutionError(false);
    setStatus("saved");
    queryClient.setQueryData<ProjectWorkspaceResponse>(
      projectKeys.workspace(serverManuscript.projectId),
      (workspace) =>
        workspace
          ? {
              ...workspace,
              manuscript: serverManuscript,
              manuscriptRevision: comparison.serverRevision,
            }
          : workspace,
    );
  }, [isResolvingConflict, queryClient, setStatus]);

  const setConflictDialogVisibility = useCallback((open: boolean) => {
    if (!inFlightRef.current) {
      setConflictDialogOpen(open);
    }
  }, []);

  const openConflictDialog = useCallback(() => {
    if (statusRef.current === "conflict") {
      const currentDraft = draftRef.current;
      const scene = currentDraft.scenes.find(({ id }) => id === currentDraft.activeSceneId);
      if (scene) {
        void requestConflictComparison({
          manuscriptId: currentDraft.id,
          sceneId: scene.id,
          localContent: scene.content,
        });
      }
    }
  }, [requestConflictComparison]);

  return {
    draft,
    updateDraft,
    status,
    retry,
    flush,
    conflict,
    conflictComparison,
    isConflictDialogOpen,
    isComparingConflict,
    isConflictCompareError,
    isResolvingConflict,
    isConflictResolutionError,
    keepLocal,
    retryKeepLocal: keepLocal,
    applyServer,
    retryConflictComparison,
    setConflictDialogVisibility,
    openConflictDialog,
  };
}
