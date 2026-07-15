import { describe, expect, test } from "vitest";

import type {
  ApiError,
  SaveWorldEntriesRequest,
  StoryBibleSnapshot,
} from "@/app/infrastructure/api/contracts";
import {
  getMockStoryBibleSnapshot,
  resetProjectWorkspaceMockData,
} from "@/mocks/data/project-workspaces";

const API_ORIGIN = window.location.origin;
const storyBibleUrl = `${API_ORIGIN}/api/projects/silver-garden/story-bible`;
const saveUrl = `${storyBibleUrl}/world-entries`;

const validRequest: SaveWorldEntriesRequest = {
  expectedRevision: 1,
  updates: [
    {
      id: "silver-garden-world-1",
      kind: "place",
      title: " 비가 그친 유리 온실 ",
      description: " 두 사람이 마지막으로 만난 장소다. ",
    },
  ],
  additions: [
    { kind: "rule", title: " 왕실의 서약 ", description: " 서약을 어기면 계승권을 잃는다. " },
  ],
};

async function getStoryBible(projectId = "silver-garden"): Promise<Response> {
  return fetch(`${API_ORIGIN}/api/projects/${projectId}/story-bible`);
}

async function readSnapshot(projectId = "silver-garden"): Promise<StoryBibleSnapshot> {
  const response = await getStoryBible(projectId);
  expect(response.status).toBe(200);
  return response.json();
}

