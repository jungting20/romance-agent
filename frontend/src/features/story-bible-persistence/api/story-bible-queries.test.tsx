import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { describe, expect, it } from "vitest";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type {
  ProjectWorkspaceResponse,
  StoryBibleSnapshot,
} from "@/app/infrastructure/api/contracts";
import { getProjectWorkspace } from "@/app/infrastructure/api/projects-api";
import { projectKeys } from "@/features/project-persistence";

import {
  storyBibleKeys,
  useSaveWorldEntriesMutation,
  useStoryBibleQuery,
} from "./story-bible-queries";

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

describe("Story Bible persistence queries", () => {
  it("uses stable project-scoped query keys", () => {
    expect(storyBibleKeys.all).toEqual(["story-bible"]);
    expect(storyBibleKeys.project("silver-garden")).toEqual(["story-bible", "silver-garden"]);
    expect(storyBibleKeys.project("silver-garden")).toEqual(
      storyBibleKeys.project("silver-garden"),
    );
  });

  it("loads a Story Bible snapshot through the query adapter", async () => {
    const queryClient = createTestQueryClient();
    const query = renderHook(() => useStoryBibleQuery("silver-garden"), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(query.result.current.isSuccess).toBe(true));

    expect(query.result.current.data).toMatchObject({
      storyBible: { projectId: "silver-garden" },
      storyBibleRevision: 1,
    });
  });

  it("writes the saved snapshot and replaces only the cached workspace Story Bible", async () => {
    const queryClient = createTestQueryClient();
    const wrapper = createWrapper(queryClient);
    const workspace = await getProjectWorkspace("silver-garden");
    queryClient.setQueryData(projectKeys.workspace("silver-garden"), workspace);
    const mutation = renderHook(() => useSaveWorldEntriesMutation(), { wrapper });

    let saved: StoryBibleSnapshot | undefined;
    await act(async () => {
      saved = await mutation.result.current.mutateAsync({
        projectId: "silver-garden",
        request: {
          expectedRevision: 1,
          updates: [
            {
              id: "silver-garden-world-1",
              kind: "place",
              title: "비가 그친 유리 온실",
              description: "두 사람이 마지막으로 만난 장소다.",
            },
          ],
          additions: [
            { kind: "rule", title: "왕실의 서약", description: "서약을 어기면 계승권을 잃는다." },
          ],
        },
      });
    });

    expect(saved).toBeDefined();
    expect(queryClient.getQueryData(storyBibleKeys.project("silver-garden"))).toEqual(saved);
    const cachedWorkspace = queryClient.getQueryData<ProjectWorkspaceResponse>(
      projectKeys.workspace("silver-garden"),
    );
    expect(cachedWorkspace).toEqual({ ...workspace, storyBible: saved?.storyBible });
    expect(cachedWorkspace?.project).toBe(workspace.project);
    expect(cachedWorkspace?.concept).toBe(workspace.concept);
    expect(cachedWorkspace?.manuscript).toBe(workspace.manuscript);
    expect(cachedWorkspace?.manuscriptRevision).toBe(workspace.manuscriptRevision);
  });

  it("does not create a workspace cache entry when one was not already cached", async () => {
    const queryClient = createTestQueryClient();
    const mutation = renderHook(() => useSaveWorldEntriesMutation(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await mutation.result.current.mutateAsync({
        projectId: "silver-garden",
        request: {
          expectedRevision: 1,
          updates: [],
          additions: [
            { kind: "object", title: "은빛 열쇠", description: "온실 문을 여는 열쇠다." },
          ],
        },
      });
    });

    expect(queryClient.getQueryData(projectKeys.workspace("silver-garden"))).toBeUndefined();
    expect(queryClient.getQueryData(storyBibleKeys.project("silver-garden"))).toMatchObject({
      storyBibleRevision: 2,
    });
  });

  it("leaves both caches unchanged when the real handler rejects a revision conflict", async () => {
    const queryClient = createTestQueryClient();
    const wrapper = createWrapper(queryClient);
    const workspace = await getProjectWorkspace("silver-garden");
    const snapshot: StoryBibleSnapshot = {
      storyBible: workspace.storyBible,
      storyBibleRevision: 1,
    };
    queryClient.setQueryData(projectKeys.workspace("silver-garden"), workspace);
    queryClient.setQueryData(storyBibleKeys.project("silver-garden"), snapshot);
    const mutation = renderHook(() => useSaveWorldEntriesMutation(), { wrapper });

    let caught: unknown;
    await act(async () => {
      try {
        await mutation.result.current.mutateAsync({
          projectId: "silver-garden",
          request: {
            expectedRevision: 2,
            updates: [],
            additions: [{ kind: "object", title: "충돌 항목", description: "저장되면 안 된다." }],
          },
        });
      } catch (error) {
        caught = error;
      }
    });

    expect(caught).toBeInstanceOf(ApiRequestError);
    expect(caught).toMatchObject({
      status: 409,
      error: { code: "STORY_BIBLE_REVISION_CONFLICT" },
    });
    expect(queryClient.getQueryData(projectKeys.workspace("silver-garden"))).toBe(workspace);
    expect(queryClient.getQueryData(storyBibleKeys.project("silver-garden"))).toBe(snapshot);
  });
});
