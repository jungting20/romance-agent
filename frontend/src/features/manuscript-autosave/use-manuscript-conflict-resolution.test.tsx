import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type {
  CompareManuscriptSceneResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
  SaveManuscriptResponse,
} from "@/app/infrastructure/api/contracts";
import { findMockWorkspace } from "@/mocks/data/project-workspaces";
import { server } from "@/mocks/server";
import { updateSceneContent, updateSceneTitle } from "@/modules/manuscript";

import { useManuscriptAutosave } from "./use-manuscript-autosave";

function getWorkspace(): ProjectWorkspaceResponse {
  const workspace = findMockWorkspace("silver-garden");
  if (!workspace) throw new Error("Expected the seeded workspace");
  return workspace;
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return function TestQueryProvider({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

async function flushPromises() {
  await act(async () => {
    for (let index = 0; index < 10; index += 1) await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

test("keeps the conflict-time local title and content on the latest server scene", async () => {
  const workspace = getWorkspace();
  const activeScene = workspace.manuscript.scenes[0]!;
  const serverManuscript = {
    ...workspace.manuscript,
    scenes: [
      {
        ...activeScene,
        title: "서버 최신 제목",
        content: "서버 최신 본문",
        relatedCharacterIds: ["server-character"],
      },
    ],
  };
  const requests: SaveManuscriptRequest[] = [];
  server.use(
    http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
      const body = (await request.json()) as SaveManuscriptRequest;
      requests.push(body);
      if (requests.length === 1) {
        return HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        );
      }
      return HttpResponse.json({
        manuscript: body.manuscript,
        manuscriptRevision: 8,
        projectActivity: {
          projectId: workspace.project.id,
          updatedAt: "2026-07-22T01:00:00.000Z",
        },
      } satisfies SaveManuscriptResponse);
    }),
    http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
      const body = (await request.json()) as { sceneId: string; localContent: string };
      return HttpResponse.json({
        sceneId: body.sceneId,
        serverRevision: 7,
        localContent: body.localContent,
        serverContent: "서버 최신 본문",
        serverManuscript,
        rows: [],
      } satisfies CompareManuscriptSceneResponse);
    }),
  );
  const { result } = renderHook(
    () =>
      useManuscriptAutosave({
        manuscript: workspace.manuscript,
        manuscriptRevision: workspace.manuscriptRevision,
      }),
    { wrapper: createWrapper() },
  );
  const localDraft = updateSceneContent(
    updateSceneTitle(workspace.manuscript, activeScene.id, "로컬 제목"),
    activeScene.id,
    "로컬 본문",
  );

  act(() => result.current.updateDraft(localDraft));
  await act(async () => vi.advanceTimersByTimeAsync(800));
  await flushPromises();
  await act(async () => result.current.keepLocal());
  await flushPromises();

  expect(requests).toHaveLength(2);
  expect(requests[1]!.expectedRevision).toBe(7);
  expect(requests[1]!.manuscript.scenes[0]).toMatchObject({
    title: "로컬 제목",
    content: "로컬 본문",
    relatedCharacterIds: ["server-character"],
  });
  expect(result.current.draft.scenes[0]).toMatchObject({
    title: "로컬 제목",
    content: "로컬 본문",
    relatedCharacterIds: ["server-character"],
  });
});