async function saveWorldEntries(request: unknown, projectId = "silver-garden"): Promise<Response> {
  return fetch(`${API_ORIGIN}/api/projects/${projectId}/story-bible/world-entries`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

describe("Story Bible persistence API handlers", () => {
  test("gets the seed Story Bible snapshot", async () => {
    const response = await getStoryBible();
    const snapshot: StoryBibleSnapshot = await response.json();

    expect(response.status).toBe(200);
    expect(snapshot).toMatchObject({
      storyBible: { projectId: "silver-garden" },
      storyBibleRevision: 1,
    });
  });

  test.each(["get", "save"])(
    "returns STORY_BIBLE_NOT_FOUND for an unknown project on %s",
    async (operation) => {
      const response =
        operation === "get"
          ? await getStoryBible("missing-project")
          : await saveWorldEntries(validRequest, "missing-project");
      const error: ApiError = await response.json();

      expect(response.status).toBe(404);
      expect(error).toEqual({
        code: "STORY_BIBLE_NOT_FOUND",
        message: "세계관 정보를 찾을 수 없습니다.",
        fieldErrors: [],
      });
    },
  );

  test("atomically saves normalized updates and deterministic additions", async () => {
    const before = await readSnapshot();
    const response = await saveWorldEntries(validRequest);
    const saved: StoryBibleSnapshot = await response.json();

    expect(response.status).toBe(200);
    expect(saved.storyBibleRevision).toBe(2);
    expect(saved.storyBible.characters).toEqual(before.storyBible.characters);
    expect(saved.storyBible.worldEntries).toEqual([
      {
        id: "silver-garden-world-1",
        kind: "place",
        title: "비가 그친 유리 온실",
        description: "두 사람이 마지막으로 만난 장소다.",
      },
      {
        id: "silver-garden-world-2",
        kind: "rule",
        title: "왕실의 서약",
        description: "서약을 어기면 계승권을 잃는다.",
      },
    ]);
    expect(await readSnapshot()).toEqual(saved);
  });

  test("preserves omitted entries and order while appending additions in request order", async () => {
    const firstSave = await saveWorldEntries(validRequest);
    expect(firstSave.status).toBe(200);

    const response = await saveWorldEntries({
      expectedRevision: 2,
      updates: [
        {
          id: "silver-garden-world-1",
          kind: "object",
          title: "은빛 열쇠",
          description: "온실 문을 여는 열쇠다.",
        },
      ],
      additions: [
        { kind: "place", title: "장미 회랑", description: "온실로 이어지는 회랑이다." },
        { kind: "object", title: "오래된 편지", description: "보내지 못한 고백이 담겼다." },
      ],
    });
    const saved: StoryBibleSnapshot = await response.json();

    expect(response.status).toBe(200);
    expect(saved.storyBibleRevision).toBe(3);
    expect(saved.storyBible.worldEntries.map(({ id }) => id)).toEqual([
      "silver-garden-world-1",
      "silver-garden-world-2",
      "silver-garden-world-3",
      "silver-garden-world-4",
    ]);
    expect(saved.storyBible.worldEntries[1]).toMatchObject({
      id: "silver-garden-world-2",
      title: "왕실의 서약",
    });
  });

  test.each([
    { name: "lower", expectedRevision: 1, advanceRevision: true },
    { name: "higher", expectedRevision: 2, advanceRevision: false },
  ])(
    "rejects a $name revision mismatch without mutation",
    async ({ expectedRevision, advanceRevision }) => {
      if (advanceRevision) {
        const advanceResponse = await saveWorldEntries(validRequest);
        expect(advanceResponse.status).toBe(200);
      }
      const before = await readSnapshot();
      const response = await saveWorldEntries({ ...validRequest, expectedRevision });
      const error: ApiError = await response.json();

      expect(response.status).toBe(409);
      expect(error).toEqual({
        code: "STORY_BIBLE_REVISION_CONFLICT",
        message: "다른 위치에서 세계관이 먼저 수정되었습니다.",
        fieldErrors: [],
      });
      expect(await readSnapshot()).toEqual(before);
    },
  );

  test.each([
    {
      name: "an empty command",
      request: { expectedRevision: 1, updates: [], additions: [] },
      paths: ["updates", "additions"],
    },
    {
      name: "blank update and addition fields",
      request: {
        expectedRevision: 1,
        updates: [{ ...validRequest.updates[0], title: "   " }],
        additions: [{ ...validRequest.additions[0], description: "   " }],
      },
      paths: ["updates[0].title", "additions[0].description"],
    },
    {
      name: "duplicate update IDs",
      request: {
        expectedRevision: 1,
        updates: [validRequest.updates[0], validRequest.updates[0]],
        additions: [],
      },
      paths: ["updates[1].id"],
    },
    {
      name: "an unknown update ID",
      request: {
        expectedRevision: 1,
        updates: [{ ...validRequest.updates[0], id: "missing-world-entry" }],
        additions: [],
      },
      paths: ["updates[0].id"],
    },
  ])("returns INVALID_WORLD_ENTRIES for $name without mutation", async ({ request, paths }) => {
    const before = await readSnapshot();
    const response = await saveWorldEntries(request);
    const error: ApiError = await response.json();

    expect(response.status).toBe(422);
    expect(error.code).toBe("INVALID_WORLD_ENTRIES");
    expect(error.fieldErrors.map(({ path }) => path)).toEqual(paths);
    expect(await readSnapshot()).toEqual(before);
  });

  test.each([
    { name: "a missing root key", request: { expectedRevision: 1, updates: [] } },
    { name: "an extra root key", request: { ...validRequest, extra: true } },
    { name: "a non-integer revision", request: { ...validRequest, expectedRevision: 1.5 } },
    {
      name: "an invalid entry kind",
      request: {
        ...validRequest,
        updates: [{ ...validRequest.updates[0], kind: "building" }],
      },
    },
    {
      name: "an extra update key",
      request: {
        ...validRequest,
        updates: [{ ...validRequest.updates[0], extra: true }],
      },
    },
  ])("returns MALFORMED_REQUEST for $name without mutation", async ({ request }) => {
    const before = await readSnapshot();
    const response = await saveWorldEntries(request);
    const error: ApiError = await response.json();

    expect(response.status).toBe(400);
    expect(error.code).toBe("MALFORMED_REQUEST");
    expect(await readSnapshot()).toEqual(before);
  });

  test("returns MALFORMED_REQUEST for malformed JSON without mutation", async () => {
    const before = await readSnapshot();
    const response = await fetch(saveUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: "{",
    });
    const error: ApiError = await response.json();

    expect(response.status).toBe(400);
    expect(error.code).toBe("MALFORMED_REQUEST");
    expect(await readSnapshot()).toEqual(before);
  });

  test("the existing mock reset restores Story Bible state and revision", async () => {
    const response = await saveWorldEntries(validRequest);
    expect(response.status).toBe(200);
    expect(getMockStoryBibleSnapshot("silver-garden")?.storyBibleRevision).toBe(2);

    resetProjectWorkspaceMockData();

    expect(getMockStoryBibleSnapshot("silver-garden")).toMatchObject({
      storyBibleRevision: 1,
      storyBible: { worldEntries: [{ id: "silver-garden-world-1" }] },
    });
  });
});
