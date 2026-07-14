import type {
  ApiError,
  ApiProject,
  ProjectWorkspaceResponse,
} from "@/app/infrastructure/api/contracts";

export const PROJECT_API_BASE_URL = "/api";
export const MOCK_NOW = "2026-07-14T03:00:00.000Z";

export const apiErrors = {
  malformedRequest: {
    code: "MALFORMED_REQUEST",
    message: "요청 형식을 확인해 주세요.",
    fieldErrors: [],
  },
  projectNotFound: {
    code: "PROJECT_NOT_FOUND",
    message: "프로젝트를 찾을 수 없습니다.",
    fieldErrors: [],
  },
  manuscriptNotFound: {
    code: "MANUSCRIPT_NOT_FOUND",
    message: "원고를 찾을 수 없습니다.",
    fieldErrors: [],
  },
  revisionConflict: {
    code: "MANUSCRIPT_REVISION_CONFLICT",
    message: "다른 위치에서 원고가 먼저 수정되었습니다.",
    fieldErrors: [],
  },
  internalError: {
    code: "INTERNAL_ERROR",
    message: "잠시 후 다시 시도해 주세요.",
    fieldErrors: [],
  },
} satisfies Record<string, ApiError>;

const OPENING_SCENE = `비가 그친 뒤의 온실은 오래된 비밀처럼 고요했다.

서윤은 젖은 돌바닥 위에 멈춰 섰다. 돌아보지 않아도 누가 와 있는지 알 수 있었다. 몇 년이 흘렀는데도 발소리 하나만은 기억 속 그대로였다.

“여긴 여전하네.”

도현의 목소리가 장미 향 사이로 낮게 번졌다. 서윤은 손에 든 편지를 조금 더 세게 쥐었다.`;

const initialProjectWorkspaces: readonly ProjectWorkspaceResponse[] = [
  {
    project: {
      id: "silver-garden",
      title: "은빛 정원의 약속",
      logline: "오해로 헤어진 두 사람이 오래된 온실에서 다시 만난다.",
      tropeId: "reunion",
      updatedAt: "2026-07-13T05:00:00.000Z",
    },
    concept: {
      id: "silver-garden-concept",
      projectId: "silver-garden",
      tropeId: "reunion",
      logline: "오해로 헤어진 두 사람이 오래된 온실에서 다시 만난다.",
      protagonistNames: ["서윤", "도현"],
    },
    storyBible: {
      projectId: "silver-garden",
      characters: [
        {
          id: "silver-garden-character-1",
          name: "서윤",
          role: "protagonist",
          desire: "상대에게 흔들리지 않고 자신의 선택을 지키고 싶다.",
          hiddenFeeling: "여전히 상대의 진심을 확인하고 싶다.",
        },
        {
          id: "silver-garden-character-2",
          name: "도현",
          role: "protagonist",
          desire: "과거의 오해를 풀고 다시 신뢰받고 싶다.",
          hiddenFeeling: "이번에는 먼저 놓치고 싶지 않다.",
        },
      ],
      worldEntries: [
        {
          id: "silver-garden-world-1",
          kind: "place",
          title: "비가 그친 온실",
          description:
            "두 사람이 과거에 마지막으로 만났던 장소. 젖은 흙과 오래된 장미 향이 남아 있다.",
        },
      ],
    },
    manuscript: {
      id: "silver-garden-manuscript",
      projectId: "silver-garden",
      activeSceneId: "silver-garden-scene-1",
      scenes: [
        {
          id: "silver-garden-scene-1",
          title: "비가 그친 뒤의 정원",
          chapterNumber: 1,
          content: OPENING_SCENE,
          relatedCharacterIds: ["silver-garden-character-1", "silver-garden-character-2"],
          relatedWorldEntryIds: ["silver-garden-world-1"],
        },
      ],
    },
    manuscriptRevision: 1,
  },
];

function cloneWorkspaces(
  workspaces: readonly ProjectWorkspaceResponse[],
): ProjectWorkspaceResponse[] {
  return workspaces.map((workspace) => structuredClone(workspace));
}

let projectWorkspaces = cloneWorkspaces(initialProjectWorkspaces);

export function listMockProjects(): ApiProject[] {
  return projectWorkspaces
    .map(({ project }) => structuredClone(project))
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}

export function findMockWorkspace(projectId: string): ProjectWorkspaceResponse | undefined {
  const workspace = projectWorkspaces.find(({ project }) => project.id === projectId);

  return workspace ? structuredClone(workspace) : undefined;
}

export function findMockWorkspaceByManuscriptId(
  manuscriptId: string,
): ProjectWorkspaceResponse | undefined {
  const workspace = projectWorkspaces.find(({ manuscript }) => manuscript.id === manuscriptId);

  return workspace ? structuredClone(workspace) : undefined;
}

export function addMockWorkspace(workspace: ProjectWorkspaceResponse): void {
  projectWorkspaces.push(structuredClone(workspace));
}

export function replaceMockWorkspace(workspace: ProjectWorkspaceResponse): void {
  projectWorkspaces = projectWorkspaces.map((currentWorkspace) =>
    currentWorkspace.project.id === workspace.project.id
      ? structuredClone(workspace)
      : currentWorkspace,
  );
}

export function resetProjectWorkspaceMockData(): void {
  projectWorkspaces = cloneWorkspaces(initialProjectWorkspaces);
}
