export interface Character {
  id: string;
  name: string;
  role: "protagonist";
  desire: string;
  hiddenFeeling: string;
}

export interface WorldEntry {
  id: string;
  kind: "place" | "object" | "rule";
  title: string;
  description: string;
}

export interface WorldEntryDraftValue {
  kind: WorldEntry["kind"];
  title: string;
  description: string;
}

export interface WorldEntryDraftErrors {
  title?: string;
  description?: string;
}

export interface StoryBible {
  projectId: string;
  characters: Character[];
  worldEntries: WorldEntry[];
}

export interface SceneContextReference {
  characterIds: string[];
  worldEntryIds: string[];
}

export interface SceneContext {
  characters: Character[];
  worldEntries: WorldEntry[];
}

export function createInitialStoryBible(
  projectId: string,
  protagonistNames: [string, string],
): StoryBible {
  return {
    projectId,
    characters: protagonistNames.map((name, index) => ({
      id: `${projectId}-character-${index + 1}`,
      name,
      role: "protagonist" as const,
      desire:
        index === 0
          ? "상대에게 흔들리지 않고 자신의 선택을 지키고 싶다."
          : "과거의 오해를 풀고 다시 신뢰받고 싶다.",
      hiddenFeeling:
        index === 0 ? "여전히 상대의 진심을 확인하고 싶다." : "이번에는 먼저 놓치고 싶지 않다.",
    })),
    worldEntries: [
      {
        id: `${projectId}-world-1`,
        kind: "place",
        title: "비가 그친 온실",
        description:
          "두 사람이 과거에 마지막으로 만났던 장소. 젖은 흙과 오래된 장미 향이 남아 있다.",
      },
    ],
  };
}

export function selectSceneContext(
  bible: StoryBible,
  reference: SceneContextReference,
): SceneContext {
  return {
    characters: bible.characters.filter(({ id }) => reference.characterIds.includes(id)),
    worldEntries: bible.worldEntries.filter(({ id }) => reference.worldEntryIds.includes(id)),
  };
}

export function validateWorldEntryDraft(value: WorldEntryDraftValue): {
  value?: WorldEntryDraftValue;
  errors: WorldEntryDraftErrors;
} {
  const normalized = {
    ...value,
    title: value.title.trim(),
    description: value.description.trim(),
  };
  const errors: WorldEntryDraftErrors = {};

  if (!normalized.title) errors.title = "제목을 입력해 주세요.";
  if (!normalized.description) errors.description = "설명을 입력해 주세요.";

  return Object.keys(errors).length > 0 ? { errors } : { value: normalized, errors };
}
