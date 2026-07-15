# Manuscript Autosave Responsibility Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the complete `useManuscriptAutosave` public contract while extracting revision-conflict comparison, presentation state, resolution, retry, and reset behavior into one focused internal hook.

**Architecture:** `useManuscriptAutosave` remains the single owner of draft, acknowledged revision, save serialization, flush waiters, idle autosave, and manuscript generation. A new colocated `useManuscriptConflictResolution` hook owns conflict-specific state and asynchronous operations and collaborates through a narrow operation-based host contract. Existing hook tests remain the behavior-preserving regression suite.

**Tech Stack:** React 19 hooks, TypeScript, TanStack Query v5, Vitest, Testing Library, MSW, pnpm, mise.

## Global Constraints

- Use the project-scoped `frontend` sub-agent defined in `.codex/agents/frontend.toml` for implementation.
- Preserve the exported `useManuscriptAutosave` return fields, types, and semantics exactly.
- Preserve the 800 ms idle-save deadline.
- Preserve save serialization, `flush`, retry, canonical response adoption, conflict suspension, comparison retry, keep-local, apply-server, and manuscript-switch race behavior.
- Keep draft, acknowledged revision, save-in-flight, flush waiters, and manuscript generation owned only by `useManuscriptAutosave`.
- Move conflict comparison, conflict presentation state, conflict resolution, conflict retry, and conflict reset into one internal colocated hook.
- Do not change the writing-workspace page or any consumer.
- Do not change domain documents, OpenAPI, MSW, API adapters, backend files, package manifests, lockfiles, product copy, or unrelated frontend files.
- Do not add dependencies.
- Do not weaken, delete, skip, or rewrite the meaning of any existing focused test assertion.
- No domain-document update is required because domain meaning and behavior remain unchanged.
- Run the focused hook test, `mise exec -- pnpm check`, and `mise exec -- pnpm build` from `frontend/`.

---

## File Structure

- Create `frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`: internal conflict workflow hook and its operation-based host contract.
- Modify `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`: retain public orchestration and compose the extracted conflict hook.
- Modify `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx` only if a new observable regression case is required; existing assertions remain unchanged.
- Verify unchanged `frontend/src/pages/writing-workspace/writing-workspace-page.tsx` and `frontend/src/features/manuscript-autosave/index.ts`.

---

### Task 1: Extract the Manuscript Conflict Workflow

