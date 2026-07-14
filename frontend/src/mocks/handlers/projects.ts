import { http, HttpResponse, type HttpResponseResolver, type RequestHandler } from "msw";

import type {
  ApiError,
  ApiManuscript,
  CompareManuscriptSceneRequest,
  CompareManuscriptSceneResponse,
  CreateProjectRequest,
  ProjectListResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
  SaveManuscriptResponse,
  SceneDiffRow,
  TropeId,
} from "@/app/infrastructure/api/contracts";
import {
  addMockWorkspace,
  apiErrors,
  findMockWorkspace,
  findMockWorkspaceByManuscriptId,
  findMockWorkspaceBySceneId,
  listMockProjects,
  MOCK_NOW,
  PROJECT_API_BASE_URL,
  replaceMockWorkspaceAtRevision,
} from "@/mocks/data/project-workspaces";

const tropeIds: readonly TropeId[] = [
  "rivals-to-lovers",
  "contract-romance",
  "reunion",
  "friends-to-lovers",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, expectedKeys: readonly string[]): boolean {
  const actualKeys = Object.keys(value);

  return (
    actualKeys.length === expectedKeys.length &&
    expectedKeys.every((key) => Object.hasOwn(value, key))
  );
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isNonEmptyStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isNonEmptyString);
}

function isTropeId(value: unknown): value is TropeId {
  return typeof value === "string" && tropeIds.some((tropeId) => tropeId === value);
}

function isApiManuscript(value: unknown): value is ApiManuscript {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["id", "projectId", "scenes", "activeSceneId"]) ||
    !isNonEmptyString(value.id) ||
    !isNonEmptyString(value.projectId)
  ) {
    return false;
  }

  if (!isNonEmptyString(value.activeSceneId) || !Array.isArray(value.scenes)) {
    return false;
  }

  return value.scenes.every(
    (scene) =>
      isRecord(scene) &&
      hasExactKeys(scene, [
        "id",
        "title",
        "chapterNumber",
        "content",
        "relatedCharacterIds",
        "relatedWorldEntryIds",
      ]) &&
      isNonEmptyString(scene.id) &&
      typeof scene.title === "string" &&
      Number.isInteger(scene.chapterNumber) &&
      Number(scene.chapterNumber) >= 0 &&
      typeof scene.content === "string" &&
      isNonEmptyStringArray(scene.relatedCharacterIds) &&
      isNonEmptyStringArray(scene.relatedWorldEntryIds),
  );
}

function parseCreateProjectRequest(value: unknown): CreateProjectRequest | ApiError {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["title", "logline", "tropeId", "protagonistNames"]) ||
    typeof value.title !== "string" ||
    typeof value.logline !== "string" ||
    typeof value.tropeId !== "string" ||
    !Array.isArray(value.protagonistNames) ||
    !value.protagonistNames.every((name): name is string => typeof name === "string")
  ) {
    return apiErrors.malformedRequest;
  }

  if (!value.title.trim()) {
    return {
      code: "INVALID_TITLE",
      message: "작품 제목을 입력해 주세요.",
      fieldErrors: [{ path: "title", message: "작품 제목을 입력해 주세요." }],
    };
  }

  if (!isTropeId(value.tropeId)) {
    return {
      code: "INVALID_TROPE",
      message: "선택한 로맨스 트로프를 찾을 수 없습니다.",
      fieldErrors: [{ path: "tropeId", message: "등록된 로맨스 트로프를 선택해 주세요." }],
    };
  }

  if (value.protagonistNames.length !== 2 || value.protagonistNames.some((name) => !name.trim())) {
    return {
      code: "INVALID_PROTAGONISTS",
      message: "두 주인공의 이름을 모두 입력해 주세요.",
      fieldErrors: [
        {
          path: "protagonistNames",
          message: "두 주인공의 이름을 모두 입력해 주세요.",
        },
      ],
    };
  }

  return {
    title: value.title.trim(),
    logline: value.logline.trim(),
    tropeId: value.tropeId,
    protagonistNames: [value.protagonistNames[0].trim(), value.protagonistNames[1].trim()],
  };
}

