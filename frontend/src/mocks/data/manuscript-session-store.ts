import type { ApiManuscript } from "@/app/infrastructure/api/contracts";

export const MANUSCRIPT_SESSION_STORAGE_KEY = "romance-agent:msw:manuscripts:v1";

export interface PersistedManuscriptEntry {
  projectId: string;
  manuscript: ApiManuscript;
  manuscriptRevision: number;
  projectUpdatedAt: string;
}

export interface PersistedManuscriptSession {
  schemaVersion: 1;
  entries: PersistedManuscriptEntry[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isIdentifierList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isNonEmptyString);
}

function isApiManuscript(value: unknown): value is ApiManuscript {
  if (
    !isRecord(value) ||
    !isNonEmptyString(value.id) ||
    !isNonEmptyString(value.projectId) ||
    !isNonEmptyString(value.activeSceneId) ||
    !Array.isArray(value.scenes)
  ) {
    return false;
  }

  const scenesAreValid = value.scenes.every(
    (scene) =>
      isRecord(scene) &&
      isNonEmptyString(scene.id) &&
      typeof scene.title === "string" &&
      Number.isInteger(scene.chapterNumber) &&
      typeof scene.content === "string" &&
      isIdentifierList(scene.relatedCharacterIds) &&
      isIdentifierList(scene.relatedWorldEntryIds),
  );

  return scenesAreValid && value.scenes.some((scene) => scene.id === value.activeSceneId);
}

function isPersistedManuscriptEntry(value: unknown): value is PersistedManuscriptEntry {
  return (
    isRecord(value) &&
    isNonEmptyString(value.projectId) &&
    isApiManuscript(value.manuscript) &&
    value.manuscript.projectId === value.projectId &&
    typeof value.manuscriptRevision === "number" &&
    Number.isInteger(value.manuscriptRevision) &&
    value.manuscriptRevision > 0 &&
    isNonEmptyString(value.projectUpdatedAt)
  );
}

function isPersistedManuscriptSession(value: unknown): value is PersistedManuscriptSession {
  return (
    isRecord(value) &&
    value.schemaVersion === 1 &&
    Array.isArray(value.entries) &&
    value.entries.every(isPersistedManuscriptEntry)
  );
}

export function loadManuscriptSession(storage: Storage): PersistedManuscriptSession | undefined {
  const raw = storage.getItem(MANUSCRIPT_SESSION_STORAGE_KEY);
  if (raw === null) {
    return undefined;
  }

  try {
    const candidate: unknown = JSON.parse(raw);
    if (!isPersistedManuscriptSession(candidate)) {
      throw new Error("invalid manuscript session snapshot");
    }

    return structuredClone(candidate);
  } catch {
    storage.removeItem(MANUSCRIPT_SESSION_STORAGE_KEY);
    return undefined;
  }
}

export function saveManuscriptSession(storage: Storage, session: PersistedManuscriptSession): void {
  storage.setItem(MANUSCRIPT_SESSION_STORAGE_KEY, JSON.stringify(structuredClone(session)));
}

export function clearManuscriptSession(storage: Storage): void {
  storage.removeItem(MANUSCRIPT_SESSION_STORAGE_KEY);
}
