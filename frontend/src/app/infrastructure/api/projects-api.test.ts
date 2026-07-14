import { describe, expect, it } from "vitest";

import { ApiRequestError } from "./api-client";
import {
  compareManuscriptScene,
  createProjectWorkspace,
  getProjectWorkspace,
  listProjects,
  saveManuscript,
} from "./projects-api";

describe("projects API adapters", () => {
  it("lists projects from the API", async () => {
    const response = await listProjects();

    expect(response.items).toEqual([
      expect.objectContaining({
        id: "silver-garden",
        title: "은빛 정원의 약속",
      }),
    ]);
  });

  it("creates a project workspace", async () => {
    const response = await createProjectWorkspace({
      title: "빗속의 재회",
      logline: "헤어진 두 사람이 비 내리는 서점에서 다시 만난다.",
      tropeId: "reunion",
      protagonistNames: ["하린", "태오"],
    });

    expect(response).toMatchObject({
      project: {
        title: "빗속의 재회",
        tropeId: "reunion",
      },
      concept: {
        protagonistNames: ["하린", "태오"],
      },
      manuscriptRevision: 1,
    });
  });

  it("gets a project workspace", async () => {
    const response = await getProjectWorkspace("silver-garden");

    expect(response).toMatchObject({
      project: { id: "silver-garden" },
      manuscript: { id: "silver-garden-manuscript" },
      manuscriptRevision: 1,
    });
  });

  it("saves a manuscript at the expected revision", async () => {
    const workspace = await getProjectWorkspace("silver-garden");
    const manuscript = {
      ...workspace.manuscript,
      scenes: workspace.manuscript.scenes.map((scene) => ({
        ...scene,
        content: "서윤은 오래된 온실 문을 천천히 열었다.",
      })),
    };

    const response = await saveManuscript(workspace.manuscript.id, {
      manuscript,
      expectedRevision: workspace.manuscriptRevision,
    });

    expect(response).toMatchObject({
      manuscript: { scenes: [{ content: "서윤은 오래된 온실 문을 천천히 열었다." }] },
      manuscriptRevision: 2,
      projectActivity: { projectId: "silver-garden" },
    });
  });

  it("compares a local scene draft with the server draft", async () => {
    const response = await compareManuscriptScene("silver-garden-manuscript", {
      sceneId: "silver-garden-scene-1",
      localContent: "로컬 초안",
    });

    expect(response).toMatchObject({
      sceneId: "silver-garden-scene-1",
      serverRevision: 1,
      localContent: "로컬 초안",
      serverManuscript: { id: "silver-garden-manuscript" },
    });
    expect(response.rows).not.toHaveLength(0);
  });

  it("throws a typed API error with the status and parsed error body", async () => {
    const request = getProjectWorkspace("missing-project");

    await expect(request).rejects.toBeInstanceOf(ApiRequestError);
    await expect(request).rejects.toMatchObject({
      status: 404,
      error: { code: "PROJECT_NOT_FOUND" },
    });
  });
});
