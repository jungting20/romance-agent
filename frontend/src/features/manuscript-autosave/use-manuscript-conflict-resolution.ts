import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type {
  CompareManuscriptSceneResponse,
  ProjectWorkspaceResponse,
} from "@/app/infrastructure/api/contracts";
import {
  projectKeys,
  projectWorkspaceQueryOptions,
  useCompareManuscriptSceneMutation,
  useSaveManuscriptMutation,
} from "@/features/project-persistence";
import type { Manuscript } from "@/modules/manuscript";
import { updateSceneContent } from "@/modules/manuscript";

import { findLocalSceneAdditions, mergeLocalSceneAdditions } from "./manuscript-structure-conflict";

type ConflictAutosaveStatus = "saving" | "saved" | "conflict";
type ConflictKind = "scene-content" | "scene-structure";

export interface ManuscriptStructureConflict {
  serverManuscript: Manuscript;
  serverRevision: number;
}

type ConflictPayload =
  | { kind: "scene-content"; comparison: CompareManuscriptSceneResponse }
  | { kind: "scene-structure"; comparison: ManuscriptStructureConflict };

type ConflictState =
  | { phase: "idle" }
  | { phase: "loading"; kind: ConflictKind }
  | { phase: "load-error"; kind: ConflictKind }
  | ({ phase: "ready" | "resolving" | "resolve-error" } & ConflictPayload);

interface ManuscriptConflictHost {
  getDraft: () => Manuscript;
  getAcknowledgedManuscript: () => Manuscript;
  getManuscriptGeneration: () => number;
  isSaveInFlight: () => boolean;
  beginResolutionSave: () => number | null;
  finishResolutionSave: (manuscriptGeneration: number) => void;
  adoptManuscript: (manuscript: Manuscript, manuscriptRevision: number) => void;
  setStatus: (status: ConflictAutosaveStatus) => void;
}

