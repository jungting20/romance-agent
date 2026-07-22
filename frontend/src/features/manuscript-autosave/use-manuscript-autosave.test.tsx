import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { PropsWithChildren } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type {
  CompareManuscriptSceneResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
  SaveManuscriptResponse,
} from "@/app/infrastructure/api/contracts";
import { projectKeys } from "@/features/project-persistence";
import { findMockWorkspace } from "@/mocks/data/project-workspaces";
import { server } from "@/mocks/server";
import { addScene, updateSceneContent } from "@/modules/manuscript";

import { useManuscriptAutosave } from "./use-manuscript-autosave";

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return function TestQueryProvider({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function getWorkspace(): ProjectWorkspaceResponse {
  const workspace = findMockWorkspace("silver-garden");
  if (!workspace) {
    throw new Error("Expected the seeded workspace");
  }
  return workspace;
}

function editActiveScene(workspace: ProjectWorkspaceResponse, content: string) {
  return updateSceneContent(workspace.manuscript, workspace.manuscript.activeSceneId, content);
}

async function flushPromises() {
  await act(async () => {
    for (let index = 0; index < 10; index += 1) {
      await Promise.resolve();
    }
  });
}

function createServerManuscript(
  workspace: ProjectWorkspaceResponse,
  sceneId = "server-only-scene",
  chapterNumber = 3,
) {
  return {
    ...workspace.manuscript,
    scenes: [
      workspace.manuscript.scenes[0],
      {
        ...workspace.manuscript.scenes[0],
        id: sceneId,
        title: "서버에서 추가된 장면",
        chapterNumber,
      },
    ],
  };
}

function installStructuralConflictHandlers({
  workspace,
  serverManuscript,
  saveRequests,
  resolveSave = true,
}: {
  workspace: ProjectWorkspaceResponse;
  serverManuscript: ProjectWorkspaceResponse["manuscript"];
  saveRequests: SaveManuscriptRequest[];
  resolveSave?: boolean;
}) {
  server.use(
    http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
      const body = (await request.json()) as SaveManuscriptRequest;
      saveRequests.push(body);
      if (saveRequests.length === 1 || !resolveSave) {
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
          updatedAt: "2026-07-14T04:00:00Z",
        },
      } satisfies SaveManuscriptResponse);
    }),
    http.get("/api/projects/:projectId/workspace", () =>
      HttpResponse.json({
        ...workspace,
        manuscript: serverManuscript,
        manuscriptRevision: 7,
      }),
    ),
  );
}