**Files:**
- Create: `frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`
- Modify: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts`
- Test only when required: `frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx`
- Verify unchanged: `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`
- Verify unchanged: `frontend/src/features/manuscript-autosave/index.ts`

**Interfaces:**
- Consumes: latest draft and manuscript-generation readers; shared save-in-flight begin/finish operations; acknowledged manuscript adoption; public status setter.
- Produces: `useManuscriptConflictResolution(host)` with conflict state/actions plus internal `enterConflict(error)` and `resetConflict()` operations.
- Public API: the return object from `useManuscriptAutosave` remains byte-for-byte field-compatible with the existing consumer.

- [ ] **Step 1: Read the authoritative context before editing**

Read in full:

```text
AGENTS.md
frontend/AGENTS.md
frontend/docs/frontend-coding-rules.md
docs/domains/manuscript.md
docs/domains/projects.md
.codex/agents/frontend.toml
frontend/src/features/project-persistence/api/project-queries.ts
frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts
frontend/src/features/manuscript-autosave/use-manuscript-autosave.test.tsx
frontend/src/pages/writing-workspace/writing-workspace-page.tsx
```

Confirm that no other agent is editing either owned implementation file before
continuing.

- [ ] **Step 2: Establish the green characterization baseline**

Run from `frontend/`:

```bash
mise exec -- pnpm exec vitest run src/features/manuscript-autosave/use-manuscript-autosave.test.tsx
```

Expected: the existing 16 tests pass with no failures. This is a pure refactor
phase under an existing behavior suite; do not add production behavior to make
an already-green test change meaning.

Capture the public return fields before editing:

```text
draft
updateDraft
status
retry
flush
conflict
conflictComparison
isConflictDialogOpen
isComparingConflict
isConflictCompareError
isResolvingConflict
isConflictResolutionError
keepLocal
retryKeepLocal
applyServer
retryConflictComparison
setConflictDialogVisibility
openConflictDialog
```

- [ ] **Step 3: Create the internal conflict-hook contract**

Create
`frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts`
with this contract at the top of the file:

```ts
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
  // Conflict-specific state, refs, mutations, and callbacks move here.
}
```

The file is internal: do not export it from
`frontend/src/features/manuscript-autosave/index.ts`.

- [ ] **Step 4: Move conflict state and request identity into the new hook**

Inside `useManuscriptConflictResolution`, own exactly these state values and
refs currently held by the public hook:

```ts
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
```

Move `requestConflictComparison` into this hook. It must:

```ts
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
```

The frontend agent may destructure stable host callbacks to make dependency
arrays precise, but must not omit a real dependency or reintroduce deadline
restarts through unstable callbacks.

- [ ] **Step 5: Move conflict entry, retry, and reset operations**

Implement these internal operations in the conflict hook:

```ts
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
```

`openConflictDialog` must remain gated by unresolved conflict state. If using
the stored error object rather than the public status ref, preserve the same
observable rule: it does nothing after conflict resolution or reset.

- [ ] **Step 6: Move keep-local and apply-server resolution**

Move `keepLocal` into the conflict hook and preserve this control sequence:

```ts
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
```

Move `applyServer` and preserve query-cache behavior:

```ts
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
```

Return conflict state/actions plus `enterConflict` and `resetConflict`. Preserve
`retryKeepLocal` as the same `keepLocal` function reference:

```ts
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
```

- [ ] **Step 7: Compose the conflict hook from the public autosave hook**

In `use-manuscript-autosave.ts`, remove conflict-only imports, state, refs,
mutations, and callbacks. Keep the ordinary save mutation and every autosave
owner listed in the design.

Add stable host operations before calling the conflict hook:

```ts
const getDraft = useCallback(() => draftRef.current, []);
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
```

Compose the new hook with a memoized host object so conflict callbacks remain
stable:

```ts
const conflictHost = useMemo(
  () => ({
    getDraft,
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
    getManuscriptGeneration,
    isSaveInFlight,
    setStatus,
  ],
);

const conflictResolution = useManuscriptConflictResolution(conflictHost);
```

Add `useMemo` and the new internal hook import. Do not add the internal hook to
the feature index.

- [ ] **Step 8: Delegate conflict entry and session reset**

In ordinary-save conflict handling, replace the inline conflict state and
comparison request with:

```ts
if (
  error instanceof ApiRequestError &&
  error.status === 409 &&
  error.error.code === "MANUSCRIPT_REVISION_CONFLICT"
) {
  conflictResolution.enterConflict(error);
  return false;
}
```

Keep `ApiRequestError` imported in the public hook because it still classifies
ordinary save failures.

In the manuscript-ID reset effect, retain generation increment, in-flight
reset, waiter notification, draft/acknowledged replacement, and status reset.
Replace all conflict-specific clearing with:

```ts
conflictResolution.resetConflict();
```

Use stable destructured `enterConflict` and `resetConflict` callbacks in
dependencies rather than depending on the complete result object if required
to avoid effect/callback churn.

- [ ] **Step 9: Reassemble the unchanged public return shape**

Return autosave-owned fields and the conflict presentation/actions with the
same names:

```ts
return {
  draft,
  updateDraft,
  status,
  retry,
  flush,
  conflict: conflictResolution.conflict,
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
```

Do not edit the page consumer or feature index.

- [ ] **Step 10: Run the focused regression suite**

Run from `frontend/`:

```bash
mise exec -- pnpm exec vitest run src/features/manuscript-autosave/use-manuscript-autosave.test.tsx
```

Expected: all 16 tests pass. If a test fails, preserve its assertion and repair
the extracted ownership, dependency stability, request identity, generation
check, or state transition that caused the regression.

- [ ] **Step 11: Verify consumer and scope invariants**

Run from repository root:

```bash
git diff --exit-code -- frontend/src/pages/writing-workspace/writing-workspace-page.tsx
git diff --exit-code -- frontend/src/features/manuscript-autosave/index.ts
git diff --check
git diff --name-only
```

Expected changed paths are limited to:

```text
frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts
frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts
```

The existing test file may also appear only if an observable regression test
was required. No other path is allowed.

- [ ] **Step 12: Run full frontend verification**

Run from `frontend/`:

```bash
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: both commands exit 0 with no errors.

- [ ] **Step 13: Commit the refactor**

From repository root:

```bash
git add \
  frontend/src/features/manuscript-autosave/use-manuscript-autosave.ts \
  frontend/src/features/manuscript-autosave/use-manuscript-conflict-resolution.ts
git commit -m "refactor(frontend): split manuscript conflict workflow"
```

If the focused test file changed for a justified new observable regression,
include it in the same commit and report why.

- [ ] **Step 14: Self-review and handoff**

Confirm and report:

```text
[ ] public return fields and semantics are unchanged
[ ] 800 ms idle deadline is unchanged
[ ] ordinary save serialization and flush remain in the public hook
[ ] conflict state and operations are owned by the conflict hook
[ ] draft/revision/in-flight/generation state is not duplicated
[ ] stale comparison and manuscript-generation checks remain
[ ] keep-local and apply-server behavior remains
[ ] page and feature index are unchanged
[ ] focused test result is 16/16
[ ] pnpm check passes
[ ] pnpm build passes
[ ] no domain or OpenAPI update is required
```

Return the changed files, behavior-preservation summary, exact commands and
results, domain-document impact, OpenAPI impact, and any remaining risk to the
main agent.

