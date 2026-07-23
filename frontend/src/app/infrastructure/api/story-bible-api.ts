import { ApiRequestError, requestJson } from "./api-client";
import type {
  CreateCharacterRequest,
  SaveWorldEntriesRequest,
  StoryBibleSnapshot,
  UpdateCharacterRequest,
} from "./contracts";

export function getStoryBible(projectId: string): Promise<StoryBibleSnapshot> {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/story-bible`);
}

export function saveWorldEntries(
  projectId: string,
  request: SaveWorldEntriesRequest,
): Promise<StoryBibleSnapshot> {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/story-bible/world-entries`, {
    method: "PUT",
    body: request,
  });
}

export function createStoryBibleCharacter(
  projectId: string,
  request: CreateCharacterRequest,
): Promise<StoryBibleSnapshot> {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/story-bible/characters`, {
    method: "POST",
    body: request,
  });
}

export function updateStoryBibleCharacter(
  projectId: string,
  characterId: string,
  request: UpdateCharacterRequest,
): Promise<StoryBibleSnapshot> {
  if (Object.keys(request).length === 0) {
    return Promise.reject(
      new ApiRequestError(422, {
        code: "INVALID_CHARACTER",
        message: "수정할 인물 정보가 필요합니다.",
        fieldErrors: [],
      }),
    );
  }
  return requestJson(
    `/api/projects/${encodeURIComponent(projectId)}/story-bible/characters/${encodeURIComponent(characterId)}`,
    { method: "PATCH", body: request },
  );
}
