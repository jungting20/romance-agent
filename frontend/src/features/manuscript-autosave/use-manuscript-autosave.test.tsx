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
import { updateSceneContent } from "@/modules/manuscript";

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
