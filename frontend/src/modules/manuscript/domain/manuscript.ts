export interface TextRange {
  start: number;
  end: number;
}

export interface Scene {
  id: string;
  title: string;
  chapterNumber: number;
  content: string;
  relatedCharacterIds: string[];
  relatedWorldEntryIds: string[];
}

export interface Manuscript {
  id: string;
  projectId: string;
  scenes: Scene[];
  activeSceneId: string;
}

const OPENING_SCENE = `비가 그친 뒤의 온실은 오래된 비밀처럼 고요했다.

서윤은 젖은 돌바닥 위에 멈춰 섰다. 돌아보지 않아도 누가 와 있는지 알 수 있었다. 몇 년이 흘렀는데도 발소리 하나만은 기억 속 그대로였다.

“여긴 여전하네.”

도현의 목소리가 장미 향 사이로 낮게 번졌다. 서윤은 손에 든 편지를 조금 더 세게 쥐었다.`;

export function createInitialManuscript(projectId: string): Manuscript {
  const sceneId = `${projectId}-scene-1`;

  return {
    id: `${projectId}-manuscript`,
    projectId,
    activeSceneId: sceneId,
    scenes: [
      {
        id: sceneId,
        title: "비가 그친 뒤의 정원",
        chapterNumber: 1,
        content: OPENING_SCENE,
        relatedCharacterIds: [`${projectId}-character-1`, `${projectId}-character-2`],
        relatedWorldEntryIds: [`${projectId}-world-1`],
      },
    ],
  };
}

export function updateSceneContent(
  manuscript: Manuscript,
  sceneId: string,
  content: string,
): Manuscript {
  if (!manuscript.scenes.some(({ id }) => id === sceneId)) {
    throw new Error("원고 장면을 찾을 수 없습니다.");
  }

  return {
    ...manuscript,
    scenes: manuscript.scenes.map((scene) =>
      scene.id === sceneId ? { ...scene, content } : scene,
    ),
  };
}

export function updateSceneTitle(
  manuscript: Manuscript,
  sceneId: string,
  title: string,
): Manuscript {
  const scene = manuscript.scenes.find(({ id }) => id === sceneId);
  if (!scene) {
    throw new Error("원고 장면을 찾을 수 없습니다.");
  }

  const normalizedTitle = title.trim();
  if (!normalizedTitle) {
    throw new Error("장면 제목을 입력해 주세요.");
  }
  if (scene.title === normalizedTitle) {
    return manuscript;
  }

  return {
    ...manuscript,
    scenes: manuscript.scenes.map((candidate) =>
      candidate.id === sceneId ? { ...candidate, title: normalizedTitle } : candidate,
    ),
  };
}

export function addScene(manuscript: Manuscript, sceneId: string): Manuscript {
  if (!sceneId.trim()) throw new Error("새 장면 식별자가 필요합니다.");
  if (manuscript.scenes.some(({ id }) => id === sceneId)) {
    throw new Error("이미 존재하는 원고 장면입니다.");
  }

  const chapterNumber = Math.max(...manuscript.scenes.map((scene) => scene.chapterNumber)) + 1;
  const scene: Scene = {
    id: sceneId,
    title: "제목 없는 장면",
    chapterNumber,
    content: "",
    relatedCharacterIds: [],
    relatedWorldEntryIds: [],
  };

  return { ...manuscript, scenes: [...manuscript.scenes, scene], activeSceneId: sceneId };
}

export function selectScene(manuscript: Manuscript, sceneId: string): Manuscript {
  if (!manuscript.scenes.some(({ id }) => id === sceneId)) {
    throw new Error("원고 장면을 찾을 수 없습니다.");
  }

  return manuscript.activeSceneId === sceneId
    ? manuscript
    : { ...manuscript, activeSceneId: sceneId };
}

export function insertText(content: string, cursorPosition: number, insertion: string): string {
  if (cursorPosition < 0 || cursorPosition > content.length) {
    throw new Error("커서 위치가 올바르지 않습니다.");
  }

  return `${content.slice(0, cursorPosition)}${insertion}${content.slice(cursorPosition)}`;
}

export function replaceTextRange(content: string, range: TextRange, replacement: string): string {
  if (range.start < 0 || range.end < range.start || range.end > content.length) {
    throw new Error("선택한 원고 범위가 올바르지 않습니다.");
  }

  return `${content.slice(0, range.start)}${replacement}${content.slice(range.end)}`;
}