function parseSaveManuscriptRequest(value: unknown): SaveManuscriptRequest | undefined {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["manuscript", "expectedRevision"]) ||
    !isApiManuscript(value.manuscript) ||
    !Number.isInteger(value.expectedRevision) ||
    Number(value.expectedRevision) < 1
  ) {
    return undefined;
  }

  return {
    manuscript: value.manuscript,
    expectedRevision: Number(value.expectedRevision),
  };
}

function parseCompareManuscriptSceneRequest(
  value: unknown,
): CompareManuscriptSceneRequest | undefined {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["sceneId", "localContent"]) ||
    !isNonEmptyString(value.sceneId) ||
    typeof value.localContent !== "string"
  ) {
    return undefined;
  }

  return { sceneId: value.sceneId, localContent: value.localContent };
}

function alignSceneLines(localContent: string, serverContent: string): SceneDiffRow[] {
  const localLines = localContent.split("\n");
  const serverLines = serverContent.split("\n");
  const longestCommonSubsequence = Array.from({ length: localLines.length + 1 }, () =>
    Array<number>(serverLines.length + 1).fill(0),
  );

  for (let localIndex = localLines.length - 1; localIndex >= 0; localIndex -= 1) {
    for (let serverIndex = serverLines.length - 1; serverIndex >= 0; serverIndex -= 1) {
      longestCommonSubsequence[localIndex][serverIndex] =
        localLines[localIndex] === serverLines[serverIndex]
          ? longestCommonSubsequence[localIndex + 1][serverIndex + 1] + 1
          : Math.max(
              longestCommonSubsequence[localIndex + 1][serverIndex],
              longestCommonSubsequence[localIndex][serverIndex + 1],
            );
    }
  }

  const rows: SceneDiffRow[] = [];
  let localIndex = 0;
  let serverIndex = 0;

  while (localIndex < localLines.length && serverIndex < serverLines.length) {
    if (localLines[localIndex] === serverLines[serverIndex]) {
      rows.push({
        kind: "unchanged",
        localLineNumber: localIndex + 1,
        localText: localLines[localIndex],
        serverLineNumber: serverIndex + 1,
        serverText: serverLines[serverIndex],
      });
      localIndex += 1;
      serverIndex += 1;
    } else if (
      longestCommonSubsequence[localIndex + 1][serverIndex] >=
      longestCommonSubsequence[localIndex][serverIndex + 1]
    ) {
      rows.push({
        kind: "local-only",
        localLineNumber: localIndex + 1,
        localText: localLines[localIndex],
        serverLineNumber: null,
        serverText: null,
      });
      localIndex += 1;
    } else {
      rows.push({
        kind: "server-only",
        localLineNumber: null,
        localText: null,
        serverLineNumber: serverIndex + 1,
        serverText: serverLines[serverIndex],
      });
      serverIndex += 1;
    }
  }

  while (localIndex < localLines.length) {
    rows.push({
      kind: "local-only",
      localLineNumber: localIndex + 1,
      localText: localLines[localIndex],
      serverLineNumber: null,
      serverText: null,
    });
    localIndex += 1;
  }

  while (serverIndex < serverLines.length) {
    rows.push({
      kind: "server-only",
      localLineNumber: null,
      localText: null,
      serverLineNumber: serverIndex + 1,
      serverText: serverLines[serverIndex],
    });
    serverIndex += 1;
  }

  return rows;
}

async function readRequestJson(request: Request): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    return undefined;
  }
}

function createProjectId(): string {
  const projectIds = new Set(listMockProjects().map(({ id }) => id));
  let sequence = 1;

  while (projectIds.has(`mock-project-${sequence}`)) {
    sequence += 1;
  }

  return `mock-project-${sequence}`;
}

