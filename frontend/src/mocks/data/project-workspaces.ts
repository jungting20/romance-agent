import type {
  ApiCharacter,
  ApiError,
  ApiProject,
  CreateCharacterRequest,
  ProjectWorkspaceResponse,
  SaveWorldEntriesRequest,
  StoryBibleSnapshot,
  UpdateCharacterRequest,
} from "@/app/infrastructure/api/contracts";
import type { PersistedManuscriptSession } from "@/mocks/data/manuscript-session-store";

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
  storyBibleNotFound: {
    code: "STORY_BIBLE_NOT_FOUND",
    message: "세계관 정보를 찾을 수 없습니다.",
    fieldErrors: [],
  },
  characterNotFound: {
    code: "CHARACTER_NOT_FOUND",
    message: "인물을 찾을 수 없습니다.",
    fieldErrors: [],
  },
  storyBibleRevisionConflict: {
    code: "STORY_BIBLE_REVISION_CONFLICT",
    message: "다른 위치에서 세계관이 먼저 수정되었습니다.",
    fieldErrors: [],
  },
  manuscriptNotFound: {
    code: "MANUSCRIPT_NOT_FOUND",
    message: "원고를 찾을 수 없습니다.",
    fieldErrors: [],
  },
  sceneNotFound: {
    code: "SCENE_NOT_FOUND",
    message: "장면을 찾을 수 없습니다.",
    fieldErrors: [],
  },
  invalidSceneReference: {
    code: "INVALID_SCENE_REFERENCE",
    message: "장면이 원고에 속하지 않습니다.",
    fieldErrors: [
      {
        path: "sceneId",
        message: "경로의 원고에 속한 장면을 선택해 주세요.",
      },
    ],
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
          gender: "여성",
          age: "31세",
          role: "protagonist",
          personality: "단호하고 세심하다.",
          proseStyle: "감각적인 묘사와 짧은 문장을 쓴다.",
          dialogueStyle: "감정을 숨기며 간결하게 말한다.",
          desire: "상대에게 흔들리지 않고 자신의 선택을 지키고 싶다.",
          hiddenFeeling: "여전히 상대의 진심을 확인하고 싶다.",
        },
        {
          id: "silver-garden-character-2",
          name: "도현",
          gender: "남성",
          age: "33세",
          role: "protagonist",
          personality: "침착하고 주의 깊다.",
          proseStyle: "절제된 문장으로 움직임을 묘사한다.",
          dialogueStyle: "직접적이지만 말끝을 흐린다.",
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
let storyBibleRevisions = createInitialStoryBibleRevisions();
let manuscriptPersistor: ((session: PersistedManuscriptSession) => void) | undefined;

function createInitialStoryBibleRevisions(): Map<string, number> {
  return new Map(initialProjectWorkspaces.map(({ project }) => [project.id, 1]));
}

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

export function findMockWorkspaceBySceneId(sceneId: string): ProjectWorkspaceResponse | undefined {
  const workspace = projectWorkspaces.find(({ manuscript }) =>
    manuscript.scenes.some(({ id }) => id === sceneId),
  );

  return workspace ? structuredClone(workspace) : undefined;
}

export function addMockWorkspace(workspace: ProjectWorkspaceResponse): void {
  projectWorkspaces.push(structuredClone(workspace));
  storyBibleRevisions.set(workspace.project.id, 1);
}

export function hydrateMockManuscripts(session: PersistedManuscriptSession | undefined): void {
  for (const entry of session?.entries ?? []) {
    const workspaceIndex = projectWorkspaces.findIndex(
      ({ project }) => project.id === entry.projectId,
    );

    if (workspaceIndex < 0) {
      continue;
    }

    const workspace = projectWorkspaces[workspaceIndex];
    projectWorkspaces[workspaceIndex] = {
      ...workspace,
      project: { ...workspace.project, updatedAt: entry.projectUpdatedAt },
      manuscript: structuredClone(entry.manuscript),
      manuscriptRevision: entry.manuscriptRevision,
    };
  }
}

export function setMockManuscriptPersistor(
  persistor: ((session: PersistedManuscriptSession) => void) | undefined,
): void {
  manuscriptPersistor = persistor;
}

function persistMockManuscripts(): void {
  if (!manuscriptPersistor) {
    return;
  }

  const session: PersistedManuscriptSession = {
    schemaVersion: 1,
    entries: projectWorkspaces.map(({ project, manuscript, manuscriptRevision }) => ({
      projectId: project.id,
      manuscript: structuredClone(manuscript),
      manuscriptRevision,
      projectUpdatedAt: project.updatedAt,
    })),
  };

  try {
    manuscriptPersistor(session);
  } catch {
    console.warn("Failed to persist the MSW manuscript session snapshot.");
  }
}

export function getMockStoryBibleSnapshot(projectId: string): StoryBibleSnapshot | undefined {
  const workspace = projectWorkspaces.find(({ project }) => project.id === projectId);
  const storyBibleRevision = storyBibleRevisions.get(projectId);

  if (!workspace || storyBibleRevision === undefined) {
    return undefined;
  }

  return {
    storyBible: structuredClone(workspace.storyBible),
    storyBibleRevision,
  };
}

export type SaveMockCharacterResult =
  | { status: "not-found" }
  | { status: "character-not-found" }
  | { status: "invalid"; error: ApiError }
  | { status: "saved"; snapshot: StoryBibleSnapshot; character: ApiCharacter };

function invalidCharacter(): ApiError {
  return {
    code: "INVALID_CHARACTER",
    message: "인물 정보를 확인해 주세요.",
    fieldErrors: [{ path: "name", message: "이름을 입력해 주세요." }],
  };
}

function emptyCharacterUpdate(): ApiError {
  return {
    code: "INVALID_CHARACTER",
    message: "수정할 인물 정보가 필요합니다.",
    fieldErrors: [],
  };
}

function characterSnapshot(
  workspaceIndex: number,
  storyBibleRevision: number,
  character: ApiCharacter,
): SaveMockCharacterResult {
  const workspace = projectWorkspaces[workspaceIndex];
  storyBibleRevisions.set(workspace.project.id, storyBibleRevision + 1);
  return {
    status: "saved",
    character: structuredClone(character),
    snapshot: {
      storyBible: structuredClone(workspace.storyBible),
      storyBibleRevision: storyBibleRevision + 1,
    },
  };
}

export function createMockCharacter(
  projectId: string,
  request: CreateCharacterRequest,
): SaveMockCharacterResult {
  const workspaceIndex = projectWorkspaces.findIndex(({ project }) => project.id === projectId);
  const revision = storyBibleRevisions.get(projectId);
  if (workspaceIndex < 0 || revision === undefined) return { status: "not-found" };
  if (!request.name.trim()) return { status: "invalid", error: invalidCharacter() };

  const workspace = projectWorkspaces[workspaceIndex];
  const ids = new Set(workspace.storyBible.characters.map(({ id }) => id));
  let sequence = 1;
  while (ids.has(`${projectId}-character-${sequence}`)) sequence += 1;
  const character: ApiCharacter = {
    id: `${projectId}-character-${sequence}`,
    ...request,
    name: request.name.trim(),
  };
  workspace.storyBible = {
    ...workspace.storyBible,
    characters: [...workspace.storyBible.characters, character],
  };
  return characterSnapshot(workspaceIndex, revision, character);
}

export function updateMockCharacter(
  projectId: string,
  characterId: string,
  request: UpdateCharacterRequest,
): SaveMockCharacterResult {
  const workspaceIndex = projectWorkspaces.findIndex(({ project }) => project.id === projectId);
  const revision = storyBibleRevisions.get(projectId);
  if (workspaceIndex < 0 || revision === undefined) return { status: "not-found" };
  if (Object.keys(request).length === 0) {
    return { status: "invalid", error: emptyCharacterUpdate() };
  }
  if (request.name !== undefined && !request.name.trim()) {
    return { status: "invalid", error: invalidCharacter() };
  }
  const workspace = projectWorkspaces[workspaceIndex];
  const characterIndex = workspace.storyBible.characters.findIndex(({ id }) => id === characterId);
  if (characterIndex < 0) return { status: "character-not-found" };
  const current = workspace.storyBible.characters[characterIndex];
  const character: ApiCharacter = {
    ...current,
    ...request,
    ...(request.name === undefined ? {} : { name: request.name.trim() }),
  };
  const characters = [...workspace.storyBible.characters];
  characters[characterIndex] = character;
  workspace.storyBible = { ...workspace.storyBible, characters };
  return characterSnapshot(workspaceIndex, revision, character);
}

export type SaveMockWorldEntriesResult =
  | { status: "not-found" }
  | { status: "revision-conflict" }
  | { status: "invalid"; error: ApiError }
  | { status: "saved"; snapshot: StoryBibleSnapshot };

function invalidWorldEntries(message: string, fieldErrors: ApiError["fieldErrors"]): ApiError {
  return { code: "INVALID_WORLD_ENTRIES", message, fieldErrors };
}

export function saveMockWorldEntries(
  projectId: string,
  request: SaveWorldEntriesRequest,
): SaveMockWorldEntriesResult {
  const workspaceIndex = projectWorkspaces.findIndex(({ project }) => project.id === projectId);
  const storyBibleRevision = storyBibleRevisions.get(projectId);

  if (workspaceIndex < 0 || storyBibleRevision === undefined) {
    return { status: "not-found" };
  }

  if (request.expectedRevision !== storyBibleRevision) {
    return { status: "revision-conflict" };
  }

  if (request.updates.length === 0 && request.additions.length === 0) {
    return {
      status: "invalid",
      error: invalidWorldEntries("수정하거나 추가할 세계관 항목이 필요합니다.", [
        {
          path: "updates",
          message: "수정 또는 추가 항목을 한 개 이상 입력해 주세요.",
        },
        {
          path: "additions",
          message: "수정 또는 추가 항목을 한 개 이상 입력해 주세요.",
        },
      ]),
    };
  }

  const blankFieldErrors: ApiError["fieldErrors"] = [];
  request.updates.forEach((entry, index) => {
    if (!entry.title.trim()) {
      blankFieldErrors.push({
        path: `updates[${index}].title`,
        message: "제목을 입력해 주세요.",
      });
    }
    if (!entry.description.trim()) {
      blankFieldErrors.push({
        path: `updates[${index}].description`,
        message: "설명을 입력해 주세요.",
      });
    }
  });
  request.additions.forEach((entry, index) => {
    if (!entry.title.trim()) {
      blankFieldErrors.push({
        path: `additions[${index}].title`,
        message: "제목을 입력해 주세요.",
      });
    }
    if (!entry.description.trim()) {
      blankFieldErrors.push({
        path: `additions[${index}].description`,
        message: "설명을 입력해 주세요.",
      });
    }
  });

  if (blankFieldErrors.length > 0) {
    return {
      status: "invalid",
      error: invalidWorldEntries("세계관 항목을 확인해 주세요.", blankFieldErrors),
    };
  }

  const seenUpdateIds = new Set<string>();
  for (const [index, update] of request.updates.entries()) {
    if (seenUpdateIds.has(update.id)) {
      return {
        status: "invalid",
        error: invalidWorldEntries("같은 세계관 항목을 두 번 수정할 수 없습니다.", [
          {
            path: `updates[${index}].id`,
            message: "수정 항목 식별자가 중복되었습니다.",
          },
        ]),
      };
    }
    seenUpdateIds.add(update.id);
  }

  const workspace = projectWorkspaces[workspaceIndex];
  const worldEntryIds = new Set(workspace.storyBible.worldEntries.map(({ id }) => id));
  for (const [index, update] of request.updates.entries()) {
    if (!worldEntryIds.has(update.id)) {
      return {
        status: "invalid",
        error: invalidWorldEntries("수정할 세계관 항목을 찾을 수 없습니다.", [
          {
            path: `updates[${index}].id`,
            message: "현재 세계관에 존재하는 항목을 선택해 주세요.",
          },
        ]),
      };
    }
  }

  const updatesById = new Map(request.updates.map((update) => [update.id, update]));
  const updatedEntries = workspace.storyBible.worldEntries.map((entry) => {
    const update = updatesById.get(entry.id);
    return update
      ? {
          ...update,
          title: update.title.trim(),
          description: update.description.trim(),
        }
      : entry;
  });
  const allocatedIds = new Set(worldEntryIds);
  let sequence = 1;
  const additions = request.additions.map((addition) => {
    while (allocatedIds.has(`${projectId}-world-${sequence}`)) {
      sequence += 1;
    }
    const id = `${projectId}-world-${sequence}`;
    allocatedIds.add(id);
    sequence += 1;
    return {
      id,
      kind: addition.kind,
      title: addition.title.trim(),
      description: addition.description.trim(),
    };
  });
  const storedWorkspace: ProjectWorkspaceResponse = {
    ...workspace,
    storyBible: {
      ...workspace.storyBible,
      worldEntries: [...updatedEntries, ...additions],
    },
  };

  projectWorkspaces[workspaceIndex] = structuredClone(storedWorkspace);
  storyBibleRevisions.set(projectId, storyBibleRevision + 1);

  return {
    status: "saved",
    snapshot: {
      storyBible: structuredClone(storedWorkspace.storyBible),
      storyBibleRevision: storyBibleRevision + 1,
    },
  };
}

export type ReplaceMockWorkspaceAtRevisionResult =
  | { status: "not-found" }
  | { status: "revision-conflict" }
  | { status: "replaced"; workspace: ProjectWorkspaceResponse };

export function replaceMockWorkspaceAtRevision(
  manuscriptId: string,
  expectedRevision: number,
  replacement: ProjectWorkspaceResponse,
): ReplaceMockWorkspaceAtRevisionResult {
  const workspaceIndex = projectWorkspaces.findIndex(
    ({ manuscript }) => manuscript.id === manuscriptId,
  );

  if (workspaceIndex < 0) {
    return { status: "not-found" };
  }

  if (projectWorkspaces[workspaceIndex].manuscriptRevision !== expectedRevision) {
    return { status: "revision-conflict" };
  }

  const storedWorkspace = structuredClone(replacement);
  projectWorkspaces[workspaceIndex] = storedWorkspace;
  persistMockManuscripts();

  return { status: "replaced", workspace: structuredClone(storedWorkspace) };
}

export function resetProjectWorkspaceMockData(): void {
  projectWorkspaces = cloneWorkspaces(initialProjectWorkspaces);
  storyBibleRevisions = createInitialStoryBibleRevisions();
  manuscriptPersistor = undefined;
}