function getConflictPayload(state: ConflictState): ConflictPayload | null {
  if (state.phase !== "ready" && state.phase !== "resolving" && state.phase !== "resolve-error") {
    return null;
  }

  return state.kind === "scene-content"
    ? { kind: state.kind, comparison: state.comparison }
    : { kind: state.kind, comparison: state.comparison };
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
  const [conflictState, setConflictStateValue] = useState<ConflictState>({ phase: "idle" });
  const conflictStateRef = useRef<ConflictState>({ phase: "idle" });
  const [isConflictDialogOpen, setConflictDialogOpen] = useState(false);
  const comparisonRequestRef = useRef(0);

  const setConflictState = useCallback((nextState: ConflictState) => {
    conflictStateRef.current = nextState;
    setConflictStateValue(nextState);
  }, []);

  const requestConflictComparison = useCallback(
    async (requestedKind?: ConflictKind) => {
      const base = host.getAcknowledgedManuscript();
      const local = host.getDraft();
      const kind =
        requestedKind ??
        (findLocalSceneAdditions(base, local).length > 0 ? "scene-structure" : "scene-content");
      const requestId = comparisonRequestRef.current + 1;
      const manuscriptGeneration = host.getManuscriptGeneration();
      comparisonRequestRef.current = requestId;
      setConflictDialogOpen(true);
      setConflictState({ phase: "loading", kind });

      try {
        if (kind === "scene-structure") {
          const latest = await queryClient.fetchQuery(
            projectWorkspaceQueryOptions(local.projectId),
          );
          if (
            comparisonRequestRef.current !== requestId ||
            host.getManuscriptGeneration() !== manuscriptGeneration
          ) {
            return;
          }
          setConflictState({
            phase: "ready",
            kind,
            comparison: {
              serverManuscript: latest.manuscript,
              serverRevision: latest.manuscriptRevision,
            },
          });
          return;
        }

        const scene = local.scenes.find(({ id }) => id === local.activeSceneId);
        if (!scene) {
          setConflictState({ phase: "load-error", kind });
          return;
        }
        const comparison = await compareAsyncRef.current({
          manuscriptId: local.id,
          request: { sceneId: scene.id, localContent: scene.content },
        });
        if (
          comparisonRequestRef.current !== requestId ||
          host.getManuscriptGeneration() !== manuscriptGeneration
        ) {
          return;
        }
        setConflictState({ phase: "ready", kind, comparison });
      } catch {
        if (
          comparisonRequestRef.current === requestId &&
          host.getManuscriptGeneration() === manuscriptGeneration
        ) {
          setConflictState({ phase: "load-error", kind });
        }
      }
    },
    [host, queryClient, setConflictState],
  );

  const enterConflict = useCallback(
    (error: ApiRequestError) => {
      setConflict(error);
      host.setStatus("conflict");
      void requestConflictComparison();
    },
    [host, requestConflictComparison],
  );

  const retryConflictComparison = useCallback(() => {
    const currentState = conflictStateRef.current;
    const kind = currentState.phase === "idle" ? undefined : currentState.kind;
    void requestConflictComparison(kind);
  }, [requestConflictComparison]);

  const openConflictDialog = useCallback(() => {
    if (conflict) {
      const currentState = conflictStateRef.current;
      const kind = currentState.phase === "idle" ? undefined : currentState.kind;
      void requestConflictComparison(kind);
    }
  }, [conflict, requestConflictComparison]);

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
    setConflictState({ phase: "idle" });
    setConflictDialogOpen(false);
  }, [setConflictState]);

  const keepLocal = useCallback(async () => {
    const currentState = conflictStateRef.current;
    const payload = getConflictPayload(currentState);
    if (!payload || currentState.phase === "resolving" || host.isSaveInFlight()) {
      return;
    }

    const manuscriptGeneration = host.beginResolutionSave();
    if (manuscriptGeneration === null) {
      return;
    }
    setConflictState({ phase: "resolving", ...payload });

    try {
      const resolvedManuscript =
        payload.kind === "scene-content"
          ? updateSceneContent(
              payload.comparison.serverManuscript,
              payload.comparison.sceneId,
              payload.comparison.localContent,
            )
          : mergeLocalSceneAdditions(
              host.getAcknowledgedManuscript(),
              host.getDraft(),
              payload.comparison.serverManuscript,
            );
      const saved = await saveAsyncRef.current({
        manuscriptId: resolvedManuscript.id,
        request: {
          manuscript: resolvedManuscript,
          expectedRevision: payload.comparison.serverRevision,
        },
      });
      if (host.getManuscriptGeneration() !== manuscriptGeneration) {
        return;
      }
      host.adoptManuscript(saved.manuscript, saved.manuscriptRevision);
      setConflict(null);
      setConflictState({ phase: "idle" });
      setConflictDialogOpen(false);
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
        host.setStatus("conflict");
        await requestConflictComparison(payload.kind);
      } else {
        setConflictDialogOpen(true);
        setConflictState({ phase: "resolve-error", ...payload });
        host.setStatus("conflict");
      }
    } finally {
      host.finishResolutionSave(manuscriptGeneration);
    }
  }, [host, requestConflictComparison, setConflictState]);

  const applyServer = useCallback(() => {
    const currentState = conflictStateRef.current;
    const payload = getConflictPayload(currentState);
    if (!payload || currentState.phase === "resolving" || host.isSaveInFlight()) {
      return;
    }

    const serverManuscript = payload.comparison.serverManuscript;
    host.adoptManuscript(serverManuscript, payload.comparison.serverRevision);
    setConflict(null);
    setConflictState({ phase: "idle" });
    setConflictDialogOpen(false);
    host.setStatus("saved");
    queryClient.setQueryData<ProjectWorkspaceResponse>(
      projectKeys.workspace(serverManuscript.projectId),
      (workspace) =>
        workspace
          ? {
              ...workspace,
              manuscript: serverManuscript,
              manuscriptRevision: payload.comparison.serverRevision,
            }
          : workspace,
    );
  }, [host, queryClient, setConflictState]);

  const payload = getConflictPayload(conflictState);

  return {
    conflict,
    conflictKind: conflictState.phase === "idle" ? null : conflictState.kind,
    conflictComparison: payload?.kind === "scene-content" ? payload.comparison : null,
    isConflictDialogOpen,
    isComparingConflict: conflictState.phase === "loading",
    isConflictCompareError: conflictState.phase === "load-error",
    isResolvingConflict: conflictState.phase === "resolving",
    isConflictResolutionError: conflictState.phase === "resolve-error",
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
