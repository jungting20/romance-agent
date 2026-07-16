import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  ProjectWorkspaceResponse,
  SaveWorldEntriesMutationVariables,
} from "@/app/infrastructure/api/contracts";
import { getStoryBible, saveWorldEntries } from "@/app/infrastructure/api/story-bible-api";
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
    onSuccess: (snapshot, { projectId }) => {
      queryClient.setQueryData(storyBibleKeys.project(projectId), snapshot);

      const workspaceKey = projectKeys.workspace(projectId);
      const workspace = queryClient.getQueryData<ProjectWorkspaceResponse>(workspaceKey);
      if (workspace) {
        queryClient.setQueryData(workspaceKey, {
          ...workspace,
          storyBible: snapshot.storyBible,
        });
      }
    },
  });
}

export { storyBibleKeys };
