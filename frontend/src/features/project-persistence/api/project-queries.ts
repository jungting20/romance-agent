import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  CompareManuscriptSceneRequest,
  CreateProjectRequest,
  ProjectListResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
} from "@/app/infrastructure/api/contracts";
import {
  compareManuscriptScene,
  createProjectWorkspace,
  getProjectWorkspace,
  listProjects,
  saveManuscript,
} from "@/app/infrastructure/api/projects-api";

import { projectKeys } from "./query-keys";

interface SaveManuscriptMutationVariables {
  manuscriptId: string;
  request: SaveManuscriptRequest;
}

interface CompareManuscriptSceneMutationVariables {
  manuscriptId: string;
  request: CompareManuscriptSceneRequest;
}

export function useProjectsQuery() {
  return useQuery({
    queryKey: projectKeys.list(),
    queryFn: listProjects,
  });
}

export function useProjectWorkspaceQuery(projectId: string) {
  return useQuery({
    queryKey: projectKeys.workspace(projectId),
    queryFn: () => getProjectWorkspace(projectId),
  });
}

export function useCreateProjectMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreateProjectRequest) => createProjectWorkspace(request),
    onSuccess: async (workspace) => {
      queryClient.setQueryData(projectKeys.workspace(workspace.project.id), workspace);

      const projects = queryClient.getQueryData<ProjectListResponse>(projectKeys.list());
      if (!projects) {
        await queryClient.invalidateQueries({ queryKey: projectKeys.list() });
        return;
      }

      queryClient.setQueryData<ProjectListResponse>(projectKeys.list(), {
        items: [
          workspace.project,
          ...projects.items.filter(({ id }) => id !== workspace.project.id),
        ],
      });
    },
  });
}

export function useSaveManuscriptMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ manuscriptId, request }: SaveManuscriptMutationVariables) =>
      saveManuscript(manuscriptId, request),
    onSuccess: async (saved) => {
      const { projectId, updatedAt } = saved.projectActivity;
      const workspaceKey = projectKeys.workspace(projectId);
      const workspace = queryClient.getQueryData<ProjectWorkspaceResponse>(workspaceKey);

      if (workspace) {
        queryClient.setQueryData(workspaceKey, {
          ...workspace,
          manuscript: saved.manuscript,
          manuscriptRevision: saved.manuscriptRevision,
          project: { ...workspace.project, updatedAt },
        });
      } else {
        await queryClient.invalidateQueries({ queryKey: workspaceKey });
      }

      const projects = queryClient.getQueryData<ProjectListResponse>(projectKeys.list());
      if (!projects) {
        await queryClient.invalidateQueries({ queryKey: projectKeys.list() });
        return;
      }

      queryClient.setQueryData<ProjectListResponse>(projectKeys.list(), {
        items: projects.items
          .map((project) => (project.id === projectId ? { ...project, updatedAt } : project))
          .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt)),
      });
    },
  });
}

export function useCompareManuscriptSceneMutation() {
  return useMutation({
    mutationFn: ({ manuscriptId, request }: CompareManuscriptSceneMutationVariables) =>
      compareManuscriptScene(manuscriptId, request),
  });
}

export { projectKeys };
