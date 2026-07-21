import type { Manuscript, Scene } from "@/modules/manuscript";

function scenesEqual(left: Scene, right: Scene): boolean {
  return (
    left.id === right.id &&
    left.title === right.title &&
    left.chapterNumber === right.chapterNumber &&
    left.content === right.content &&
    left.relatedCharacterIds.length === right.relatedCharacterIds.length &&
    left.relatedCharacterIds.every((id, index) => id === right.relatedCharacterIds[index]) &&
    left.relatedWorldEntryIds.length === right.relatedWorldEntryIds.length &&
    left.relatedWorldEntryIds.every((id, index) => id === right.relatedWorldEntryIds[index])
  );
}

export function findLocalSceneAdditions(base: Manuscript, local: Manuscript): Scene[] {
  const baseIds = new Set(base.scenes.map(({ id }) => id));

  return local.scenes.filter(({ id }) => !baseIds.has(id));
}

export function mergeLocalSceneAdditions(
  base: Manuscript,
  local: Manuscript,
  server: Manuscript,
): Manuscript {
  const additions = findLocalSceneAdditions(base, local);
  if (additions.length === 0) throw new Error("병합할 새 장면이 없습니다.");

  const baseSceneChanged = base.scenes.some((scene) => {
    const localScene = local.scenes.find(({ id }) => id === scene.id);

    return !localScene || !scenesEqual(scene, localScene);
  });
  if (baseSceneChanged) {
    throw new Error("기존 장면의 로컬 변경과 새 장면을 동시에 자동 병합할 수 없습니다.");
  }

  const serverIds = new Set(server.scenes.map(({ id }) => id));
  if (additions.some(({ id }) => serverIds.has(id))) {
    throw new Error("서버 원고와 새 장면 식별자가 충돌합니다.");
  }

  const serverChapters = new Set(server.scenes.map(({ chapterNumber }) => chapterNumber));
  if (additions.some(({ chapterNumber }) => serverChapters.has(chapterNumber))) {
    throw new Error("서버 원고와 새 장 번호가 충돌합니다.");
  }

  const scenes = [...server.scenes, ...additions];

  return {
    ...server,
    scenes,
    activeSceneId: scenes.some(({ id }) => id === local.activeSceneId)
      ? local.activeSceneId
      : server.activeSceneId,
  };
}
