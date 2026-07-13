import { describe, expect, test } from "vitest";

describe("createProjectFromTrope", () => {
  test("creates a consistent workspace across bounded contexts", async () => {
    const { createProjectFromTrope } = await import("./create-project");

    const workspace = createProjectFromTrope(
      {
        title: "은빛 정원의 약속",
        logline: "헤어진 연인이 온실에서 다시 만난다.",
        tropeId: "reunion",
        protagonistNames: ["서윤", "도현"],
      },
      {
        projectId: "project-1",
        conceptId: "concept-1",
        now: "2026-07-13T05:00:00.000Z",
      },
    );

    expect(workspace.project.id).toBe("project-1");
    expect(workspace.concept.projectId).toBe("project-1");
    expect(workspace.storyBible.projectId).toBe("project-1");
    expect(workspace.manuscript.projectId).toBe("project-1");
    expect(workspace.manuscript.scenes[0]?.relatedCharacterIds).toEqual(
      workspace.storyBible.characters.map(({ id }) => id),
    );
  });
});
