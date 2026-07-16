import { http, HttpResponse, type HttpResponseResolver, type RequestHandler } from "msw";

import type {
  ApiWorldEntry,
  SaveWorldEntriesRequest,
  WorldEntryAddition,
} from "@/app/infrastructure/api/contracts";
import {
  apiErrors,
  getMockStoryBibleSnapshot,
  PROJECT_API_BASE_URL,
  saveMockWorldEntries,
} from "@/mocks/data/project-workspaces";

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

function isWorldEntryKind(value: unknown): value is ApiWorldEntry["kind"] {
  return value === "place" || value === "object" || value === "rule";
}

function isWorldEntryUpdate(value: unknown): value is ApiWorldEntry {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["id", "kind", "title", "description"]) &&
    typeof value.id === "string" &&
    value.id.length > 0 &&
    isWorldEntryKind(value.kind) &&
    typeof value.title === "string" &&
    typeof value.description === "string"
  );
}

function isWorldEntryAddition(value: unknown): value is WorldEntryAddition {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["kind", "title", "description"]) &&
    isWorldEntryKind(value.kind) &&
    typeof value.title === "string" &&
    typeof value.description === "string"
  );
}

function parseSaveWorldEntriesRequest(value: unknown): SaveWorldEntriesRequest | undefined {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["expectedRevision", "updates", "additions"]) ||
    !Number.isInteger(value.expectedRevision) ||
    Number(value.expectedRevision) < 1 ||
    !Array.isArray(value.updates) ||
    !value.updates.every(isWorldEntryUpdate) ||
    !Array.isArray(value.additions) ||
    !value.additions.every(isWorldEntryAddition)
  ) {
    return undefined;
  }

  return {
    expectedRevision: Number(value.expectedRevision),
    updates: value.updates,
    additions: value.additions,
  };
}

async function readRequestJson(request: Request): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    return undefined;
  }
}

const getStoryBibleHandler: HttpResponseResolver = ({ params }) => {
  const projectId = params.projectId;
  const snapshot = typeof projectId === "string" ? getMockStoryBibleSnapshot(projectId) : undefined;

  return snapshot
    ? HttpResponse.json(snapshot)
    : HttpResponse.json(apiErrors.storyBibleNotFound, { status: 404 });
};

const saveWorldEntriesHandler: HttpResponseResolver = async ({ params, request }) => {
  const parsedRequest = parseSaveWorldEntriesRequest(await readRequestJson(request));

  if (!parsedRequest) {
    return HttpResponse.json(apiErrors.malformedRequest, { status: 400 });
  }

  const projectId = params.projectId;
  const result =
    typeof projectId === "string"
      ? saveMockWorldEntries(projectId, parsedRequest)
      : { status: "not-found" as const };

  switch (result.status) {
    case "not-found":
      return HttpResponse.json(apiErrors.storyBibleNotFound, { status: 404 });
    case "revision-conflict":
      return HttpResponse.json(apiErrors.storyBibleRevisionConflict, { status: 409 });
    case "invalid":
      return HttpResponse.json(result.error, { status: 422 });
    case "saved":
      return HttpResponse.json(result.snapshot);
  }
};

export const storyBibleHandlers: RequestHandler[] = [
  http.get(`${PROJECT_API_BASE_URL}/projects/:projectId/story-bible`, getStoryBibleHandler),
  http.put(
    `${PROJECT_API_BASE_URL}/projects/:projectId/story-bible/world-entries`,
    saveWorldEntriesHandler,
  ),
];
