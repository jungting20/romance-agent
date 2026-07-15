import { useCallback, useRef, useState } from "react";
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

type ConflictAutosaveStatus = "saving" | "saved" | "conflict";

interface ManuscriptConflictHost {
  getDraft: () => Manuscript;
  getManuscriptGeneration: () => number;
  isSaveInFlight: () => boolean;
  beginResolutionSave: () => number | null;
  finishResolutionSave: (manuscriptGeneration: number) => void;
  adoptManuscript: (manuscript: Manuscript, manuscriptRevision: number) => void;
  setStatus: (status: ConflictAutosaveStatus) => void;
}

export function useManuscriptConflictResolution(host: ManuscriptConflictHost) {
  const queryClient = useQueryClient();
  const saveMutation = useSaveManuscriptMutation();
  const compareMutation = useCompareManuscriptSceneMutation();
  const saveAsyncRef = useRef(saveMutation.mutateAsync);
  saveAsyncRef.current = saveMutation.mutateAsync;
  const compareAsyncRef = useRef(compareMutation.mutateAsync);
  compareAsyncRef.current = compareMutation.mutateAsync;

  const [conflict, setConflict] = useState<ApiRequestError | null>(null);
  const [conflictComparison, setConflictComparison] =
    useState<CompareManuscriptSceneResponse | null>(null);
  const [isConflictDialogOpen, setConflictDialogOpen] = useState(false);
  const [isComparingConflict, setComparingConflict] = useState(false);
  const [isConflictCompareError, setConflictCompareError] = useState(false);
  const [isResolvingConflict, setResolvingConflict] = useState(false);
  const [isConflictResolutionError, setConflictResolutionError] = useState(false);
  const conflictComparisonRef = useRef<CompareManuscriptSceneResponse | null>(null);
  const comparisonRequestRef = useRef(0);

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
      const manuscriptGeneration = host.getManuscriptGeneration();
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
          host.getManuscriptGeneration() !== manuscriptGeneration
        ) {
          return;
        }
        conflictComparisonRef.current = comparison;
        setConflictComparison(comparison);
      } catch {
        if (
          comparisonRequestRef.current === requestId &&
          host.getManuscriptGeneration() === manuscriptGeneration
        ) {
          setConflictCompareError(true);
        }
      } finally {
        if (
          comparisonRequestRef.current === requestId &&
          host.getManuscriptGeneration() === manuscriptGeneration
        ) {
          setComparingConflict(false);
        }
      }
    },
    [host],
  );

  const requestLatestDraftComparison = useCallback(() => {
    const currentDraft = host.getDraft();
    const scene = currentDraft.scenes.find(({ id }) => id === currentDraft.activeSceneId);
    if (!scene) {
      return;
    }
    void requestConflictComparison({
      manuscriptId: currentDraft.id,
      sceneId: scene.id,
      localContent: scene.content,
    });
  }, [host, requestConflictComparison]);

  const enterConflict = useCallback(
    (error: ApiRequestError) => {
      setConflict(error);
      host.setStatus("conflict");
      requestLatestDraftComparison();
    },
    [host, requestLatestDraftComparison],
  );

  const retryConflictComparison = useCallback(() => {
    requestLatestDraftComparison();
  }, [requestLatestDraftComparison]);

  const openConflictDialog = useCallback(() => {
    if (conflict) {
      requestLatestDraftComparison();
    }
  }, [conflict, requestLatestDraftComparison]);

  const setConflictDialogVisibility = useCallback(
    (open: boolean) => {
      if (!host.isSaveInFlight()) {
        setConflictDialogOpen(open);
      }
    },
    [host],
  );

  const resetConflict = useCallback(() => {
    comparisonRequestRef.current += 1;
    setConflict(null);
    conflictComparisonRef.current = null;
    setConflictComparison(null);
    setConflictDialogOpen(false);
    setComparingConflict(false);
    setConflictCompareError(false);
    setResolvingConflict(false);
    setConflictResolutionError(false);
  }, []);

  const keepLocal = useCallback(async () => {
    const comparison = conflictComparisonRef.current;
    if (!comparison || isResolvingConflict || host.isSaveInFlight()) {
      return;
    }

    const resolvedManuscript = updateSceneContent(
      comparison.serverManuscript,
      comparison.sceneId,
      comparison.localContent,
    );
    const manuscriptGeneration = host.beginResolutionSave();
    if (manuscriptGeneration === null) {
      return;
    }
    setResolvingConflict(true);
    setConflictResolutionError(false);

    try {
      const saved = await saveAsyncRef.current({
        manuscriptId: resolvedManuscript.id,
        request: {
          manuscript: resolvedManuscript,
          expectedRevision: comparison.serverRevision,
        },
      });
      if (host.getManuscriptGeneration() !== manuscriptGeneration) {
        return;
      }
      host.adoptManuscript(saved.manuscript, saved.manuscriptRevision);
      setConflict(null);
      conflictComparisonRef.current = null;
      setConflictComparison(null);
      setConflictDialogOpen(false);
      setConflictCompareError(false);
      setConflictResolutionError(false);
      host.setStatus("saved");
    } catch (error) {
      if (host.getManuscriptGeneration() !== manuscriptGeneration) {
        return;
      }
      if (
        error instanceof ApiRequestError &&
        error.status === 409 &&
        error.error.code === "MANUSCRIPT_REVISION_CONFLICT"
      ) {
        setConflict(error);
        setConflictResolutionError(false);
        host.setStatus("conflict");
        await requestConflictComparison({
          manuscriptId: resolvedManuscript.id,
          sceneId: comparison.sceneId,
          localContent: comparison.localContent,
        });
      } else {
        setConflictDialogOpen(true);
        setConflictResolutionError(true);
        host.setStatus("conflict");
      }
    } finally {
      host.finishResolutionSave(manuscriptGeneration);
      if (host.getManuscriptGeneration() === manuscriptGeneration) {
        setResolvingConflict(false);
      }
    }
  }, [host, isResolvingConflict, requestConflictComparison]);

  const applyServer = useCallback(() => {
    const comparison = conflictComparisonRef.current;
    if (!comparison || isResolvingConflict || host.isSaveInFlight()) {
      return;
    }

    const serverManuscript = comparison.serverManuscript;
    host.adoptManuscript(serverManuscript, comparison.serverRevision);
    setConflict(null);
    conflictComparisonRef.current = null;
    setConflictComparison(null);
    setConflictDialogOpen(false);
    setConflictCompareError(false);
    setConflictResolutionError(false);
    host.setStatus("saved");
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
  }, [host, isResolvingConflict, queryClient]);

  return {
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
    enterConflict,
    resetConflict,
  };
}
