import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import { useSaveManuscriptMutation } from "@/features/project-persistence";
import type { Manuscript } from "@/modules/manuscript";

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
  const [conflict, setConflict] = useState<ApiRequestError | null>(null);
  const draftRef = useRef(manuscript);
  const acknowledgedManuscriptRef = useRef(manuscript);
  const acknowledgedRevisionRef = useRef(manuscriptRevision);
  const inFlightRef = useRef(false);
  const statusRef = useRef<ManuscriptAutosaveStatus>("saved");

  const setStatus = useCallback((nextStatus: ManuscriptAutosaveStatus) => {
    statusRef.current = nextStatus;
    setStatusState(nextStatus);
  }, []);

  const saveCurrentDraft = useCallback(async () => {
    if (inFlightRef.current || statusRef.current === "conflict") {
      return;
    }

    const savingDraft = draftRef.current;
    const expectedRevision = acknowledgedRevisionRef.current;
    inFlightRef.current = true;
    setStatus("saving");

    try {
      const saved = await mutateAsyncRef.current({
        manuscriptId: savingDraft.id,
        request: { manuscript: savingDraft, expectedRevision },
      });

      inFlightRef.current = false;
      acknowledgedManuscriptRef.current = saved.manuscript;
      acknowledgedRevisionRef.current = saved.manuscriptRevision;
      setConflict(null);
      setStatus(draftRef.current === savingDraft ? "saved" : "editing");
    } catch (error) {
      inFlightRef.current = false;
      if (
        error instanceof ApiRequestError &&
        error.status === 409 &&
        error.error.code === "MANUSCRIPT_REVISION_CONFLICT"
      ) {
        setConflict(error);
        setStatus("conflict");
        return;
      }

      setStatus("error");
    }
  }, [setStatus]);

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
      return;
    }

    draftRef.current = manuscript;
    acknowledgedManuscriptRef.current = manuscript;
    acknowledgedRevisionRef.current = manuscriptRevision;
    setDraft(manuscript);
    setConflict(null);
    setStatus("saved");
  }, [manuscript, manuscriptRevision, setStatus]);

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

  return { draft, updateDraft, status, retry, conflict };
}