function buildWorkspace(
  projectId: string,
  request: CreateProjectRequest,
): ProjectWorkspaceResponse {
  const firstCharacterId = `${projectId}-character-1`;
  const secondCharacterId = `${projectId}-character-2`;
  const worldEntryId = `${projectId}-world-1`;
  const sceneId = `${projectId}-scene-1`;

  return {
    project: {
      id: projectId,
      title: request.title,
      logline: request.logline,
      tropeId: request.tropeId,
      updatedAt: MOCK_NOW,
    },
    concept: {
      id: `${projectId}-concept`,
      projectId,
      tropeId: request.tropeId,
      logline: request.logline,
      protagonistNames: request.protagonistNames,
    },
    storyBible: {
      projectId,
      characters: [
        {
          id: firstCharacterId,
          name: request.protagonistNames[0],
          role: "protagonist",
          desire: "상대에게 흔들리지 않고 자신의 선택을 지키고 싶다.",
          hiddenFeeling: "여전히 상대의 진심을 확인하고 싶다.",
        },
        {
          id: secondCharacterId,
          name: request.protagonistNames[1],
          role: "protagonist",
          desire: "과거의 오해를 풀고 다시 신뢰받고 싶다.",
          hiddenFeeling: "이번에는 먼저 놓치고 싶지 않다.",
        },
      ],
      worldEntries: [
        {
          id: worldEntryId,
          kind: "place",
          title: "첫 장면의 장소",
          description: "두 주인공의 이야기가 시작되는 장소다.",
        },
      ],
    },
    manuscript: {
      id: `${projectId}-manuscript`,
      projectId,
      scenes: [
        {
          id: sceneId,
          title: "첫 장면",
          chapterNumber: 1,
          content: "",
          relatedCharacterIds: [firstCharacterId, secondCharacterId],
          relatedWorldEntryIds: [worldEntryId],
        },
      ],
      activeSceneId: sceneId,
    },
    manuscriptRevision: 1,
  };
}

function invalidManuscript(path: string, message: string): ApiError {
  return {
    code: "INVALID_MANUSCRIPT",
    message: "원고 정보를 확인해 주세요.",
    fieldErrors: [{ path, message }],
  };
}

const listProjectsHandler: HttpResponseResolver = () => {
  const response: ProjectListResponse = { items: listMockProjects() };
  return HttpResponse.json(response);
};

const createProjectHandler: HttpResponseResolver = async ({ request }) => {
  const requestJson = await readRequestJson(request);

  if (requestJson === undefined) {
    return HttpResponse.json(apiErrors.malformedRequest, { status: 400 });
  }

  const parsedRequest = parseCreateProjectRequest(requestJson);

  if ("code" in parsedRequest) {
    const status = parsedRequest.code === "MALFORMED_REQUEST" ? 400 : 422;
    return HttpResponse.json(parsedRequest, { status });
  }

  const workspace = buildWorkspace(createProjectId(), parsedRequest);
  addMockWorkspace(workspace);

  return HttpResponse.json(workspace, {
    status: 201,
    headers: {
      Location: `${PROJECT_API_BASE_URL}/projects/${workspace.project.id}/workspace`,
    },
  });
};

const getWorkspaceHandler: HttpResponseResolver = ({ params }) => {
  const projectId = params.projectId;
  const workspace = typeof projectId === "string" ? findMockWorkspace(projectId) : undefined;

  return workspace
    ? HttpResponse.json(workspace)
    : HttpResponse.json(apiErrors.projectNotFound, { status: 404 });
};

