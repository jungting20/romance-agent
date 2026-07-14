import { http, HttpResponse } from "msw";
import { describe, expect, test } from "vitest";

import type {
  ApiError,
  CreateProjectRequest,
  ProjectListResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
  SaveManuscriptResponse,
} from "@/app/infrastructure/api/contracts";
import { apiErrors, MOCK_NOW } from "@/mocks/data/project-workspaces";
import { server } from "@/mocks/server";

const API_ORIGIN = window.location.origin;

const validCreateRequest: CreateProjectRequest = {
  title: " 빗속의 재회 ",
  logline: " 헤어진 두 사람이 비 내리는 서점에서 다시 만난다. ",
  tropeId: "reunion",
  protagonistNames: [" 하린 ", " 태오 "],
};

async function getSeedWorkspace(): Promise<ProjectWorkspaceResponse> {
  const response = await fetch(`${API_ORIGIN}/api/projects/silver-garden/workspace`);

  expect(response.status).toBe(200);
  return response.json();
}

describe("project persistence API handlers", () => {
  test("lists the seed project in descending updatedAt order", async () => {
    const createResponse = await fetch(`${API_ORIGIN}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(validCreateRequest),
    });
    expect(createResponse.status).toBe(201);

    const response = await fetch(`${API_ORIGIN}/api/projects`);
    const body: ProjectListResponse = await response.json();

    expect(response.status).toBe(200);
    expect(body.items).toHaveLength(2);
    expect(body.items.map(({ id }) => id)).toContain("silver-garden");
    expect(
      body.items
        .map(({ updatedAt }) => updatedAt)
        .toSorted()
        .toReversed(),
    ).toEqual(body.items.map(({ updatedAt }) => updatedAt));
  });

  test("creates an atomic workspace and exposes it at Location", async () => {
    const createResponse = await fetch(`${API_ORIGIN}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(validCreateRequest),
    });
    const created: ProjectWorkspaceResponse = await createResponse.json();
    const location = createResponse.headers.get("Location");

    expect(createResponse.status).toBe(201);
    expect(location).toBe(`/api/projects/${created.project.id}/workspace`);
    expect(created).toMatchObject({
      project: {
        title: "빗속의 재회",
        logline: "헤어진 두 사람이 비 내리는 서점에서 다시 만난다.",
        tropeId: "reunion",
        updatedAt: MOCK_NOW,
      },
      concept: { protagonistNames: ["하린", "태오"] },
      manuscriptRevision: 1,
    });
    expect(created.concept.id).toBe(`${created.project.id}-concept`);
    expect(created.manuscript.id).toBe(`${created.project.id}-manuscript`);

    const getResponse = await fetch(`${API_ORIGIN}${location}`);
    const loaded: ProjectWorkspaceResponse = await getResponse.json();

    expect(getResponse.status).toBe(200);
    expect(loaded).toEqual(created);
  });

  test.each([
    {
      name: "blank title",
      request: { ...validCreateRequest, title: "   " },
      code: "INVALID_TITLE",
      path: "title",
    },
    {
      name: "unknown trope",
      request: { ...validCreateRequest, tropeId: "unknown-trope" },
      code: "INVALID_TROPE",
      path: "tropeId",
    },
    {
      name: "blank protagonist",
      request: { ...validCreateRequest, protagonistNames: ["하린", " "] },
      code: "INVALID_PROTAGONISTS",
      path: "protagonistNames",
    },
    {
      name: "incorrect protagonist count",
      request: { ...validCreateRequest, protagonistNames: ["하린"] },
      code: "INVALID_PROTAGONISTS",
      path: "protagonistNames",
    },
  ])("returns the declared validation error for $name", async ({ request, code, path }) => {
    const response = await fetch(`${API_ORIGIN}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const body: ApiError = await response.json();

    expect(response.status).toBe(422);
    expect(body.code).toBe(code);
    expect(body.fieldErrors).toContainEqual(expect.objectContaining({ path }));
  });

  test("returns MALFORMED_REQUEST for malformed JSON", async () => {
    const response = await fetch(`${API_ORIGIN}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{",
    });
    const body: ApiError = await response.json();

    expect(response.status).toBe(400);
    expect(body).toEqual(apiErrors.malformedRequest);
  });

  test.each([
    {
      name: "a missing required field",
      request: {
        title: validCreateRequest.title,
        logline: validCreateRequest.logline,
        tropeId: validCreateRequest.tropeId,
      },
    },
    {
      name: "a wrong field type",
      request: { ...validCreateRequest, title: 42 },
    },
    {
      name: "an additional root property",
      request: { ...validCreateRequest, unexpected: true },
    },
  ])("returns MALFORMED_REQUEST for create input with $name", async ({ request }) => {
    const response = await fetch(`${API_ORIGIN}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const body: ApiError = await response.json();

    expect(response.status).toBe(400);
    expect(body).toEqual(apiErrors.malformedRequest);
  });

  test("returns PROJECT_NOT_FOUND for an unknown workspace", async () => {
    const response = await fetch(`${API_ORIGIN}/api/projects/missing/workspace`);
    const body: ApiError = await response.json();

    expect(response.status).toBe(404);
    expect(body).toEqual(apiErrors.projectNotFound);
  });

  test("saves a manuscript atomically and rejects a stale retry without mutation", async () => {
    const original = await getSeedWorkspace();
    const changedManuscript = structuredClone(original.manuscript);
    changedManuscript.scenes[0].content = "서윤은 오래된 온실 문을 천천히 열었다.";
    const request: SaveManuscriptRequest = {
      manuscript: changedManuscript,
      expectedRevision: 1,
    };

    const saveResponse = await fetch(`${API_ORIGIN}/api/manuscripts/${changedManuscript.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const saved: SaveManuscriptResponse = await saveResponse.json();

    expect(saveResponse.status).toBe(200);
    expect(saved).toEqual({
      manuscript: changedManuscript,
      manuscriptRevision: 2,
      projectActivity: { projectId: "silver-garden", updatedAt: MOCK_NOW },
    });

    const loadedAfterSave = await getSeedWorkspace();
    expect(loadedAfterSave.manuscriptRevision).toBe(2);
    expect(loadedAfterSave.manuscript.scenes[0].content).toBe(
      "서윤은 오래된 온실 문을 천천히 열었다.",
    );
    expect(loadedAfterSave.project.updatedAt).toBe(MOCK_NOW);

    const staleManuscript = structuredClone(changedManuscript);
    staleManuscript.scenes[0].content = "충돌 요청은 저장되면 안 된다.";
    const staleResponse = await fetch(`${API_ORIGIN}/api/manuscripts/${staleManuscript.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manuscript: staleManuscript, expectedRevision: 1 }),
    });
    const staleError: ApiError = await staleResponse.json();

    expect(staleResponse.status).toBe(409);
    expect(staleError).toEqual(apiErrors.revisionConflict);

    const loadedAfterConflict = await getSeedWorkspace();
    expect(loadedAfterConflict).toEqual(loadedAfterSave);
  });

  test("allows exactly one of two concurrent writes at the same revision", async () => {
    const original = await getSeedWorkspace();
    const firstManuscript = structuredClone(original.manuscript);
    const secondManuscript = structuredClone(original.manuscript);
    firstManuscript.scenes[0].content = "첫 번째 동시 저장";
    secondManuscript.scenes[0].content = "두 번째 동시 저장";

    const responses = await Promise.all(
      [firstManuscript, secondManuscript].map((manuscript) =>
        fetch(`${API_ORIGIN}/api/manuscripts/${manuscript.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ manuscript, expectedRevision: 1 }),
        }),
      ),
    );

    expect(responses.map(({ status }) => status).toSorted((left, right) => left - right)).toEqual([
      200, 409,
    ]);
    const winnerIndex = responses.findIndex(({ status }) => status === 200);
    const loserIndex = responses.findIndex(({ status }) => status === 409);
    const winner: SaveManuscriptResponse = await responses[winnerIndex].json();
    const loser: ApiError = await responses[loserIndex].json();

    expect(winner.manuscriptRevision).toBe(2);
    expect(loser).toEqual(apiErrors.revisionConflict);

    const stored = await getSeedWorkspace();
    expect(stored.manuscriptRevision).toBe(2);
    expect(stored.manuscript.scenes[0].content).toBe(
      [firstManuscript, secondManuscript][winnerIndex].scenes[0].content,
    );
  });

  test("returns MALFORMED_REQUEST for malformed save JSON", async () => {
    const response = await fetch(`${API_ORIGIN}/api/manuscripts/silver-garden-manuscript`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: "{",
    });
    const body: ApiError = await response.json();

    expect(response.status).toBe(400);
    expect(body).toEqual(apiErrors.malformedRequest);
  });

  test.each([
    {
      name: "an additional save root property",
      mutate: (request: Record<string, unknown>) => ({ ...request, unexpected: true }),
    },
    {
      name: "an additional manuscript property",
      mutate: (request: Record<string, unknown>) => ({
        ...request,
        manuscript: { ...(request.manuscript as object), unexpected: true },
      }),
    },
    {
      name: "an additional scene property",
      mutate: (request: Record<string, unknown>) => {
        const manuscript = structuredClone(
          request.manuscript,
        ) as ProjectWorkspaceResponse["manuscript"];
        return {
          ...request,
          manuscript: {
            ...manuscript,
            scenes: [{ ...manuscript.scenes[0], unexpected: true }],
          },
        };
      },
    },
    {
      name: "an empty manuscript identifier",
      mutate: (request: Record<string, unknown>) => ({
        ...request,
        manuscript: { ...(request.manuscript as object), id: "" },
      }),
    },
    {
      name: "an empty project identifier",
      mutate: (request: Record<string, unknown>) => ({
        ...request,
        manuscript: { ...(request.manuscript as object), projectId: "" },
      }),
    },
    {
      name: "an empty scene identifier",
      mutate: (request: Record<string, unknown>) => {
        const manuscript = structuredClone(
          request.manuscript,
        ) as ProjectWorkspaceResponse["manuscript"];
        return {
          ...request,
          manuscript: {
            ...manuscript,
            activeSceneId: "",
            scenes: [{ ...manuscript.scenes[0], id: "" }],
          },
        };
      },
    },
    {
      name: "an empty related character identifier",
      mutate: (request: Record<string, unknown>) => {
        const manuscript = structuredClone(
          request.manuscript,
        ) as ProjectWorkspaceResponse["manuscript"];
        return {
          ...request,
          manuscript: {
            ...manuscript,
            scenes: [{ ...manuscript.scenes[0], relatedCharacterIds: [""] }],
          },
        };
      },
    },
  ])("returns MALFORMED_REQUEST for save input with $name", async ({ mutate }) => {
    const workspace = await getSeedWorkspace();
    const request = mutate({ manuscript: workspace.manuscript, expectedRevision: 1 });
    const response = await fetch(`${API_ORIGIN}/api/manuscripts/${workspace.manuscript.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const body: ApiError = await response.json();

    expect(response.status).toBe(400);
    expect(body).toEqual(apiErrors.malformedRequest);
    expect((await getSeedWorkspace()).manuscriptRevision).toBe(1);
  });

  test("returns MANUSCRIPT_NOT_FOUND for an unknown manuscript", async () => {
    const workspace = await getSeedWorkspace();
    const response = await fetch(`${API_ORIGIN}/api/manuscripts/missing-manuscript`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manuscript: workspace.manuscript, expectedRevision: 1 }),
    });
    const body: ApiError = await response.json();

    expect(response.status).toBe(404);
    expect(body).toEqual(apiErrors.manuscriptNotFound);
  });

  test("returns INVALID_MANUSCRIPT when path and body identifiers differ", async () => {
    const workspace = await getSeedWorkspace();
    const mismatchedManuscript = {
      ...workspace.manuscript,
      id: "different-manuscript",
    };
    const response = await fetch(`${API_ORIGIN}/api/manuscripts/${workspace.manuscript.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manuscript: mismatchedManuscript, expectedRevision: 1 }),
    });
    const body: ApiError = await response.json();

    expect(response.status).toBe(422);
    expect(body.code).toBe("INVALID_MANUSCRIPT");
    expect(body.fieldErrors).toContainEqual(expect.objectContaining({ path: "manuscript.id" }));
  });

  test.each([
    {
      name: "the project relationship differs",
      mutate: (workspace: ProjectWorkspaceResponse) => ({
        ...workspace.manuscript,
        projectId: "different-project",
      }),
      path: "manuscript.projectId",
    },
    {
      name: "the active scene is absent",
      mutate: (workspace: ProjectWorkspaceResponse) => ({
        ...workspace.manuscript,
        activeSceneId: "missing-scene",
      }),
      path: "manuscript.activeSceneId",
    },
  ])("returns INVALID_MANUSCRIPT when $name", async ({ mutate, path }) => {
    const workspace = await getSeedWorkspace();
    const response = await fetch(`${API_ORIGIN}/api/manuscripts/${workspace.manuscript.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manuscript: mutate(workspace), expectedRevision: 1 }),
    });
    const body: ApiError = await response.json();

    expect(response.status).toBe(422);
    expect(body.code).toBe("INVALID_MANUSCRIPT");
    expect(body.fieldErrors).toContainEqual(expect.objectContaining({ path }));
  });

  test("supports a test-local INTERNAL_ERROR response", async () => {
    server.use(
      http.get(`${API_ORIGIN}/api/projects`, () =>
        HttpResponse.json(apiErrors.internalError, { status: 500 }),
      ),
    );

    const response = await fetch(`${API_ORIGIN}/api/projects`);
    const body: ApiError = await response.json();

    expect(response.status).toBe(500);
    expect(body).toEqual(apiErrors.internalError);
  });

  test("starts the next test with the seed manuscript at revision 1", async () => {
    const workspace = await getSeedWorkspace();

    expect(workspace.manuscriptRevision).toBe(1);
  });
});
