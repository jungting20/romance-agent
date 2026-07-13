import type { Manuscript } from "@/modules/manuscript";
import type { Project } from "@/modules/projects";
import type { StoryBible } from "@/modules/story-bible";
import type { StoryConcept } from "@/modules/story-design";

export const APP_STORAGE_KEY = "romance-agent:v1";

export interface AppSnapshotV1 {
  version: 1;
  projects: Project[];
  concepts: StoryConcept[];
  storyBibles: StoryBible[];
  manuscripts: Manuscript[];
  lastProjectId: string | null;
}

export interface StoragePort {
  getItem(key: string): string | null;
  setItem(key: string, value: string): unknown;
}

export interface AppStorage {
  load(): AppSnapshotV1 | null;
  save(snapshot: AppSnapshotV1): void;
}

export function createAppStorage(storage: StoragePort): AppStorage {
  return {
    load() {
      const stored = storage.getItem(APP_STORAGE_KEY);

      if (!stored) {
        return null;
      }

      try {
        const parsed: unknown = JSON.parse(stored);
        return isAppSnapshotV1(parsed) ? parsed : null;
      } catch {
        return null;
      }
    },
    save(snapshot) {
      storage.setItem(APP_STORAGE_KEY, JSON.stringify(snapshot));
    },
  };
}

function isAppSnapshotV1(value: unknown): value is AppSnapshotV1 {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<AppSnapshotV1>;

  return (
    candidate.version === 1 &&
    Array.isArray(candidate.projects) &&
    Array.isArray(candidate.concepts) &&
    Array.isArray(candidate.storyBibles) &&
    Array.isArray(candidate.manuscripts) &&
    (candidate.lastProjectId === null || typeof candidate.lastProjectId === "string")
  );
}
