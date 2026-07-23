import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  CreateCharacterMutationVariables,
  ProjectWorkspaceResponse,
  SaveWorldEntriesMutationVariables,
  StoryBibleSnapshot,
  UpdateCharacterMutationVariables,
} from "@/app/infrastructure/api/contracts";
import {
  createStoryBibleCharacter,
  getStoryBible,
  saveWorldEntries,
  updateStoryBibleCharacter,
} from "@/app/infrastructure/api/story-bible-api";
import { projectKeys } from "@/features/project-persistence";

import { storyBibleKeys } from "./query-keys";

export function useStoryBibleQuery(projectId: string) {
  return useQuery({
    queryKey: storyBibleKeys.project(projectId),
    queryFn: () => getStoryBible(projectId),
  });
}

export function useSaveWorldEntriesMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, request }: SaveWorldEntriesMutationVariables) =>
      saveWorldEntries(projectId, request),
    onSuccess: (snapshot, { projectId }) =>
      updateStoryBibleCaches(queryClient, projectId, snapshot),
  });
}

export function useCreateCharacterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, request }: CreateCharacterMutationVariables) =>
      createStoryBibleCharacter(projectId, request),
    onSuccess: (snapshot, { projectId }) =>
      updateStoryBibleCaches(queryClient, projectId, snapshot),
  });
}

export function useUpdateCharacterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, characterId, request }: UpdateCharacterMutationVariables) =>
      updateStoryBibleCharacter(projectId, characterId, request),
    onSuccess: (snapshot, { projectId }) =>
      updateStoryBibleCaches(queryClient, projectId, snapshot),
  });
}

function updateStoryBibleCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
  snapshot: StoryBibleSnapshot,
) {
  queryClient.setQueryData(storyBibleKeys.project(projectId), snapshot);
  const workspaceKey = projectKeys.workspace(projectId);
  const workspace = queryClient.getQueryData<ProjectWorkspaceResponse>(workspaceKey);
  if (workspace) {
    queryClient.setQueryData(workspaceKey, {
      ...workspace,
      storyBible: snapshot.storyBible,
    });
  }
}

export { storyBibleKeys };