describe("useManuscriptAutosave", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("waits for exactly 800 ms of idle time before saving once", async () => {
    const requests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        requests.push((await request.json()) as SaveManuscriptRequest);
        const workspace = getWorkspace();
        return HttpResponse.json({
          manuscript: requests[0].manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: workspace.project.id,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
    );
    const workspace = getWorkspace();
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(projectKeys.workspace(workspace.project.id), workspace);
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "800밀리초 뒤 저장")));
    expect(result.current.status).toBe("editing");

    await act(async () => vi.advanceTimersByTimeAsync(799));
    expect(requests).toHaveLength(0);

    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(requests).toHaveLength(1);
    expect(requests[0]).toMatchObject({ expectedRevision: 1 });
    expect(requests[0].manuscript.scenes[0].content).toBe("800밀리초 뒤 저장");
  });

  test("does not restart the idle deadline after an unrelated rerender", async () => {
    const requests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
    );
    const workspace = getWorkspace();
    const queryClient = createTestQueryClient();
    const { result, rerender } = renderHook(
      ({ unrelated }: { unrelated: number }) => {
        void unrelated;
        return useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        });
      },
      {
        initialProps: { unrelated: 0 },
        wrapper: createWrapper(queryClient),
      },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "원래 마감에 저장")));
    await act(async () => vi.advanceTimersByTimeAsync(400));
    rerender({ unrelated: 1 });

    await act(async () => vi.advanceTimersByTimeAsync(399));
    expect(requests).toHaveLength(0);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(requests).toHaveLength(1);
  });

  test("adopts a canonicalized save response when no newer local edit exists", async () => {
    const workspace = getWorkspace();
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        return HttpResponse.json({
          manuscript: updateSceneContent(
            body.manuscript,
            body.manuscript.activeSceneId,
            "서버가 정규화한 원고",
          ),
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "정규화 전 원고")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();

    expect(result.current.status).toBe("saved");
    expect(result.current.draft.scenes[0].content).toBe("서버가 정규화한 원고");
  });

  test("adopts a newer same-manuscript workspace update while clean", () => {
    const workspace = getWorkspace();
    const incomingManuscript = editActiveScene(workspace, "다른 쿼리가 받은 최신 원고");
    const { result, rerender } = renderHook(
      ({ manuscript, manuscriptRevision }) =>
        useManuscriptAutosave({ manuscript, manuscriptRevision }),
      {
        initialProps: {
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        },
        wrapper: createWrapper(createTestQueryClient()),
      },
    );

    rerender({ manuscript: incomingManuscript, manuscriptRevision: 2 });

    expect(result.current.status).toBe("saved");
    expect(result.current.draft).toBe(incomingManuscript);
  });

  test("preserves a dirty local draft when a newer same-manuscript workspace update arrives", () => {
    const workspace = getWorkspace();
    const incomingManuscript = editActiveScene(workspace, "쿼리의 최신 원고");
    const localDraft = editActiveScene(workspace, "아직 저장하지 않은 로컬 원고");
    const { result, rerender } = renderHook(
      ({ manuscript, manuscriptRevision }) =>
        useManuscriptAutosave({ manuscript, manuscriptRevision }),
      {
        initialProps: {
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        },
        wrapper: createWrapper(createTestQueryClient()),
      },
    );

    act(() => result.current.updateDraft(localDraft));
    rerender({ manuscript: incomingManuscript, manuscriptRevision: 2 });

    expect(result.current.status).toBe("editing");
    expect(result.current.draft).toBe(localDraft);
  });

  test("retains newer edits during an active save and schedules a serial follow-up", async () => {
    const requests: SaveManuscriptRequest[] = [];
    let releaseFirstSave!: (response: SaveManuscriptResponse) => void;
    const firstSave = new Promise<SaveManuscriptResponse>((resolve) => {
      releaseFirstSave = resolve;
    });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        if (requests.length === 1) {
          return HttpResponse.json(await firstSave);
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 3,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:01:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
    );
    const workspace = getWorkspace();
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(projectKeys.workspace(workspace.project.id), workspace);
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "첫 번째 초안")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    expect(requests).toHaveLength(1);
    expect(result.current.status).toBe("saving");

    act(() => result.current.updateDraft(editActiveScene(workspace, "더 새로운 초안")));
    expect(result.current.draft.scenes[0].content).toBe("더 새로운 초안");
    await act(async () => vi.advanceTimersByTimeAsync(800));
    expect(requests).toHaveLength(1);

    await act(async () => {
      releaseFirstSave({
        manuscript: requests[0].manuscript,
        manuscriptRevision: 2,
        projectActivity: {
          projectId: workspace.project.id,
          updatedAt: "2026-07-14T03:00:00.000Z",
        },
      });
      await Promise.resolve();
    });
    await flushPromises();
    expect(result.current.status).toBe("editing");
    expect(result.current.draft.scenes[0].content).toBe("더 새로운 초안");

    await act(async () => vi.advanceTimersByTimeAsync(799));
    expect(requests).toHaveLength(1);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(requests).toHaveLength(2);
    expect(requests[1]).toMatchObject({ expectedRevision: 2 });
    expect(requests[1].manuscript.scenes[0].content).toBe("더 새로운 초안");

    await flushPromises();
    expect(result.current.status).toBe("saved");
    expect(
      queryClient.getQueryData<ProjectWorkspaceResponse>(
        projectKeys.workspace(workspace.project.id),
      ),
    ).toMatchObject({
      manuscriptRevision: 3,
      manuscript: { scenes: [{ content: "더 새로운 초안" }] },
    });
  });

  test("keeps a failed draft and retries a non-conflict error immediately", async () => {
    let requestCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        requestCount += 1;
        const body = (await request.json()) as SaveManuscriptRequest;
        if (requestCount === 1) {
          return HttpResponse.json(
            { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
            { status: 500 },
          );
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
    );
    const workspace = getWorkspace();
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(projectKeys.workspace(workspace.project.id), workspace);
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "실패해도 남는 초안")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    expect(result.current.status).toBe("error");
    expect(result.current.draft.scenes[0].content).toBe("실패해도 남는 초안");

    act(() => result.current.retry());
    await flushPromises();
    expect(requestCount).toBe(2);
    expect(result.current.status).toBe("saved");
  });

  test("suspends autosave and exposes revision conflicts", async () => {
    let requestCount = 0;
    let compareCount = 0;
    const workspace = getWorkspace();
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () => {
        requestCount += 1;
        return HttpResponse.json(
          {
            code: "MANUSCRIPT_REVISION_CONFLICT",
            message: "다른 위치에서 원고가 먼저 수정되었습니다.",
            fieldErrors: [],
          },
          { status: 409 },
        );
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        compareCount += 1;
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json(createComparison(workspace, body.localContent, 2));
      }),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "충돌한 로컬 초안")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();

    expect(result.current.status).toBe("conflict");
    expect(result.current.conflict?.error.code).toBe("MANUSCRIPT_REVISION_CONFLICT");
    expect(result.current.draft.scenes[0].content).toBe("충돌한 로컬 초안");
    expect(compareCount).toBe(1);
    expect(result.current.conflictComparison?.localContent).toBe("충돌한 로컬 초안");

    act(() => result.current.updateDraft(editActiveScene(workspace, "충돌 뒤의 더 최신 초안")));
    expect(result.current.status).toBe("conflict");
    expect(result.current.draft.scenes[0].content).toBe("충돌 뒤의 더 최신 초안");
    await act(async () => vi.advanceTimersByTimeAsync(5_000));
    expect(result.current.status).toBe("conflict");
    expect(requestCount).toBe(1);
  });

  test("compares the latest active local scene when an in-flight save returns a conflict", async () => {
    const workspace = getWorkspace();
    const secondScene = {
      ...workspace.manuscript.scenes[0],
      id: "latest-active-scene",
      title: "새 활성 장면",
      content: "두 번째 장면의 이전 내용",
    };
    const manuscript = {
      ...workspace.manuscript,
      scenes: [...workspace.manuscript.scenes, secondScene],
    };
    let releaseSave!: () => void;
    const saveBarrier = new Promise<void>((resolve) => {
      releaseSave = resolve;
    });
    const comparisons: Array<{ sceneId: string; localContent: string }> = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async () => {
        await saveBarrier;
        return HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        );
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { sceneId: string; localContent: string };
        comparisons.push(body);
        return HttpResponse.json(
          createComparisonForScene(manuscript, body.sceneId, body.localContent, 2),
        );
      }),
    );
    const { result } = renderHook(
      () => useManuscriptAutosave({ manuscript, manuscriptRevision: 1 }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() =>
      result.current.updateDraft(
        updateSceneContent(manuscript, manuscript.activeSceneId, "저장 중인 첫 장면"),
      ),
    );
    await act(async () => vi.advanceTimersByTimeAsync(800));
    act(() =>
      result.current.updateDraft((current) => ({
        ...updateSceneContent(current, secondScene.id, "PUT 대기 중 고친 최신 장면"),
        activeSceneId: secondScene.id,
      })),
    );
    await act(async () => {
      releaseSave();
      await Promise.resolve();
    });
    await flushPromises();

    expect(comparisons).toEqual([
      { sceneId: secondScene.id, localContent: "PUT 대기 중 고친 최신 장면" },
    ]);
    expect(result.current.conflictComparison?.sceneId).toBe(secondScene.id);
  });

  test("keeps the local scene on the latest server manuscript and saves at the server revision", async () => {
    const workspace = getWorkspace();
    const serverManuscript = {
      ...workspace.manuscript,
      scenes: [
        { ...workspace.manuscript.scenes[0], content: "서버의 활성 장면" },
        {
          ...workspace.manuscript.scenes[0],
          id: "server-only-scene",
          title: "서버에서 추가된 장면",
          content: "보존해야 하는 서버 변경",
        },
      ],
    };
    const saveRequests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        saveRequests.push(body);
        if (saveRequests.length === 1) {
          return HttpResponse.json(
            { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
            { status: 409 },
          );
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 8,
          projectActivity: { projectId: workspace.project.id, updatedAt: "2026-07-14T04:00:00Z" },
        } satisfies SaveManuscriptResponse);
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { localContent: string };
        return HttpResponse.json({
          ...createComparison(workspace, body.localContent, 7),
          serverManuscript,
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "유지할 로컬 장면")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    await act(async () => {
      await Promise.all([result.current.keepLocal(), result.current.keepLocal()]);
    });
    await flushPromises();

    expect(saveRequests).toHaveLength(2);
    expect(saveRequests[1].expectedRevision).toBe(7);
    expect(saveRequests[1].manuscript.scenes[0].content).toBe("유지할 로컬 장면");
    expect(saveRequests[1].manuscript.scenes[1]).toMatchObject({
      id: "server-only-scene",
      content: "보존해야 하는 서버 변경",
    });
    expect(result.current.status).toBe("saved");
  });

  test("merges a local-only scene onto the refreshed server manuscript", async () => {
    const workspace = getWorkspace();
    const localDraft = addScene(workspace.manuscript, "local-new-scene");
    const serverManuscript = createServerManuscript(workspace);
    const saveRequests: SaveManuscriptRequest[] = [];
    installStructuralConflictHandlers({ workspace, serverManuscript, saveRequests });
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(localDraft));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();

    expect(result.current.conflictKind).toBe("scene-structure");
    await act(async () => result.current.keepLocal());
    await flushPromises();

    expect(saveRequests[1]?.expectedRevision).toBe(7);
    expect(saveRequests[1]?.manuscript.scenes.map(({ id }) => id)).toEqual([
      "silver-garden-scene-1",
      "server-only-scene",
      "local-new-scene",
    ]);
    expect(result.current.status).toBe("saved");
  });

  test("applies the refreshed server manuscript for a structural conflict", async () => {
    const workspace = getWorkspace();
    const localDraft = addScene(workspace.manuscript, "local-new-scene");
    const serverManuscript = createServerManuscript(workspace);
    const saveRequests: SaveManuscriptRequest[] = [];
    installStructuralConflictHandlers({ workspace, serverManuscript, saveRequests });
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(localDraft));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    act(() => result.current.applyServer());

    expect(result.current.draft.scenes).toEqual(serverManuscript.scenes);
    expect(result.current.status).toBe("saved");
  });

  test("refreshes the structural comparison after a repeated revision conflict", async () => {
    const workspace = getWorkspace();
    const localDraft = addScene(workspace.manuscript, "local-new-scene");
    const serverManuscript = createServerManuscript(workspace);
    const saveRequests: SaveManuscriptRequest[] = [];
    let workspaceRequestCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        saveRequests.push(body);
        if (saveRequests.length < 3) {
          return HttpResponse.json(
            { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
            { status: 409 },
          );
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 9,
          projectActivity: {
            projectId: workspace.project.id,
            updatedAt: "2026-07-14T04:00:00Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
      http.get("/api/projects/:projectId/workspace", () => {
        workspaceRequestCount += 1;
        return HttpResponse.json({
          ...workspace,
          manuscript: serverManuscript,
          manuscriptRevision: 6 + workspaceRequestCount,
        });
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: 30_000 },
        mutations: { retry: false },
      },
    });
    queryClient.setQueryData(projectKeys.workspace(workspace.project.id), workspace);
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => result.current.updateDraft(localDraft));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    await act(async () => result.current.keepLocal());
    await flushPromises();
    await act(async () => result.current.keepLocal());
    await flushPromises();

    expect(saveRequests).toHaveLength(3);
    expect(saveRequests[1]?.expectedRevision).toBe(7);
    expect(saveRequests[2]?.expectedRevision).toBe(8);
    expect(workspaceRequestCount).toBe(2);
    expect(result.current.conflictKind).toBeNull();
    expect(result.current.status).toBe("saved");
    expect(result.current.isComparingConflict).toBe(false);
    expect(result.current.draft.scenes.map(({ id }) => id)).toEqual([
      "silver-garden-scene-1",
      "server-only-scene",
      "local-new-scene",
    ]);
  });

  test("preserves the structural draft when the latest workspace cannot be loaded", async () => {
    const workspace = getWorkspace();
    const localDraft = addScene(workspace.manuscript, "local-new-scene");
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.get("/api/projects/:projectId/workspace", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "작업 공간 조회 실패", fieldErrors: [] },
          { status: 500 },
        ),
      ),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(localDraft));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();

    expect(result.current.conflictKind).toBe("scene-structure");
    expect(result.current.isConflictCompareError).toBe(true);
    expect(result.current.status).toBe("conflict");
    expect(result.current.draft).toEqual(localDraft);
  });

  test.each([
    ["scene id", "local-new-scene", 3],
    ["chapter number", "server-only-scene", 2],
  ])(
    "preserves the local-only scene when the server has a %s collision",
    async (_, sceneId, chapterNumber) => {
      const workspace = getWorkspace();
      const localDraft = addScene(workspace.manuscript, "local-new-scene");
      const serverManuscript = createServerManuscript(workspace, sceneId, chapterNumber);
      const saveRequests: SaveManuscriptRequest[] = [];
      installStructuralConflictHandlers({
        workspace,
        serverManuscript,
        saveRequests,
        resolveSave: false,
      });
      const { result } = renderHook(
        () =>
          useManuscriptAutosave({
            manuscript: workspace.manuscript,
            manuscriptRevision: workspace.manuscriptRevision,
          }),
        { wrapper: createWrapper(createTestQueryClient()) },
      );

      act(() => result.current.updateDraft(localDraft));
      await act(async () => vi.advanceTimersByTimeAsync(800));
      await flushPromises();
      await act(async () => result.current.keepLocal());
      await flushPromises();

      expect(result.current.draft.scenes).toContainEqual(
        expect.objectContaining({ id: "local-new-scene" }),
      );
      expect(result.current.status).toBe("conflict");
      expect(result.current.isConflictResolutionError).toBe(true);
    },
  );

  test("requests a fresh diff after local resolution meets another conflict", async () => {
    const workspace = getWorkspace();
    let saveCount = 0;
    let compareCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () => {
        saveCount += 1;
        return HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        );
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        compareCount += 1;
        const body = (await request.json()) as { localContent: string };
        return HttpResponse.json(createComparison(workspace, body.localContent, compareCount + 1));
      }),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() =>
      result.current.updateDraft(editActiveScene(workspace, "반복 충돌에도 남는 로컬 장면")),
    );
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    expect(compareCount).toBe(1);

    await act(async () => result.current.keepLocal());
    await flushPromises();

    expect(saveCount).toBe(2);
    expect(compareCount).toBe(2);
    expect(result.current.status).toBe("conflict");
    expect(result.current.conflictComparison?.serverRevision).toBe(3);
    expect(result.current.conflictComparison?.localContent).toBe("반복 충돌에도 남는 로컬 장면");
    expect(result.current.draft.scenes[0].content).toBe("반복 충돌에도 남는 로컬 장면");
  });

  test("keeps a non-conflict resolution failure distinct and retries the same server-based save", async () => {
    const workspace = getWorkspace();
    const serverManuscript = editActiveScene(workspace, "서버 장면");
    const saveRequests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        saveRequests.push(body);
        if (saveRequests.length === 1) {
          return HttpResponse.json(
            { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
            { status: 409 },
          );
        }
        if (saveRequests.length === 2) {
          return HttpResponse.json(
            { code: "INTERNAL_ERROR", message: "저장 실패", fieldErrors: [] },
            { status: 500 },
          );
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 10,
          projectActivity: {
            projectId: workspace.project.id,
            updatedAt: "2026-07-14T05:00:00Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { localContent: string };
        return HttpResponse.json({
          ...createComparison(workspace, body.localContent, 9),
          serverManuscript,
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "재시도할 로컬 장면")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    await act(async () => result.current.keepLocal());
    await flushPromises();

    expect(result.current.status).toBe("conflict");
    expect(result.current.isConflictResolutionError).toBe(true);
    expect(result.current.isConflictDialogOpen).toBe(true);
    expect(result.current.draft.scenes[0].content).toBe("재시도할 로컬 장면");

    await act(async () => result.current.retryKeepLocal());
    await flushPromises();

    expect(saveRequests).toHaveLength(3);
    expect(saveRequests[2]).toEqual(saveRequests[1]);
    expect(saveRequests[2].expectedRevision).toBe(9);
    expect(saveRequests[2].manuscript.scenes[0].content).toBe("재시도할 로컬 장면");
    expect(result.current.status).toBe("saved");
  });

  test("adopts the complete server manuscript and revision without saving", async () => {
    const workspace = getWorkspace();
    const serverManuscript = editActiveScene(workspace, "서버가 선택한 최신 장면");
    let saveCount = 0;
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(projectKeys.workspace(workspace.project.id), workspace);
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () => {
        saveCount += 1;
        return HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        );
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { localContent: string };
        return HttpResponse.json({
          ...createComparison(workspace, body.localContent, 5),
          serverManuscript,
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "버릴 로컬 장면")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    act(() => result.current.applyServer());

    expect(saveCount).toBe(1);
    expect(result.current.status).toBe("saved");
    expect(result.current.draft).toEqual(serverManuscript);
    expect(result.current.conflictComparison).toBeNull();
    expect(result.current.isConflictDialogOpen).toBe(false);
    expect(
      queryClient.getQueryData<ProjectWorkspaceResponse>(
        projectKeys.workspace(workspace.project.id),
      ),
    ).toMatchObject({ manuscript: serverManuscript, manuscriptRevision: 5 });
  });

  test("preserves the local draft when comparison fails", async () => {
    const workspace = getWorkspace();
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "비교 실패", fieldErrors: [] },
          { status: 500 },
        ),
      ),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "비교 실패에도 남는 초안")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();

    expect(result.current.status).toBe("conflict");
    expect(result.current.isConflictCompareError).toBe(true);
    expect(result.current.draft.scenes[0].content).toBe("비교 실패에도 남는 초안");
  });

  test("refreshes a dismissed comparison with edits made while conflict autosave is suspended", async () => {
    const workspace = getWorkspace();
    const comparedContents: string[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { localContent: string };
        comparedContents.push(body.localContent);
        return HttpResponse.json(
          createComparison(workspace, body.localContent, comparedContents.length + 1),
        );
      }),
    );
    const { result } = renderHook(
      () =>
        useManuscriptAutosave({
          manuscript: workspace.manuscript,
          manuscriptRevision: workspace.manuscriptRevision,
        }),
      { wrapper: createWrapper(createTestQueryClient()) },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "처음 충돌한 초안")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    act(() => result.current.setConflictDialogVisibility(false));
    act(() => result.current.updateDraft(editActiveScene(workspace, "닫은 뒤 더 고친 초안")));
    act(() => result.current.openConflictDialog());
    await flushPromises();

    expect(comparedContents).toEqual(["처음 충돌한 초안", "닫은 뒤 더 고친 초안"]);
    expect(result.current.conflictComparison?.localContent).toBe("닫은 뒤 더 고친 초안");
    expect(result.current.draft.scenes[0].content).toBe("닫은 뒤 더 고친 초안");
  });

  test("ignores an old manuscript comparison that finishes after a manuscript reset", async () => {
    const workspace = getWorkspace();
    const nextManuscript = {
      ...workspace.manuscript,
      id: "next-manuscript",
      projectId: "next-project",
      activeSceneId: "next-scene",
      scenes: [
        {
          ...workspace.manuscript.scenes[0],
          id: "next-scene",
          content: "다음 원고",
        },
      ],
    };
    let releaseComparison!: (comparison: CompareManuscriptSceneResponse) => void;
    const pendingComparison = new Promise<CompareManuscriptSceneResponse>((resolve) => {
      releaseComparison = resolve;
    });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async () =>
        HttpResponse.json(await pendingComparison),
      ),
    );
    const { result, rerender } = renderHook(
      ({ manuscript, revision }: { manuscript: typeof workspace.manuscript; revision: number }) =>
        useManuscriptAutosave({ manuscript, manuscriptRevision: revision }),
      {
        initialProps: { manuscript: workspace.manuscript, revision: 1 },
        wrapper: createWrapper(createTestQueryClient()),
      },
    );

    act(() => result.current.updateDraft(editActiveScene(workspace, "이전 원고의 충돌 초안")));
    await act(async () => vi.advanceTimersByTimeAsync(800));
    await flushPromises();
    expect(result.current.isComparingConflict).toBe(true);

    rerender({ manuscript: nextManuscript, revision: 4 });
    await flushPromises();
    await act(async () => {
      releaseComparison(createComparison(workspace, "이전 원고의 충돌 초안", 2));
      await Promise.resolve();
    });
    await flushPromises();

    expect(result.current.draft).toEqual(nextManuscript);
    expect(result.current.status).toBe("saved");
    expect(result.current.conflictComparison).toBeNull();
    expect(result.current.isConflictDialogOpen).toBe(false);
    expect(result.current.isComparingConflict).toBe(false);
  });
});

function createComparison(
  workspace: ProjectWorkspaceResponse,
  localContent: string,
  serverRevision: number,
): CompareManuscriptSceneResponse {
  const scene = workspace.manuscript.scenes[0];
  return {
    sceneId: scene.id,
    serverRevision,
    localContent,
    serverContent: scene.content,
    serverManuscript: workspace.manuscript,
    rows: [
      {
        kind: "local-only",
        localLineNumber: 1,
        localText: localContent,
        serverLineNumber: null,
        serverText: null,
      },
      {
        kind: "server-only",
        localLineNumber: null,
        localText: null,
        serverLineNumber: 1,
        serverText: scene.content,
      },
    ],
  };
}

function createComparisonForScene(
  manuscript: ProjectWorkspaceResponse["manuscript"],
  sceneId: string,
  localContent: string,
  serverRevision: number,
): CompareManuscriptSceneResponse {
  const scene = manuscript.scenes.find(({ id }) => id === sceneId);
  if (!scene) {
    throw new Error("Expected comparison scene");
  }
  return {
    sceneId,
    serverRevision,
    localContent,
    serverContent: scene.content,
    serverManuscript: manuscript,
    rows: [],
  };
}