const saveManuscriptHandler: HttpResponseResolver = async ({ params, request }) => {
  const requestJson = await readRequestJson(request);
  const parsedRequest = parseSaveManuscriptRequest(requestJson);

  if (!parsedRequest) {
    return HttpResponse.json(apiErrors.malformedRequest, { status: 400 });
  }

  const manuscriptId = params.manuscriptId;
  const workspace =
    typeof manuscriptId === "string" ? findMockWorkspaceByManuscriptId(manuscriptId) : undefined;

  if (!workspace) {
    return HttpResponse.json(apiErrors.manuscriptNotFound, { status: 404 });
  }

  if (parsedRequest.manuscript.id !== manuscriptId) {
    return HttpResponse.json(
      invalidManuscript("manuscript.id", "경로의 원고 식별자와 일치해야 합니다."),
      { status: 422 },
    );
  }

  if (parsedRequest.manuscript.projectId !== workspace.project.id) {
    return HttpResponse.json(
      invalidManuscript("manuscript.projectId", "원고가 속한 프로젝트와 일치해야 합니다."),
      { status: 422 },
    );
  }

  if (
    !parsedRequest.manuscript.scenes.some(({ id }) => id === parsedRequest.manuscript.activeSceneId)
  ) {
    return HttpResponse.json(
      invalidManuscript("manuscript.activeSceneId", "원고에 존재하는 장면을 선택해 주세요."),
      { status: 422 },
    );
  }

  const updatedWorkspace: ProjectWorkspaceResponse = {
    ...workspace,
    project: { ...workspace.project, updatedAt: MOCK_NOW },
    manuscript: parsedRequest.manuscript,
    manuscriptRevision: workspace.manuscriptRevision + 1,
  };
  const replacement = replaceMockWorkspaceAtRevision(
    workspace.manuscript.id,
    parsedRequest.expectedRevision,
    updatedWorkspace,
  );

  if (replacement.status === "not-found") {
    return HttpResponse.json(apiErrors.manuscriptNotFound, { status: 404 });
  }

  if (replacement.status === "revision-conflict") {
    return HttpResponse.json(apiErrors.revisionConflict, { status: 409 });
  }

  const response: SaveManuscriptResponse = {
    manuscript: replacement.workspace.manuscript,
    manuscriptRevision: replacement.workspace.manuscriptRevision,
    projectActivity: {
      projectId: replacement.workspace.project.id,
      updatedAt: replacement.workspace.project.updatedAt,
    },
  };

  return HttpResponse.json(response);
};

const compareManuscriptSceneHandler: HttpResponseResolver = async ({ params, request }) => {
  const parsedRequest = parseCompareManuscriptSceneRequest(await readRequestJson(request));

  if (!parsedRequest) {
    return HttpResponse.json(apiErrors.malformedRequest, { status: 400 });
  }

  const manuscriptId = params.manuscriptId;
  const workspace =
    typeof manuscriptId === "string" ? findMockWorkspaceByManuscriptId(manuscriptId) : undefined;

  if (!workspace) {
    return HttpResponse.json(apiErrors.manuscriptNotFound, { status: 404 });
  }

  const sceneWorkspace = findMockWorkspaceBySceneId(parsedRequest.sceneId);

  if (!sceneWorkspace) {
    return HttpResponse.json(apiErrors.sceneNotFound, { status: 404 });
  }

  if (sceneWorkspace.manuscript.id !== manuscriptId) {
    return HttpResponse.json(apiErrors.invalidSceneReference, { status: 422 });
  }

  const serverScene = workspace.manuscript.scenes.find(({ id }) => id === parsedRequest.sceneId);

  if (!serverScene) {
    return HttpResponse.json(apiErrors.invalidSceneReference, { status: 422 });
  }

  const response: CompareManuscriptSceneResponse = {
    sceneId: parsedRequest.sceneId,
    serverRevision: workspace.manuscriptRevision,
    localContent: parsedRequest.localContent,
    serverContent: serverScene.content,
    serverManuscript: structuredClone(workspace.manuscript),
    rows: alignSceneLines(parsedRequest.localContent, serverScene.content),
  };

  return HttpResponse.json(response);
};

export const projectHandlers: RequestHandler[] = [
  http.get(`${PROJECT_API_BASE_URL}/projects`, listProjectsHandler),
  http.post(`${PROJECT_API_BASE_URL}/projects`, createProjectHandler),
  http.get(`${PROJECT_API_BASE_URL}/projects/:projectId/workspace`, getWorkspaceHandler),
  http.put(`${PROJECT_API_BASE_URL}/manuscripts/:manuscriptId`, saveManuscriptHandler),
  http.post(
    `${PROJECT_API_BASE_URL}/manuscripts/:manuscriptId/scene-diffs`,
    compareManuscriptSceneHandler,
  ),
];
