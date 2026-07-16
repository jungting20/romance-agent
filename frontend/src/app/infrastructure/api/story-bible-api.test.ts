import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { ApiRequestError } from "./api-client";
import type { SaveWorldEntriesRequest } from "./contracts";
import { getStoryBible, saveWorldEntries } from "./story-bible-api";
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
});
