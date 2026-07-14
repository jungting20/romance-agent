import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { describe, expect, it } from "vitest";

import type {
  ProjectListResponse,
  ProjectWorkspaceResponse,
} from "@/app/infrastructure/api/contracts";

import {
  projectKeys,
  useCompareManuscriptSceneMutation,
  useCreateProjectMutation,
  useProjectsQuery,
  useProjectWorkspaceQuery,
  useSaveManuscriptMutation,
} from "./project-queries";

function createWrapper(queryClient: QueryClient) {
  return function TestQueryProvider({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

describe("project persistence queries", () => {
  it("uses stable list and workspace query keys", () => {
    expect(projectKeys.list()).toEqual(["projects", "list"]);
    expect(projectKeys.list()).toEqual(projectKeys.list());
    expect(projectKeys.workspace("silver-garden")).toEqual([
      "projects",
      "workspace",
      "silver-garden",
    ]);
    expect(projectKeys.workspace("silver-garden")).toEqual(projectKeys.workspace("silver-garden"));
  });

  it("loads the project list and a project workspace", async () => {
    const queryClient = createTestQueryClient();
    const wrapper = createWrapper(queryClient);
    const projects = renderHook(() => useProjectsQuery(), { wrapper });
    const workspace = renderHook(() => useProjectWorkspaceQuery("silver-garden"), { wrapper });

    await waitFor(() => {
      expect(projects.result.current.isSuccess).toBe(true);
      expect(workspace.result.current.isSuccess).toBe(true);
    });

    expect(projects.result.current.data?.items[0].id).toBe("silver-garden");
    expect(workspace.result.current.data?.project.id).toBe("silver-garden");
  });

  it("seeds the workspace cache and adds a created project to the list cache", async () => {
    const queryClient = createTestQueryClient();
    const wrapper = createWrapper(queryClient);
    const projects = renderHook(() => useProjectsQuery(), { wrapper });

    await waitFor(() => expect(projects.result.current.isSuccess).toBe(true));

    const mutation = renderHook(() => useCreateProjectMutation(), { wrapper });

    let createdWorkspace: ProjectWorkspaceResponse | undefined;
    await act(async () => {
      createdWorkspace = await mutation.result.current.mutateAsync({
        title: "빗속의 재회",
        logline: "헤어진 두 사람이 비 내리는 서점에서 다시 만난다.",
        tropeId: "reunion",
        protagonistNames: ["하린", "태오"],
      });
    });

    expect(createdWorkspace).toBeDefined();
    if (!createdWorkspace) {
      throw new Error("Expected the create mutation to return a workspace");
    }
    expect(
      queryClient.getQueryData<ProjectWorkspaceResponse>(
        projectKeys.workspace(createdWorkspace.project.id),
      ),
    ).toEqual(createdWorkspace);
    expect(queryClient.getQueryData<ProjectListResponse>(projectKeys.list())?.items[0]).toEqual(
      createdWorkspace.project,
    );
  });

  it("updates workspace manuscript state and project activity after saving", async () => {
    const queryClient = createTestQueryClient();
    const wrapper = createWrapper(queryClient);
    const workspaceHook = renderHook(() => useProjectWorkspaceQuery("silver-garden"), { wrapper });
    const projectsHook = renderHook(() => useProjectsQuery(), { wrapper });

    await waitFor(() => {
      expect(workspaceHook.result.current.isSuccess).toBe(true);
      expect(projectsHook.result.current.isSuccess).toBe(true);
    });

    const workspace = workspaceHook.result.current.data!;
    const manuscript = {
      ...workspace.manuscript,
      scenes: workspace.manuscript.scenes.map((scene) => ({
        ...scene,
        content: "서윤은 오래된 온실 문을 천천히 열었다.",
      })),
    };
    const mutation = renderHook(() => useSaveManuscriptMutation(), { wrapper });

    await act(async () => {
      await mutation.result.current.mutateAsync({
        manuscriptId: manuscript.id,
        request: { manuscript, expectedRevision: workspace.manuscriptRevision },
      });
    });

    const cachedWorkspace = queryClient.getQueryData<ProjectWorkspaceResponse>(
      projectKeys.workspace("silver-garden"),
    );
    const cachedList = queryClient.getQueryData<ProjectListResponse>(projectKeys.list());

    expect(cachedWorkspace).toMatchObject({
      manuscript,
      manuscriptRevision: 2,
      project: { updatedAt: "2026-07-14T03:00:00.000Z" },
    });
    expect(cachedList?.items.find(({ id }) => id === "silver-garden")?.updatedAt).toBe(
      "2026-07-14T03:00:00.000Z",
    );
  });

  it("compares a local scene through the comparison mutation", async () => {
    const queryClient = createTestQueryClient();
    const wrapper = createWrapper(queryClient);
    const mutation = renderHook(() => useCompareManuscriptSceneMutation(), { wrapper });

    await act(async () => {
      await mutation.result.current.mutateAsync({
        manuscriptId: "silver-garden-manuscript",
        request: {
          sceneId: "silver-garden-scene-1",
          localContent: "로컬 초안",
        },
      });
    });

    expect(mutation.result.current.data).toMatchObject({
      sceneId: "silver-garden-scene-1",
      serverRevision: 1,
      localContent: "로컬 초안",
    });
  });
});
