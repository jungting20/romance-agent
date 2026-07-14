import { requestJson } from "./api-client";
import type {
  CompareManuscriptSceneRequest,
  CompareManuscriptSceneResponse,
  CreateProjectRequest,
  ProjectListResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
  SaveManuscriptResponse,
} from "./contracts";

const apiBasePath = "/api";

export function listProjects(): Promise<ProjectListResponse> {
  return requestJson(`${apiBasePath}/projects`);
}

export function createProjectWorkspace(
  request: CreateProjectRequest,
): Promise<ProjectWorkspaceResponse> {
  return requestJson(`${apiBasePath}/projects`, { method: "POST", body: request });
}

export function getProjectWorkspace(projectId: string): Promise<ProjectWorkspaceResponse> {
  return requestJson(`${apiBasePath}/projects/${encodeURIComponent(projectId)}/workspace`);
}

export function saveManuscript(
  manuscriptId: string,
  request: SaveManuscriptRequest,
): Promise<SaveManuscriptResponse> {
  return requestJson(`${apiBasePath}/manuscripts/${encodeURIComponent(manuscriptId)}`, {
    method: "PUT",
    body: request,
  });
}

export function compareManuscriptScene(
  manuscriptId: string,
  request: CompareManuscriptSceneRequest,
): Promise<CompareManuscriptSceneResponse> {
  return requestJson(`${apiBasePath}/manuscripts/${encodeURIComponent(manuscriptId)}/scene-diffs`, {
    method: "POST",
    body: request,
  });
}
