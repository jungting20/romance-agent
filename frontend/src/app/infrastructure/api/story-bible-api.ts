import { requestJson } from "./api-client";
import type { SaveWorldEntriesRequest, StoryBibleSnapshot } from "./contracts";

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
