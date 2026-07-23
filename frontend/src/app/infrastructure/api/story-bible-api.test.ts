import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { ApiRequestError } from "./api-client";
import type { CreateCharacterRequest, SaveWorldEntriesRequest } from "./contracts";
import {
  createStoryBibleCharacter,
  getStoryBible,
  saveWorldEntries,
  updateStoryBibleCharacter,
} from "./story-bible-api";
import { server } from "@/mocks/server";

const saveRequest: SaveWorldEntriesRequest = {
  expectedRevision: 1,
  updates: [
    {
      id: "silver-garden-world-1",
      kind: "place",
      title: "비가 그친 유리 온실",
      description: "두 사람이 마지막으로 만난 장소다.",
    },
  ],
  additions: [
    { kind: "rule", title: "왕실의 서약", description: "서약을 어기면 계승권을 잃는다." },
  ],
};

const characterRequest: CreateCharacterRequest = {
  name: "민서",
  gender: "여성",
  age: "29세",
  role: "서점 주인",
  personality: "차분하다.",
  proseStyle: "짧은 문장",
  dialogueStyle: "정중한 말투",
  desire: "서점을 지키고 싶다.",
  hiddenFeeling: "다시 상처받을까 두렵다.",
};

describe("Story Bible API adapters", () => {
  it("gets the Story Bible from the exact API path", async () => {
    let observedMethod: string | undefined;
    server.use(
      http.get("/api/projects/:projectId/story-bible", ({ params, request }) => {
        expect(params.projectId).toBe("silver garden/2026");
        observedMethod = request.method;

        return HttpResponse.json({
          storyBible: { projectId: params.projectId, characters: [], worldEntries: [] },
          storyBibleRevision: 1,
        });
      }),
    );

    await expect(getStoryBible("silver garden/2026")).resolves.toMatchObject({
      storyBibleRevision: 1,
    });
    expect(observedMethod).toBe("GET");
  });

  it("puts the exact save body to the exact API path", async () => {
    let observedMethod: string | undefined;
    let observedBody: unknown;
    server.use(
      http.put(
        "/api/projects/:projectId/story-bible/world-entries",
        async ({ params, request }) => {
          expect(params.projectId).toBe("silver garden/2026");
          observedMethod = request.method;
          observedBody = await request.json();

          return HttpResponse.json({
            storyBible: {
              projectId: params.projectId,
              characters: [],
              worldEntries: [
                ...saveRequest.updates,
                { id: "silver-garden-world-2", ...saveRequest.additions[0] },
              ],
            },
            storyBibleRevision: 2,
          });
        },
      ),
    );

    await expect(saveWorldEntries("silver garden/2026", saveRequest)).resolves.toMatchObject({
      storyBibleRevision: 2,
      storyBible: {
        worldEntries: expect.arrayContaining([expect.objectContaining({ kind: "rule" })]),
      },
    });
    expect(observedMethod).toBe("PUT");
    expect(observedBody).toEqual(saveRequest);
  });

  it.each([
    [404, "STORY_BIBLE_NOT_FOUND"],
    [409, "STORY_BIBLE_REVISION_CONFLICT"],
    [422, "INVALID_WORLD_ENTRIES"],
  ] as const)("consumes the declared %s %s error", async (status, code) => {
    server.use(
      http.put("/api/projects/:projectId/story-bible/world-entries", () =>
        HttpResponse.json({ code, message: "declared error", fieldErrors: [] }, { status }),
      ),
    );

    const response = saveWorldEntries("silver-garden", saveRequest);

    await expect(response).rejects.toBeInstanceOf(ApiRequestError);
    await expect(response).rejects.toMatchObject({ status, error: { code } });
  });

  it("posts every mutable field without an id and consumes the authoritative snapshot", async () => {
    let observedBody: unknown;
    server.use(
      http.post("/api/projects/:projectId/story-bible/characters", async ({ request }) => {
        observedBody = await request.json();
        return HttpResponse.json(
          {
            storyBible: {
              projectId: "silver garden/2026",
              characters: [{ id: "server-character-9", ...characterRequest, name: "서버 민서" }],
              worldEntries: [],
            },
            storyBibleRevision: 9,
          },
          { status: 201 },
        );
      }),
    );

    await expect(
      createStoryBibleCharacter("silver garden/2026", characterRequest),
    ).resolves.toMatchObject({
      storyBibleRevision: 9,
      storyBible: { characters: [{ id: "server-character-9", name: "서버 민서" }] },
    });
    expect(observedBody).toEqual(characterRequest);
    expect(observedBody).not.toHaveProperty("id");
  });

  it("patches the encoded immutable character resource without revision data", async () => {
    let observedBody: unknown;
    server.use(
      http.patch(
        "/api/projects/:projectId/story-bible/characters/:characterId",
        async ({ params, request }) => {
          expect(params).toMatchObject({
            projectId: "silver garden/2026",
            characterId: "character/9",
          });
          observedBody = await request.json();
          return HttpResponse.json({
            storyBible: { projectId: params.projectId, characters: [], worldEntries: [] },
            storyBibleRevision: 3,
          });
        },
      ),
    );

    await updateStoryBibleCharacter("silver garden/2026", "character/9", {
      hiddenFeeling: "권위 응답을 기다린다.",
    });
    expect(observedBody).toEqual({ hiddenFeeling: "권위 응답을 기다린다." });
    expect(observedBody).not.toHaveProperty("id");
    expect(observedBody).not.toHaveProperty("expectedRevision");
  });

  it("rejects an empty character update before issuing a PATCH request", async () => {
    let requests = 0;
    server.use(
      http.patch("/api/projects/:projectId/story-bible/characters/:characterId", () => {
        requests += 1;
        return HttpResponse.json({});
      }),
    );

    await expect(
      updateStoryBibleCharacter("silver-garden", "silver-garden-character-1", {}),
    ).rejects.toMatchObject({
      status: 422,
      error: { code: "INVALID_CHARACTER" },
    });
    expect(requests).toBe(0);
  });
});
